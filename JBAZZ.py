#This file will run our main JBAZZ stuff
#JBazz will need his state machine to be implemented as well
#This is our state machine file or main thread

import os
import signal
import threading
import time

# Raspberry Pi Connect (wayvnc) runs Wayland; set DISPLAY so OpenCV windows work
os.environ.setdefault("DISPLAY", ":0")

from transitions import Machine
from events import * 
from threads.tcp_server import run_client_thread
from threads.tcp_server_sim import sim_run_client_thread
from threads.mic import Microphone
from threads.tts import TTS
from threads.display import show_emotions_thread
from thread_controls import listen_event, camera_servo_stop_event, fire_event



EVENT_TO_TRIGGER = {
    EventType.WAKE_UP_DETECTED:   'scan',
    EventType.PERSON_DETECTED:    'track',
    EventType.PERSON_LOST:        'rescan',
    EventType.FIRE_DART:          'fire_dart',
    EventType.FINISHED_SHOOTING:  'resume',
}

class JBAZZ:
    states = ['sleeping', 'scanning', 'tracking', 'firing']

    def __init__(self):
        self.machine = Machine(model=self, states=JBAZZ.states, initial='sleeping')

        self.machine.add_transition('scan',      'sleeping',              'scanning')
        self.machine.add_transition('track',     'scanning',              'tracking')
        self.machine.add_transition('rescan',    ['tracking', 'firing'],  'scanning')
        self.machine.add_transition('sleep',     ['scanning', 'tracking'], 'sleeping',
                                    before='_stop_camera_thread')
        self.machine.add_transition('fire_dart', 'tracking',              'firing')
        self.machine.add_transition('resume',    'firing',                'tracking')

        self._camera_thread: threading.Thread | None = None

    def _stop_camera_thread(self):
        camera_servo_stop_event.set()
        if self._camera_thread and self._camera_thread.is_alive():
            self._camera_thread.join(timeout=2.0)
        self._camera_thread = None

    def on_enter_scanning(self):
        # Start the thread only if it isn't already running.
        # On the sleeping→scanning transition it won't exist yet.
        # On tracking/firing→scanning (PERSON_LOST) the thread is still alive.
        if self._camera_thread is None or not self._camera_thread.is_alive():
            camera_servo_stop_event.clear()
            self._camera_thread = threading.Thread(
                target=run_camera_servo_thread,
                args=(camera_servo_stop_event,),
                daemon=True,
            )
            self._camera_thread.start()
            print("[JBAZZ] camera+servo thread started")

    def on_enter_tracking(self):
        # Thread is already running; it switched to TRACKING mode internally.
        print("[JBAZZ] now tracking person")

    def on_enter_firing(self):
        # Signal the camera/servo thread to fire a dart.
        # The thread calls mc.fire() then posts FINISHED_SHOOTING.
        print("[JBAZZ] firing dart")
        fire_event.set()

    def on_enter_sleeping(self):
        print("[JBAZZ] sleeping")

jbazz = JBAZZ()

