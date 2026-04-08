from RealtimeTTS import TextToAudioStream, SystemEngine, AzureEngine, ElevenlabsEngine
from queue import Queue
from data_queues import text_queue
# print("hello")
class TTS:
    def __init__(self):
        self.engine = SystemEngine(voice="en-us-nyc",print_installed_voices=False) 
        self.stream = TextToAudioStream(self.engine, )
        # print(f"voices: {self.engine.get_voices()}")
        # self.stream.feed("Hello world! How are you today?")

    #Function that takes an input string in and speaks the text instantly 
    #This only works if ur awesome. Dont use it. I'm not awesome.
    def speak_string(self, input_text):
        self.stream.feed(input_text)
        # import time
        # time.sleep(.5)
        self.stream.play()

    
#Use while stream.is_playing somewhere else to prevent code from moving past Until done speaking. 
def tts_thread(tts : TTS):
    #Enable async play right away
    tts.stream.play_async(fast_sentence_fragment=False)

    #Poll the text queue infinitely.
    while True:

        #This is a blocking call until data is provided.
        text = text_queue.get()
        # print(f"Data from the text_queue: {text} and type is {type(text)}")
        if type(text)== str:

            tts.stream.feed(text)



# def tts_thread():
#     tts = TTS()
#     while True:
#         if not text_queue.empty():
#             print("consuming text")
#             text = text_queue.get()
#             if isinstance(text,str):
#                 tts.stream.feed(text)
#                 tts.stream.play_async()




if __name__ == "__main__":
    tts = TTS()
    while True:
        text = input()
        if isinstance(text,str):
            tts.stream.feed(text)
            tts.stream.play_async()