# Text generation web UI

A gradio web UI for running large language models like gpt-j-6B, gpt-neo, opt, galactica, and pygmalion on your own computer.

Its goal is to become the [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) of text generation.

[[Try it on Google Colab]](https://colab.research.google.com/github/oobabooga/AI-Notebooks/blob/main/Colab-TextGen-GPU.ipynb)

|![Image1](https://github.com/oobabooga/screenshots/raw/main/qa.png) | ![Image2](https://github.com/oobabooga/screenshots/raw/main/cai3.png) |
|:---:|:---:|
|![Image3](https://github.com/oobabooga/screenshots/raw/main/gpt4chan.png) | ![Image4](https://github.com/oobabooga/screenshots/raw/main/galactica.png) |

## Features

* Switch between different models using a dropdown menu.
* Notebook mode that resembles OpenAI's playground.
* Chat mode for conversation and role playing.
* Generate nice HTML output for GPT-4chan.
* Generate Markdown output for [GALACTICA](https://github.com/paperswithcode/galai), including LaTeX support.
* Support for [Pygmalion](https://huggingface.co/models?search=pygmalionai/pygmalion) and custom characters in JSON or TavernAI Character Card formats ([FAQ](https://github.com/oobabooga/text-generation-webui/wiki/Pygmalion-chat-model-FAQ)).
* Stream the text output in real time.
* Load parameter presets from text files.
* Load large models in 8-bit mode ([see here](https://github.com/oobabooga/text-generation-webui/issues/20#issuecomment-1411650652) if you are on Windows).
* Split large models across your GPU(s), CPU, and disk.
* CPU mode.
* Get responses via API.
* Supports extensions ([guide](https://github.com/oobabooga/text-generation-webui/wiki/Extensions)).
* Works on Google Colab ([guide](https://github.com/oobabooga/text-generation-webui/wiki/Running-on-Colab)).

## Installation option 1: conda

Open a terminal and copy and paste these commands one at a time ([install conda](https://docs.conda.io/en/latest/miniconda.html) first if you don't have it already):

```
conda create -n textgen
conda activate textgen
conda install torchvision torchaudio pytorch-cuda=11.7 git -c pytorch -c nvidia
git clone https://github.com/oobabooga/text-generation-webui
cd text-generation-webui
pip install -r requirements.txt
```

The third line assumes that you have an NVIDIA GPU. 

* If you have an AMD GPU, you should install the ROCm version of pytorch instead.
* If you are running in CPU mode, you just need the standard pytorch and should replace the third command with this one:

```
conda install pytorch torchvision torchaudio git -c pytorch
```

Once you have completed these steps, you should be able to start the web UI. However, you will first need to download a model.

## Installation option 2: 1-click Windows installer

[oobabooga-windows.zip](https://github.com/oobabooga/text-generation-webui/releases/download/windows/oobabooga-windows.zip)

Just download the zip above, extract it, and double click on "install". The web UI and all its dependencies will be installed in the same folder.

* To download a model, double click on "download-model"
* To start the web UI, double click on "start-webui" 

## Downloading models

Models should be placed under `models/model-name`. For instance, `models/gpt-j-6B` for [GPT-J 6B](https://huggingface.co/EleutherAI/gpt-j-6B/tree/main).

#### Hugging Face

[Hugging Face](https://huggingface.co/models?pipeline_tag=text-generation&sort=downloads) is the main place to download models. These are some noteworthy examples:

* [GPT-J 6B](https://huggingface.co/EleutherAI/gpt-j-6B/tree/main)
* [GPT-Neo](https://huggingface.co/models?pipeline_tag=text-generation&sort=downloads&search=eleutherai+%2F+gpt-neo)
* [OPT](https://huggingface.co/models?search=facebook/opt)
* [GALACTICA](https://huggingface.co/models?search=facebook/galactica)
* [\*-Erebus](https://huggingface.co/models?search=erebus)
* [Pygmalion](https://huggingface.co/models?search=pygmalion)

You can automatically download a model from HF using the script `download-model.py`. Its usage is very simple:

    python download-model.py organization/model

For instance:

    python download-model.py facebook/opt-1.3b

If you want to download a model manually, note that all you need are the json, txt, and pytorch\*.bin files. The remaining files are not necessary.

#### GPT-4chan

[GPT-4chan](https://huggingface.co/ykilcher/gpt-4chan) has been shut down from Hugging Face, so you need to download it elsewhere. You have two options:

* Torrent: [16-bit](https://archive.org/details/gpt4chan_model_float16) / [32-bit](https://archive.org/details/gpt4chan_model)
* Direct download: [16-bit](https://theswissbay.ch/pdf/_notpdf_/gpt4chan_model_float16/) / [32-bit](https://theswissbay.ch/pdf/_notpdf_/gpt4chan_model/)

The 32-bit version is only relevant if you intend to run the model in CPU mode. Otherwise, you should use the 16-bit version.

After downloading the model, follow these steps:

1. Place the files under `models/gpt4chan_model_float16` or `models/gpt4chan_model`.
2. Place GPT-J 6B's config.json file in that same folder: [config.json](https://huggingface.co/EleutherAI/gpt-j-6B/raw/main/config.json).
3. Download GPT-J 6B under `models/gpt-j-6B`:

```
python download-model.py EleutherAI/gpt-j-6B
```

You don't really need all of GPT-J 6B's files, just the tokenizer files, but you might as well download the whole thing. Those files will be automatically detected when you attempt to load GPT-4chan.

#### Converting to pytorch (optional)

The script `convert-to-torch.py` allows you to convert models to .pt format, which is sometimes 10x faster to load to the GPU:

    python convert-to-torch.py models/model-name

The output model will be saved to `torch-dumps/model-name.pt`. When you load a new model, the web UI first looks for this .pt file; if it is not found, it loads the model as usual from `models/model-name`. 

## Starting the web UI

    conda activate textgen
    python server.py

Then browse to 

`http://localhost:7860/?__theme=dark`



Optionally, you can use the following command-line flags:

| Flag        | Description |
|-------------|-------------|
| `-h`, `--help`  | show this help message and exit |
| `--model MODEL`    | Name of the model to load by default. |
| `--notebook`  | Launch the web UI in notebook mode, where the output is written to the same text box as the input. |
| `--chat`      | Launch the web UI in chat mode.|
| `--cai-chat`  | Launch the web UI in chat mode with a style similar to Character.AI's. If the file `img_bot.png` or `img_bot.jpg` exists in the same folder as server.py, this image will be used as the bot's profile picture. Similarly, `img_me.png` or `img_me.jpg` will be used as your profile picture. |
| `--cpu`       | Use the CPU to generate text.|
| `--load-in-8bit`  | Load the model with 8-bit precision.|
| `--auto-devices` | Automatically split the model across the available GPU(s) and CPU.|
| `--disk` | If the model is too large for your GPU(s) and CPU combined, send the remaining layers to the disk. |
| `--disk-cache-dir DISK_CACHE_DIR` | Directory to save the disk cache to. Defaults to `cache/`. |
| `--gpu-memory GPU_MEMORY` | Maximum GPU memory in GiB to allocate. This is useful if you get out of memory errors while trying to generate text. Must be an integer number. |
| `--cpu-memory CPU_MEMORY`    | Maximum CPU memory in GiB to allocate for offloaded weights. Must be an integer number. Defaults to 99.|
| `--no-stream`   | Don't stream the text output in real time. This improves the text generation performance.|
| `--settings SETTINGS_FILE` | Load the default interface settings from this json file. See `settings-template.json` for an example.|
| `--extensions EXTENSIONS` | The list of extensions to load. If you want to load more than one extension, write the names separated by commas and between quotation marks, "like,this". |
| `--listen`   | Make the web UI reachable from your local network.|
|  `--listen-port LISTEN_PORT` | The listening port that the server will use. |
| `--share`   | Create a public URL. This is useful for running the web UI on Google Colab or similar. |
| `--verbose`   | Print the prompts to the terminal. |

Out of memory errors? [Check this guide](https://github.com/oobabooga/text-generation-webui/wiki/Low-VRAM-guide).

## Presets

Inference settings presets can be created under `presets/` as text files. These files are detected automatically at startup.

By default, 10 presets by NovelAI and KoboldAI are included. These were selected out of a sample of 43 presets after applying a K-Means clustering algorithm and selecting the elements closest to the average of each cluster.

## System requirements

Check the [wiki](https://github.com/oobabooga/text-generation-webui/wiki/System-requirements) for some examples of VRAM and RAM usage in both GPU and CPU mode.

## Contributing

Pull requests, suggestions, and issue reports are welcome.

Before reporting a bug, make sure that you have created a conda environment and installed the dependencies exactly as in the *Installation* section above.

These issues are known:

* 8-bit doesn't work properly on Windows or older GPUs.
* Deepspeed doesn't work properly on Windows.

For these two, please try commenting on an existing issue instead of creating a new one.

## Credits

- NovelAI and KoboldAI presets: https://github.com/KoboldAI/KoboldAI-Client/wiki/Settings-Presets
- Pygmalion preset, code for early stopping in chat mode, code for some of the sliders: https://github.com/PygmalionAI/gradio-ui/
- Verbose preset: Anonymous 4chan user.
- Gradio dropdown menu refresh button: https://github.com/AUTOMATIC1111/stable-diffusion-webui
