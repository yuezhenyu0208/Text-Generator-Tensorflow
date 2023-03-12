import gradio as gr
import modules.shared as shared
import pandas as pd

df = pd.read_csv("https://raw.githubusercontent.com/devbrones/llama-prompts/main/prompts/prompts.csv")

def get_prompt_by_name(name):
    if name == 'None':
        return ''
    else:
        return df[df['Prompt name'] == name].iloc[0]['Prompt'].replace('\\n', '\n')

def ui():
    if not shared.args.chat or shared.args.cai_chat:
        choices = ['None'] + list(df['Prompt name'])

        prompts_menu = gr.Dropdown(value=choices[0], choices=choices, label='Prompt')
        prompts_menu.change(get_prompt_by_name, prompts_menu, shared.gradio['textbox'])
