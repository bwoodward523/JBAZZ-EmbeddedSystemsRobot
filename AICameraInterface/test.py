#!/usr/bin/env python3
"""
Quick test: capture one frame from the AI camera and show person detections.
Run on the Pi: python3 test.py
"""

import sys


def main():
    from ai_camera import AICameraFeed, ai_camera_available, draw_detections

    if not ai_camera_available():
        print("AI camera (IMX500) not available. Install: sudo apt install -y python3-picamera2 imx500-models")
        return 1

    print("Starting AI camera...")
    with AICameraFeed(width=640, height=480, confidence_threshold=0.5) as cam:
        frame, persons = cam.capture_frame_and_persons()
    print(f"Frame shape: {frame.shape}, persons detected: {len(persons)}")

    try:
        import cv2
        draw_detections(frame, persons, color=(0, 255, 0), thickness=2)
        cv2.imwrite("/tmp/person_test.jpg", frame)
        print("Saved /tmp/person_test.jpg")
    except Exception as e:
        print("Could not save image:", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
