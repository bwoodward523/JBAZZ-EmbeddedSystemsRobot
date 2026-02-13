from RealtimeTTS import TextToAudioStream, SystemEngine, AzureEngine, ElevenlabsEngine

# print("hello")
class TTS:
    def __init__(self):
        self.engine = SystemEngine() # replace with your TTS engine
        self.stream = TextToAudioStream(self.engine)
        # self.stream.feed("Hello world! How are you today?")
        self.stream.play_async()

    #Function that takes an input string in and speaks the text instantly 
    def speak_string(self, input_text):
        self.stream.feed(input_text)
        self.stream.play_async()

tts = TTS()
while True:
    print("Type text you'd like to hear, press [Enter] to submit: ")
    text = input()
    tts.stream.feed(text)
    tts.stream.play_async()
