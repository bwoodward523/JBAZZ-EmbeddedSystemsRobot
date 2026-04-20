"""
Pi-side streaming PCM playback (step 4).

Consumes 24 kHz mono int16 chunks (TCP/Kokoro protocol). Optionally resamples and
upmixes for USB DACs that only expose 48 kHz stereo. Advances ``seconds_played`` using
the protocol timeline only (incoming mono chunk length), not output byte counts.

Environment:
  JBAZZ_AUDIO_OUTPUT_DEVICE_INDEX — optional int, ``PyAudio`` output device index.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from queue import Queue
from typing import Optional

import numpy as np
import pyaudio

# --- Protocol (must match desktop TTS / TCP) ---
PROTOCOL_SAMPLE_RATE = 24000
PROTOCOL_CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes per sample (16-bit)

# --- Default output (Jieli USB UAC: 48 kHz stereo) ---
OUTPUT_SAMPLE_RATE = 48000
OUTPUT_CHANNELS = 2

# Sentinel: one object identity per stream/response end (queue consumer strips it).
AUDIO_STREAM_END = object()


@dataclass
class PlaybackClock:
    """Shared playback position for lip-sync; audio thread writes, display may read."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    seconds_played: float = 0.0
    active: bool = False
    #: Snapshot of ``seconds_played`` immediately before reset on ``AUDIO_STREAM_END``.
    last_utterance_seconds: float = 0.0


