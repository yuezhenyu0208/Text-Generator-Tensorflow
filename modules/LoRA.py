from pathlib import Path

import modules.shared as shared
from modules.models import load_model
from modules.text_generation import clear_torch_cache


def reload_model():
    shared.model = shared.tokenizer = None
    clear_torch_cache()
    shared.model, shared.tokenizer = load_model(shared.model_name)

def add_lora_to_model(lora_name):

    from peft import PeftModel

    # If a LoRA had been previously loaded, or if we want
    # to unload a LoRA, reload the model
    if shared.lora_name != "None" or lora_name == "None":
        reload_model()
    shared.lora_name = lora_name

    if lora_name != "None":
        print(f"Adding the LoRA {lora_name} to the model...")
        params = {}
        if not shared.args.cpu:
            params['dtype'] = shared.model.dtype
            if hasattr(shared.model, "hf_device_map"):
                params['device_map'] = {"base_model.model."+k: v for k, v in shared.model.hf_device_map.items()}
            elif shared.args.load_in_8bit:
                params['device_map'] = {'': 0}
            
        shared.model = PeftModel.from_pretrained(shared.model, Path(f"loras/{lora_name}"), **params)
        if not shared.args.load_in_8bit and not shared.args.cpu:
            shared.model.half()
            if not hasattr(shared.model, "hf_device_map"):
                shared.model.cuda()
