import gc
import re
import time

import numpy as np
import torch
import transformers

import modules.shared as shared
from modules.callbacks import (Iteratorize, Stream,
                               _SentinelTokenStoppingCriteria)
from modules.extensions import apply_extensions
from modules.html_generator import generate_4chan_html, generate_basic_html
from modules.models import local_rank


def get_max_prompt_length(tokens):
    max_length = 2048-tokens
    if shared.soft_prompt:
        max_length -= shared.soft_prompt_tensor.shape[1]
    return max_length

def encode(prompt, tokens_to_generate=0, add_special_tokens=True):
    if shared.is_RWKV:
        input_ids = shared.tokenizer.encode(str(prompt))
        input_ids = np.array(input_ids).reshape(1, len(input_ids))
        return input_ids
    else:
        input_ids = shared.tokenizer.encode(str(prompt), return_tensors='pt', truncation=True, max_length=get_max_prompt_length(tokens_to_generate), add_special_tokens=add_special_tokens)
        if shared.args.cpu:
            return input_ids
        elif shared.args.flexgen:
            return input_ids.numpy()
        elif shared.args.deepspeed:
            return input_ids.to(device=local_rank)
        else:
            return input_ids.cuda()

def decode(output_ids):
    reply = shared.tokenizer.decode(output_ids, skip_special_tokens=True)
    reply = reply.replace(r'<|endoftext|>', '')
    return reply

def generate_softprompt_input_tensors(input_ids):
    inputs_embeds = shared.model.transformer.wte(input_ids)
    inputs_embeds = torch.cat((shared.soft_prompt_tensor, inputs_embeds), dim=1)
    filler_input_ids = torch.zeros((1, inputs_embeds.shape[1]), dtype=input_ids.dtype).to(shared.model.device)
    #filler_input_ids += shared.model.config.bos_token_id # setting dummy input_ids to bos tokens
    return inputs_embeds, filler_input_ids

# Removes empty replies from gpt4chan outputs
def fix_gpt4chan(s):
    for i in range(10):
        s = re.sub("--- [0-9]*\n>>[0-9]*\n---", "---", s)
        s = re.sub("--- [0-9]*\n *\n---", "---", s)
        s = re.sub("--- [0-9]*\n\n\n---", "---", s)
    return s

