"""
app/container.py

Single source of truth for all shared application objects.
Every component is created exactly once here.
To add a new module, add it here — nothing else changes.
"""

from brain.llm import LLM
from brain.planner import Planner
from brain.reasoner import Reasoner
from brain.reflection import ReflectionEngine
from core.agent import AutonomousAgent
from core.events import EventBus
from core.executor import Executor
from core.workflow import WorkflowEngine
from memory.memory_manager import MemoryManager
from tools.tool_manager import ToolManager
from voice.listen import Listener
from voice.speak import Speaker


class Container:
    """Dependency injection container — builds and holds every shared service."""

    def __init__(self) -> None:

        # ── Memory ────────────────────────────────────────────
        self.memory_manager = MemoryManager()

        # ── Tools ─────────────────────────────────────────────
        self.tool_manager = ToolManager()

        # ── Brain ─────────────────────────────────────────────
        # Planner needs known_tools for plan validation — build after ToolManager
        self.llm       = LLM(self.memory_manager)
        self.reasoner  = Reasoner()
        self.planner   = Planner(known_tools=set(self.tool_manager.tools.keys()))

        # ── Core infrastructure ───────────────────────────────
        self.events = EventBus()

        # Executor gets all three deps injected — build after tools, memory, events
        self.executor = Executor(
            tool_manager   = self.tool_manager,
            memory_manager = self.memory_manager,
            event_bus      = self.events,
        )

        # ReflectionEngine wires planner + executor + memory + events
        self.reflection = ReflectionEngine(
            planner        = self.planner,
            executor       = self.executor,
            memory_manager = self.memory_manager,
            event_bus      = self.events,
        )

        # WorkflowEngine — top-level orchestrator tying everything together
        self.workflow = WorkflowEngine(
            planner        = self.planner,
            executor       = self.executor,
            reflection     = self.reflection,
            memory_manager = self.memory_manager,
            event_bus      = self.events,
        )

        # AutonomousAgent — self-directed intelligence layer
        self.agent = AutonomousAgent(
            workflow       = self.workflow,
            planner        = self.planner,
            executor       = self.executor,
            reflection     = self.reflection,
            llm            = self.llm,
            memory_manager = self.memory_manager,
            tool_manager   = self.tool_manager,
            event_bus      = self.events,
        )

        # ── Voice ─────────────────────────────────────────────
        self.speaker  = Speaker()
        self.listener = Listener()

        # ── Future modules (uncomment as you build them) ──────
        # self.vision         = Vision()
        # self.plugin_manager = PluginManager()
        # self.browser        = Browser()
        # self.github         = GitHub()
        # self.email          = EmailClient()
        # self.calendar       = Calendar()
