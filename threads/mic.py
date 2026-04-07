import time
import pyaudio
import wave
import webrtcvad

class Microphone:
    def __init__(self, idle_window=2, fs=48000, frame_ms=20):
        self.fs = fs
        self.frame_ms = frame_ms
        self.channels = 1
        self.sample_format = pyaudio.paInt16

        self.samples_per_frame = int(self.fs * self.frame_ms / 1000)
        self.chunk = self.samples_per_frame  # CRITICAL
        
        #From 0 to 3 controls the intensity it listens for speech. 3 means it is the strictest when looking for words. 
        self.vad = webrtcvad.Vad(3)
        self.p = pyaudio.PyAudio()

        self.valid_audio = False


    def record(self):
        print("Beginning recording")

        #Valid audio means if speech was detected. If Audio is invalid, then it won't have speech and it wont be sent to the TCP server. 
        stream = self.p.open(
            format=self.sample_format,
            channels=self.channels,
            rate=self.fs,
            frames_per_buffer=self.chunk,
            input_device_index=1,
            input=True
        )

        frames = []
        last_voice_time = time.time()
        try:
            while True:
                frame = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(frame)

                if self.vad.is_speech(frame, self.fs):
                    self.valid_audio = True
                    last_voice_time = time.time()
                    print("speech detected")

                if time.time() - last_voice_time > 2:
                    break
                else:
                    print(f"no detected {time.time() - last_voice_time}")
        except Exception as e:
            print(f"Recording error: {e}")
        

        stream.stop_stream()
        stream.close()

        audio_bytes = b''.join(frames)
        self.save_as_wav(audio_bytes)
        return audio_bytes

    def save_as_wav(self, audio_bytes):
        wf = wave.open("output.wav", 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.sample_format))
        wf.setframerate(self.fs)
        wf.writeframes(audio_bytes)
        wf.close()

    def disconnect(self):
        self.p.terminate()


if __name__ == "__main__":
    mic = Microphone()
    data = mic.record()
    mic.disconnect()