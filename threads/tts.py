from RealtimeTTS import TextToAudioStream, SystemEngine, AzureEngine, ElevenlabsEngine
from queue import Queue
# print("hello")
class TTS:
    def __init__(self):
        self.engine = SystemEngine() 
        self.stream = TextToAudioStream(self.engine)
        # self.stream.feed("Hello world! How are you today?")

    #Function that takes an input string in and speaks the text instantly 
    def speak_string(self, input_text):
        self.stream.feed(input_text)
        self.stream.play_async()
        
#public queue for others to push to. 
text_queue = Queue()

def tts_thread():
    tts = TTS()
    while True:
        if not text_queue.empty():
            print("consuming text")
            text = text_queue.get()
            if isinstance(text,str):
                tts.stream.feed(text)
                tts.stream.play()

if __name__ == "__main__":
    tts_thread()
