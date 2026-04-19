#!/usr/bin/env python3
"""
Raspberry Pi AI camera person tracking application.
Person detection runs on the AI camera (IMX500); no host-side model.
"""

from __future__ import annotations

import argparse
import signal
import sys
from typing import Tuple

import cv2

from ai_camera import (
    AICameraFeed,
    BoundingBox,
    draw_detections,
    draw_tracked,
    select_tracked_person,
)


def _display_available() -> bool:
    """True if OpenCV was built with GUI support (imshow works)."""
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
    confidence: float = 0.5,
) -> None:
    frame_center: Tuple[int, int] = (width // 2, height // 2)
    tracked: BoundingBox | None = None
    shutdown = False

    if not headless and not _display_available():
        print("Note: OpenCV has no GUI support (e.g. opencv-python-headless). Running headless. Use --headless to silence.")
        headless = True

    def on_signal(*_args: object) -> None:
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    with AICameraFeed(width=width, height=height, confidence_threshold=confidence) as cam:
        for frame, person_boxes in cam.frames():
            if shutdown:
                break
            previous_center = tracked.center if tracked is not None else None
            tracked = select_tracked_person(person_boxes, previous_center, frame_center)
            if show_all:
                draw_detections(frame, person_boxes, color=(100, 100, 255), thickness=1)
            draw_tracked(frame, tracked, color=(0, 255, 0), thickness=2)
            if not headless:
                try:
                    cv2.imshow("Person tracker", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q") or key == 27:
                        break
                except cv2.error:
                    headless = True

    if not headless:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Person tracking with Raspberry Pi AI camera (on-camera inference only)")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    parser.add_argument("--show-all", action="store_true", help="Draw all detections, not just tracked")
    parser.add_argument("--headless", action="store_true", help="No GUI; run for integration (e.g. servos)")
    parser.add_argument("--confidence", type=float, default=0.5, help="Detection confidence threshold (0–1)")
    args = parser.parse_args()
    run(
        width=args.width,
        height=args.height,
        show_all=args.show_all,
        headless=args.headless,
        confidence=args.confidence,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
