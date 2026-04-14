#!/usr/bin/python3
import re
import time
from queue import Empty

import numpy as np
import PIL.Image as Image
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from data_queues import display_character_queue, display_queue

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

VISEME_WEIGHTS = {
    "MBP": 1.35,
    "FV": 1.25,
    "TH": 1.25,
    "A_OPEN": 1.1,
    "E_WIDE": 1.0,
    "O_ROUND": 1.1,
    "L": 0.95,
    "R": 1.0,
    "SIBILANT": 0.95,
    "NEUTRAL": 0.9,
}

emotion_cache = {}
mouth_cache = {}

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


def estimate_viseme_durations(visemes, word):
    if not visemes:
        return []

    # Character-count heuristic (fallback until TTS callbacks provide timing).
    base_duration_ms = int(100 + len(word) * 28)
    word_duration_ms = max(130, min(460, base_duration_ms))

    weights = [VISEME_WEIGHTS.get(viseme, 1.0) for viseme in visemes]
    total_weight = sum(weights) if sum(weights) > 0 else len(weights)

    durations = [int(word_duration_ms * (weight / total_weight)) for weight in weights]
    durations = [max(50, min(180, duration)) for duration in durations]

    delta = word_duration_ms - sum(durations)
    index = 0
    while delta != 0 and durations:
        step = 1 if delta > 0 else -1
        candidate = durations[index] + step
        if 45 <= candidate <= 220:
            durations[index] = candidate
            delta -= step
        index = (index + 1) % len(durations)
    return durations


# Returns the list of sprite events to render in order.
def process_incoming_word(word):
    normalized_word = normalize_word(word)
    if not normalized_word:
        return []

    phonemes = word_to_phonemes(normalized_word)
    visemes = phoneme_to_visemes(phonemes)
    durations = estimate_viseme_durations(visemes, normalized_word)

    events = []
    for viseme, duration_ms in zip(visemes, durations):
        sprite_file = VISEME_TO_SPRITE.get(viseme, VISEME_TO_SPRITE[DEFAULT_VISEME])
        events.append(
            {
                "viseme": viseme,
                "sprite": sprite_file,
                "duration_ms": duration_ms,
                "word": normalized_word,
            }
        )
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
            emotion_cache[emotion] = Image.open(f"{BASE_EMOTION_DIR}/{emotion}.png").convert("RGBA")
        except Exception:
            emotion_cache[emotion] = Image.open(f"{BASE_EMOTION_DIR}/{DEFAULT_EMOTION}.png").convert("RGBA")
    return emotion_cache[emotion]


def load_mouth_image(sprite_name):
    if sprite_name not in mouth_cache:
        try:
            mouth_img = Image.open(f"{MOUTH_SPRITE_DIR}/{sprite_name}").convert("RGBA")
        except Exception:
            mouth_img = Image.open(
                f"{MOUTH_SPRITE_DIR}/{VISEME_TO_SPRITE[DEFAULT_VISEME]}"
            ).convert("RGBA")
        if mouth_img.size != (width, height):
            fitted = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            x_pos = max(0, (width - mouth_img.width) // 2)
            y_pos = max(0, height - mouth_img.height)
            fitted.paste(mouth_img, (x_pos, y_pos), mouth_img)
            mouth_img = fitted
        mouth_cache[sprite_name] = mouth_img
    return mouth_cache[sprite_name]


def show_full_emotion(emotion):
    emotion_img = load_emotion_image(emotion).convert("RGB")
    framebuffer[:] = np.asarray(emotion_img)
    matrix.show()


def show_emotion_with_mouth(emotion, mouth_sprite):
    base = load_emotion_image(emotion).copy()
    mouth = load_mouth_image(mouth_sprite)
    base.alpha_composite(mouth)
    framebuffer[:] = np.asarray(base.convert("RGB"))
    matrix.show()




def show_emotions_thread():
    active_emotion = DEFAULT_EMOTION
    viseme_events = []
    active_event_end = 0.0
    is_talking = False

    show_full_emotion(active_emotion)
    while True:
        try:
            while True:
                incoming_emotion = display_queue.get_nowait()
                active_emotion = sanitize_emotion(incoming_emotion)
                if not is_talking:
                    show_full_emotion(active_emotion)
        except Empty:
            pass

        try:
            while True:
                word = display_character_queue.get_nowait()
                events = process_incoming_word(word)
                if events:
                    viseme_events.extend(events)
                    if DEBUG_VISEMES:
                        print(f"Queued {len(events)} visemes for word '{word}'")
        except Empty:
            pass

        now = time.monotonic()
        if viseme_events:
            if now >= active_event_end:
                next_event = viseme_events.pop(0)
                show_emotion_with_mouth(active_emotion, next_event["sprite"])
                active_event_end = now + (next_event["duration_ms"] / 1000.0)
                is_talking = True
        elif is_talking:
            # Idle state uses full emotion PNG for stronger personality effect.
            show_full_emotion(active_emotion)
            is_talking = False

        time.sleep(0.01)