if __name__ == "__main__":
    # --- Feature flags: set to False to skip that subsystem ---
    ENABLE_SERVO_TEST       = False  # run servo/motor test sequence then continue
    ENABLE_TCP              = True  # TCP server / audio pipeline
    ENABLE_DISPLAY          = True  # LED emotion display
    ENABLE_CAMERA_TRACKING  = True   # camera + servo tracking state machine
    sim_tcp                 = False   # True = use simulated TCP (no real server needed)
    ENABLE_MOTORS           = False

    if ENABLE_SERVO_TEST:
        from MotorControllerInterface.motor_controller import MotorController
        print("[SERVO TEST] Running servo/motor test sequence...")
        with MotorController() as mc:
            mc.wake()
            mc.test()
            mc.sleep()
        print("[SERVO TEST] Done.")

    # --- Graceful shutdown on Ctrl+C or kill signal ---
    _shutting_down = threading.Event()
    
    def _shutdown():
        if ENABLE_MOTORS:
            print("[JBAZZ] Shutting down...")
            camera_servo_stop_event.set()
            if jbazz._camera_thread and jbazz._camera_thread.is_alive():
                jbazz._camera_thread.join(timeout=5.0)
            # Safety net: send MCU to safe state in case the thread's finally block failed
            try:
                from MotorControllerInterface.motor_controller import MotorController
                with MotorController() as mc:
                    mc.motors_off()
                    mc.sleep()   # homes servos + PWM off
            except Exception as e:
                print(f"[JBAZZ] MCU shutdown error: {e}")
            print("[JBAZZ] Shutdown complete.")

    def _handle_signal(sig, frame):
        _shutting_down.set()

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    def _run_fire_sequence():
        from MotorControllerInterface.motor_controller import (
            MotorController, SERVO_PUSHER, motor_controller_available, DEFAULT_PORT
        )
        try:
            if not motor_controller_available(DEFAULT_PORT):
                print("[FIRE] STM32 not found, skipping.")
                return

            print("[FIRE] Starting fire sequence...")
            with MotorController() as mc:
                print("[FIRE] Waking...")
                if not mc.wake():
                    print("[FIRE] Wake failed, aborting.")
                    return
                time.sleep(0.3)

                print("[FIRE] Motors on...")
                mc.motors_on()

                print("[FIRE] Waiting 2s for spin-up...")
                time.sleep(2)

                print("[FIRE] Pusher to start (3,0)...")
                mc.set_angle(SERVO_PUSHER, 0)

                print("[FIRE] Waiting 2s for servo travel...")
                time.sleep(2)

                print("[FIRE] Pusher forward (3,180)...")
                mc.set_angle(SERVO_PUSHER, 180)

                print("[FIRE] Waiting 0.5s...")
                time.sleep(0.5)

                print("[FIRE] Motors off...")
                mc.motors_off()

            print("[FIRE] Done.")
        except Exception as e:
            print(f"[FIRE] Error during fire sequence: {e}")
        finally: #I did this try finally because more thread safe but it looks dumb
            post_event(EventType.FINISHED_SHOOTING, source="fire_sequence")  # always resumes tracking, thread exits

    def _manual_fire_thread():
        if ENABLE_MOTORS:

            print("[JBAZZ] Press ENTER at any time to fire a dart.")
            while not _shutting_down.is_set():
                try:
                    input()
                    if jbazz.state == 'tracking':
                        print("[JBAZZ] Manual fire triggered!")
                        post_event(EventType.FIRE_DART, source="manual")
                    elif jbazz.state in ('scanning', 'firing'):
                        # Fire directly via the camera thread's fire_event so it works
                        # even if the state machine isn't in tracking yet
                        print(f"[JBAZZ] Manual fire triggered (state={jbazz.state}, firing directly)")
                        fire_event.set()
                    else:
                        print(f"[JBAZZ] Can't fire — state is '{jbazz.state}'")
                except EOFError:
                    break
    if ENABLE_MOTORS:
        threading.Thread(target=_manual_fire_thread, daemon=True).start()
    if ENABLE_CAMERA_TRACKING:
        from threads.camera_servo_thread import run_camera_servo_thread
        print(jbazz.state)

        if ENABLE_TCP:
            if not sim_tcp:
                from threads.tcp_server import run_client_thread
                threading.Thread(target=run_client_thread, daemon=True).start()
            else:
                from threads.tcp_server_sim import sim_run_client_thread
                threading.Thread(target=sim_run_client_thread, daemon=True).start()

        if ENABLE_DISPLAY:
            from threads.display import show_emotions_thread
            threading.Thread(target=show_emotions_thread, daemon=True).start()

        # Kick off scanning immediately on startup
        post_event(event_type=EventType.WAKE_UP_DETECTED, source="startup")

        while not _shutting_down.is_set():
            if not event_queue.empty():
                event = event_queue.get()
                print(f"{event.source} triggered {event.type}")
                if event.type in EVENT_TO_TRIGGER and EVENT_TO_TRIGGER[event.type] in jbazz.machine.get_triggers(jbazz.state):
                    getattr(jbazz, EVENT_TO_TRIGGER[event.type])()
                    print(f"State: {jbazz.state}")
                    if event.type == EventType.FIRE_DART and ENABLE_MOTORS:
                        threading.Thread(target=_run_fire_sequence, daemon=True).start()

    _shutdown()
