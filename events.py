#This file will hold the definitions of the events that threads can trigger
#For example the TCP server thread may trigger an event like sent_data or received_data

from enum import Enum, auto
from dataclasses import dataclass
from queue import Queue 

class EventType(Enum):
    WAKE_UP_DETECTED = auto()
    FINISHED_LISTENING = auto()
    AUDIO_SENT_TO_SERVER = auto()
    AUDIO_RECEIVED_FROM_SERVER = auto()
    SERVER_ERROR = auto()
    FINISHED_SPEAKING = auto()
    FINISHED_SHOOTING = auto()

# Event container
@dataclass
class Event:
    type: EventType
    data: dict | None = None
    source: str | None = None

event_queue = Queue()

def post_event(event_type, data = None, source=None):
    e = Event(event_type, data, source)
    print(f"Added event {e}")
    event_queue.put(e)