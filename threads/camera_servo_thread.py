"""
Camera + servo thread for JBAZZ.

Two internal modes:
  SCANNING  — sweeps the pan servo back and forth looking for a person
  TRACKING  — follows the detected person with pan/tilt

Posts PERSON_DETECTED when a person is found while scanning.
Posts PERSON_LOST when the person disappears for LOST_GRACE consecutive frames,
then internally returns to SCANNING mode (state machine mirrors this via 'rescan').

The thread exits cleanly when stop_event is set (set by JBAZZ on sleep transitions).
On exit the servos are always homed via mc.center() + mc.sleep().
"""

import sys
import os
import time
import threading
from enum import Enum, auto

import cv2

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from AICameraInterface.ai_camera import AICameraFeed, draw_detections, draw_tracked, select_tracked_person
from MotorControllerInterface.motor_controller import MotorController
from events import post_event, EventType
from thread_controls import fire_event


def _display_available() -> bool:
    try:
        cv2.namedWindow("__test__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__test__")
        return True
    except cv2.error:
        return False

# --- Frame geometry ---
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480
FRAME_CX     = FRAME_WIDTH  // 2
FRAME_CY     = FRAME_HEIGHT // 2

# --- Camera FOV (degrees) ---
HFOV = 60.0
VFOV = 45.0

# --- Tracking ---
DEADZONE_PX = 20        # ignore error smaller than this (prevents jitter)
CONFIDENCE  = 0.3       # person detection confidence threshold

# --- Scan sweep ---
SCAN_MIN   = 75         # leftmost pan angle (degrees) — 135° center - 60°
SCAN_MAX   = 195        # rightmost pan angle (degrees) — 135° center + 60°
SCAN_TILT  = 85         # fixed tilt during scan (slightly below center)
SCAN_STEP  = 5          # degrees per sweep step
SCAN_DELAY = 0.12       # seconds between sweep steps

# --- Lost grace period ---
LOST_GRACE = 20         # consecutive empty frames before declaring person lost


class _Mode(Enum):
    SCANNING = auto()
    TRACKING = auto()


def _clamp_pan(angle: float) -> float:
    return max(0.0, min(270.0, angle))


def _clamp_tilt(angle: float) -> float:
    return max(0.0, min(180.0, angle))


def run_camera_servo_thread(stop_event: threading.Event) -> None:
    """
    Main entry point. Pass camera_servo_stop_event from thread_controls.
    Runs until stop_event is set, then homes servos and exits.
    """
    mode          = _Mode.SCANNING
    pan           = 135.0
    tilt          = float(SCAN_TILT)
    direction     = 1           # +1 sweeping right, -1 sweeping left
    tracked_center = None
    tracked_box    = None       # full BoundingBox object used for display
    lost_counter  = 0
    show_display  = _display_available()

    last_pan_cmd  = None        # UART throttle: only send when int value changes
    last_tilt_cmd = None

    def send_pan(mc: MotorController, angle: float) -> None:
        nonlocal last_pan_cmd
        cmd = int(angle)
        if cmd != last_pan_cmd:
            mc.set_pan(cmd)
            last_pan_cmd = cmd

    def send_tilt(mc: MotorController, angle: float) -> None:
        nonlocal last_tilt_cmd
        cmd = int(angle)
        if cmd != last_tilt_cmd:
            mc.set_tilt(cmd)
            last_tilt_cmd = cmd

    try:
        with MotorController() as mc:
            mc.wake()
            send_pan(mc, pan)
            send_tilt(mc, tilt)

            with AICameraFeed(
                width=FRAME_WIDTH,
                height=FRAME_HEIGHT,
                confidence_threshold=CONFIDENCE,
            ) as cam:
                cam.wait_until_ready()

                while not stop_event.is_set():
                    # Fire dart if the state machine requested it
                    if fire_event.is_set():
                        print("[camera_servo] firing dart")
                        mc.fire()
                        fire_event.clear()
                        post_event(EventType.FINISHED_SHOOTING, source="camera_servo_thread")

                    frame, persons = cam.capture_frame_and_persons()

                    if mode == _Mode.SCANNING:
                        if persons:
                            # Person found — switch to tracking
                            mode = _Mode.TRACKING
                            tracked_center = None
                            lost_counter = 0
                            post_event(EventType.PERSON_DETECTED, source="camera_servo_thread")
                        else:
                            # Advance sweep
                            pan += SCAN_STEP * direction
                            if pan >= SCAN_MAX:
                                pan = float(SCAN_MAX)
                                direction = -1
                            elif pan <= SCAN_MIN:
                                pan = float(SCAN_MIN)
                                direction = 1
                            send_pan(mc, pan)
                            time.sleep(SCAN_DELAY)

                    else:  # _Mode.TRACKING
                        tracked = select_tracked_person(
                            persons, tracked_center, (FRAME_CX, FRAME_CY)
                        )

                        if tracked is not None:
                            lost_counter = 0
                            tracked_box    = tracked
                            tracked_center = tracked.center
                            px, py = tracked_center

                            err_x = px - FRAME_CX
                            err_y = py - FRAME_CY

                            if abs(err_x) >= DEADZONE_PX:
                                pan = _clamp_pan(pan - (err_x / FRAME_WIDTH) * HFOV)
                                send_pan(mc, pan)

                            if abs(err_y) >= DEADZONE_PX:
                                tilt = _clamp_tilt(tilt + (err_y / FRAME_HEIGHT) * VFOV)
                                send_tilt(mc, tilt)
                        else:
                            lost_counter += 1
                            if lost_counter >= LOST_GRACE:
                                # Person confirmed lost — return to scanning
                                mode = _Mode.SCANNING
                                tracked_center = None
                                tracked_box    = None
                                lost_counter = 0
                                tilt = float(SCAN_TILT)
                                send_tilt(mc, tilt)
                                post_event(EventType.PERSON_LOST, source="camera_servo_thread")

                    # --- Live display ---
                    if show_display:
                        try:
                            draw_detections(frame, persons, color=(100, 100, 255), thickness=1)
                            draw_tracked(frame, tracked_box, color=(0, 255, 0), thickness=2)
                            # Crosshair at frame center
                            cv2.line(frame, (FRAME_CX - 10, FRAME_CY), (FRAME_CX + 10, FRAME_CY), (0, 255, 255), 1)
                            cv2.line(frame, (FRAME_CX, FRAME_CY - 10), (FRAME_CX, FRAME_CY + 10), (0, 255, 255), 1)
                            # Status overlay: mode + servo angles
                            status = f"{mode.name}  pan={int(pan)}  tilt={int(tilt)}"
                            cv2.putText(frame, status, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
                            cv2.imshow("JBAZZ Camera", frame)
                            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                                show_display = False
                                cv2.destroyAllWindows()
                        except cv2.error:
                            show_display = False

    except Exception as e:
        print(f"[camera_servo] error: {e}")
    finally:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
        # Always home servos on exit regardless of why we stopped
        try:
            with MotorController() as mc:
                mc.center()
                mc.sleep()
        except Exception:
            pass


if __name__ == "__main__":
    # Quick standalone test: run for 30 seconds then stop
    stop = threading.Event()
    t = threading.Thread(target=run_camera_servo_thread, args=(stop,))
    t.start()
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        t.join(timeout=5)
