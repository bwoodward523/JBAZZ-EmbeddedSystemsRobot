#!/usr/bin/env python3
"""
Interface test – AI Camera person tracking + Motor Controller servo output.

Based on tracker_app.py (which displays correctly), with motor controller
pan/tilt logic layered on top.

Run from AICameraInterface (same as tracker_app.py):
    cd AICameraInterface && python ../MotorControllerInterface/interface_test.py

Or from project root:
    PYTHONPATH=AICameraInterface python MotorControllerInterface/interface_test.py
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from typing import Tuple

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "AICameraInterface"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_camera import (
    AICameraFeed,
    BoundingBox,
    draw_detections,
    draw_tracked,
    select_tracked_person,
)
from MotorControllerInterface.motor_controller import (
    DEFAULT_PORT,
    MAX_ANGLE,
    MIN_ANGLE,
    SERVO_PAN,
    SERVO_TILT,
    MotorController,
    motor_controller_available,
)

HFOV = 60.0
VFOV = 45.0
DEADZONE_PX = 20


def clamp_angle(angle: float) -> int:
    return max(MIN_ANGLE, min(MAX_ANGLE, int(round(angle))))


def _display_available() -> bool:
    try:
        cv2.namedWindow("__test__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__test__")
        return True
    except cv2.error:
        return False


def run(
    width: int = 640,
    height: int = 480,
    show_all: bool = False,
    headless: bool = False,
    confidence: float = 0.3,
    dry_run: bool = False,
    port: str = DEFAULT_PORT,
) -> None:
    frame_center: Tuple[int, int] = (width // 2, height // 2)
    frame_cx, frame_cy = frame_center
    deg_per_px_x = HFOV / width
    deg_per_px_y = VFOV / height

    tracked: BoundingBox | None = None
    shutdown = False
    pan_angle = 90.0
    tilt_angle = 90.0

    if not headless and not _display_available():
        print("OpenCV has no GUI support. Running headless.")
        headless = True

    def on_signal(*_args: object) -> None:
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    # --- Motor controller setup ---
    mc: MotorController | None = None
    motor_ok = False

    if not dry_run and motor_controller_available(port):
        try:
            mc = MotorController(port=port)
            mc.open()
            motor_ok = mc.wake()
            if motor_ok:
                print(f"STM32 on {port}: connected and awake.")
            else:
                print(f"STM32 on {port}: wake failed; servo commands will only print.")
                mc.close()
                mc = None
        except Exception as e:
            print(f"STM32 UART error: {e}. Servo commands will only print.")
            mc = None
    elif not dry_run:
        print(f"No STM32 on {port}. Servo commands will only print.")

    last_pan_cmd: int | None = None
    last_tilt_cmd: int | None = None

    print(f"Camera {width}x{height}, confidence={confidence}, FoV={HFOV}x{VFOV}")
    print("Press q or Ctrl+C to stop.\n")

    with AICameraFeed(width=width, height=height, confidence_threshold=confidence) as cam:
        for frame, person_boxes in cam.frames():
            if shutdown:
                break

            previous_center = tracked.center if tracked is not None else None
            tracked = select_tracked_person(person_boxes, previous_center, frame_center)

            if show_all:
                draw_detections(frame, person_boxes, color=(100, 100, 255), thickness=1)
            draw_tracked(frame, tracked, color=(0, 255, 0), thickness=2)

            if tracked is not None:
                px, py = tracked.center
                err_x = px - frame_cx
                err_y = py - frame_cy

                delta_pan = -err_x * deg_per_px_x
                delta_tilt = err_y * deg_per_px_y

                if abs(err_x) >= DEADZONE_PX:
                    pan_angle = clamp_angle(pan_angle + delta_pan)
                if abs(err_y) >= DEADZONE_PX:
                    tilt_angle = clamp_angle(tilt_angle + delta_tilt)

                pan_cmd = clamp_angle(pan_angle)
                tilt_cmd = clamp_angle(tilt_angle)

                h_dir = "RIGHT" if err_x > 0 else "LEFT " if err_x < 0 else "CTR  "
                v_dir = "DOWN " if err_y > 0 else "UP   " if err_y < 0 else "CTR  "

                print(
                    f"Person ({px:4d},{py:4d})  "
                    f"err=({err_x:+4d},{err_y:+4d})  "
                    f"[{h_dir} {v_dir}]  "
                    f"pan={pan_cmd:3d}  tilt={tilt_cmd:3d}"
                )

                if motor_ok and mc is not None:
                    if pan_cmd != last_pan_cmd:
                        mc.set_pan(pan_cmd)
                        last_pan_cmd = pan_cmd
                    if tilt_cmd != last_tilt_cmd:
                        mc.set_tilt(tilt_cmd)
                        last_tilt_cmd = tilt_cmd

                if not headless:
                    cv2.line(frame, (frame_cx, frame_cy), (px, py), (200, 200, 0), 1)
                    info = f"pan={pan_cmd} tilt={tilt_cmd}  err=({err_x:+d},{err_y:+d})"
                    cv2.putText(frame, info, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            if not headless:
                try:
                    cv2.imshow("Person tracker + servo", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q") or key == 27:
                        break
                except cv2.error:
                    headless = True

    # Cleanup
    if mc is not None and mc.is_open:
        try:
            mc.sleep()
        except Exception:
            pass
        mc.close()

    if not headless:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AI camera person tracking with motor controller output."
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--show-all", action="store_true", help="Draw all detections")
    parser.add_argument("--headless", action="store_true", help="No GUI window")
    parser.add_argument("--confidence", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true", help="Skip STM32 UART")
    parser.add_argument("--port", type=str, default=DEFAULT_PORT)
    args = parser.parse_args()
    run(
        width=args.width,
        height=args.height,
        show_all=args.show_all,
        headless=args.headless,
        confidence=args.confidence,
        dry_run=args.dry_run,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
