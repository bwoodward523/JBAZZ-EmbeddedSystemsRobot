import socket
import struct
import time
from .tts import text_queue
from .mic import Microphone


HOST = "10.127.70.21"
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


def run_client_thread():
    print("Starting microphone")
    mic = Microphone()
    print("I am running")
    #Temporary microphhone creation in the TCP client. 
    #TODO: Move mic to JBAZZ once the file is ready to handle the TCP connection
    print("hello")
    print("socket?")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected.")

        counter = 0

        try:
            while True:
                # msg = f"Message {counter}"

                #The mic recording will create an output.wav file when its complete.
                #The mic will continue trying to record if no speech is detected inside of the audio.
                #This is essentially a listen loop
                while not mic.valid_audio:
                    mic.record()
                
                mic.valid_audio = False

                #Grab the data from the output file
                with open("./output.wav", "rb") as f:
                    audio = f.read()

                #Send the data to the TCP server.
                send_message(s, audio)

                payload = recv_message(s)
                if payload is None:
                    print("Server closed connection.")
                    break

                response = payload.decode("utf-8")
                print("Server:", response)
                
                #Parse server output. LLM is told to delimit by !@#$ because it needs to be something the AI would not generate in conversation
                response = response.split('!@#$')
                #Ensure we have three items in our returned message from the server before we try and operate 
                if len(response) == 3:
                    print(response[1])
                    if response[0]:
                        print(f"Emotion: {response[0]}")
                    else:
                        print("LLM failed to return an emotion")

                    if response[1] == None:
                        print("Model failed to return a text response")

                    if response[2]:
                        print(f"Shoot: {response[2]}")
                    else:
                        print("LLM failed to return an emotion")

                    if text_queue is not None:
                        #Try to grab text from model
                        words = response[1].split(":")
                        if words:
                            text_queue.put(words[1])
                        else:
                            text_queue.put("error getting returned text from model")
                    else:
                        print("No TTS")
                else:
                    if text_queue is not None:
                        text_queue.put("list is not of size 3")
                    else: 
                        print("List is not of size 3")
                counter += 1
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
        except Exception as e:
            print(f"Error with the server thread {e}")
        finally:
            print("Closing connection.")
            mic.disconnect()

if __name__ == "__main__":
    run_client_thread()
