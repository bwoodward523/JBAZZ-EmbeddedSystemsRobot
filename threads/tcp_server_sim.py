def sim_run_client_thread():
    from data_queues import display_queue
    import time
    import random

    while True:
        emotions = ["happiness","surprise","fear","disgust","sadness","anger"]

        print("Fake Audio Recording")
        time.sleep(2)

        #sim trigger for shoot
        shoot = bool(random.getrandbits(1))

        #Sim display result
        display_queue.put(random.choice(emotions))
        
        #Speaker and Microphone are faked in this thread.
        print("Fake Speaker output")
        time.sleep(2)

