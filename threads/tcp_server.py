"""
Pi-side TCP client (Step 5).

Receives typed messages from the desktop server and routes them into the Step 4
audio playback pipeline and existing display/shoot plumbing:

  * EMOTION         -> display_queue
  * AUDIO_CHUNK     -> audio_playback_queue (raw PCM bytes)
  * TIMING_DATA     -> timing_queue ((start_s, end_s, word) tuples, consumed in Step 6)
  * END_OF_RESPONSE -> AUDIO_STREAM_END sentinel into audio_playback_queue
  * SHOOT           -> wait for audio_stream_end_event, optionally post FIRE_DART

Framing: length-prefixed 4-byte big-endian u32, payload's first byte is the
message type, remaining bytes are the typed payload.
"""

from __future__ import annotations

import json
import socket
import struct
import threading

from data_queues import (
    AUDIO_STREAM_END,
    audio_playback_queue,
    audio_stream_end_event,
    display_queue,
    playback_clock,
    timing_queue,
)
from events import EventType, post_event

from .audio_playback import audio_playback_loop

HOST = "10.127.70.21"
PORT = 5555

# --- Typed protocol message constants (match desktop TCP server) ---
MSG_EMOTION = 0x00
MSG_AUDIO_CHUNK = 0x01
MSG_TIMING_DATA = 0x02
MSG_END_OF_RESPONSE = 0x03
MSG_SHOOT = 0x04

_MSG_TYPE_NAMES = {
    MSG_EMOTION: "EMOTION",
    MSG_AUDIO_CHUNK: "AUDIO_CHUNK",
    MSG_TIMING_DATA: "TIMING_DATA",
    MSG_END_OF_RESPONSE: "END_OF_RESPONSE",
    MSG_SHOOT: "SHOOT",
}

# One-shot warning latch for legacy/mismatched frames.
_legacy_format_warned = False


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------
def recv_exact(sock, n):
    buffer = b""
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer


def send_message(sock, payload: bytes) -> None:
    header = struct.pack("!I", len(payload))
    sock.sendall(header)
    sock.sendall(payload)


def recv_message(sock):
    header = recv_exact(sock, 4)
    if header is None:
        return None
    length = struct.unpack("!I", header)[0]
    return recv_exact(sock, length)


def recv_typed_message(sock):
    """
    Read one length-prefixed frame and split it into (msg_type, payload_bytes).

    Returns:
      (None, None) on clean disconnect
      (None, b"")  on malformed/empty frame (caller should skip)
      (int,  bytes) otherwise
    """
    frame = recv_message(sock)
    if frame is None:
        return None, None
    if len(frame) < 1:
        print("[TCP] empty frame received; skipping")
        return None, b""
    return frame[0], frame[1:]


# ---------------------------------------------------------------------------
# Per-type handlers
# ---------------------------------------------------------------------------
def _handle_emotion(payload: bytes) -> None:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"[TCP] EMOTION utf-8 decode failed: {e}")
        return
    emotion = text.split(":", 1)[1] if ":" in text else text
    emotion = emotion.strip()
    if not emotion:
        print("[TCP] EMOTION payload empty after parse; skipping")
        return
    display_queue.put(emotion)
    print(
        f"[TCP] EMOTION -> display_queue "
        f"(value={emotion!r}, depth={display_queue.qsize()})"
    )


def _handle_timing_data(payload: bytes) -> None:
    try:
        text = payload.decode("utf-8")
        timings = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"[TCP] TIMING_DATA decode failed: {e}")
        return
    if not isinstance(timings, list):
        print(f"[TCP] TIMING_DATA not a list: {type(timings).__name__}")
        return

    count = 0
    first_ts = None
    last_ts = None
    for entry in timings:
        try:
            start_s = float(entry["s"])
            end_s = float(entry["e"])
            word = entry["w"]
        except (KeyError, TypeError, ValueError):
            continue
        timing_queue.put((start_s, end_s, word))
        if first_ts is None:
            first_ts = start_s
        last_ts = end_s
        count += 1

    if count:
        print(
            f"[TCP] TIMING_DATA -> timing_queue "
            f"(count={count}, first={first_ts:.3f}s, last={last_ts:.3f}s, "
            f"depth={timing_queue.qsize()})"
        )


