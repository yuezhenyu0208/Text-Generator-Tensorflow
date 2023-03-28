import json
import sys
import threading
import time
from pathlib import Path

import gradio as gr
import torch
import transformers
from datasets import load_dataset
from peft import (LoraConfig, get_peft_model, get_peft_model_state_dict,
                  prepare_model_for_int8_training)

from modules import shared, ui

WANT_INTERRUPT = False
CURRENT_STEPS = 0
MAX_STEPS = 0
CURRENT_GRADIENT_ACCUM = 1

def get_json_dataset(path: str):
    def get_set():
        return ['None'] + sorted(set(map(lambda x : '.'.join(str(x.name).split('.')[:-1]), Path(path).glob('*.json'))), key=str.lower)
    return get_set

def create_train_interface():
    with gr.Tab('Train LoRA', elem_id='lora-train-tab'):
        lora_name = gr.Textbox(label="Name", info="The name of your new LoRA file")
        with gr.Row():
            # TODO: Implement multi-device support.
            micro_batch_size = gr.Slider(label='Micro Batch Size', value=4, minimum=1, maximum=128, step=1, info='Per-device batch size (NOTE: multiple devices not yet implemented). Increasing this will increase VRAM usage.')
            batch_size = gr.Slider(label='Batch Size', value=128, minimum=1, maximum=1024, step=4, info='Global batch size. The two batch sizes together determine gradient accumulation (gradientAccum = batch / microBatch). Higher gradient accum values lead to better quality training.')

        with gr.Row():
            epochs = gr.Number(label='Epochs', value=1, info='Number of times every entry in the dataset should be fed into training. So 1 means feed each item in once, 5 means feed it in five times, etc.')
            learning_rate = gr.Textbox(label='Learning Rate', value='3e-4', info='Learning rate, in scientific notation. 3e-4 is a good starting base point. 1e-2 is extremely high, 1e-6 is extremely low.')

        # TODO: What is the actual maximum rank? Likely distinct per model. This might be better to somehow be on a log scale.
        lora_rank = gr.Slider(label='LoRA Rank', value=8, minimum=1, maximum=1024, step=4, info='LoRA Rank, or dimension count. Higher values produce a larger file with better control over the model\'s content. Smaller values produce a smaller file with less overall control. Small values like 4 or 8 are great for stylistic guidance, high values like 128 or 256 are good for teaching content upgrades. Higher ranks also require higher VRAM.')
        lora_alpha = gr.Slider(label='LoRA Alpha', value=16, minimum=1, maximum=2048, step=4, info='LoRA Alpha. This divided by the rank becomes the scaling of the LoRA. Higher means stronger. A good standard value is twice your Rank.')
        # TODO: Better explain what this does, in terms of real world effect especially.
        lora_dropout = gr.Slider(label='LoRA Dropout', minimum=0.0, maximum=1.0, step=0.025, value=0.05, info='Percentage probability for dropout of LoRA layers.')
        cutoff_len = gr.Slider(label='Cutoff Length', minimum=1,maximum=2048, value=256, step=32, info='Cutoff length for text input. Essentially, how long of a line of text to feed in at a time. Higher values require drastically more VRAM.')

        with gr.Row():
            dataset_function = get_json_dataset('training/datasets')
            dataset = gr.Dropdown(choices=dataset_function(), value='None', label='Dataset', info='The dataset file to use for training.')
            ui.create_refresh_button(dataset, lambda : None, lambda : {'choices': dataset_function()}, 'refresh-button')
            eval_dataset = gr.Dropdown(choices=dataset_function(), value='None', label='Evaluation Dataset', info='The dataset file used to evaluate the model after training.')
            ui.create_refresh_button(eval_dataset, lambda : None, lambda : {'choices': dataset_function()}, 'refresh-button')
            formats_function = get_json_dataset('training/formats')
            format = gr.Dropdown(choices=formats_function(), value='None', label='Data Format', info='The format file used to decide how to format the dataset input.')
            ui.create_refresh_button(format, lambda : None, lambda : {'choices': formats_function()}, 'refresh-button')

        with gr.Row():
            start_button = gr.Button("Start LoRA Training")
            stop_button = gr.Button("Interrupt")

        output = gr.Markdown(value="Ready")
        startEvent = start_button.click(do_train, [lora_name, micro_batch_size, batch_size, epochs, learning_rate, lora_rank, lora_alpha, lora_dropout, cutoff_len, dataset, eval_dataset, format], [output])
        stop_button.click(do_interrupt, [], [], cancels=[], queue=False)

