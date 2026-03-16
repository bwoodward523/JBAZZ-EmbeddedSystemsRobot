from RealtimeTTS import TextToAudioStream, SystemEngine, AzureEngine, ElevenlabsEngine

# print("hello")
class TTS:
    def __init__(self):
        self.engine = SystemEngine() 
        self.stream = TextToAudioStream(self.engine)
        # self.stream.feed("Hello world! How are you today?")
        self.stream.play_async()

    #Function that takes an input string in and speaks the text instantly 
    def speak_string(self, input_text):
        self.stream.feed(input_text)
        self.stream.play_async()

def tts_thread():
    tts = TTS()
    while True:
        print("Type text you'd like to hear, press [Enter] to submit: ")
        text = input()
        tts.stream.feed("Hi")
        tts.stream.play_async()
if __name__ == "__main__":
    tts = TTS()
    while True:
        print("Type text you'd like to hear, press [Enter] to submit: ")
        text = input()
        tts.stream.feed(text)
        tts.stream.play_async()
        # tts.speak_string(input)
