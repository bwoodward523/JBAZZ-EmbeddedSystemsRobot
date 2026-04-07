from RealtimeTTS import TextToAudioStream, SystemEngine
import numpy as np
# import scipy.signal as signal

# 1. Set up engine
engine = SystemEngine(print_installed_voices=True)
stream = TextToAudioStream(engine)

# 2. Define your target sample rate
TARGET_RATE = 22050  # Example: 22.05 kHz

# # 3. Create a callback to process audio
# def on_audio_chunk_callback(chunk):
#     # Convert incoming chunk to numpy array (assuming 16-bit PCM)
#     audio_data = np.frombuffer(chunk, dtype=np.int16)
    
#     # Resample the chunk
#     # (Requires estimation of ratio if stream rate isn't fixed, 
#     # but for simple rate changes, linear interpolation works)
#     number_of_samples = int(len(audio_data) * TARGET_RATE / engine.rate)
#     resampled_chunk = signal.resample(audio_data, number_of_samples)
    
#     # Convert back to bytes for playing
#     processed_chunk = resampled_chunk.astype(np.int16).tobytes()
    
#     # Optionally: send to websocket or handle elsewhere
#     # print(f"Processing chunk, new length: {len(processed_chunk)}")

# # 4. Play with callback
stream.feed("Hello, this is a real-time speech test.")
stream.play_async()