def do_interrupt():
    global WANT_INTERRUPT
    WANT_INTERRUPT = True

class Callbacks(transformers.TrainerCallback):
    def on_step_begin(self, args: transformers.TrainingArguments, state: transformers.TrainerState, control: transformers.TrainerControl, **kwargs):
        global CURRENT_STEPS, MAX_STEPS
        CURRENT_STEPS = state.global_step * CURRENT_GRADIENT_ACCUM
        MAX_STEPS = state.max_steps * CURRENT_GRADIENT_ACCUM
        if WANT_INTERRUPT:
            control.should_epoch_stop = True
            control.should_training_stop = True
    def on_substep_end(self, args: transformers.TrainingArguments, state: transformers.TrainerState, control: transformers.TrainerControl, **kwargs):
        global CURRENT_STEPS
        CURRENT_STEPS += 1
        if WANT_INTERRUPT:
            control.should_epoch_stop = True
            control.should_training_stop = True

def clean_path(base_path: str, path: str):
    """"Strips unusual symbols and forcibly builds a path as relative to the intended directory."""
    # TODO: Probably could do with a security audit to guarantee there's no ways this can be bypassed to target an unwanted path.
    # Or swap it to a strict whitelist of [a-zA-Z_0-9]
    path = path.replace('\\', '/').replace('..', '_')
    if base_path is None:
        return path
    return f'{Path(base_path).absolute()}/{path}'

