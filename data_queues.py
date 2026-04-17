import threading
from queue import Queue

display_queue = Queue()
display_character_queue = Queue()
shoot_queue = Queue()

# TTS thread: items are str (streamed words) or TTS_END_OF_RESPONSE (one per server response).
TTS_END_OF_RESPONSE = object()

# Set by threads/tts after each response play() completes; cleared on TCP before TTS_END_OF_RESPONSE.
tts_response_playback_done = threading.Event()

# Used for the TTS model.
text_queue = Queue()
