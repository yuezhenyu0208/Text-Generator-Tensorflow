import argparse

model = None
tokenizer = None
model_name = ""
soft_prompt_tensor = None
soft_prompt = False

# Chat variables
history = {'internal': [], 'visible': []}
character = 'None'
stop_everything = False

# UI elements (buttons, sliders, HTML, etc)
gradio = {}

# Generation input parameters
input_params = []

settings = {
    'max_new_tokens': 200,
    'max_new_tokens_min': 1,
    'max_new_tokens_max': 2000,
    'preset': 'NovelAI-Sphinx Moth',
    'name1': 'Person 1',
    'name2': 'Person 2',
    'context': 'This is a conversation between two people.',
    'prompt': 'Common sense questions and answers\n\nQuestion: \nFactual answer:',
    'prompt_gpt4chan': '-----\n--- 865467536\nInput text\n--- 865467537\n',
    'stop_at_newline': True,
    'chat_prompt_size': 2048,
    'chat_prompt_size_min': 0,
    'chat_prompt_size_max': 2048,
    'chat_generation_attempts': 1,
    'chat_generation_attempts_min': 1,
    'chat_generation_attempts_max': 5,
    'preset_pygmalion': 'Pygmalion',
    'name1_pygmalion': 'You',
    'name2_pygmalion': 'Kawaii',
    'context_pygmalion': "Kawaii's persona: Kawaii is a cheerful person who loves to make others smile. She is an optimist who loves to spread happiness and positivity wherever she goes.\n<START>",
    'stop_at_newline_pygmalion': False,
}

parser = argparse.ArgumentParser(formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=54))
parser.add_argument('--model', type=str, help='Name of the model to load by default.')
parser.add_argument('--notebook', action='store_true', help='Launch the web UI in notebook mode, where the output is written to the same text box as the input.')
parser.add_argument('--chat', action='store_true', help='Launch the web UI in chat mode.')
parser.add_argument('--cai-chat', action='store_true', help='Launch the web UI in chat mode with a style similar to Character.AI\'s. If the file img_bot.png or img_bot.jpg exists in the same folder as server.py, this image will be used as the bot\'s profile picture. Similarly, img_me.png or img_me.jpg will be used as your profile picture.')
parser.add_argument('--cpu', action='store_true', help='Use the CPU to generate text.')
parser.add_argument('--load-in-8bit', action='store_true', help='Load the model with 8-bit precision.')
parser.add_argument('--bf16', action='store_true', help='Load the model with bfloat16 precision. Requires NVIDIA Ampere GPU.')
parser.add_argument('--auto-devices', action='store_true', help='Automatically split the model across the available GPU(s) and CPU.')
parser.add_argument('--disk', action='store_true', help='If the model is too large for your GPU(s) and CPU combined, send the remaining layers to the disk.')
parser.add_argument('--disk-cache-dir', type=str, default="cache", help='Directory to save the disk cache to. Defaults to "cache".')
parser.add_argument('--gpu-memory', type=int, nargs="+", help='Maxmimum GPU memory in GiB to be allocated per GPU. Example: --gpu-memory 10 for a single GPU, --gpu-memory 10 5 for two GPUs.')
parser.add_argument('--cpu-memory', type=int, help='Maximum CPU memory in GiB to allocate for offloaded weights. Must be an integer number. Defaults to 99.')
parser.add_argument('--flexgen', action='store_true', help='Enable the use of FlexGen offloading.')
parser.add_argument('--percent', type=int, nargs="+", default=[0, 100, 100, 0, 100, 0], help='FlexGen: allocation percentages. Must be 6 numbers separated by spaces (default: 0, 100, 100, 0, 100, 0).')
parser.add_argument("--compress-weight", action="store_true", help="FlexGen: activate weight compression.")
parser.add_argument('--deepspeed', action='store_true', help='Enable the use of DeepSpeed ZeRO-3 for inference via the Transformers integration.')
parser.add_argument('--nvme-offload-dir', type=str, help='DeepSpeed: Directory to use for ZeRO-3 NVME offloading.')
parser.add_argument('--local_rank', type=int, default=0, help='DeepSpeed: Optional argument for distributed setups.')
parser.add_argument('--no-stream', action='store_true', help='Don\'t stream the text output in real time. This improves the text generation performance.')
parser.add_argument('--settings', type=str, help='Load the default interface settings from this json file. See settings-template.json for an example.')
parser.add_argument('--extensions', type=str, nargs="+", help='The list of extensions to load. If you want to load more than one extension, write the names separated by spaces.')
parser.add_argument('--listen', action='store_true', help='Make the web UI reachable from your local network.')
parser.add_argument('--listen-port', type=int, help='The listening port that the server will use.')
parser.add_argument('--share', action='store_true', help='Create a public URL. This is useful for running the web UI on Google Colab or similar.')
parser.add_argument('--verbose', action='store_true', help='Print the prompts to the terminal.')
args = parser.parse_args()
