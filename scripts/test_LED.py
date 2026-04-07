#!/usr/bin/python3
# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Display a simple test pattern of 3 shapes on a single 32x32 matrix panel.
"""

import numpy as np
from PIL import Image, ImageDraw
import adafruit_blinka_raspberry_pi5_piomatter as piomatter

# --- Configuration Changes ---
width = 32
height = 32

# n_addr_lines is 4 for 32x32 (1/16 scan)
geometry = piomatter.Geometry(width=width, height=height, n_addr_lines=4,
                              rotation=piomatter.Orientation.Normal)

canvas = Image.new('RGB', (width, height), (255, 255, 255))
draw = ImageDraw.Draw(canvas)

framebuffer = np.asarray(canvas) + 0  
matrix = piomatter.PioMatter(colorspace=piomatter.Colorspace.RGB888Packed,
                             pinout=piomatter.Pinout.Active3,
                             framebuffer=framebuffer,
                             geometry=geometry)

# Drawing shapes (adjusted coordinates to fit 32x32 better)
draw.rectangle((2, 2, 10, 10), fill=0x008800)      # Green Square
draw.circle((20, 8), 10, fill=0x880000)             # Red Circle
draw.polygon([(10, 20), (18, 28), (2, 28)], fill=0x000088) # Blue Triangle

framebuffer[:] = np.asarray(canvas)
matrix.show()

input("Press enter to exit")
