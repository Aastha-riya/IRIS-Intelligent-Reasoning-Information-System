from app.startup import Startup
from core.assistant import IrisAssistant


def main():
    container = Startup.initialize()
    iris = IrisAssistant(container)
    iris.start()


if __name__ == "__main__":
    main()
