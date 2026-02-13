import socket
import struct

HOST = "127.0.0.1"
PORT = 5555



def setup_microphone():
    import RPi.GPIO as GPIO

    MicPin = 3
    RelayPin = 4

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(MicPin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(RelayPin, GPIO.OUT, initial=GPIO.LOW)

    while True:
        GPIO.output(LedPin, GPIO.input(MicPin))

# Fake audio for now
with open("test.mp3", "rb") as f:
    audio = f.read()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    # Send audio
    s.sendall(struct.pack("!I", len(audio)))
    s.sendall(audio)

    # End-of-stream marker
    s.sendall(struct.pack("!I", 0))

    # IMPORTANT: half-close write side
    s.shutdown(socket.SHUT_WR)

    # Receive transcript
    header = s.recv(4)
    if not header:
        raise RuntimeError("Server closed without response")

    text_len = struct.unpack("!I", header)[0]

    data = b""
    while len(data) < text_len:
        chunk = s.recv(text_len - len(data))
        if not chunk:
            raise RuntimeError("Connection closed early")
        data += chunk

    transcript = data.decode("utf-8")
    print("\n--- TRANSCRIPT ---")
    print(transcript)