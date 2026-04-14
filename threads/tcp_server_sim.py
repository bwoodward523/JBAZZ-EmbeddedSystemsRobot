import random
import threading
import time

from data_queues import (
    TTS_END_OF_RESPONSE,
    display_character_queue,
    display_queue,
    shoot_queue,
    text_queue,
    tts_response_playback_done,
)
from .tts import TTS, tts_thread


def sim_run_client_thread():
    emotions = ["happiness", "surprise", "fear", "disgust", "sadness", "anger"]
    fake_responses = [
        "Hello there I am online and ready to help",
        "Great question let me think through that quickly",
        "Systems are stable and all checks look good",
        "I heard you loud and clear what should we do next",
    ]

    tts_model = TTS()
    tts_thread_live = threading.Thread(target=tts_thread, args=(tts_model,), daemon=True)
    tts_thread_live.start()

    while True:
        print("Fake Audio Recording")
        time.sleep(2)

        # Simulated emotion data packet from server.
        display_queue.put(random.choice(emotions))

        # Simulated streamed tokens from server -> display/TTS queues.
        response = random.choice(fake_responses)
        tts_response_playback_done.clear()
        for word in response.split():
            display_character_queue.put(word)
            text_queue.put(word)
            time.sleep(0.1)

        text_queue.put(TTS_END_OF_RESPONSE)
        tts_response_playback_done.wait()

        # Simulated shoot state payload for other threads.
        shoot_queue.put(bool(random.getrandbits(1)))

