"""
core/agent.py

The Autonomous Agent — the top-level self-directing intelligence of IRIS.

Single responsibility:
    goal (str)  →  agent loop  →  AgentResult

The AutonomousAgent is the only public-facing entry point for complex,
multi-step tasks. For simple conversational replies, IrisAssistant.start()
is sufficient. For goal-directed autonomous work, use AutonomousAgent.run().

Agent loop (Observe → Reason → Plan → Execute → Reflect → Learn → Repeat):

    User submits goal
        │
        ▼
    OBSERVE     — load context: conversation history + semantic memories
        │
        ▼
    REASON      — classify the goal: direct answer / tool / plan / clarify
        │
        ▼
    PLAN        — decompose complex goals into sub-goals / tasks
        │
        ▼
    EXECUTE     — run tasks via WorkflowEngine
        │
        ▼
    REFLECT     — evaluate outcome
        │
        ▼
    LEARN       — store summaries, failures, successful strategies
        │
        ▼
    Goal complete? ──Yes──► FINISH
        │ No
        └──────────────────► Repeat (up to MAX_AGENT_ITERATIONS)

Decision engine:
    DIRECT      → Answer using LLM only (simple questions, no plan needed)
    TOOL        → A single tool can handle this (calculator, file reader, etc.)
    PLAN        → Complex goal requiring multiple steps → WorkflowEngine
    CLARIFY     → Goal is ambiguous → ask the user for more information

Safety layer:
    - Destructive keyword detection → confirmation required before proceeding
    - Iteration limit → prevents infinite loops
    - Exception isolation → one failed goal never crashes the whole agent

Events published:
    "agent.started"        → data: goal str
    "agent.goal_created"   → data: AgentGoal
    "agent.goal_completed" → data: AgentGoal
    "agent.goal_failed"    → data: AgentGoal
    "agent.paused"         → data: agent
    "agent.resumed"        → data: agent
    "agent.stopped"        → data: agent
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from utils.logger import logger

if TYPE_CHECKING:
    from brain.llm import LLM
    from brain.planner import Planner
    from brain.reflection import ReflectionEngine
    from core.events import EventBus
    from core.executor import Executor
    from core.workflow import WorkflowEngine
    from memory.memory_manager import MemoryManager
    from tools.tool_manager import ToolManager


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_AGENT_ITERATIONS: int = 5   # Max observe-reason-plan-execute loops per goal

# Keywords that flag a goal as potentially destructive
_DESTRUCTIVE_KEYWORDS: tuple = (
    "delete", "remove", "drop", "erase", "wipe", "format",
    "overwrite", "destroy", "purge", "uninstall",
)


# ── Goal model ────────────────────────────────────────────────────────────────

class GoalStatus(str, Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class DecisionType(str, Enum):
    DIRECT  = "direct"    # Answer directly with LLM
    TOOL    = "tool"      # Route to a single tool
    PLAN    = "plan"      # Full workflow with multiple tasks
    CLARIFY = "clarify"   # Ask user for clarification


@dataclass
class AgentGoal:
    """Represents one goal submitted to the agent."""
    goal_id:    str
    text:       str
    status:     GoalStatus   = GoalStatus.PENDING
    decision:   DecisionType = DecisionType.PLAN
    result:     str          = ""
    error:      str          = ""
    iterations: int          = 0
    created_at: str          = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    finished_at: str | None  = None

    def __str__(self) -> str:
        return (
            f"AgentGoal[{self.goal_id[:8]}] "
            f"'{self.text[:50]}' — {self.status.value}"
        )


@dataclass
class AgentResult:
    """Final result returned to the caller after run() completes."""
    goal:       str
    status:     GoalStatus
    output:     str
    decision:   DecisionType
    iterations: int
    error:      str = ""

    def succeeded(self) -> bool:
        return self.status == GoalStatus.COMPLETED

    def __str__(self) -> str:
        return (
            f"AgentResult({self.status.value} | "
            f"decision={self.decision.value} | "
            f"iter={self.iterations} | "
            f"'{self.goal[:50]}')"
        )


# ── Agent state ───────────────────────────────────────────────────────────────

class AgentStatus(str, Enum):
    IDLE    = "idle"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"


# ── Autonomous Agent ──────────────────────────────────────────────────────────

class AutonomousAgent:
    """
    Self-directed AI agent that observes, reasons, plans, executes,
    reflects, and learns to complete goals autonomously.

    All dependencies are optional — the agent degrades gracefully:
        No WorkflowEngine → falls back to LLM direct answer
        No LLM            → returns a structured failure result
        No MemoryManager  → skips context loading and learning
        No ToolManager    → skips tool routing
    """

    def __init__(
        self,
        workflow:       WorkflowEngine  | None = None,
        planner:        Planner         | None = None,
        executor:       Executor        | None = None,
        reflection:     ReflectionEngine | None = None,
        llm:            LLM             | None = None,
        memory_manager: MemoryManager   | None = None,
        tool_manager:   ToolManager     | None = None,
        event_bus:      EventBus        | None = None,
    ) -> None:
        self._workflow  = workflow
        self._planner   = planner
        self._executor  = executor
        self._reflection = reflection
        self._llm       = llm
        self._memory    = memory_manager
        self._tools     = tool_manager
        self._events    = event_bus

        self._status:        AgentStatus         = AgentStatus.IDLE
        self._active_goals:  dict[str, AgentGoal] = {}
        self._goal_history:  list[AgentGoal]      = []

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, goal: str) -> AgentResult:
        """
        Execute a goal through the full autonomous agent loop.

        Steps:
            1. Safety check — flag destructive goals
            2. Create an AgentGoal
            3. OBSERVE — load relevant context from memory
            4. REASON  — classify what kind of response is needed
            5. PLAN/EXECUTE — route to the right handler
            6. REFLECT — evaluate and learn
            7. Return AgentResult

        Args:
            goal: Natural-language goal from the user.

        Returns:
            AgentResult with the final status, output, and metadata.
        """
        if self._status == AgentStatus.STOPPED:
            return AgentResult(
                goal=goal, status=GoalStatus.FAILED,
                output="", decision=DecisionType.DIRECT,
                iterations=0, error="Agent is stopped."
            )

        logger.info(f"Agent: received goal — '{goal[:80]}'")
        self._emit("agent.started", goal)

        # ── Safety check ──────────────────────────────────────────────────────
        if self._is_destructive(goal):
            logger.warning(f"Agent: destructive goal flagged — '{goal[:60]}'")
            return AgentResult(
                goal=goal, status=GoalStatus.FAILED,
                output="",
                decision=DecisionType.CLARIFY,
                iterations=0,
                error=(
                    "This goal contains potentially destructive keywords. "
                    "Please confirm your intent before proceeding."
                ),
            )

        # ── Create goal ───────────────────────────────────────────────────────
        agent_goal = self._create_goal(goal)
        self._emit("agent.goal_created", agent_goal)

        try:
            result = self._agent_loop(agent_goal)
        except Exception as exc:
            logger.exception(f"Agent: unexpected error for goal '{goal[:60]}': {exc}")
            agent_goal.status     = GoalStatus.FAILED
            agent_goal.error      = str(exc)
            agent_goal.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._emit("agent.goal_failed", agent_goal)
            self._store_goal_summary(agent_goal)
            result = AgentResult(
                goal=goal, status=GoalStatus.FAILED,
                output="", decision=agent_goal.decision,
                iterations=agent_goal.iterations, error=str(exc),
            )

        return result

    def step(self) -> str:
        """
        Return a description of what the agent is currently doing.
        Useful for progress monitoring in a UI.
        """
        active = list(self._active_goals.values())
        if not active:
            return "Agent is idle."
        goal = active[0]
        return f"Working on: '{goal.text[:60]}' (iteration {goal.iterations})"

    def stop(self) -> None:
        """Permanently stop the agent. Cannot be restarted."""
        self._status = AgentStatus.STOPPED
        logger.info("Agent: stopped.")
        self._emit("agent.stopped", self)

    def pause(self) -> None:
        """Suspend the agent. Can be resumed."""
        if self._status == AgentStatus.RUNNING:
            self._status = AgentStatus.PAUSED
            logger.info("Agent: paused.")
            self._emit("agent.paused", self)

    def resume(self) -> None:
        """Resume a paused agent."""
        if self._status == AgentStatus.PAUSED:
            self._status = AgentStatus.RUNNING
            logger.info("Agent: resumed.")
            self._emit("agent.resumed", self)

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def active_goal_count(self) -> int:
        return len(self._active_goals)

    # ── Private — agent loop ──────────────────────────────────────────────────

    def _agent_loop(self, agent_goal: AgentGoal) -> AgentResult:
        """
        Main observe → reason → plan → execute → reflect → learn loop.
        Runs up to MAX_AGENT_ITERATIONS times.
        """
        self._status = AgentStatus.RUNNING
        goal = agent_goal.text

        for iteration in range(1, MAX_AGENT_ITERATIONS + 1):

            if self._status == AgentStatus.PAUSED:
                logger.info(f"Agent: paused during iteration {iteration}.")
                break

            agent_goal.iterations = iteration
            logger.info(f"Agent: iteration {iteration}/{MAX_AGENT_ITERATIONS} — '{goal[:60]}'")

            # ── Step 1: OBSERVE ───────────────────────────────────────────────
            context = self._observe(goal)
            logger.debug(f"Agent: context loaded ({len(context)} memories).")

            # ── Step 2: REASON ────────────────────────────────────────────────
            decision = self._reason(goal)
            agent_goal.decision = decision
            logger.info(f"Agent: decision = {decision.value}")

            # ── Step 3: EXECUTE ───────────────────────────────────────────────
            output = self._execute_decision(goal, decision)

            if output is not None:
                # ── Step 4: REFLECT ───────────────────────────────────────────
                self._reflect_and_learn(goal, output, success=True)

                agent_goal.result     = output
                agent_goal.status     = GoalStatus.COMPLETED
                agent_goal.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                self._move_to_history(agent_goal)
                self._emit("agent.goal_completed", agent_goal)

                self._status = AgentStatus.IDLE
                return AgentResult(
                    goal       = goal,
                    status     = GoalStatus.COMPLETED,
                    output     = output,
                    decision   = decision,
                    iterations = iteration,
                )

            # Execution produced no output — try again
            logger.warning(f"Agent: no output on iteration {iteration}, retrying.")
            self._reflect_and_learn(goal, "", success=False)

        # All iterations exhausted
        logger.error(f"Agent: goal failed after {MAX_AGENT_ITERATIONS} iterations.")
        agent_goal.status     = GoalStatus.FAILED
        agent_goal.error      = f"No result after {MAX_AGENT_ITERATIONS} iterations."
        agent_goal.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._move_to_history(agent_goal)
        self._emit("agent.goal_failed", agent_goal)
        self._store_goal_summary(agent_goal)
        self._status = AgentStatus.IDLE

        return AgentResult(
            goal       = goal,
            status     = GoalStatus.FAILED,
            output     = "",
            decision   = agent_goal.decision,
            iterations = MAX_AGENT_ITERATIONS,
            error      = agent_goal.error,
        )

    # ── Private — observe ─────────────────────────────────────────────────────

    def _observe(self, goal: str) -> list[str]:
        """
        Load relevant context from memory for the current goal.
        Returns a list of relevant memory strings.
        """
        if self._memory is None:
            return []
        try:
            return self._memory.retrieve_memory(goal)
        except Exception as e:
            logger.warning(f"Agent: context load failed: {e}")
            return []

    # ── Private — reason ──────────────────────────────────────────────────────

    def _reason(self, goal: str) -> DecisionType:
        """
        Classify the goal into a decision type.

        Heuristics:
            Short question → DIRECT
            Math / file / scan / search keyword → TOOL
            Multi-step / analyse / generate / create → PLAN
            Vague/ambiguous → CLARIFY
        """
        lowered = goal.lower().strip()

        # Tool keywords
        tool_triggers = (
            "calculate", "compute", "+", "-", "*", "/",
            "read file", "read ", "scan ", "search ",
        )
        if any(t in lowered for t in tool_triggers):
            return DecisionType.TOOL

        # Plan keywords
        plan_triggers = (
            "analyse", "analyze", "create", "generate", "build",
            "write", "summarise", "summarize", "plan", "design",
            "develop", "implement", "research",
        )
        if any(t in lowered for t in plan_triggers):
            return DecisionType.PLAN

        # Clarification needed
        if len(lowered) < 5 or lowered in ("?", "help", "what", "how"):
            return DecisionType.CLARIFY

        # Default to direct LLM answer
        return DecisionType.DIRECT

    # ── Private — execute decision ────────────────────────────────────────────

    def _execute_decision(self, goal: str, decision: DecisionType) -> str | None:
        """
        Route the goal to the appropriate handler based on the decision.
        Returns output string on success, None on failure.
        """
        if decision == DecisionType.CLARIFY:
            return (
                "I need more information to help with that. "
                "Could you please provide more detail?"
            )

        if decision == DecisionType.TOOL:
            return self._run_tool(goal)

        if decision == DecisionType.PLAN:
            return self._run_workflow(goal)

        # DIRECT — LLM answer
        return self._run_llm(goal)

    def _run_llm(self, goal: str) -> str | None:
        """Ask the LLM directly and return its response."""
        if self._llm is None:
            logger.warning("Agent: no LLM available for direct answer.")
            return None
        try:
            response = self._llm.chat(goal)
            logger.info("Agent: LLM response received.")
            return response
        except Exception as e:
            logger.exception(f"Agent: LLM call failed: {e}")
            return None

    def _run_tool(self, goal: str) -> str | None:
        """Route the goal to ToolManager. Falls back to LLM if no tool matches."""
        if self._tools is not None:
            try:
                result = self._tools.execute(goal)
                if result is not None:
                    logger.info("Agent: tool executed successfully.")
                    return str(result)
            except Exception as e:
                logger.exception(f"Agent: tool execution failed: {e}")

        # No tool matched — fall back to LLM
        logger.debug("Agent: no tool matched, falling back to LLM.")
        return self._run_llm(goal)

    def _run_workflow(self, goal: str) -> str | None:
        """Run a full multi-step workflow via WorkflowEngine."""
        if self._workflow is None:
            logger.warning("Agent: no WorkflowEngine — falling back to LLM.")
            return self._run_llm(goal)
        try:
            wf_result = self._workflow.run(goal)
            if wf_result.succeeded() and wf_result.plan:
                # Collect completed task outputs as the final answer
                outputs = [
                    t.output_text
                    for t in wf_result.plan.completed_tasks()
                    if t.output_text
                ]
                summary = "\n".join(outputs) if outputs else f"Goal '{goal}' completed."
                logger.info("Agent: workflow completed.")
                return summary
            logger.warning(f"Agent: workflow did not succeed: {wf_result.error}")
            return None
        except Exception as e:
            logger.exception(f"Agent: workflow error: {e}")
            return None

    # ── Private — reflect and learn ───────────────────────────────────────────

    def _reflect_and_learn(self, goal: str, output: str, success: bool) -> None:
        """Store execution outcome to memory for future learning."""
        if self._memory is None:
            return
        try:
            status_label = "SUCCESS" if success else "FAILURE"
            entry = (
                f"[AGENT {status_label}] Goal: '{goal[:80]}' | "
                f"Output: '{output[:120]}'"
            )
            self._memory.store_memory(entry)
            logger.debug(f"Agent: learned from {status_label.lower()} experience.")
        except Exception as e:
            logger.warning(f"Agent: could not store learning: {e}")

    def _store_goal_summary(self, agent_goal: AgentGoal) -> None:
        """Persist a full goal summary to memory after failure."""
        if self._memory is None:
            return
        try:
            entry = (
                f"[AGENT GOAL] '{agent_goal.text[:80]}' | "
                f"Status: {agent_goal.status.value} | "
                f"Iterations: {agent_goal.iterations} | "
                f"Decision: {agent_goal.decision.value}"
            )
            if agent_goal.error:
                entry += f" | Error: {agent_goal.error[:100]}"
            self._memory.store_memory(entry)
        except Exception as e:
            logger.warning(f"Agent: could not store goal summary: {e}")

    # ── Private — goal management ─────────────────────────────────────────────

    def _create_goal(self, text: str) -> AgentGoal:
        goal = AgentGoal(goal_id=str(uuid.uuid4()), text=text)
        self._active_goals[goal.goal_id] = goal
        return goal

    def _move_to_history(self, agent_goal: AgentGoal) -> None:
        self._active_goals.pop(agent_goal.goal_id, None)
        self._goal_history.append(agent_goal)

    # ── Private — safety layer ────────────────────────────────────────────────

    @staticmethod
    def _is_destructive(goal: str) -> bool:
        """Return True if the goal contains destructive keywords."""
        lowered = goal.lower()
        return any(kw in lowered for kw in _DESTRUCTIVE_KEYWORDS)

    # ── Private — event bus ───────────────────────────────────────────────────

    def _emit(self, event_name: str, data: object = None) -> None:
        if self._events is None:
            return
        try:
            self._events.emit(event_name, data)
        except Exception as e:
            logger.warning(f"Agent: event '{event_name}' emit failed: {e}")
