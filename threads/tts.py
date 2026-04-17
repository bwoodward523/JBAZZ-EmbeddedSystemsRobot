from RealtimeTTS import TextToAudioStream, SystemEngine#, AzureEngine, ElevenlabsEngine
from data_queues import text_queue, TTS_END_OF_RESPONSE, tts_response_playback_done
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

    
# Use while stream.is_playing somewhere else to prevent code from moving past until done speaking.
def tts_thread(tts: TTS):
    while True:

        def response_tokens():
            while True:
                item = text_queue.get()
                if item is TTS_END_OF_RESPONSE:
                    break
                if isinstance(item, str):
                    yield item + " "
        print(f"Feeding tokens")
        tts.stream.feed(response_tokens())
        tts.stream.play_async(fast_sentence_fragment=False)
        if tts.stream.play_thread is not None:
            tts.stream.play_thread.join()
        tts_response_playback_done.set()




if __name__ == "__main__":
    tts = TTS()
    while True:
        text = input()
        if isinstance(text,str):
            tts.stream.feed(text)
            tts.stream.play_async()