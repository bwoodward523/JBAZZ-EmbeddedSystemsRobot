import socket
import struct
import numpy as np
from faster_whisper import WhisperModel
import soundfile as sf
import io


HOST = "0.0.0.0"
PORT = 5555


def recv_all(sock, n):
    data = b""
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
        except ConnectionAbortedError:
            return None
        if not packet:
            return None
        data += packet
    return data


model = WhisperModel("base", device="cuda", compute_type="float16")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print("Listening...")

    conn, addr = s.accept()
    with conn:
        print("Connected:", addr)

        audio_chunks = []

        while True:
            header = recv_all(conn, 4)
            if not header:
                print("Client disconnected")
                break

            size = struct.unpack("!I", header)[0]
            if size == 0:
                break

            chunk = recv_all(conn, size)
            if not chunk:
                print("Client disconnected mid-stream")
                break

            audio_chunks.append(chunk)

        print("Audio received, transcribing...")

        audio_bytes = b"".join(audio_chunks)

    
        with io.BytesIO(audio_bytes) as f:
            data, samplerate = sf.read(f, dtype="float32")  # returns float32 PCM in range [-1, 1]

        # data shape: (num_samples,) for mono, (num_samples, 2) for stereo
        # Whisper expects mono, so convert if needed
        if len(data.shape) > 1:
            data = data.mean(axis=1)  # stereo → mono

        print(f"Audio len {len(audio_bytes)}")
        # Convert bytes → PCM float32
        pcm = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )

        segments, info = model.transcribe(data, language="en")

        transcript = " ".join(seg.text.strip() for seg in segments)
        transcript_bytes = transcript.encode("utf-8")

        for segment in segments:
            print("there are segments")
            print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        # Send transcript back
        conn.sendall(struct.pack("!I", len(transcript_bytes)))
        conn.sendall(transcript_bytes)

        print("Transcript sent")
