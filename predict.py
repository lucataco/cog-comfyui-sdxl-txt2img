import subprocess
import threading
import time
from cog import BasePredictor, Input, Path
# from typing import List
import os
import torch
import shutil
import uuid
import json
import urllib
import websocket
from PIL import Image
from urllib.error import URLError
import random


class Predictor(BasePredictor):
    def setup(self):
        # start server
        self.server_address = "127.0.0.1:8188"
        self.start_server()

    def start_server(self):
        server_thread = threading.Thread(target=self.run_server)
        server_thread.start()

        while not self.is_server_running():
            time.sleep(1)  # Wait for 1 second before checking again

        print("Server is up and running!")

    def run_server(self):
        command = "python ./ComfyUI/main.py"
        server_process = subprocess.Popen(command, shell=True)
        server_process.wait()

    # hacky solution, will fix later
    def is_server_running(self):
        try:
            with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, "123")) as response:
                return response.status == 200
        except URLError:
            return False
    
    def queue_prompt(self, prompt, client_id):
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req =  urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        print(folder_type)
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def get_images(self, ws, prompt, client_id):
        prompt_id = self.queue_prompt(prompt, client_id)['prompt_id']
        output_images = {}
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break #Execution is done
            else:
                continue #previews are binary data

        history = self.get_history(prompt_id)[prompt_id]
        for o in history['outputs']:
            for node_id in history['outputs']:
                node_output = history['outputs'][node_id]
                print("node output: ", node_output)

                if 'images' in node_output:
                    images_output = []
                    for image in node_output['images']:
                        image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                        images_output.append(image_data)
                output_images[node_id] = images_output

        return output_images

    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())
    
    # TODO: add dynamic fields based on the workflow selected
    def predict(
        self,
        input_prompt: str = Input(description="Prompt", default="beautiful scenery nature glass bottle landscape, purple galaxy bottle"),
        negative_prompt: str = Input(description="Negative Prompt", default="text, watermark, ugly, blurry"),
        steps: int = Input(
            description="Steps",
            default=30
        ),
        seed: int = Input(description="Sampling seed, leave Empty for Random", default=None),
    ) -> Path:
        """Run a single prediction on the model"""
        if seed is None:
            seed = int.from_bytes(os.urandom(3), "big")
        print(f"Using seed: {seed}")
        generator = torch.Generator("cuda").manual_seed(seed)

        # queue prompt
        img_output_path = self.get_workflow_output(
            input_prompt = input_prompt,
            negative_prompt = negative_prompt,
            steps = steps,
            seed = seed
        )
        return Path(img_output_path)


    def get_workflow_output(self, input_prompt, negative_prompt, steps, seed):
        # load config
        prompt = None
        workflow_config = "./custom_workflows/sdxl_txt2img.json"
        with open(workflow_config, 'r') as file:
            prompt = json.load(file)

        if not prompt:
            raise Exception('no workflow config found')

        # set input variables
        prompt["6"]["inputs"]["text"] = input_prompt
        prompt["7"]["inputs"]["text"] = negative_prompt

        prompt["3"]["inputs"]["seed"] = seed
        prompt["3"]["inputs"]["steps"] = steps

        # start the process
        client_id = str(uuid.uuid4())
        ws = websocket.WebSocket()
        ws.connect("ws://{}/ws?clientId={}".format(self.server_address, client_id))
        images = self.get_images(ws, prompt, client_id)

        for node_id in images:
            for image_data in images[node_id]:
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(image_data))
                image.save("out-"+node_id+".png")
                return Path("out-"+node_id+".png")
