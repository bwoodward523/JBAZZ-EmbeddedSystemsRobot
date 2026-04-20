#!/usr/bin/python3
import re
import time
from queue import Empty

import numpy as np
import PIL.Image as Image
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from data_queues import display_queue, timing_queue

width = 32
height = 32
emotions = ["happiness.png", "surprise.png", "fear.png", "disgust.png", "sadness.png", "anger.png"]
DEBUG_VISEMES = True

BASE_EMOTION_DIR = "led_display/assets/base_emotions"
MOUTH_SPRITE_DIR = "led_display/assets/mouth_visemes"
DEFAULT_EMOTION = "happiness"
DEFAULT_VISEME = "NEUTRAL"

VISEME_TO_SPRITE = {
    "MBP": "mouth_mbp.png",
    "FV": "mouth_fv.png",
    "A_OPEN": "mouth_a_open.png",
    "E_WIDE": "mouth_e_wide.png",
    "O_ROUND": "mouth_o_round.png",
    "L": "mouth_l.png",
    "R": "mouth_r.png",
    "TH": "mouth_th.png",
    "SIBILANT": "mouth_sibilant.png",
    "NEUTRAL": "mouth_neutral.png",
}

PHONEME_TO_VISEME = {
    "M": "MBP",
    "B": "MBP",
    "P": "MBP",
    "F": "FV",
    "V": "FV",
    "AA": "A_OPEN",
    "AE": "A_OPEN",
    "AH": "A_OPEN",
    "AO": "A_OPEN",
    "AW": "A_OPEN",
    "AY": "A_OPEN",
    "EH": "E_WIDE",
    "EY": "E_WIDE",
    "IH": "E_WIDE",
    "IY": "E_WIDE",
    "OW": "O_ROUND",
    "OY": "O_ROUND",
    "UH": "O_ROUND",
    "UW": "O_ROUND",
    "L": "L",
    "R": "R",
    "TH": "TH",
    "DH": "TH",
    "S": "SIBILANT",
    "Z": "SIBILANT",
    "SH": "SIBILANT",
    "ZH": "SIBILANT",
    "CH": "SIBILANT",
    "JH": "SIBILANT",
}

COMMON_WORD_PHONEMES = {
    "hello": ["HH", "AH0", "L", "OW1"],
    "world": ["W", "ER1", "L", "D"],
    "i": ["AY1"],
    "im": ["AY1", "M"],
    "i'm": ["AY1", "M"],
    "you": ["Y", "UW1"],
    "we": ["W", "IY1"],
    "they": ["DH", "EY1"],
    "the": ["DH", "AH0"],
    "a": ["AH0"],
    "am": ["AE1", "M"],
    "is": ["IH1", "Z"],
    "are": ["AA1", "R"],
    "and": ["AE1", "N", "D"],
    "to": ["T", "UW1"],
    "for": ["F", "AO1", "R"],
}

LETTER_CLUSTER_PHONEMES = {
    "th": "TH",
    "sh": "SH",
    "ch": "CH",
    "ph": "F",
    "wh": "W",
    "ck": "K",
    "ng": "N",
}

LETTER_FALLBACK_PHONEMES = {
    "a": "AH",
    "b": "B",
    "c": "K",
    "d": "D",
    "e": "EH",
    "f": "F",
    "g": "G",
    "h": "HH",
    "i": "IH",
    "j": "JH",
    "k": "K",
    "l": "L",
    "m": "M",
    "n": "N",
    "o": "OW",
    "p": "P",
    "q": "K",
    "r": "R",
    "s": "S",
    "t": "T",
    "u": "UW",
    "v": "V",
    "w": "W",
    "x": "S",
    "y": "Y",
    "z": "Z",
}

emotion_cache = {}
mouth_cache = {}
invalid_mouth_warnings = set()

geometry = piomatter.Geometry(
    width=width,
    height=height,
    n_addr_lines=4,
    rotation=piomatter.Orientation.Normal
)

canvas = Image.new("RGB", (width, height))
framebuffer = np.asarray(canvas, dtype=np.uint8) + 0

