#!/usr/bin/python3
import time
import numpy as np
import PIL.Image as Image
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

width = 32
height = 32
gif_file = "assets/b2.gif"
# gif_file = "assets/Eye.png"
# gif_file = "assets/rainbow.gif"

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

with Image.open(gif_file) as img:
    print(f"frames: {img.n_frames}")
    
    while True:
        for i in range(img.n_frames):
            img.seek(i)

            # Convert frame → RGB (critical for GIFs)
            frame = img.convert("RGB")

            # Scale to matrix resolution
            frame = frame.resize((width, height), Image.NEAREST)

            # Copy into framebuffer
            framebuffer[:] = np.asarray(frame, dtype=np.uint8)

            matrix.show()
            time.sleep(0.1)
