"""
Interface test – AI Camera + Motor Controller.

Uses the AI Camera to detect a person and prints the servo commands
that the MotorController *would* send to keep the person centered
in the frame.  No STM32 connection required; this is a dry-run that
logs everything to the console.

Run from the project root:
    python -m MotorControllerInterface.interface_test
  or:
    cd MotorControllerInterface && python interface_test.py
"""

from __future__ import annotations

import sys
import os
import time

# Allow imports from sibling packages when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from AICameraInterface.ai_camera import (
    AICameraFeed,
    ai_camera_available,
    select_tracked_person,
    BoundingBox,
)
from MotorControllerInterface.motor_controller import (
    SERVO_PAN,
    SERVO_TILT,
    MIN_ANGLE,
    MAX_ANGLE,
)

# -- tuning constants -----------------------------------------------------

FRAME_W = 640
FRAME_H = 480

# Approximate camera field-of-view (degrees)
HFOV = 60.0
VFOV = 45.0

# Degrees per pixel
DEG_PER_PX_X = HFOV / FRAME_W
DEG_PER_PX_Y = VFOV / FRAME_H

# Ignore errors smaller than this (pixels) to avoid jitter
DEADZONE_PX = 20


def clamp_angle(angle: float) -> int:
    """Clamp a float angle to the valid servo range and round to int."""
    return max(MIN_ANGLE, min(MAX_ANGLE, int(round(angle))))


def main() -> None:
    if not ai_camera_available():
        print("AI Camera (IMX500) is not available.")
        print("Install: sudo apt install -y python3-picamera2 imx500-models")
        return

    frame_cx = FRAME_W // 2
    frame_cy = FRAME_H // 2

    # Start both servos at center
    pan_angle = 90.0
    tilt_angle = 90.0
    prev_center = None

    print("=" * 60)
    print("  Interface Test: AI Camera  ->  Motor Controller (dry run)")
    print("=" * 60)
    print(f"  Frame size   : {FRAME_W}x{FRAME_H}")
    print(f"  Camera FoV   : {HFOV}° x {VFOV}°")
    print(f"  Dead-zone    : {DEADZONE_PX} px")
    print(f"  Starting pose: pan={int(pan_angle)}°  tilt={int(tilt_angle)}°")
    print("=" * 60)
    print("Press Ctrl+C to stop.\n")

    with AICameraFeed(width=FRAME_W, height=FRAME_H) as cam:
        for frame, persons in cam.frames():
            tracked = select_tracked_person(
                persons, prev_center, (frame_cx, frame_cy)
            )

            if tracked is None:
                print("[no person detected]")
                prev_center = None
                time.sleep(0.1)
                continue

            prev_center = tracked.center
            px, py = tracked.center

            # Pixel error from frame center (positive = right / down)
            err_x = px - frame_cx
            err_y = py - frame_cy

            in_deadzone_x = abs(err_x) < DEADZONE_PX
            in_deadzone_y = abs(err_y) < DEADZONE_PX

            # Convert pixel error to degree adjustment
            delta_pan = err_x * DEG_PER_PX_X
            delta_tilt = err_y * DEG_PER_PX_Y

            # Apply adjustments (only outside deadzone)
            if not in_deadzone_x:
                pan_angle = clamp_angle(pan_angle + delta_pan)
            if not in_deadzone_y:
                tilt_angle = clamp_angle(tilt_angle + delta_tilt)

            pan_cmd = clamp_angle(pan_angle)
            tilt_cmd = clamp_angle(tilt_angle)

            # Build human-readable direction strings
            h_dir = "RIGHT" if err_x > 0 else "LEFT " if err_x < 0 else "CENTER"
            v_dir = "DOWN " if err_y > 0 else "UP   " if err_y < 0 else "CENTER"

            print(
                f"Person at ({px:4d},{py:4d})  "
                f"err=({err_x:+4d},{err_y:+4d})px  "
                f"[{h_dir} {v_dir}]  "
                f"-->  mc.set_angle({SERVO_PAN}, {pan_cmd:3d})  "
                f"mc.set_angle({SERVO_TILT}, {tilt_cmd:3d})"
            )

            time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
