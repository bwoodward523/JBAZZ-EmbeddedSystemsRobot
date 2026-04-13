import socket
import struct
import time
from .tts import TTS
from data_queues import display_queue
from events import post_event, EventType

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
    #Temporary microphhone creation in the TCP client. 
    #TODO: Move mic to JBAZZ once the file is ready to handle the TCP connection
    from .mic import Microphone
    mic = Microphone()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected.")

        counter = 0

        try:
          
            while True:
                while tts_model.stream.is_playing():
                    print(f"Saving the world ")
                    time.sleep(0.1)
                #The mic recording will create an output.wav file when its complete.
                #The mic will continue trying to record if no speech is detected inside of the audio.
                #This is essentially a listen loop
                while not mic.valid_audio:
                    mic.record()
                
                mic.valid_audio = False

                #Grab the data from the output file
                with open("output.wav", "rb") as f:
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
                print(f"size of list {len(response)} | response list = {response}")
                if len(response) == 4:
                    print(response[1])
                    if response[1]:
                        emotion = response[1].split(":")
                        print(f"HERE IS THE EMOTION {emotion[1]}")
                        display_queue.put(emotion[1])
                    else:
                        print("LLM failed to return an emotion")
                       

                    if response[2] == None:
                        print("Model failed to return a text response")

                    if response[3]:
                        print(f"Shoot: {response[3]}")
                        post_event(EventType.FIRE_DART, source="tcp_server")
                    else:
                        print("LLM failed to return shoot signal")

                    if tts_model:
                        #Try to grab text from model
                        words = response[2].split(":")
                        if words:
                            print(f"Words {words}")
                            tts_model.stream.feed(words[1])
                            tts_model.stream.play(log_synthesized_text=True)
                        
                        else:
                            print(f"Error getting text from model")
                            tts_model.stream.feed("error getting returned text from model")
                            tts_model.stream.play(log_synthesized_text=True)
                    else:
                        print("No TTS")
                else:
                    if tts_model:
                        print("List Was not of expected")
                        tts_model.stream.feed("list is not of size 4")
                        tts_model.stream.play()
                    else: 
                        print("List is not of size 4")
                counter += 1
        except KeyboardInterrupt:
            print("\nInterrupted by user.")

        finally:
            print("Closing connection.")
            mic.disconnect()


tts_model = TTS()

if __name__ == "__main__":
    run_client_thread()