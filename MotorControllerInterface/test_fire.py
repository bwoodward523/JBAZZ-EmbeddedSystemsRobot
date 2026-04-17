"""
Fire motion test.

Sequence:
  1. wake       — enable servos, go to home
  2. motors on  — spin up flywheels
  3. wait 0.5s  — let motors spin up
  4. 3,180      — pusher servo forward
  5. wait 0.5s  — let servo reach 180 before reversing
  6. 3,0        — pusher servo back
  7. wait 0.5s
  8. motors off — stop flywheels

Run from project root:
    venv/bin/python MotorControllerInterface/test_fire.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from motor_controller import MotorController, motor_controller_available, DEFAULT_PORT, SERVO_PUSHER


def send_and_print(label, mc, fn):
    """Call fn(), print label and PASS/FAIL, return result."""
    ok = fn()
    print(f"  {label:<25} -> {'OK' if ok else 'FAIL'}")
    return ok


def main():
    if not motor_controller_available(DEFAULT_PORT):
        print(f"STM32 not found on {DEFAULT_PORT}. Check USB connection.")
        sys.exit(1)

    print(f"STM32 found on {DEFAULT_PORT}\n")

    with MotorController() as mc:

        # 1. Wake
        print("Waking...")
        ok = mc.wake()
        print(f"  wake                      -> {'OK' if ok else 'FAIL'}")
        if not ok:
            print("Wake failed, aborting.")
            return
        time.sleep(0.3)

        # 2. Motors on
        print("Motors on...")
        ok = mc.motors_on()
        print(f"  motors on                 -> {'OK' if ok else 'FAIL'}")

        # 3. Wait for spin-up
        print("Waiting 2s for spin-up...")
        time.sleep(2)

        # 4. Pusher to 0 (start position)
        print("Pusher to start (3,0)...")
        ok = mc.set_angle(SERVO_PUSHER, 0)
        print(f"  3,0                       -> {'OK' if ok else 'FAIL'}")

        # 5. Wait for servo to reach 0
        print("Waiting 2s for servo travel...")
        time.sleep(2)

        # 6. Pusher forward
        print("Pusher forward (3,180)...")
        ok = mc.set_angle(SERVO_PUSHER, 180)
        print(f"  3,180                     -> {'OK' if ok else 'FAIL'}")

        # 7. Wait
        print("Waiting 0.5s...")
        time.sleep(0.5)

        # 8. Motors off
        print("Motors off...")
        ok = mc.motors_off()
        print(f"  motors off                -> {'OK' if ok else 'FAIL'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
