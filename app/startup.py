
from app.container import ServiceContainer
from brain.llm import LLM
from voice.speak import Speaker
from core.events import EventBus


from tools.tool_manager import ToolManager

from voice.listen import Listener



class Startup:

    @staticmethod
    def initialize():
        container = ServiceContainer()

        container.register("brain", LLM())
        container.register("speaker", Speaker())
        container.register("listener", Listener())
        container.register("tools", ToolManager())
        container.register("events", EventBus())
        return container