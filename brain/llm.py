import ollama
from config.settings import MODEL_NAME, SYSTEM_PROMPT
from memory.database import Memory


class LLM:

    def __init__(self):
        self.memory = Memory()

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        self.messages.extend(self.memory.load())

    def chat(self, prompt):

        self.messages.append({
            "role": "user",
            "content": prompt
        })

        self.memory.save("user", prompt)

        response = ollama.chat(
            model=MODEL_NAME,
            messages=self.messages
        )

        reply = response["message"]["content"]

        self.messages.append({
            "role": "assistant",
            "content": reply
        })

        self.memory.save("assistant", reply)

        return reply