def do_train(lora_name: str, micro_batch_size: int, batch_size: int, epochs: int, learning_rate: float, lora_rank: int, lora_alpha: int, lora_dropout: float, cutoff_len: int, dataset: str, eval_dataset: str, format: str):
    global WANT_INTERRUPT, CURRENT_STEPS, MAX_STEPS, CURRENT_GRADIENT_ACCUM
    WANT_INTERRUPT = False
    CURRENT_STEPS = 0
    MAX_STEPS = 0

    # == Input validation / processing ==
    yield "Prepping..."
    # TODO: --lora-dir PR once pulled will need to be applied here
    lora_name = f"loras/{clean_path(None, lora_name)}"
    if dataset is None:
        return "**Missing dataset choice input, cannot continue.**"
    if format is None:
        return "**Missing format choice input, cannot continue.**"
    gradient_accumulation_steps = batch_size // micro_batch_size
    CURRENT_GRADIENT_ACCUM = gradient_accumulation_steps
    actual_lr = float(learning_rate)
    shared.tokenizer.pad_token = 0
    shared.tokenizer.padding_side = "left"

    # == Prep the dataset, format, etc ==
    with open(clean_path('training/formats', f'{format}.json'), 'r') as formatFile:
        format_data: dict[str, str] = json.load(formatFile)

    def tokenize(prompt):
        result = shared.tokenizer(prompt, truncation=True, max_length=cutoff_len + 1, padding="max_length")
        return {
            "input_ids": result["input_ids"][:-1],
            "attention_mask": result["attention_mask"][:-1],
        }

    def generate_prompt(data_point: dict[str, str]):
        for options, data in format_data.items():
            if set(options.split(',')) == set(x[0] for x in data_point.items() if len(x[1].strip()) > 0):
                for key, val in data_point.items():
                    data = data.replace(f'%{key}%', val)
            return data
        raise RuntimeError(f'Data-point "{data_point}" has no keyset match within format "{list(format_data.keys())}"')

    def generate_and_tokenize_prompt(data_point):
        prompt = generate_prompt(data_point)
        return tokenize(prompt)

    print("Loading datasets...")
    data = load_dataset("json", data_files=clean_path('training/datasets', f'{dataset}.json'))
    train_data = data['train'].shuffle().map(generate_and_tokenize_prompt)

    if eval_dataset == 'None':
        eval_data = None
    else:
        eval_data = load_dataset("json", data_files=clean_path('training/datasets', f'{eval_dataset}.json'))
        eval_data = eval_data['train'].shuffle().map(generate_and_tokenize_prompt)
    
    # == Start prepping the model itself ==
    if not hasattr(shared.model, 'lm_head') or hasattr(shared.model.lm_head, 'weight'):
        print("Getting model ready...")
        prepare_model_for_int8_training(shared.model)
    
    print("Prepping for training...")
    config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        # TODO: Should target_modules be configurable?
        target_modules=[ "q_proj", "v_proj" ],
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM"
    )
    lora_model = get_peft_model(shared.model, config)
    trainer = transformers.Trainer(
        model=lora_model,
        train_dataset=train_data,
        eval_dataset=eval_data,
        args=transformers.TrainingArguments(
            per_device_train_batch_size=micro_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            # TODO: Should more of these be configurable? Probably.
            warmup_steps=100,
            num_train_epochs=epochs,
            learning_rate=actual_lr,
            fp16=True,
            logging_steps=20,
            evaluation_strategy="steps" if eval_data is not None else "no",
            save_strategy="steps",
            eval_steps=200 if eval_data is not None else None,
            save_steps=200,
            output_dir=lora_name,
            save_total_limit=3,
            load_best_model_at_end=True if eval_data is not None else False,
            # TODO: Enable multi-device support
            ddp_find_unused_parameters=None
        ),
        data_collator=transformers.DataCollatorForLanguageModeling(shared.tokenizer, mlm=False),
        callbacks=list([Callbacks()])
    )

    lora_model.config.use_cache = False
    old_state_dict = lora_model.state_dict
    lora_model.state_dict = (
        lambda self, *_, **__: get_peft_model_state_dict(self, old_state_dict())
    ).__get__(lora_model, type(lora_model))

    if torch.__version__ >= "2" and sys.platform != "win32":
        lora_model = torch.compile(lora_model)

    # == Main run and monitor loop ==
    # TODO: save/load checkpoints to resume from?
    print("Starting training...")
    yield "Starting..."

    def threadedRun():
        trainer.train()

    thread = threading.Thread(target=threadedRun)
    thread.start()
    lastStep = 0
    startTime = time.perf_counter()

    while thread.is_alive():
        time.sleep(0.5)
        if WANT_INTERRUPT:
            yield "Interrupting, please wait... *(Run will stop after the current training step completes.)*"
        elif CURRENT_STEPS != lastStep:
            lastStep = CURRENT_STEPS
            timeElapsed = time.perf_counter() - startTime
            if timeElapsed <= 0:
                timerInfo = ""
                totalTimeEstimate = 999
            else:
                its = CURRENT_STEPS / timeElapsed
                if its > 1:
                    timerInfo = f"`{its:.2f}` it/s"
                else:
                    timerInfo = f"`{1.0/its:.2f}` s/it"
                totalTimeEstimate = (1.0/its) * (MAX_STEPS)
            yield f"Running... **{CURRENT_STEPS}** / **{MAX_STEPS}** ... {timerInfo}, `{timeElapsed:.0f}`/`{totalTimeEstimate:.0f}` seconds"

    print("Training complete, saving...")
    lora_model.save_pretrained(lora_name)

    if WANT_INTERRUPT:
        print("Training interrupted.")
        yield f"Interrupted. Incomplete LoRA saved to `{lora_name}`"
    else:
        print("Training complete!")
        yield f"Done! LoRA saved to `{lora_name}`"
