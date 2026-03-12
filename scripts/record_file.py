import pyaudio
import wave

# Configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1  # Often 1 for a single mic, but check your device specs
RATE = 44100  # Sample rate (Hz)
RECORD_SECONDS = 5  # Duration of recording
WAVE_OUTPUT_FILENAME = "output.wav"
DEVICE_INDEX = 3  # *** CHANGE THIS to your microphone's index ***

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open stream
print(f"Recording from device index {DEVICE_INDEX}...")
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=DEVICE_INDEX)

frames = []

# Record data in chunks
for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)

# Stop and close the stream
stream.stop_stream()
stream.close()
p.terminate()

print(f"Recording complete. Saving to {WAVE_OUTPUT_FILENAME}...")

# Save the recorded data as a WAV file
wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
wf.setnchannels(CHANNELS)
wf.setsampwidth(p.get_sample_size(FORMAT))
wf.setframerate(RATE)
wf.writeframes(b''.join(frames))
wf.close()

print("File saved.")
