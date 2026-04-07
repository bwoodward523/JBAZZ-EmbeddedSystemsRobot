#!/usr/bin/python3
import time
import numpy as np
import PIL.Image as Image
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from data_queues import display_queue

width = 32
height = 32
emotions = ["happiness.png","surprise.png","fear.png","disgust.png","sadness.png","anger.png"]

geometry = piomatter.Geometry(
    width=width,
    height=height,
    n_addr_lines=4,
    rotation=piomatter.Orientation.Normal
)

canvas = Image.new("RGB", (width, height))
framebuffer = np.asarray(canvas, dtype=np.uint8) + 0

matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.Active3,
    framebuffer=framebuffer,
    geometry=geometry
)

# with Image.open(gif_file) as img:
def show_emotions_thread():
    img = np.asarray(Image.open(f"led_display/assets/base_emotions/happiness.png").convert("RGB"))
    framebuffer[:] = img[:, :, :]

    matrix.show()
    time.sleep(1)
    while True:
        emotion = display_queue.get()
        # print(f"{emotion} hahahahahahahaha")

        #Implement a function to try its best to turn non deterministic result into safe one from emotion. ie getting "anger" instead of anger. 
        #Temp half-fix
        emotion = emotion.replace('"', "")
        emotion = emotion.replace(" ", "")
        try:
            img = np.asarray(Image.open(f"led_display/assets/base_emotions/{emotion}.png").convert("RGB"))
            framebuffer[:] = img[:, :, :]

            matrix.show()
        except Exception as e:
            print(f"Failed to set display Error: {e}")
        time.sleep(1)
        # print("?")
        # for i in range(len(emotions)):
        #     img = np.asarray(Image.open(f"led_display/assets/base_emotions/{emotions[i]}").convert("RGB"))
        #     framebuffer[:] = img[:, :, :]

        #     matrix.show()
        #     time.sleep(1)
