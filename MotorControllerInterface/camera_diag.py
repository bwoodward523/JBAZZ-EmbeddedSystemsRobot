"""Quick diagnostic: what is the AI camera actually producing?"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from AICameraInterface.ai_camera import AICameraFeed, ai_camera_available

if not ai_camera_available():
    print("AI Camera not available.")
    sys.exit(1)

print("Opening camera...")
with AICameraFeed(width=640, height=480, confidence_threshold=0.3) as cam:
    print("Camera started. Capturing 10 frames over ~5 seconds...\n")
    for i in range(10):
        frame, persons = cam.capture_frame_and_persons()
        print(
            f"  Frame {i+1:2d}: shape={frame.shape}  dtype={frame.dtype}  "
            f"min={frame.min()}  max={frame.max()}  mean={frame.mean():.1f}  "
            f"persons={len(persons)}"
        )
        if i == 9:
            try:
                import cv2
                path = "/tmp/camera_diag.jpg"
                cv2.imwrite(path, frame)
                print(f"\n  Last frame saved to {path}")
            except Exception as e:
                print(f"\n  Could not save frame: {e}")
            print(f"\n  First 5 pixel values (row 240): {frame[240, :5]}")
        time.sleep(0.5)

print("\nDone.")
