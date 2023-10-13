# ComfyUI SDXL txt2img Cog model

This is an implementation of the ComfyUI text2img workflow as a Cog model. [Cog packages machine learning models as standard containers.](https://github.com/replicate/cog)

First, download the pre-trained weights:

    cog run script/download-weights

Then, you can run predictions:

    cog predict -i input_prompt="beautiful scenery nature glass bottle landscape, pink galaxy bottle"

The workflow used for this repo is found under:

    custom_workflows/sdxl_txt2img.json

## Example:

"beautiful scenery nature glass bottle landscape, pink galaxy bottle"

![alt text](output.png)