# Fix the LaTeX equations in galactica
def fix_galactica(s):
    s = s.replace(r'\[', r'$')
    s = s.replace(r'\]', r'$')
    s = s.replace(r'\(', r'$')
    s = s.replace(r'\)', r'$')
    s = s.replace(r'$$', r'$')
    s = re.sub(r'\n', r'\n\n', s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def formatted_outputs(reply, model_name):
    if not (shared.args.chat or shared.args.cai_chat):
        if model_name.lower().startswith('galactica'):
            reply = fix_galactica(reply)
            return reply, reply, generate_basic_html(reply)
        elif model_name.lower().startswith(('gpt4chan', 'gpt-4chan', '4chan')):
            reply = fix_gpt4chan(reply)
            return reply, 'Only applicable for GALACTICA models.', generate_4chan_html(reply)
        else:
            return reply, 'Only applicable for GALACTICA models.', generate_basic_html(reply)
    else:
        return reply

def clear_torch_cache():
    gc.collect()
    if not shared.args.cpu:
        torch.cuda.empty_cache()

def generate_reply(question, max_new_tokens, do_sample, temperature, top_p, typical_p, repetition_penalty, top_k, min_length, no_repeat_ngram_size, num_beams, penalty_alpha, length_penalty, early_stopping, eos_token=None, stopping_string=None):
    clear_torch_cache()
    t0 = time.time()

    # These models are not part of Hugging Face, so we handle them
    # separately and terminate the function call earlier
    if shared.is_RWKV:
        try:
            if shared.args.no_stream:
                reply = shared.model.generate(context=question, token_count=max_new_tokens, temperature=temperature, top_p=top_p, top_k=top_k)
                yield formatted_outputs(reply, shared.model_name)
            else:
                yield formatted_outputs(question, shared.model_name)
                # RWKV has proper streaming, which is very nice.
                # No need to generate 8 tokens at a time.
                for reply in shared.model.generate_with_streaming(context=question, token_count=max_new_tokens, temperature=temperature, top_p=top_p, top_k=top_k):
                    yield formatted_outputs(reply, shared.model_name)
        finally:
            t1 = time.time()
            output = encode(reply)[0]
            input_ids = encode(question)
            print(f"Output generated in {(t1-t0):.2f} seconds ({(len(output)-len(input_ids[0]))/(t1-t0):.2f} tokens/s, {len(output)-len(input_ids[0])} tokens)")
            return

    original_question = question
    if not (shared.args.chat or shared.args.cai_chat):
        question = apply_extensions(question, "input")
    if shared.args.verbose:
        print(f"\n\n{question}\n--------------------\n")

    input_ids = encode(question, max_new_tokens)
    original_input_ids = input_ids
    output = input_ids[0]
    cuda = "" if (shared.args.cpu or shared.args.deepspeed or shared.args.flexgen) else ".cuda()"
    eos_token_ids = [shared.tokenizer.eos_token_id]
    if eos_token is not None:
        eos_token_ids.append(int(encode(eos_token)[0][-1]))
    stopping_criteria_list = transformers.StoppingCriteriaList()
    if stopping_string is not None:
        # Copied from https://github.com/PygmalionAI/gradio-ui/blob/master/src/model.py
        t = encode(stopping_string, 0, add_special_tokens=False)
        stopping_criteria_list.append(_SentinelTokenStoppingCriteria(sentinel_token_ids=t, starting_idx=len(input_ids[0])))

    if not shared.args.flexgen:
        generate_params = [
            f"max_new_tokens=max_new_tokens",
            f"eos_token_id={eos_token_ids}",
            f"stopping_criteria=stopping_criteria_list",
            f"do_sample={do_sample}",
            f"temperature={temperature}",
            f"top_p={top_p}",
            f"typical_p={typical_p}",
            f"repetition_penalty={repetition_penalty}",
            f"top_k={top_k}",
            f"min_length={min_length if shared.args.no_stream else 0}",
            f"no_repeat_ngram_size={no_repeat_ngram_size}",
            f"num_beams={num_beams}",
            f"penalty_alpha={penalty_alpha}",
            f"length_penalty={length_penalty}",
            f"early_stopping={early_stopping}",
        ]
    else:
        generate_params = [
            f"max_new_tokens={max_new_tokens if shared.args.no_stream else 8}",
            f"do_sample={do_sample}",
            f"temperature={temperature}",
            f"stop={eos_token_ids[-1]}",
        ]
    if shared.args.deepspeed:
        generate_params.append("synced_gpus=True")
    if shared.soft_prompt:
        inputs_embeds, filler_input_ids = generate_softprompt_input_tensors(input_ids)
        generate_params.insert(0, "inputs_embeds=inputs_embeds")
        generate_params.insert(0, "inputs=filler_input_ids")
    else:
        generate_params.insert(0, "inputs=input_ids")

    try:
        # Generate the entire reply at once.
        if shared.args.no_stream:
            with torch.no_grad():
                output = eval(f"shared.model.generate({', '.join(generate_params)}){cuda}")[0]
            if shared.soft_prompt:
                output = torch.cat((input_ids[0], output[filler_input_ids.shape[1]:]))

            reply = decode(output)
            if not (shared.args.chat or shared.args.cai_chat):
                reply = original_question + apply_extensions(reply[len(question):], "output")

            yield formatted_outputs(reply, shared.model_name)

        # Stream the reply 1 token at a time.
        # This is based on the trick of using 'stopping_criteria' to create an iterator.
        elif not shared.args.flexgen:

            def generate_with_callback(callback=None, **kwargs):
                kwargs['stopping_criteria'].append(Stream(callback_func=callback))
                clear_torch_cache()
                with torch.no_grad():
                    shared.model.generate(**kwargs)

            def generate_with_streaming(**kwargs):
                return Iteratorize(generate_with_callback, kwargs, callback=None)

            shared.still_streaming = True
            yield formatted_outputs(original_question, shared.model_name)
            with eval(f"generate_with_streaming({', '.join(generate_params)})") as generator:
                for output in generator:
                    if shared.soft_prompt:
                        output = torch.cat((input_ids[0], output[filler_input_ids.shape[1]:]))
                    reply = decode(output)

                    if not (shared.args.chat or shared.args.cai_chat):
                        reply = original_question + apply_extensions(reply[len(question):], "output")

                    if output[-1] in eos_token_ids:
                        break
                    yield formatted_outputs(reply, shared.model_name)

                shared.still_streaming = False
                yield formatted_outputs(reply, shared.model_name)

        # Stream the output naively for FlexGen since it doesn't support 'stopping_criteria'
        else:
            shared.still_streaming = True
            for i in range(max_new_tokens//8+1):
                clear_torch_cache()
                with torch.no_grad():
                    output = eval(f"shared.model.generate({', '.join(generate_params)})")[0]
                if shared.soft_prompt:
                    output = torch.cat((input_ids[0], output[filler_input_ids.shape[1]:]))
                reply = decode(output)

                if not (shared.args.chat or shared.args.cai_chat):
                    reply = original_question + apply_extensions(reply[len(question):], "output")

                if np.count_nonzero(np.isin(input_ids[0], eos_token_ids)) < np.count_nonzero(np.isin(output, eos_token_ids)):
                    break
                yield formatted_outputs(reply, shared.model_name)

                input_ids = np.reshape(output, (1, output.shape[0]))
                if shared.soft_prompt:
                    inputs_embeds, filler_input_ids = generate_softprompt_input_tensors(input_ids)

            shared.still_streaming = False
            yield formatted_outputs(reply, shared.model_name)

    finally:
        t1 = time.time()
        print(f"Output generated in {(t1-t0):.2f} seconds ({(len(output)-len(original_input_ids[0]))/(t1-t0):.2f} tokens/s, {len(output)-len(original_input_ids[0])} tokens)")
        return
