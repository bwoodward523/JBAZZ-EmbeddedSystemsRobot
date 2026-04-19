#!/usr/bin/env python3
"""Send ``sleep`` (PWM off, servos homed) and exit. Run: python test_stop.py"""

import argparse
import sys

from motor_controller import (
    DEFAULT_PORT,
    MotorController,
    motor_controller_available,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stop motors: send sleep (homes servos, turns PWM off)."
    )
    parser.add_argument("--port", type=str, default=DEFAULT_PORT)
    args = parser.parse_args()

    if not motor_controller_available(args.port):
        print(f"No device on {args.port}")
        return 1

    with MotorController(port=args.port) as mc:
        if not mc.sleep():
            print("sleep failed")
            return 1
    print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
