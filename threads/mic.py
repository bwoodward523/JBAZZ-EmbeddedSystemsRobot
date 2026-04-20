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
QUEUE_MAXSIZE = 960
MAX_STREAM_RECOVERIES = 30
VAD_DETECTION_FREQUENCY = 5 #Every 5 loops, run a voice activity check 

MAX_CONSECUTIVE_READ_ERRORS = 10


def _capture_loop(stream, audio_queue, stop_event):
    """Read-only: stream.read() and queue.put. Runs on a dedicated thread."""
    consecutive_errors = 0
    while not stop_event.is_set():
        try:
            frame = stream.read(READ_CHUNK, exception_on_overflow=False)
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            print(f"Error from recording thread: {e}")
            if consecutive_errors >= MAX_CONSECUTIVE_READ_ERRORS:
                print("Capture: too many consecutive read errors, exiting.")
                return
            time.sleep(0.01)
            continue

        while not stop_event.is_set():
            try:
                audio_queue.put(frame, timeout=0.2)
                break
            except queue.Full:
                print("Q FULL - back-pressure, retrying put")


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

        self.stream = self.p.open(
            format=self.sample_format,
            channels=self.channels,
            rate=self.fs,
            frames_per_buffer=READ_CHUNK,
            input_device_index=1,
            input=True,
            start=False,
        )

    def record(self):
        print("Beginning recording")

        #Used with VAD_DETECTION_FREQUENCY to speed up real time operations
        vad_counter = 0

        try:
            if self.stream.is_stopped():
                print("Starting the mic stream)")
                self.stream.start_stream()
        except Exception as e:
            print(f"Error starting the record stream: {e}")

        audio_queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        stop_event = threading.Event()

        reader_thread = threading.Thread(
            target=_capture_loop,
            args=(self.stream, audio_queue, stop_event),
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
                        print("Silenced Threshold Reached. Sending Audio. - signature 1")
                        break
                    continue

                frames.append(frame)

                #After 1 sec has passed since last time we tried to detect voice, try again. 
                # if time.time() - last_voice_time > 1.0:
                if vad_counter == VAD_DETECTION_FREQUENCY:
                    #Reset the vad counter to 0
                    vad_counter = 0

                    # t1 = time.time()
                    # print(f"Time before audio math: {time.time()}")
                    audio_tensor = self.bytes_to_tensor(frame)
                    new_data = resample(
                        audio_tensor,
                        int(len(audio_tensor) * SILERO_VAD_SAMPLE_RATE / self.fs),
                    )
                    tensor = torch.from_numpy(new_data)
                    speech_prob = self.vad(tensor, SILERO_VAD_SAMPLE_RATE).item()
                    # print(f"Elapsed audio math time: {time.time() - t1}")

                    if speech_prob > 0.85:
                        self.valid_audio = True
                        last_voice_time = time.time()
                        print("speech detected")
                    if time.time() - last_voice_time > 2:
                        print("Silenced Threshold Reached. Sending Audio. - signature 2")
                        break
                    else:
                        print(f"no detected {time.time() - last_voice_time}")
                else:
                    vad_counter += 1
        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            stop_event.set()
            reader_thread.join(timeout=2.0)
            if reader_thread.is_alive():
                print("Capture thread did not exit within timeout.")
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
            except Exception as e:
                print(f"Exception during stream stopping: {e}")
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
        try:
            if self.stream.is_active():
                self.stream.stop_stream()
        except Exception as e:
            print(f"Exception during stream stopping on disconnect: {e}")
        self.stream.close()
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
