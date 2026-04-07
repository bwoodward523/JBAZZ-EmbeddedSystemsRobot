"""
STM32 Nucleo servo control over UART (text commands).

The Nucleo appears as /dev/ttyACM0 when connected to the Raspberry Pi via USB.

Firmware protocol (line-terminated with \\n), extended firmware:
  wake           - PWM on; pan scan may run
  sleep          - home both servos, PWM off
  auto           - turn pan scan back on (after manual angles)
  <id>,<angle>   - e.g. 1,90  (servo 1 = pan / TIM3_CH2, 2 = tilt / TIM3_CH1)
                   angle 0-180 maps to 1000-2000 us. Replies OK or ERR.

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

SERVO_PAN = 1
SERVO_TILT = 2
MIN_ANGLE = 0
MAX_ANGLE = 180


class MotorController:
    """
    Usage:
        with MotorController() as mc:
            mc.wake()
            mc.set_angle(SERVO_PAN, 90)
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
        self._serial.write(f"{line}\n".encode("ascii"))
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

    def wake(self) -> bool:
        self._serial.reset_input_buffer()
        self._send_line("wake")
        text = self._read_until("Awake", "Unknown", timeout=self._timeout)
        return "Awake" in text

    def sleep(self) -> bool:
        self._serial.reset_input_buffer()
        self._send_line("sleep")
        text = self._read_until("Sleeping", "Unknown", timeout=self._timeout)
        return "Sleeping" in text

    def enable_auto_scan(self) -> bool:
        """Re-enable pan sweep on the MCU (command ``auto``)."""
        self._serial.reset_input_buffer()
        self._send_line("auto")
        text = self._read_until("Auto scan on", "ERR", timeout=self._timeout)
        return "Auto scan on" in text

    def set_angle(self, servo_id: int, angle: int) -> bool:
        """
        Send ``<servo_id>,<angle>``. Returns True if firmware answers with OK.
        """
        if servo_id not in (SERVO_PAN, SERVO_TILT):
            raise ValueError(f"Invalid servo_id {servo_id}; use {SERVO_PAN} or {SERVO_TILT}")
        angle = max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))
        self._serial.reset_input_buffer()
        self._send_line(f"{servo_id},{angle}")
        text = self._read_until("OK", "ERR", timeout=self._timeout)
        return "OK" in text and "ERR" not in text

    def set_pan(self, angle: int) -> bool:
        return self.set_angle(SERVO_PAN, angle)

    def set_tilt(self, angle: int) -> bool:
        return self.set_angle(SERVO_TILT, angle)

    def center(self) -> bool:
        return self.set_pan(90) and self.set_tilt(90)


def motor_controller_available(port: str = DEFAULT_PORT) -> bool:
    try:
        with serial.Serial(port, DEFAULT_BAUD, timeout=0.5) as s:
            return s.is_open
    except (serial.SerialException, OSError):
        return False
