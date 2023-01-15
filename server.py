import re
import time
import glob
from sys import exit
import torch
import argparse
from pathlib import Path
import gradio as gr
import transformers
from html_generator import *
from transformers import AutoTokenizer, AutoModelForCausalLM


parser = argparse.ArgumentParser()
parser.add_argument('--model', type=str, help='Name of the model to load by default.')
parser.add_argument('--notebook', action='store_true', help='Launch the webui in notebook mode, where the output is written to the same text box as the input.')
parser.add_argument('--chat', action='store_true', help='Launch the webui in chat mode.')
parser.add_argument('--cpu', action='store_true', help='Use the CPU to generate text.')
parser.add_argument('--auto-devices', action='store_true', help='Automatically split the model across the available GPU(s) and CPU.')
parser.add_argument('--load-in-8bit', action='store_true', help='Load the model with 8-bit precision.')
parser.add_argument('--no-listen', action='store_true', help='Make the webui unreachable from your local network.')
args = parser.parse_args()
loaded_preset = None
available_models = sorted(set(map(lambda x : str(x.name).replace('.pt', ''), list(Path('models/').glob('*'))+list(Path('torch-dumps/').glob('*')))))
available_models = [item for item in available_models if not item.endswith('.txt')]
available_models = sorted(available_models, key=str.lower)
available_presets = sorted(set(map(lambda x : str(x.name).split('.')[0], list(Path('presets').glob('*.txt')))))

def load_model(model_name):
    print(f"Loading {model_name}...")
    t0 = time.time()

    # Default settings
    if not (args.cpu or args.auto_devices or args.load_in_8bit):
        if Path(f"torch-dumps/{model_name}.pt").exists():
            print("Loading in .pt format...")
            model = torch.load(Path(f"torch-dumps/{model_name}.pt"))
        elif model_name.lower().startswith(('gpt-neo', 'opt-', 'galactica')) and any(size in model_name.lower() for size in ('13b', '20b', '30b')):
            model = AutoModelForCausalLM.from_pretrained(Path(f"models/{model_name}"), device_map='auto', load_in_8bit=True)
        else:
            model = AutoModelForCausalLM.from_pretrained(Path(f"models/{model_name}"), low_cpu_mem_usage=True, torch_dtype=torch.float16).cuda()

    # Custom
    else:
        settings = ["low_cpu_mem_usage=True"]
        cuda = ""
        command = "AutoModelForCausalLM.from_pretrained"

        if args.cpu:
            settings.append("torch_dtype=torch.float32")
        else:
            if args.load_in_8bit:
                settings.append("device_map='auto'")
                settings.append("load_in_8bit=True")
            else:
                settings.append("torch_dtype=torch.float16")
                if args.auto_devices:
                    settings.append("device_map='auto'")
                else:
                    cuda = ".cuda()"

        settings = ', '.join(settings)
        command = f"{command}(Path(f'models/{model_name}'), {settings}){cuda}"
        model = eval(command)

    # Loading the tokenizer
    if model_name.lower().startswith(('gpt4chan', 'gpt-4chan', '4chan')) and Path(f"models/gpt-j-6B/").exists():
        tokenizer = AutoTokenizer.from_pretrained(Path("models/gpt-j-6B/"))
    else:
        tokenizer = AutoTokenizer.from_pretrained(Path(f"models/{model_name}/"))

    print(f"Loaded the model in {(time.time()-t0):.2f} seconds.")
    return model, tokenizer

# Removes empty replies from gpt4chan outputs
def fix_gpt4chan(s):
    for i in range(10):
        s = re.sub("--- [0-9]*\n>>[0-9]*\n---", "---", s)
        s = re.sub("--- [0-9]*\n *\n---", "---", s)
        s = re.sub("--- [0-9]*\n\n\n---", "---", s)
    return s

# Fix the LaTeX equations in GALACTICA
def fix_galactica(s):
    s = s.replace(r'\[', r'$')
    s = s.replace(r'\]', r'$')
    s = s.replace(r'\(', r'$')
    s = s.replace(r'\)', r'$')
    s = s.replace(r'$$', r'$')
    return s

