'''

This is an example on how to use the API for oobabooga/text-generation-webui.

Make sure to start the web UI with the following flags:

python server.py --model MODEL --listen --no-stream

Optionally, you can also add the --share flag to generate a public gradio URL,
allowing you to use the API remotely.

'''
import requests

# Server address
server = "127.0.0.1"

# Generation parameters
# Reference: https://huggingface.co/docs/transformers/main_classes/text_generation#transformers.GenerationConfig
params = {
    'max_new_tokens': 200,
    'do_sample': True,
    'temperature': 0.5,
    'top_p': 0.9,
    'typical_p': 1,
    'repetition_penalty': 1.05,
    'encoder_repetition_penalty': 1.0,
    'top_k': 0,
    'min_length': 0,
    'no_repeat_ngram_size': 0,
    'num_beams': 1,
    'penalty_alpha': 0,
    'length_penalty': 1,
    'early_stopping': False,
    'seed': -1,
}

# Input prompt
prompt = "What I would like to say is the following: "

response = requests.post(f"http://{server}:7860/run/textgen", json={
    "data": [
        prompt,
        params['max_new_tokens'],
        params['do_sample'],
        params['temperature'],
        params['top_p'],
        params['typical_p'],
        params['repetition_penalty'],
        params['encoder_repetition_penalty'],
        params['top_k'],
        params['min_length'],
        params['no_repeat_ngram_size'],
        params['num_beams'],
        params['penalty_alpha'],
        params['length_penalty'],
        params['early_stopping'],
        params['seed'],
    ]
}).json()

reply = response["data"][0]
print(reply)
