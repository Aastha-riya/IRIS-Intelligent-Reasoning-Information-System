from datetime import datetime


def log(message):

    time = datetime.now().strftime("%H:%M:%S")

    print(f"[{time}] {message}")

class Logger:

    def log(self, message):

        time = datetime.now().strftime("%H:%M:%S")

        print(f"[{time}] {message}")