"""
app/container.py

Single source of truth for all shared application objects.
Every component is created exactly once here.
To add a new module, add it here — nothing else changes.
"""

from brain.llm import LLM
from brain.planner import Planner
from brain.reasoner import Reasoner
from core.events import EventBus
from core.executor import Executor
from memory.memory_manager import MemoryManager
from tools.tool_manager import ToolManager
from voice.listen import Listener
from voice.speak import Speaker


class Container:
    """Dependency injection container — builds and holds every shared service."""

    def __init__(self) -> None:

        # ── Memory ────────────────────────────────────────────
        self.memory_manager = MemoryManager()

        # ── Brain ─────────────────────────────────────────────
        self.llm       = LLM(self.memory_manager)
        self.reasoner  = Reasoner()
        self.planner   = Planner()
        self.executor  = Executor()

        # ── Tools ─────────────────────────────────────────────
        self.tool_manager = ToolManager()

        # ── Voice ─────────────────────────────────────────────
        self.speaker  = Speaker()
        self.listener = Listener()

        # ── Core infrastructure ───────────────────────────────
        self.events = EventBus()

        # ── Future modules (uncomment as you build them) ──────
        # self.vision         = Vision()
        # self.plugin_manager = PluginManager()
        # self.browser        = Browser()
        # self.github         = GitHub()
        # self.email          = EmailClient()
        # self.calendar       = Calendar()
