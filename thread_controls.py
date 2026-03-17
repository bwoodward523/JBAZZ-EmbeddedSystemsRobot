#This file handles declaration of thread events. These events are different than that of events.py 
#These events allow us to tell threads when they are allowed to perform certain acitons. This allows
#Us to keep certain threads alive without having them constantly trying to perform actions. 

import threading

listen_event = threading.Event()