import socket
import struct
import time

HOST = "127.0.0.1"
PORT = 5555

def recv_exact(sock, n):
    buffer = b''
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            return None
        buffer += chunk
    return buffer


def send_message(sock, payload: bytes):
    header = struct.pack("!I", len(payload))
    sock.sendall(header)
    sock.sendall(payload)


def recv_message(sock):
    header = recv_exact(sock, 4)
    if header is None:
        return None

    length = struct.unpack("!I", header)[0]
    return recv_exact(sock, length)


def run_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected.")

        counter = 0

        try:
            while True:
                msg = f"Message {counter}"
                send_message(s, msg.encode("utf-8"))

                payload = recv_message(s)
                if payload is None:
                    print("Server closed connection.")
                    break

                response = payload.decode("utf-8")
                print("Server:", response)

                counter += 1
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")

        finally:
            print("Closing connection.")


if __name__ == "__main__":
    run_client()
