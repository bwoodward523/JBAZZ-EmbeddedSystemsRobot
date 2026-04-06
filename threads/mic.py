import time
import pyaudio
import wave
# import webrtcvad
from silero_vad import load_silero_vad, read_audio, get_speech_timestamps, VADIterator
import torch
import numpy as np
from scipy.signal import resample

SILERO_VAD_SAMPLE_RATE = 16000

class Microphone:
    def __init__(self, idle_window=2, fs=48000, frame_ms=20):
        self.fs = fs
        self.frame_ms = frame_ms
        self.channels = 1
        self.sample_format = pyaudio.paInt16

        self.samples_per_frame = int(self.fs * self.frame_ms / 1000) #48000 * 20 /1000
        self.chunk = self.samples_per_frame  # CRITICAL
        
        #From 0 to 3 controls the intensity it listens for speech. 3 means it is the strictest when looking for words. 
        #self.vad = webrtc

        #Create Silero VAD model
        self.vad = load_silero_vad()
        #Create iterator to read frames
        # self.vad_iterator = VADIterator(self.vad)

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
        speech_probs = []

        last_voice_time = time.time()
        try:
            while True:
                #1536 is a magic number. This number was derived by 48000 sample rate which we need for our mic / 16000 which the VAD needs = 3
                #And the sample window of 512 that Silero VAD needs. Giving 512*3 = 1536
                #I think that this sample rate is reducing the ability for WhisperSTT to effectively decode though. 
                frame = stream.read(1536, exception_on_overflow=False) 
                frames.append(frame)

                #fs is sampling rate
              
                audio_tensor = self.bytes_to_tensor(frame)
                # print(f"len of audio chunk = {len(frame)}") 
                new_data = resample(audio_tensor, int(len(audio_tensor) * SILERO_VAD_SAMPLE_RATE / self.fs)) #16000 / 48000
                # print("??")
                # print(f"len of audio tensor = {len(new_data)}")

                tensor =  torch.from_numpy(new_data)
                # print(f"len of tensor = {len(tensor)} and tensor: {tensor}")
                speech_prob = self.vad(tensor, SILERO_VAD_SAMPLE_RATE).item()
                print(f"speech_prob: {speech_prob}")

                #If audio is 85% chance to be speech, extend the listen timer.  
                if speech_prob > .85:
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

    def bytes_to_tensor(self, audio_bytes: bytes) -> torch.Tensor:
        # 1. Convert bytes to 16-bit integers
        # prin/t("hi")
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # 2. Convert to float32 and normalize to [-1, 1]
        audio_float32 = int2float(audio_int16)
        # print(2)
        return audio_float32
        # 3. Convert NumPy array to PyTorch tensor
        # return torch.from_numpy(audio_float32)
def int2float(sound):
    abs_max = np.abs(sound).max()
    sound = sound.astype('float32')
    if abs_max > 0:
        sound *= 1/32768
    sound = sound.squeeze()  # depends on the use case
    return sound

if __name__ == "__main__":
    mic = Microphone()
    data = mic.record()
    mic.disconnect()