"""
Full command verification for the STM32 motor/servo controller.

Tests every command in the firmware protocol:
  wake, sleep, auto, home, motors on, motors off, push, fire, test,
  1,<angle>, 2,<angle>, 3,<angle>

Run from project root:
    venv/bin/python MotorControllerInterface/test_all_commands.py
"""

import sys
import time
import os

sys.path.insert(0, os.path.dirname(__file__))
from motor_controller import MotorController, motor_controller_available, DEFAULT_PORT

PASS = "PASS"
FAIL = "FAIL"

def check(label, result):
    status = PASS if result else FAIL
    print(f"  [{status}] {label}")
    return result

def main():
    if not motor_controller_available(DEFAULT_PORT):
        print(f"STM32 not found on {DEFAULT_PORT}. Check USB connection.")
        sys.exit(1)

    print(f"STM32 found on {DEFAULT_PORT}\n")

    with MotorController() as mc:

        # ── wake ──────────────────────────────────────────────────────────
        print("--- wake ---")
        check("wake (servos on, go to home)", mc.wake())
        time.sleep(1)

        # ── angle commands ────────────────────────────────────────────────
        print("\n--- 1,<angle>  pan servo (0-270) ---")
        check("1,0   pan to 0°",   mc.set_pan(0));   time.sleep(0.6)
        check("1,135 pan to 135°", mc.set_pan(135)); time.sleep(0.6)
        check("1,270 pan to 270°", mc.set_pan(270)); time.sleep(0.6)
        check("1,135 pan back to center", mc.set_pan(135)); time.sleep(0.6)

        print("\n--- 2,<angle>  tilt servo (0-180) ---")
        check("2,0   tilt to 0°",  mc.set_tilt(0));  time.sleep(0.6)
        check("2,90  tilt to 90°", mc.set_tilt(90)); time.sleep(0.6)
        check("2,180 tilt to 180°",mc.set_tilt(180));time.sleep(0.6)
        check("2,90  tilt back to 90°", mc.set_tilt(90)); time.sleep(0.6)

        print("\n--- 3,<angle>  pusher servo (0-180) ---")
        from motor_controller import SERVO_PUSHER
        check("3,0   pusher to 0°",   mc.set_angle(SERVO_PUSHER, 0));   time.sleep(0.6)
        check("3,90  pusher to 90°",  mc.set_angle(SERVO_PUSHER, 90));  time.sleep(0.6)
        check("3,0   pusher back to 0°", mc.set_angle(SERVO_PUSHER, 0)); time.sleep(0.6)

        # ── home ──────────────────────────────────────────────────────────
        print("\n--- home ---")
        check("home (pan returns to 135°)", mc.home())
        time.sleep(1)

        # ── auto scan ─────────────────────────────────────────────────────
        print("\n--- auto ---")
        check("auto (pan sweeps 0-270°)", mc.enable_auto_scan())
        print("  [INFO] watching auto-sweep for 3 seconds...")
        time.sleep(3)

        # Stop auto by returning home
        check("home (stop sweep, return to center)", mc.home())
        time.sleep(1)

        # ── motors ────────────────────────────────────────────────────────
        print("\n--- motors on / motors off ---")
        check("motors on  (spin up flywheels)", mc.motors_on())
        time.sleep(1.5)
        check("motors off (stop flywheels)",    mc.motors_off())
        time.sleep(0.5)

        # ── push ──────────────────────────────────────────────────────────
        print("\n--- push ---")
        print("  [INFO] push moves the pusher servo — no motors, no dart should fly")
        check("push (one dart push cycle, no motors)", mc.push())
        time.sleep(1)

        # ── fire ──────────────────────────────────────────────────────────
        print("\n--- fire ---")
        input("  Press ENTER to fire a dart (motors on + push)... ")
        check("fire (motors on + 50ms spin-up + push)", mc.fire())
        time.sleep(1)

        # ── test sequence ─────────────────────────────────────────────────
        print("\n--- test ---")
        input("  Press ENTER to run the full MCU test sequence (~10s)... ")
        check("test (full automated servo/motor sequence)", mc.test())
        time.sleep(1)

        # ── sleep ─────────────────────────────────────────────────────────
        print("\n--- sleep ---")
        check("sleep (home all servos, motors off, PWM off)", mc.sleep())

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
