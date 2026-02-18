"""Quick test for the STM32 Nucleo servo motor controller."""

import time
from motor_controller import (
    MotorController,
    motor_controller_available,
    DEFAULT_PORT,
)


def main() -> None:
    port = DEFAULT_PORT
    if not motor_controller_available(port):
        print(f"STM32 Nucleo not found on {port}")
        print("Make sure the board is connected via USB and the port is correct.")
        return

    print(f"STM32 Nucleo found on {port}. Centering servos...")
    with MotorController(port=port) as mc:
        mc.center()
        print("Servos centered to 90 degrees.")

        # Sweep pan servo
        print("\nSweeping pan servo:")
        for angle in range(0, 181, 30):
            ok = mc.set_pan(angle)
            print(f"  Pan -> {angle}°  {'OK' if ok else 'FAIL'}")
            time.sleep(0.5)

        # Sweep tilt servo
        print("\nSweeping tilt servo:")
        for angle in range(0, 181, 30):
            ok = mc.set_tilt(angle)
            print(f"  Tilt -> {angle}°  {'OK' if ok else 'FAIL'}")
            time.sleep(0.5)

        mc.center()
        print("\nServos re-centered. Done.")


if __name__ == "__main__":
    main()
