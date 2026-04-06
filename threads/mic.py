import queue
import threading
import time
import pyaudio
import wave

from silero_vad import load_silero_vad
import torch
import numpy as np
from scipy.signal import resample


SILERO_VAD_SAMPLE_RATE = 16000
# 48 kHz / 16 kHz = 3; Silero uses 512 samples at 16 kHz → 1536 samples at 48 kHz
READ_CHUNK = 1536
QUEUE_MAXSIZE = 96


def _capture_loop(stream, audio_queue, stop_event):
    """Read-only: stream.read() and queue.put. Runs on a dedicated thread."""
    while not stop_event.is_set():
        try:
            print("Reading!")
            frame = stream.read(READ_CHUNK, exception_on_overflow=False)
            print("Read")
        except OSError:
            break
        while not stop_event.is_set():
            try:
                audio_queue.put(frame, timeout=0.2)
                break
            except queue.Full:
                pass


class Microphone:
    def __init__(self, idle_window=2, fs=48000, frame_ms=20):
        self.fs = fs
        self.frame_ms = frame_ms
        self.channels = 1
        self.sample_format = pyaudio.paInt16

        self.samples_per_frame = int(self.fs * self.frame_ms / 1000)
        self.chunk = self.samples_per_frame

        self.vad = load_silero_vad()

        self.p = pyaudio.PyAudio()

        self.valid_audio = False

    def _open_input_stream(self):
        return self.p.open(
            format=self.sample_format,
            channels=self.channels,
            rate=self.fs,
            frames_per_buffer=READ_CHUNK,
            input_device_index=1,
            input=True,
        )

    def record(self):
        print("Beginning recording")

        stream = self._open_input_stream()
        audio_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        stop_event = threading.Event()

        reader_thread = threading.Thread(
            target=_capture_loop,
            args=(stream, audio_queue, stop_event),
            daemon=True,
        )
        reader_thread.start()

        frames = []
        last_voice_time = time.time()
        try:
            while True:
                try:
                    frame = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    if time.time() - last_voice_time > 2:
                        break
                    continue

                frames.append(frame)

                audio_tensor = self.bytes_to_tensor(frame)
                new_data = resample(
                    audio_tensor,
                    int(len(audio_tensor) * SILERO_VAD_SAMPLE_RATE / self.fs),
                )
                tensor = torch.from_numpy(new_data)
                speech_prob = self.vad(tensor, SILERO_VAD_SAMPLE_RATE).item()

                if speech_prob > 0.85:
                    self.valid_audio = True
                    last_voice_time = time.time()
                    print("speech detected")

                if time.time() - last_voice_time > 2:
                    break
                else:
                    print(f"no detected {time.time() - last_voice_time}")
        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            stop_event.set()
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            reader_thread.join(timeout=0.0)
            while True:
                try:
                    frames.append(audio_queue.get_nowait())
                except queue.Empty:
                    break

        audio_bytes = b"".join(frames)
        self.save_as_wav(audio_bytes)
        return audio_bytes

    def save_as_wav(self, audio_bytes):
        wf = wave.open("output.wav", "wb")
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)
        wf.writeframes(audio_bytes)
        wf.close()

    def disconnect(self):
        self.p.terminate()

    def bytes_to_tensor(self, audio_bytes: bytes) -> torch.Tensor:
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float32 = int2float(audio_int16)
        return audio_float32


def int2float(sound):
    abs_max = np.abs(sound).max()
    sound = sound.astype("float32")
    if abs_max > 0:
        sound *= 1 / 32768
    sound = sound.squeeze()
    return sound


if __name__ == "__main__":
    mic = Microphone()
    data = mic.record()
    mic.disconnect()