matrix = piomatter.PioMatter(
    colorspace=piomatter.Colorspace.RGB888Packed,
    pinout=piomatter.Pinout.Active3,
    framebuffer=framebuffer,
    geometry=geometry
)


def normalize_word(word):
    normalized = word.lower().strip()
    normalized = re.sub(r"[^a-z]", "", normalized)
    return normalized


def approximate_word_to_phonemes(word):
    phonemes = []
    i = 0
    while i < len(word):
        if i + 1 < len(word):
            cluster = word[i : i + 2]
            mapped_cluster = LETTER_CLUSTER_PHONEMES.get(cluster)
            if mapped_cluster is not None:
                phonemes.append(mapped_cluster)
                i += 2
                continue
        mapped_single = LETTER_FALLBACK_PHONEMES.get(word[i])
        if mapped_single is not None:
            phonemes.append(mapped_single)
        i += 1
    return phonemes or ["AH"]


# Converts word to phonemes, returns the phonemes.
def word_to_phonemes(word):
    if word in COMMON_WORD_PHONEMES:
        raw = COMMON_WORD_PHONEMES[word]
    else:
        raw = approximate_word_to_phonemes(word)

    return [re.sub(r"\d", "", phoneme) for phoneme in raw]


# Converts phoneme to visemes, returns a list of visemes.
def phoneme_to_visemes(phonemes):
    visemes = []
    for phoneme in phonemes:
        viseme = PHONEME_TO_VISEME.get(phoneme, DEFAULT_VISEME)
        if not visemes or visemes[-1] != viseme:
            visemes.append(viseme)
    return visemes or [DEFAULT_VISEME]


# Builds a list of (trigger_s, sprite) tuples for a single timed word.
# Uniform per-viseme split across Kokoro's reported [start_s, end_s] duration.
def build_word_events(start_s, end_s, word):
    normalized = normalize_word(word)
    if not normalized:
        return []
    visemes = phoneme_to_visemes(word_to_phonemes(normalized))
    if not visemes:
        return []
    duration = max(0.0, end_s - start_s)
    if duration <= 0.0:
        return []
    per_viseme = duration / len(visemes)
    events = []
    for i, viseme in enumerate(visemes):
        sprite = VISEME_TO_SPRITE.get(viseme, VISEME_TO_SPRITE[DEFAULT_VISEME])
        events.append((start_s + i * per_viseme, sprite))
    return events

#Protects against unexpected characters that the LLM might have generated causing the emotion to not match the file
def sanitize_emotion(emotion):
    clean = emotion.replace('"', "").replace(" ", "").replace(".png", "")
    if clean in {value.replace(".png", "") for value in emotions}:
        return clean
    return DEFAULT_EMOTION


def load_emotion_image(emotion):
    if emotion not in emotion_cache:
        try:
            emotion_cache[emotion] = np.asarray(
                Image.open(f"{BASE_EMOTION_DIR}/{emotion}.png").convert("RGB"), dtype=np.uint8
            )
        except Exception:
            emotion_cache[emotion] = np.asarray(
                Image.open(f"{BASE_EMOTION_DIR}/{DEFAULT_EMOTION}.png").convert("RGB"), dtype=np.uint8
            )
    return emotion_cache[emotion]


def _load_raw_mouth_sprite(sprite_name):
    return np.asarray(Image.open(f"{MOUTH_SPRITE_DIR}/{sprite_name}").convert("RGB"), dtype=np.uint8)


def load_mouth_image(sprite_name):
    if sprite_name not in mouth_cache:
        try:
            mouth_img = _load_raw_mouth_sprite(sprite_name)
        except Exception:
            neutral_sprite = VISEME_TO_SPRITE[DEFAULT_VISEME]
            try:
                mouth_img = _load_raw_mouth_sprite(neutral_sprite)
            except Exception:
                if sprite_name not in invalid_mouth_warnings:
                    print(
                        f"Missing mouth sprite '{sprite_name}' and fallback '{neutral_sprite}'. "
                        "Skipping talking frame."
                    )
                    invalid_mouth_warnings.add(sprite_name)
                mouth_cache[sprite_name] = None
                return None

        if mouth_img.shape != (16, width, 3):
            neutral_sprite = VISEME_TO_SPRITE[DEFAULT_VISEME]
            if sprite_name not in invalid_mouth_warnings:
                print(
                    f"Mouth sprite '{sprite_name}' has invalid shape {mouth_img.shape}. "
                    f"Expected (16, {width}, 3). Using neutral fallback."
                )
                invalid_mouth_warnings.add(sprite_name)
            if sprite_name != neutral_sprite:
                return load_mouth_image(neutral_sprite)
            mouth_cache[sprite_name] = None
            return None

        mouth_cache[sprite_name] = mouth_img
    return mouth_cache[sprite_name]


