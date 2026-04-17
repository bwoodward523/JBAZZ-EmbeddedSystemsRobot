"""
STM32 Nucleo servo/motor control over UART (text commands).

The Nucleo appears as /dev/ttyACM0 when connected to the Raspberry Pi via USB.

Firmware protocol (line-terminated with \\n):
  wake              — enable servos, go to home positions; replies "Awake"
  sleep             — home all servos, motors off, PWM off; replies "Sleeping"
  auto              — pan sweeps 0-270° MCU-controlled; replies "Auto scan on"
  home              — pan returns to center (135°); replies "OK"
  motors on         — spin up flywheels; replies "OK"
  motors off        — stop flywheels; replies "OK"
  push              — one dart push cycle; replies "OK"
  fire              — motors on + push (50 ms MCU-timed spin-up); replies "OK"
  test              — run full servo/motor test sequence; replies "OK"
  1,<angle>         — pan servo, 0-270°; replies OK or ERR
  2,<angle>         — tilt servo, 0-180°; replies OK or ERR
  3,<angle>         — pusher servo, 0-180° (prefer `fire` over direct control)

Character echo + prompts still appear on the wire; helpers wait for keywords.

Requires:
  pip install pyserial
"""

from __future__ import annotations

import time
from typing import Optional

import serial


DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 2.0

SERVO_PAN    = 1
SERVO_TILT   = 2
SERVO_PUSHER = 3

MIN_ANGLE        = 0
MAX_ANGLE_PAN    = 270   # pan servo physical range
MAX_ANGLE_TILT   = 180   # tilt servo physical range
MAX_ANGLE_PUSHER = 180   # pusher servo physical range (use fire, not direct)

_SERVO_MAX = {
    SERVO_PAN:    MAX_ANGLE_PAN,
    SERVO_TILT:   MAX_ANGLE_TILT,
    SERVO_PUSHER: MAX_ANGLE_PUSHER,
}


