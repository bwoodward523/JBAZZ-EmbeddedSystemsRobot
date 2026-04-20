import threading
from queue import Queue

from threads.audio_playback import AUDIO_STREAM_END, PlaybackClock

# --- Display / control queues (shared across threads) ---
display_queue = Queue()
display_character_queue = Queue()  # legacy word stream (simulator + display fallback)
shoot_queue = Queue()

# --- Legacy local-TTS plumbing (used by threads/tts.py + tcp_server_sim.py) ---
# Kept during the Step 5 transition so the simulator and old local-TTS path keep
# working. The new typed-protocol receiver no longer uses these.
TTS_END_OF_RESPONSE = object()
tts_response_playback_done = threading.Event()
text_queue = Queue()

# --- Step 5 typed TCP audio/timing pipeline ---
# Raw PCM bytes (or AUDIO_STREAM_END sentinel) consumed by audio_playback_loop.
audio_playback_queue: Queue = Queue()
# (start_s, end_s, word) tuples for Step 6 viseme scheduling.
timing_queue: Queue = Queue()
# Set by audio_playback_loop when AUDIO_STREAM_END drains; used as a SHOOT gate.
audio_stream_end_event = threading.Event()
# Shared playback clock - audio thread writes, display thread reads in Step 6.
playback_clock = PlaybackClock()

# Re-export the sentinel so other modules don't have to reach into audio_playback.
__all__ = [
    "AUDIO_STREAM_END",
    "TTS_END_OF_RESPONSE",
    "audio_playback_queue",
    "audio_stream_end_event",
    "display_character_queue",
    "display_queue",
    "playback_clock",
    "shoot_queue",
    "text_queue",
    "timing_queue",
    "tts_response_playback_done",
]