def generate_html(s):
    s = '\n'.join([f'<p style="margin-bottom: 20px">{line}</p>' for line in s.split('\n')])
    s = f'<div style="max-width: 600px; margin-left: auto; margin-right: auto; background-color:#eef2ff; color:#0b0f19; padding:3em; font-size:1.2em;">{s}</div>'
    return s

def generate_reply(question, tokens, inference_settings, selected_model, eos_token=None):
    global model, tokenizer, model_name, loaded_preset, preset

    if selected_model != model_name:
        model_name = selected_model
        model = None
        tokenizer = None
        if not args.cpu:
            torch.cuda.empty_cache()
        model, tokenizer = load_model(model_name)
    if inference_settings != loaded_preset:
        with open(Path(f'presets/{inference_settings}.txt'), 'r') as infile:
            preset = infile.read()
        loaded_preset = inference_settings

    if not args.cpu:
        torch.cuda.empty_cache()
        input_ids = tokenizer.encode(str(question), return_tensors='pt').cuda()
        cuda = ".cuda()"
    else:
        input_ids = tokenizer.encode(str(question), return_tensors='pt')
        cuda = ""

    if eos_token is None:
        output = eval(f"model.generate(input_ids, {preset}){cuda}")
    else:
        n = tokenizer.encode(eos_token, return_tensors='pt')[0][-1]
        output = eval(f"model.generate(input_ids, eos_token_id={n}, {preset}){cuda}")

    reply = tokenizer.decode(output[0], skip_special_tokens=True)
    reply = reply.replace(r'<|endoftext|>', '')
    if model_name.lower().startswith('galactica'):
        reply = fix_galactica(reply)
        return reply, reply, generate_html(reply)
    elif model_name.lower().startswith('gpt4chan'):
        reply = fix_gpt4chan(reply)
        return reply, 'Only applicable for galactica models.', generate_4chan_html(reply)
    else:
        return reply, 'Only applicable for galactica models.', generate_html(reply)

# Choosing the default model
if args.model is not None:
    model_name = args.model
else:
    if len(available_models) == 0:
        print("No models are available! Please download at least one.")
        exit(0)
    elif len(available_models) == 1:
        i = 0
    else:
        print("The following models are available:\n")
        for i,model in enumerate(available_models):
            print(f"{i+1}. {model}")
        print(f"\nWhich one do you want to load? 1-{len(available_models)}\n")
        i = int(input())-1
        print()
    model_name = available_models[i]
model, tokenizer = load_model(model_name)

# UI settings
if model_name.lower().startswith('gpt4chan'):
    default_text = "-----\n--- 865467536\nInput text\n--- 865467537\n"
else:
    default_text = "Common sense questions and answers\n\nQuestion: \nFactual answer:"
description = f"""

        # Text generation lab
        Generate text using Large Language Models.
        """
css=".my-4 {margin-top: 0} .py-6 {padding-top: 2.5rem}"

if args.notebook:
    with gr.Blocks(css=css, analytics_enabled=False) as interface:
        gr.Markdown(description)
        with gr.Tab('Raw'):
            textbox = gr.Textbox(value=default_text, lines=23)
        with gr.Tab('Markdown'):
            markdown = gr.Markdown()
        with gr.Tab('HTML'):
            html = gr.HTML()
        btn = gr.Button("Generate")

        length_slider = gr.Slider(minimum=1, maximum=2000, step=1, label='max_new_tokens', value=200)
        with gr.Row():
            with gr.Column():
                model_menu = gr.Dropdown(choices=available_models, value=model_name, label='Model')
            with gr.Column():
                preset_menu = gr.Dropdown(choices=available_presets, value="NovelAI-Sphinx Moth", label='Settings preset')

        btn.click(generate_reply, [textbox, length_slider, preset_menu, model_menu], [textbox, markdown, html], show_progress=True, api_name="textgen")
        textbox.submit(generate_reply, [textbox, length_slider, preset_menu, model_menu], [textbox, markdown, html], show_progress=True)