def _handle_audio_chunk(payload: bytes) -> None:
    if not payload:
        return
    audio_playback_queue.put(payload)


def _handle_end_of_response() -> None:
    # Clear the gate before enqueuing the sentinel so a subsequent SHOOT wait()
    # cannot race past a previous response's stale set.
    audio_stream_end_event.clear()
    audio_playback_queue.put(AUDIO_STREAM_END)
    print(
        "[TCP] END_OF_RESPONSE -> AUDIO_STREAM_END enqueued "
        f"(audio_depth={audio_playback_queue.qsize()}); awaiting playback drain"
    )


def _handle_shoot(payload: bytes) -> bool:
    """
    Block until audio playback has fully drained, then optionally post FIRE_DART.
    Returns True so the recv loop exits for the current response cycle.
    """
    audio_stream_end_event.wait()
    try:
        text = payload.decode("utf-8").strip().lower()
    except UnicodeDecodeError:
        text = ""
    should_fire = text in ("true", "1", "yes")
    print(f"[TCP] SHOOT payload={text!r} -> fire={should_fire}")
    if should_fire:
        post_event(EventType.FIRE_DART, source="tcp_server")
    return True


# ---------------------------------------------------------------------------
# Dispatch loop
# ---------------------------------------------------------------------------
def blocking_recv_state_machine(s) -> None:
    """
    Consume typed messages from the server until SHOOT is handled for the
    current response, or the server disconnects.
    """
    global _legacy_format_warned

    while True:
        msg_type, payload = recv_typed_message(s)

        # Clean disconnect: recv_message returned None.
        if msg_type is None and payload is None:
            print("[TCP] server closed connection")
            break
        # Malformed / empty frame: skip and continue.
        if msg_type is None:
            continue

        if msg_type == MSG_EMOTION:
            _handle_emotion(payload)
        elif msg_type == MSG_AUDIO_CHUNK:
            _handle_audio_chunk(payload)
        elif msg_type == MSG_TIMING_DATA:
            _handle_timing_data(payload)
        elif msg_type == MSG_END_OF_RESPONSE:
            _handle_end_of_response()
        elif msg_type == MSG_SHOOT:
            if _handle_shoot(payload):
                break
        else:
            if not _legacy_format_warned:
                _legacy_format_warned = True
                preview = payload[:32]
                print(
                    f"[TCP] UNKNOWN msg_type=0x{msg_type:02X} "
                    f"(len={len(payload)}, preview={preview!r}) - "
                    "possible protocol/version mismatch with server"
                )
            continue

    print("[TCP] recv state machine completed")


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def _start_audio_playback_thread() -> threading.Thread:
    """Start the Step 4 audio playback worker bound to the shared queues."""
    thread = threading.Thread(
        target=audio_playback_loop,
        kwargs=dict(
            audio_queue=audio_playback_queue,
            clock=playback_clock,
            stream_end_event=audio_stream_end_event,
        ),
        daemon=True,
        name="audio_playback",
    )
    thread.start()
    return thread


def run_client_thread() -> None:
    from .mic import Microphone

    mic = Microphone()
    _start_audio_playback_thread()

    print("attempting connection to host")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print(f"[TCP] connected to {HOST}:{PORT}")

        try:
            while True:
                while not mic.valid_audio:
                    mic.record()
                mic.valid_audio = False

                with open("output.wav", "rb") as f:
                    audio = f.read()
                send_message(s, audio)

                blocking_recv_state_machine(s)
        except KeyboardInterrupt:
            print("\n[TCP] interrupted by user")
        finally:
            print("[TCP] closing connection")
            mic.disconnect()

    print("Finished connection to host")

if __name__ == "__main__":
    run_client_thread()
