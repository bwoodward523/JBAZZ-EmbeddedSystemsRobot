#!/usr/bin/env python3
"""Send the MCU pan-scan command (``auto``) and exit. Run from this directory: python test_scan.py"""

import argparse
import sys

from motor_controller import (
    DEFAULT_PORT,
    MotorController,
    motor_controller_available,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wake Nucleo (optional) and start pan scan (auto).")
    parser.add_argument("--port", type=str, default=DEFAULT_PORT)
    parser.add_argument(
        "--no-wake",
        action="store_true",
        help="Do not send wake; only send auto (use if board is already awake).",
    )
    args = parser.parse_args()

    if not motor_controller_available(args.port):
        print(f"No device on {args.port}")
        return 1

    with MotorController(port=args.port) as mc:
        if not args.no_wake and not mc.wake():
            print("wake failed")
            return 1
        if not mc.enable_auto_scan():
            print("scan (auto) failed")
            return 1
    print("scan started")
    return 0


if __name__ == "__main__":
    sys.exit(main())
