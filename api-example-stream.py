'''

Contributed by SagsMug. Thank you SagsMug.
https://github.com/oobabooga/text-generation-webui/pull/175

'''

import asyncio
import json
import random
import string

import websockets


def random_hash():
    letters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(letters) for i in range(9))

async def run(context):
    server = "127.0.0.1"
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
    session = random_hash()

    async with websockets.connect(f"ws://{server}:7860/queue/join") as websocket:
        while content := json.loads(await websocket.recv()):
            #Python3.10 syntax, replace with if elif on older
            match content["msg"]:
                case "send_hash":
                    await websocket.send(json.dumps({
                        "session_hash": session,
                        "fn_index": 12
                    }))
                case "estimation":
                    pass
                case "send_data":
                    await websocket.send(json.dumps({
                        "session_hash": session,
                        "fn_index": 12,
                        "data": [
                            context,
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
                    }))
                case "process_starts":
                    pass
                case "process_generating" | "process_completed":
                    yield content["output"]["data"][0]
                    # You can search for your desired end indicator and 
                    #  stop generation by closing the websocket here
                    if (content["msg"] == "process_completed"):
                        break

prompt = "What I would like to say is the following: "

async def get_result():
    async for response in run(prompt):
        # Print intermediate steps
        print(response)

    # Print final result
    print(response)

asyncio.run(get_result())