elif args.chat:
    history = []

    def chatbot_wrapper(text, tokens, inference_settings, selected_model, name1, name2, context, check):
        text = text.replace('\n', '\n\n')
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        question = context+'\n\n'
        for i in range(len(history)):
            question += f"{name1}: {history[i][0][3:-5].strip()}\n"
            question += f"{name2}: {history[i][1][3:-5].strip()}\n"
        question += f"{name1}: {text}\n"
        question += f"{name2}:"

        if check:
            reply = generate_reply(question, tokens, inference_settings, selected_model, eos_token='\n')[0]
            reply = reply[len(question):].split('\n')[0].strip()
        else:
            reply = generate_reply(question, tokens, inference_settings, selected_model)[0]
            reply = reply[len(question):]
            idx = reply.find(f"\n{name1}:")
            if idx != -1:
                reply = reply[:idx]
            reply = reply.replace('\n', '\n\n')
            reply = re.sub(r"\n{3,}", "\n\n", reply)
            reply = reply.strip()

        history.append((text, reply))
        return history

    def clear():
        global history
        history = []

    if 'pygmalion' in model_name.lower():
        context_str = "This is a conversation between two people.\n<START>"
        name1_str = "You"
        name2_str = "Kawaii"
    else:
        context_str = "This is a conversation between two people."
        name1_str = "Person 1"
        name2_str = "Person 2"

    with gr.Blocks(css=css+".h-\[40vh\] {height: 50vh}", analytics_enabled=False) as interface:
        gr.Markdown(description)
        with gr.Row():
            with gr.Column():
                length_slider = gr.Slider(minimum=1, maximum=2000, step=1, label='max_new_tokens', value=200)
                with gr.Row():
                    with gr.Column():
                        model_menu = gr.Dropdown(choices=available_models, value=model_name, label='Model')
                    with gr.Column():
                        preset_menu = gr.Dropdown(choices=available_presets, value="NovelAI-Sphinx Moth", label='Settings preset')

                name1 = gr.Textbox(value=name1_str, lines=1, label='Your name')
                name2 = gr.Textbox(value=name2_str, lines=1, label='Bot\'s name')
                context = gr.Textbox(value=context_str, lines=2, label='Context')
                with gr.Row():
                    check = gr.Checkbox(value=True, label='Stop generating at new line character?')

            with gr.Column():
                display1 = gr.Chatbot()
                textbox = gr.Textbox(lines=2, label='Input')
                btn = gr.Button("Generate")
                btn2 = gr.Button("Clear history")

        btn.click(chatbot_wrapper, [textbox, length_slider, preset_menu, model_menu, name1, name2, context, check], display1, show_progress=True, api_name="textgen")
        textbox.submit(chatbot_wrapper, [textbox, length_slider, preset_menu, model_menu, name1, name2, context, check], display1, show_progress=True)
        btn2.click(clear)
        btn.click(lambda x: "", textbox, textbox, show_progress=False)
        textbox.submit(lambda x: "", textbox, textbox, show_progress=False)
        btn2.click(lambda x: "", display1, display1)
else:

    def continue_wrapper(question, tokens, inference_settings, selected_model):
        a, b, c = generate_reply(question, tokens, inference_settings, selected_model)
        return a, a, b, c

    with gr.Blocks(css=css, analytics_enabled=False) as interface:
        gr.Markdown(description)
        with gr.Row():
            with gr.Column():
                textbox = gr.Textbox(value=default_text, lines=15, label='Input')
                length_slider = gr.Slider(minimum=1, maximum=2000, step=1, label='max_new_tokens', value=200)
                preset_menu = gr.Dropdown(choices=available_presets, value="NovelAI-Sphinx Moth", label='Settings preset')
                model_menu = gr.Dropdown(choices=available_models, value=model_name, label='Model')
                btn = gr.Button("Generate")
                cont = gr.Button("Continue")
            with gr.Column():
                with gr.Tab('Raw'):
                    output_textbox = gr.Textbox(lines=15, label='Output')
                with gr.Tab('Markdown'):
                    markdown = gr.Markdown()
                with gr.Tab('HTML'):
                    html = gr.HTML()

        btn.click(generate_reply, [textbox, length_slider, preset_menu, model_menu], [output_textbox, markdown, html], show_progress=True, api_name="textgen")
        cont.click(continue_wrapper, [output_textbox, length_slider, preset_menu, model_menu], [output_textbox, textbox, markdown, html], show_progress=True)
        textbox.submit(generate_reply, [textbox, length_slider, preset_menu, model_menu], [output_textbox, markdown, html], show_progress=True)

if args.no_listen:
    interface.launch(share=False)
else:
    interface.launch(share=False, server_name="0.0.0.0")
