from brain.llm import LLM
from voice.speak import Speaker
from voice.listen import Listener
from tools.tool_manager import ToolManager
from core.assistant import IrisAssistant
from app.startup import Startup


tools = ToolManager()
brain = LLM()
speaker = Speaker()
listener = Listener()

def main():

    container = Startup.initialize()

    iris = IrisAssistant(container)

    iris.start()


def main():
    services = Startup.initialize()

    iris = IrisAssistant(services)

    iris.start()





def main():
    assistant = IrisAssistant()
    assistant.run()


if __name__ == "__main__":
    main()


print("🤖 IRIS is Online!")

mode = input("\nChoose (type/speak): ").strip().lower()

voice_mode = mode in ["2", "speak", "s", "voice"]

while True:

    if voice_mode:
        user = listener.listen()
    else:
        user = input("You: ")

    if not user:
        continue

    if user.lower() == "exit":
        speaker.speak("Goodbye!")
        break

    tool_result = tools.execute(user)

    if tool_result:
        speaker.speak(tool_result)
        continue


    reply = brain.chat(user)
    speaker.speak(reply)