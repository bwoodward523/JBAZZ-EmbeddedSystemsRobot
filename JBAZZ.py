#This file will run our main JBAZZ stuff
#JBazz will need his state machine to be implemented as well
#This is our state machine file or main thread

import threading
import time
from transitions import Machine
from events import * 
from threads.tcp_server import run_client_thread
from threads.tcp_server_sim import sim_run_client_thread
from threads.mic import Microphone
from threads.tts import TTS
from threads.display import show_emotions_thread
from thread_controls import listen_event


EVENT_TO_TRIGGER = {
    EventType.WAKE_UP_DETECTED: 'listen',
    EventType.SEND_TO_SLEEP: 'sleep',
    EventType.FINISHED_LISTENING: 'sleep'
}

class JBAZZ:
    states = ['sleeping', 'listening', 'processing', 'speaking']

    def __init__(self):
        # self.mic = Microphone()
        # self.tts = TTS()
        self.machine = Machine(model=self, states=JBAZZ.states, initial='sleeping')

        #Here we handle defining which transitions are valid. 
        self.machine.add_transition('listen', 'sleeping', 'listening')
        self.machine.add_transition('sleep', 'listening', 'sleeping')

    def on_enter_listening(self):
        # threading.Thread(target=self.mic.record_mic_thread, daemon=True).start()
        pass
    def on_exit_listening(self):
        print("finsihed listening")
        # dipslay_queue('thinking face')

jbazz = JBAZZ()
 
if __name__ == "__main__":
    print(jbazz.state)
    post_event(event_type=EventType.WAKE_UP_DETECTED, source="Test Skip")
    post_event(event_type=EventType.SEND_TO_SLEEP, source="Test Skip")

    #Establish the conenction to the server ASAP
    print("hello")
    sim_tcp = True
    if not sim_tcp:
        threading.Thread(target=run_client_thread, daemon=True).start() 
    else:
        threading.Thread(target=sim_run_client_thread, daemon=True).start() 

    #TODO: Look for connected display
    #Start display thread if available.
    threading.Thread(target=show_emotions_thread, daemon=True).start()


    while True:
        if not event_queue.empty():
            event = event_queue.get()
            print(f"{event.source} triggered {event.type}")
            #Determine if the event can be triggered and then trigger it from the event trigger map
            if event.type in EVENT_TO_TRIGGER and EVENT_TO_TRIGGER[event.type] in jbazz.machine.get_triggers(jbazz.state):
                getattr(jbazz, EVENT_TO_TRIGGER[event.type])()
                print(f"Event successfully triggered: {event.type} by {event.source}")
        