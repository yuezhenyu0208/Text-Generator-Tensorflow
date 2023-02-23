import extensions
import modules.shared as shared

extension_state = {}
available_extensions = []

def load_extensions():
    global extension_state
    for i,ext in enumerate(shared.args.extensions.split(',')):
        if ext in available_extensions:
            print(f'Loading the extension "{ext}"... ', end='')
            ext_string = f"extensions.{ext}.script"
            exec(f"import {ext_string}")
            extension_state[ext] = [True, i]
            print(f'Ok.')

def apply_extensions(text, typ):
    for ext in sorted(extension_state, key=lambda x : extension_state[x][1]):
        if extension_state[ext][0] == True:
            ext_string = f"extensions.{ext}.script"
            if typ == "input" and hasattr(eval(ext_string), "input_modifier"):
                text = eval(f"{ext_string}.input_modifier(text)")
            elif typ == "output" and hasattr(eval(ext_string), "output_modifier"):
                text = eval(f"{ext_string}.output_modifier(text)")
            elif typ == "bot_prefix" and hasattr(eval(ext_string), "bot_prefix_modifier"):
                text = eval(f"{ext_string}.bot_prefix_modifier(text)")
    return text

def update_extensions_parameters(*kwargs):
    i = 0
    for ext in sorted(extension_state, key=lambda x : extension_state[x][1]):
        if extension_state[ext][0] == True:
            params = eval(f"extensions.{ext}.script.params")
            for param in params:
                if len(kwargs) >= i+1:
                    params[param] = eval(f"kwargs[{i}]")
                    i += 1

def get_params(name):
    return eval(f"extensions.{name}.script.params")
