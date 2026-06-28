import pyttsx3

class Speaker:
    def __init__(self):
        self.engine = pyttsx3.init()

    def speak(self, text):
        self.engine.stop()      # Stops any speech already in progress
        print(f"IRIS: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def stop(self):
        self.engine.stop()
