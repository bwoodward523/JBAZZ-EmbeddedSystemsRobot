#This file will run our main JBAZZ stuff
#JBazz will need his state machine to be implemented as well
#This is our state machine file or main thread

import threading
import time
from transitions import Machine
import events 
from threads.tcp_server import run_client_thread
from threads.tts import tts_thread
class JBAZZ:
    states = ['sleeping', 'listening', 'processing', 'speaking']

    def __init__(self):
        self.machine = Machine(model=self, states=JBAZZ.states, initial='sleeping')

        #Here we handle defining which transitions are valid. 
        self.machine.add_transition('hear_sound', 'sleeping', 'listening')

jbazz = JBAZZ()
 
if __name__ == "__main__":
    print(jbazz.state)

    #Establish the conenction to the server ASAP
    threading.Thread(target=run_client_thread, daemon=True).start()

    #Yeeeeah... I see this. I know. It prevents a race condition with audio libraries. The TCP client starts the microphone and then the TTS gets the speaker ready. They fight. 
    #SOOOOO Sleep one!
    time.sleep(5)
    #Boot thread for Text to speech
    # threading.Thread(target=tts_thread, daemon=True).start()

    #Look for connected display:
    #Start display thread if available.

    while True:
        if not events.event_queue.empty():
            event = events.event_queue.get()
            print(f"{event.source} triggered {event.event_type}")

       