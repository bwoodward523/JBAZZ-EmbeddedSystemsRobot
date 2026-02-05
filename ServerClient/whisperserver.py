import socket
import struct
import numpy as np
from faster_whisper import WhisperModel
import soundfile as sf
import io

import requests
import json 

from ollama_funcs import send_prompt_local

from dia.model import Dia


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

        #Turn the incoming chunk of bytes into a buffer. Then send this buffer to whisper model.
        buffer = io.BytesIO(chunk)
        #Name the buffer as a file so whisper accepts it
        buffer.name = "audio.mp3"

        print("Audio received, transcribing...")

        #Sending the buffer to whisper.
        segments, info = model.transcribe(buffer, language="en")

        #Get the response and turn it into a string
        transcript = " ".join(seg.text.strip() for seg in segments)
        #Send the string back to the client
        #TODO: Update this to send the string instead to Ollama. 

        ollama_resp = send_prompt_local(transcript)


        transcript_bytes = ollama_resp.encode("utf-8")

        tts_model = Dia.from_pretrained("nari-labs/Dia-1.6B-0626")


        # Send transcript back
        conn.sendall(struct.pack("!I", len(transcript_bytes)))
        conn.sendall(transcript_bytes)

        print("Transcript sent")


        text = f"[S1] Hello World"

        output = tts_model.generate(
            text,
            use_torch_compile=False,
            verbose=True,
            cfg_scale=3.0,
            temperature=1.8,
            top_p=0.90,
            cfg_filter_top_k=50,
        )

        tts_model.save_audio("simple.mp3", output)
