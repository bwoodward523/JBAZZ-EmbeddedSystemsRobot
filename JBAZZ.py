#This file will run our main JBAZZ stuff
#JBazz will need his state machine to be implemented as well
#This is our state machine file or main thread

import threading
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

        

if __name__ == "__main__":
    jbazz = JBAZZ()
    print(jbazz.state)

    #Establish the conenction to the server ASAP
    threading.Thread(target=run_client_thread, daemon=True).start()
    #Boot thread for Text to speech
    threading.Thread(target=tts_thread, daemon=True).start()
    print("?")
