import json
import os
import re
import time
import zipfile
from pathlib import Path

import numpy as np
import torch
import transformers
from accelerate import infer_auto_device_map, init_empty_weights
from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer,
                          BitsAndBytesConfig)

import modules.shared as shared

transformers.logging.set_verbosity_error()

local_rank = None

if shared.args.flexgen:
    from flexgen.flex_opt import CompressionConfig, ExecutionEnv, OptLM, Policy

if shared.args.deepspeed:
    import deepspeed
    from transformers.deepspeed import (HfDeepSpeedConfig,
                                        is_deepspeed_zero3_enabled)

    from modules.deepspeed_parameters import generate_ds_config

    # Distributed setup
    local_rank = shared.args.local_rank if shared.args.local_rank is not None else int(os.getenv("LOCAL_RANK", "0"))
    world_size = int(os.getenv("WORLD_SIZE", "1"))
    torch.cuda.set_device(local_rank)
    deepspeed.init_distributed()
    ds_config = generate_ds_config(shared.args.bf16, 1 * world_size, shared.args.nvme_offload_dir)
    dschf = HfDeepSpeedConfig(ds_config) # Keep this object alive for the Transformers integration


def load_model(model_name):
    print(f"Loading {model_name}...")
    t0 = time.time()

    shared.is_RWKV = model_name.lower().startswith('rwkv-')

    # Default settings
    if not any([shared.args.cpu, shared.args.load_in_8bit, shared.args.gptq_bits, shared.args.auto_devices, shared.args.disk, shared.args.gpu_memory is not None, shared.args.cpu_memory is not None, shared.args.deepspeed, shared.args.flexgen, shared.is_RWKV]):
        if any(size in shared.model_name.lower() for size in ('13b', '20b', '30b')):
            model = AutoModelForCausalLM.from_pretrained(Path(f"models/{shared.model_name}"), device_map='auto', load_in_8bit=True)
        else:
            model = AutoModelForCausalLM.from_pretrained(Path(f"models/{shared.model_name}"), low_cpu_mem_usage=True, torch_dtype=torch.bfloat16 if shared.args.bf16 else torch.float16)
            if torch.has_mps:
                device = torch.device('mps')
                model = model.to(device)
            else:
                model = model.cuda()

    # FlexGen
    elif shared.args.flexgen:
        # Initialize environment
        env = ExecutionEnv.create(shared.args.disk_cache_dir)

        # Offloading policy
        policy = Policy(1, 1,
                        shared.args.percent[0], shared.args.percent[1],
                        shared.args.percent[2], shared.args.percent[3],
                        shared.args.percent[4], shared.args.percent[5],
                        overlap=True, sep_layer=True, pin_weight=shared.args.pin_weight,
                        cpu_cache_compute=False, attn_sparsity=1.0,
                        compress_weight=shared.args.compress_weight,
                        comp_weight_config=CompressionConfig(
                            num_bits=4, group_size=64,
                            group_dim=0, symmetric=False),
                        compress_cache=False,
                        comp_cache_config=CompressionConfig(
                            num_bits=4, group_size=64,
                            group_dim=2, symmetric=False))

        model = OptLM(f"facebook/{shared.model_name}", env, "models", policy)

    # DeepSpeed ZeRO-3
    elif shared.args.deepspeed:
        model = AutoModelForCausalLM.from_pretrained(Path(f"models/{shared.model_name}"), torch_dtype=torch.bfloat16 if shared.args.bf16 else torch.float16)
        model = deepspeed.initialize(model=model, config_params=ds_config, model_parameters=None, optimizer=None, lr_scheduler=None)[0]
        model.module.eval() # Inference
        print(f"DeepSpeed ZeRO-3 is enabled: {is_deepspeed_zero3_enabled()}")

    # RMKV model (not on HuggingFace)
    elif shared.is_RWKV:
        from modules.RWKV import RWKVModel, RWKVTokenizer

        model = RWKVModel.from_pretrained(Path(f'models/{model_name}'), dtype="fp32" if shared.args.cpu else "bf16" if shared.args.bf16 else "fp16", device="cpu" if shared.args.cpu else "cuda")
        tokenizer = RWKVTokenizer.from_pretrained(Path('models'))

        return model, tokenizer

    # Quantized model
    elif shared.args.gptq_bits > 0:
        from modules.GPTQ_loader import load_quantized

        model = load_quantized(model_name)

    # Custom
    else:
        params = {"low_cpu_mem_usage": True}
        if not any((shared.args.cpu, torch.cuda.is_available(), torch.has_mps)):
            print("Warning: torch.cuda.is_available() returned False.\nThis means that no GPU has been detected.\nFalling back to CPU mode.\n")
            shared.args.cpu = True

        if shared.args.cpu:
            params["torch_dtype"] = torch.float32
        else:
            params["device_map"] = 'auto'
            if shared.args.load_in_8bit and any((shared.args.auto_devices, shared.args.gpu_memory)):
                params['quantization_config'] = BitsAndBytesConfig(load_in_8bit=True, llm_int8_enable_fp32_cpu_offload=True)
            elif shared.args.load_in_8bit:
                params['quantization_config'] = BitsAndBytesConfig(load_in_8bit=True)
            elif shared.args.bf16:
                params["torch_dtype"] = torch.bfloat16
            else:
                params["torch_dtype"] = torch.float16

            if shared.args.gpu_memory:
                memory_map = list(map(lambda x : x.strip(), shared.args.gpu_memory))
                max_cpu_memory = shared.args.cpu_memory.strip() if shared.args.cpu_memory is not None else '99GiB'
                max_memory = {}
                for i in range(len(memory_map)):
                    max_memory[i] = f'{memory_map[i]}GiB' if not re.match('.*ib$', memory_map[i].lower()) else memory_map[i]
                max_memory['cpu'] = max_cpu_memory
                params['max_memory'] = max_memory
            elif shared.args.auto_devices:
                total_mem = (torch.cuda.get_device_properties(0).total_memory / (1024*1024))
                suggestion = round((total_mem-1000) / 1000) * 1000
                if total_mem - suggestion < 800:
                    suggestion -= 1000
                suggestion = int(round(suggestion/1000))
                print(f"\033[1;32;1mAuto-assiging --gpu-memory {suggestion} for your GPU to try to prevent out-of-memory errors.\nYou can manually set other values.\033[0;37;0m")
                
                max_memory = {0: f'{suggestion}GiB', 'cpu': f'{shared.args.cpu_memory or 99}GiB'}
                params['max_memory'] = max_memory

            if shared.args.disk:
                params["offload_folder"] = shared.args.disk_cache_dir

        checkpoint = Path(f'models/{shared.model_name}')

        if shared.args.load_in_8bit and params.get('max_memory', None) is not None and params['device_map'] == 'auto':
            config = AutoConfig.from_pretrained(checkpoint)
            with init_empty_weights():
                model = AutoModelForCausalLM.from_config(config)
            model.tie_weights()
            params['device_map'] = infer_auto_device_map(
                model, 
                dtype=torch.int8, 
                max_memory=params['max_memory'],
                no_split_module_classes = model._no_split_modules
            )

        model = AutoModelForCausalLM.from_pretrained(checkpoint, **params)

    # Loading the tokenizer
    if shared.model_name.lower().startswith(('gpt4chan', 'gpt-4chan', '4chan')) and Path("models/gpt-j-6B/").exists():
        tokenizer = AutoTokenizer.from_pretrained(Path("models/gpt-j-6B/"))
    else:
        tokenizer = AutoTokenizer.from_pretrained(Path(f"models/{shared.model_name}/"))
    tokenizer.truncation_side = 'left'

    print(f"Loaded the model in {(time.time()-t0):.2f} seconds.")
    return model, tokenizer

def load_soft_prompt(name):
    if name == 'None':
        shared.soft_prompt = False
        shared.soft_prompt_tensor = None
    else:
        with zipfile.ZipFile(Path(f'softprompts/{name}.zip')) as zf:
            zf.extract('tensor.npy')
            zf.extract('meta.json')
            j = json.loads(open('meta.json', 'r').read())
            print(f"\nLoading the softprompt \"{name}\".")
            for field in j:
                if field != 'name':
                    if type(j[field]) is list:
                        print(f"{field}: {', '.join(j[field])}")
                    else:
                        print(f"{field}: {j[field]}")
            print()
            tensor = np.load('tensor.npy')
            Path('tensor.npy').unlink()
            Path('meta.json').unlink()
        tensor = torch.Tensor(tensor).to(device=shared.model.device, dtype=shared.model.dtype)
        tensor = torch.reshape(tensor, (1, tensor.shape[0], tensor.shape[1]))

        shared.soft_prompt = True
        shared.soft_prompt_tensor = tensor

    return name