def show_full_emotion(emotion):
    emotion_img = load_emotion_image(emotion)
    framebuffer[:] = emotion_img
    matrix.show()


def show_emotion_with_mouth(emotion, mouth_sprite):
    mouth = load_mouth_image(mouth_sprite)
    if mouth is None:
        return False

    emotion_img = load_emotion_image(emotion)
    frame = np.empty((height, width, 3), dtype=np.uint8)
    frame[0:16, :, :] = emotion_img[0:16, :, :]
    frame[16:32, :, :] = mouth[0:16, :, :]
    framebuffer[:] = frame
    matrix.show()
    return True




def show_emotions_thread():
    active_emotion = DEFAULT_EMOTION
    # Kokoro timeline: elapsed = time.monotonic() - utterance_t0 ≈ protocol seconds from TTS start.
    utterance_t0 = None
    prev_word_start_s = None
    # (start_s, end_s, word, events) where events is [(trigger_s, sprite), ...]
    current = None
    last_sprite_rendered = None
    is_talking = False

    show_full_emotion(active_emotion)

    def try_start_word(start_s, end_s, word):
        nonlocal utterance_t0, prev_word_start_s, current, is_talking
        events = build_word_events(start_s, end_s, word)
        if not events:
            return False
        if utterance_t0 is None:
            utterance_t0 = time.monotonic() - start_s
        elif prev_word_start_s is not None and start_s < prev_word_start_s - 1e-3:
            utterance_t0 = time.monotonic() - start_s
        prev_word_start_s = start_s
        current = (start_s, end_s, word, events)
        is_talking = True
        if DEBUG_VISEMES:
            print(
                f"[display] timing word={word!r} "
                f"start={start_s:.3f}s end={end_s:.3f}s "
                f"visemes={len(events)}"
            )
        return True

    def finish_utterance_idle():
        nonlocal utterance_t0, prev_word_start_s, current, last_sprite_rendered, is_talking
        current = None
        last_sprite_rendered = None
        is_talking = False
        utterance_t0 = None
        prev_word_start_s = None
        show_full_emotion(active_emotion)

    def pull_next_word_after_gap():
        """After a word ends: show full face, then take the next timing triple or go idle."""
        nonlocal last_sprite_rendered, is_talking
        last_sprite_rendered = None
        is_talking = False
        show_full_emotion(active_emotion)
        while True:
            try:
                start_s, end_s, word = timing_queue.get_nowait()
            except Empty:
                finish_utterance_idle()
                return
            if try_start_word(start_s, end_s, word):
                return

    while True:
        try:
            while True:
                incoming_emotion = display_queue.get_nowait()
                active_emotion = sanitize_emotion(incoming_emotion)
                if not is_talking:
                    show_full_emotion(active_emotion)
        except Empty:
            pass

        if current is None:
            try:
                start_s, end_s, word = timing_queue.get_nowait()
            except Empty:
                time.sleep(0.01)
                continue
            if not try_start_word(start_s, end_s, word):
                continue

        start_s, end_s, word, events = current
        elapsed = time.monotonic() - utterance_t0

        current_sprite = None
        while events and events[0][0] <= elapsed:
            _, current_sprite = events.pop(0)

        if current_sprite is not None and current_sprite != last_sprite_rendered:
            if DEBUG_VISEMES:
                print("Showing viseme")
            frame_shown = show_emotion_with_mouth(active_emotion, current_sprite)
            if frame_shown:
                last_sprite_rendered = current_sprite

        if elapsed >= end_s:
            pull_next_word_after_gap()

        time.sleep(0.01)
