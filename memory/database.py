import json
import os

MEMORY_FILE = "data/memory.json"


class Memory:

    def __init__(self):
        if not os.path.exists("data"):
            os.makedirs("data")

        if not os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "w") as f:
                json.dump([], f)

    def save(self, role, message):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)

        data.append({
            "role": role,
            "content": message
        })

        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def load(self):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)