def _env_output_device_index() -> Optional[int]:
    raw = os.environ.get("JBAZZ_AUDIO_OUTPUT_DEVICE_INDEX")
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _resample_mono_linear(mono_i16: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray:
    """Linear interpolation resample; numpy-only."""
    if src_hz == dst_hz:
        return mono_i16
    n_in = int(mono_i16.shape[0])
    if n_in == 0:
        return mono_i16
    n_out = max(1, int(round(n_in * dst_hz / src_hz)))
    x_in = np.arange(n_in, dtype=np.float64)
    x_out = np.linspace(0.0, float(n_in - 1), n_out)
    y = np.interp(x_out, x_in, mono_i16.astype(np.float64))
    return np.clip(np.round(y), -32768, 32767).astype(np.int16)


def _interleave_dup_mono_stereo(mono_i16: np.ndarray) -> bytes:
    """Duplicate mono into L/R interleaved S16."""
    n = mono_i16.shape[0]
    if n == 0:
        return b""
    out = np.empty(2 * n, dtype=np.int16)
    out[0::2] = mono_i16
    out[1::2] = mono_i16
    return out.tobytes()


def protocol_chunk_to_output_pcm(
    chunk: bytes,
    *,
    protocol_rate: int = PROTOCOL_SAMPLE_RATE,
    protocol_ch: int = PROTOCOL_CHANNELS,
    output_rate: int = OUTPUT_SAMPLE_RATE,
    output_ch: int = OUTPUT_CHANNELS,
) -> bytes:
    """
    Convert one protocol chunk to output-device PCM bytes.
    If protocol and output formats match, returns chunk unchanged.
    """
    if len(chunk) % SAMPLE_WIDTH != 0:
        chunk = chunk[: (len(chunk) // SAMPLE_WIDTH) * SAMPLE_WIDTH]

    if (
        protocol_rate == output_rate
        and protocol_ch == output_ch
    ):
        return chunk

    mono = np.frombuffer(chunk, dtype=np.int16)
    if mono.size == 0:
        return b""

    rs = _resample_mono_linear(mono, protocol_rate, output_rate)
    if output_ch == 1:
        return rs.tobytes()
    if output_ch == 2:
        return _interleave_dup_mono_stereo(rs)
    # Generic: repeat mono across N channels
    n = rs.shape[0]
    inter = np.empty(n * output_ch, dtype=np.int16)
    for c in range(output_ch):
        inter[c::output_ch] = rs
    return inter.tobytes()


def _advance_seconds_for_protocol_chunk(chunk_len: int) -> float:
    denom = PROTOCOL_SAMPLE_RATE * SAMPLE_WIDTH * PROTOCOL_CHANNELS
    return chunk_len / denom


def audio_playback_loop(
    audio_queue: Queue,
    clock: PlaybackClock,
    *,
    stream_end_event: threading.Event | None = None,
    on_stream_end: Callable[[], None] | None = None,
    output_sample_rate: int = OUTPUT_SAMPLE_RATE,
    output_channels: int = OUTPUT_CHANNELS,
    output_device_index: int | None = None,
    protocol_sample_rate: int = PROTOCOL_SAMPLE_RATE,
    protocol_channels: int = PROTOCOL_CHANNELS,
) -> None:
    """
    Blocking loop: pull PCM or ``AUDIO_STREAM_END`` from ``audio_queue``.

    Opens one PyAudio output stream for the session. On each PCM chunk, converts
    protocol → output format, writes, then increases ``clock.seconds_played`` by the
    **protocol** duration only.
    """
    if output_device_index is None:
        output_device_index = _env_output_device_index()

    pa = pyaudio.PyAudio()
    kw: dict = dict(
        format=pyaudio.paInt16,
        channels=output_channels,
        rate=output_sample_rate,
        output=True,
        frames_per_buffer=1024,
    )
    if output_device_index is not None:
        kw["output_device_index"] = output_device_index

    stream = pa.open(**kw)

    try:
        while True:
            item = audio_queue.get()
            if item is AUDIO_STREAM_END:
                with clock.lock:
                    clock.last_utterance_seconds = clock.seconds_played
                    clock.seconds_played = 0.0
                    clock.active = False
                if stream_end_event is not None:
                    stream_end_event.set()
                if on_stream_end is not None:
                    on_stream_end()
                continue

            if not isinstance(item, (bytes, bytearray)):
                continue

            chunk = bytes(item)
            bl = len(chunk)
            if bl % SAMPLE_WIDTH != 0:
                bl = (bl // SAMPLE_WIDTH) * SAMPLE_WIDTH
                chunk = chunk[:bl]
            if bl == 0:
                continue

            delta = _advance_seconds_for_protocol_chunk(bl)

            out_pcm = protocol_chunk_to_output_pcm(
                chunk,
                protocol_rate=protocol_sample_rate,
                protocol_ch=protocol_channels,
                output_rate=output_sample_rate,
                output_ch=output_channels,
            )
            if len(out_pcm) == 0:
                with clock.lock:
                    clock.seconds_played += delta
                continue

            with clock.lock:
                clock.active = True

            stream.write(out_pcm)

            with clock.lock:
                clock.seconds_played += delta
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


if __name__ == "__main__":
    duration_s = 1.5
    chunk_ms = 50
    protocol_frames_per_chunk = max(1, int(PROTOCOL_SAMPLE_RATE * chunk_ms / 1000))

    t = np.linspace(
        0.0,
        duration_s,
        int(PROTOCOL_SAMPLE_RATE * duration_s),
        endpoint=False,
        dtype=np.float64,
    )
    tone = (0.12 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float64)
    mono_i16 = (tone * 32767.0).clip(-32768, 32767).astype(np.int16)
    pcm_full = mono_i16.tobytes()

    chunk_b = protocol_frames_per_chunk * SAMPLE_WIDTH * PROTOCOL_CHANNELS
    q: Queue = Queue()
    for i in range(0, len(pcm_full), chunk_b):
        q.put(pcm_full[i : i + chunk_b])

    expected_seconds = len(mono_i16) / float(PROTOCOL_SAMPLE_RATE)

    clk = PlaybackClock()
    done = threading.Event()

    worker = threading.Thread(
        target=audio_playback_loop,
        kwargs=dict(
            audio_queue=q,
            clock=clk,
            stream_end_event=done,
        ),
        daemon=True,
    )
    worker.start()

    q.put(AUDIO_STREAM_END)
    done.wait(timeout=duration_s + 5.0)

    err = abs(clk.last_utterance_seconds - expected_seconds)
    print(
        f"expected={expected_seconds:.6f}s  last_utterance={clk.last_utterance_seconds:.6f}s  err={err:.6f}s"
    )
    assert err < 0.05, f"sync drift too large: {err}"
    print("audio_playback self-test OK")