class MotorController:
    """
    Usage:
        with MotorController() as mc:
            mc.wake()
            mc.set_angle(SERVO_PAN, 135)    # pan center on 0-270° range
            mc.set_angle(SERVO_TILT, 90)    # tilt center
            mc.fire()                        # fire one dart
            mc.enable_auto_scan()
            mc.sleep()
    """

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baudrate: int = DEFAULT_BAUD,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: Optional[serial.Serial] = None

    def __enter__(self) -> MotorController:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout,
        )
        time.sleep(2)
        self._serial.reset_input_buffer()

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def _send_line(self, line: str) -> None:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("UART connection is not open")
        for char in line:
            self._serial.write(char.encode("ascii"))
            self._serial.flush()
            time.sleep(0.01)       # 10ms between chars so STM32 can process each one
        self._serial.write(b"\r")
        self._serial.flush()

    def _read_until(
        self,
        *needles: str,
        timeout: Optional[float] = None,
    ) -> str:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("UART connection is not open")
        limit = timeout if timeout is not None else self._timeout
        deadline = time.monotonic() + limit
        buf = bytearray()
        while time.monotonic() < deadline:
            n = self._serial.in_waiting
            if n:
                buf.extend(self._serial.read(n))
                text = buf.decode("ascii", errors="replace")
                for needle in needles:
                    if needle in text:
                        return text
            else:
                time.sleep(0.01)
        return buf.decode("ascii", errors="replace")

    def wake(self, retries: int = 5, retry_delay: float = 1.0) -> bool:
        for attempt in range(1, retries + 1):
            self._serial.reset_input_buffer()
            self._send_line("wake")
            text = self._read_until("Awake", "Unknown", timeout=self._timeout)
            if "Awake" in text:
                return True
            print(f"[MotorController] wake attempt {attempt}/{retries} failed, retrying...")
            time.sleep(retry_delay)
        return False

    def sleep(self) -> bool:
        self._serial.reset_input_buffer()
        self._send_line("sleep")
        text = self._read_until("Sleeping", "Unknown", timeout=self._timeout)
        return "Sleeping" in text

    def enable_auto_scan(self) -> bool:
        """Re-enable pan sweep on the MCU (command ``auto``)."""
        self._serial.reset_input_buffer()
        self._send_line("auto")
        text = self._read_until("Auto scan:", "ERR", timeout=self._timeout)
        return "Auto scan:" in text

    def set_angle(self, servo_id: int, angle: int, speed: Optional[int] = None) -> bool:
        """
        Send ``<servo_id>,<angle>`` or ``<servo_id>,<angle>,<speed>``.
        Pan (1): 0-270°.  Tilt (2): 0-180°.  Pusher (3): 0-180°.
        speed: pan slew rate in deg/sec (pan only).
               Omit for firmware default (90 deg/sec).
               e.g. speed=45 for cinematic, speed=270 for near-instant.
        Returns True if firmware answers with OK.
        """
        if servo_id not in _SERVO_MAX:
            raise ValueError(
                f"Invalid servo_id {servo_id}; use SERVO_PAN, SERVO_TILT, or SERVO_PUSHER"
            )
        angle = max(MIN_ANGLE, min(_SERVO_MAX[servo_id], int(angle)))
        if speed is not None and servo_id == SERVO_PAN:
            cmd = f"{servo_id},{angle},{int(speed)}"
        else:
            cmd = f"{servo_id},{angle}"
        self._serial.reset_input_buffer()
        self._send_line(cmd)
        text = self._read_until("OK", "ERR", timeout=self._timeout)
        return "OK" in text and "ERR" not in text

    def set_pan(self, angle: int, speed: Optional[int] = None) -> bool:
        return self.set_angle(SERVO_PAN, angle, speed=speed)

    def set_tilt(self, angle: int) -> bool:
        return self.set_angle(SERVO_TILT, angle)

    def center(self) -> bool:
        """Move pan to 135° (center of 0-270° range) and tilt to 90°."""
        return self.set_pan(135) and self.set_tilt(90)

    def home(self) -> bool:
        """Pan returns to center (135°) via ``home`` command."""
        self._serial.reset_input_buffer()
        self._send_line("home")
        text = self._read_until("Pan homed", "ERR", timeout=self._timeout)
        return "Pan homed" in text

    def motors_on(self) -> bool:
        """Spin up flywheels."""
        self._serial.reset_input_buffer()
        self._send_line("motors on")
        text = self._read_until("Motors ON", "ERR", timeout=self._timeout)
        print(f"[DEBUG motors_on] raw: {repr(text)}")
        return "Motors ON" in text

    def motors_off(self) -> bool:
        """Stop flywheels."""
        self._serial.reset_input_buffer()
        self._send_line("motors off")
        text = self._read_until("Motors OFF", "ERR", timeout=self._timeout)
        print(f"[DEBUG motors_off] raw: {repr(text)}")
        return "Motors OFF" in text

    def push(self) -> bool:
        """Execute one dart push cycle."""
        self._serial.reset_input_buffer()
        self._send_line("push")
        text = self._read_until("Push", "ERR", timeout=self._timeout)
        return "Push" in text

    def fire(self) -> bool:
        """Fire one dart: motors on, 0.5s spin-up, pusher 0->180, 0.5s travel, pusher back, 0.5s, motors off."""
        if not self.motors_on():
            return False
        time.sleep(2)                          # spin-up
        if not self.set_angle(SERVO_PUSHER, 0):
            return False
        time.sleep(2)                          # wait for servo to reach 0
        if not self.set_angle(SERVO_PUSHER, 180):
            return False
        time.sleep(0.5)
        return self.motors_off()

    def test(self) -> bool:
        """Run full servo/motor test sequence on MCU."""
        self._serial.reset_input_buffer()
        self._send_line("test")
        text = self._read_until("TEST:", "ERR", timeout=10.0)
        return "TEST:" in text


def motor_controller_available(port: str = DEFAULT_PORT) -> bool:
    try:
        with serial.Serial(port, DEFAULT_BAUD, timeout=0.5) as s:
            return s.is_open
    except (serial.SerialException, OSError):
        return False
