"""Exercise wake / sleep / auto / angle commands on the STM32 Nucleo."""

import time

from motor_controller import (
    DEFAULT_PORT,
    MotorController,
    motor_controller_available,
)


def main() -> None:
    port = DEFAULT_PORT
    if not motor_controller_available(port):
        print(f"STM32 Nucleo not found on {port}")
        print("Connect USB and check the device path (ls /dev/ttyACM*).")
        return

    print(f"Using {port}.\n")

    with MotorController(port=port) as mc:
        ok = mc.wake()
        print(f"wake       -> {'OK' if ok else 'FAIL'}")

        ok = mc.set_pan(45)
        print(f"1,45 (pan) -> {'OK' if ok else 'FAIL'}")
        time.sleep(0.5)
        ok = mc.set_tilt(135)
        print(f"2,135 tilt -> {'OK' if ok else 'FAIL'}")
        time.sleep(0.5)
        ok = mc.center()
        print(f"center     -> {'OK' if ok else 'FAIL'}")

        ok = mc.enable_auto_scan()
        print(f"auto scan  -> {'OK' if ok else 'FAIL'}")
        time.sleep(2)

        ok = mc.sleep()
        print(f"sleep      -> {'OK' if ok else 'FAIL'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
