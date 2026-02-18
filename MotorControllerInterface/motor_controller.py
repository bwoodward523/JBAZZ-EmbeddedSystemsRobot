"""
STM32 Nucleo servo motor controller over UART.

Sends angle commands (in degrees) to an STM32 Nucleo board that drives
two servos (pan / tilt).  The Nucleo appears as /dev/ttyACM0 when
connected to the Raspberry Pi via USB.

UART protocol (Pi -> STM32):
  "<servo_id>,<angle>\n"
    servo_id : 1 or 2
    angle    : integer 0-180

STM32 response:
  "OK\n"  on success
  "ERR\n" on failure

Requires:
  pip install pyserial
"""

from __future__ import annotations

import time
from typing import Optional

import serial


# Defaults
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 1.0        # seconds

SERVO_PAN  = 1               # horizontal axis
SERVO_TILT = 2               # vertical axis

MIN_ANGLE = 0
MAX_ANGLE = 180


class MotorController:
    """
    Controls two servos on an STM32 Nucleo via UART.

    Usage:
        with MotorController() as mc:
            mc.set_angle(SERVO_PAN, 90)
            mc.set_angle(SERVO_TILT, 45)
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

    # -- context manager --------------------------------------------------

    def __enter__(self) -> MotorController:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- connection -------------------------------------------------------

    def open(self) -> None:
        """Open the UART connection to the STM32 Nucleo."""
        if self._serial is not None and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout,
        )
        # Give the STM32 time to reset after serial open
        time.sleep(2)
        self._serial.reset_input_buffer()

    def close(self) -> None:
        """Close the UART connection."""
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    # -- core commands ----------------------------------------------------

    def _send(self, message: str) -> str:
        """Send a message and return the response line from the STM32."""
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("UART connection is not open")
        self._serial.write(f"{message}\n".encode("ascii"))
        self._serial.flush()
        response = self._serial.readline().decode("ascii").strip()
        return response

    def set_angle(self, servo_id: int, angle: int) -> bool:
        """
        Command a servo to move to the given angle in degrees.

        Parameters
        ----------
        servo_id : int
            Which servo to move (SERVO_PAN = 1, SERVO_TILT = 2).
        angle : int
            Target angle in degrees (0 – 180).

        Returns
        -------
        bool
            True if the STM32 acknowledged the command.
        """
        if servo_id not in (SERVO_PAN, SERVO_TILT):
            raise ValueError(f"Invalid servo_id {servo_id}; must be {SERVO_PAN} or {SERVO_TILT}")
        angle = max(MIN_ANGLE, min(MAX_ANGLE, int(angle)))
        response = self._send(f"{servo_id},{angle}")
        return response == "OK"

    def set_pan(self, angle: int) -> bool:
        """Move the pan (horizontal) servo to *angle* degrees."""
        return self.set_angle(SERVO_PAN, angle)

    def set_tilt(self, angle: int) -> bool:
        """Move the tilt (vertical) servo to *angle* degrees."""
        return self.set_angle(SERVO_TILT, angle)

    def center(self) -> None:
        """Center both servos to 90 degrees."""
        self.set_pan(90)
        self.set_tilt(90)


# -- module-level helpers -------------------------------------------------

def motor_controller_available(port: str = DEFAULT_PORT) -> bool:
    """Return True if the STM32 Nucleo serial port exists and can be opened."""
    try:
        with serial.Serial(port, DEFAULT_BAUD, timeout=0.5) as s:
            return s.is_open
    except (serial.SerialException, OSError):
        return False
