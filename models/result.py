"""
models/result.py

TaskResult — the standardised output of every tool execution.

────────────────────────────────────────────────────────────────────────────────
Why does this exist?
────────────────────────────────────────────────────────────────────────────────

Without TaskResult, every module that calls a tool must handle different types:

    calculator  → int   (42)
    file_reader → str   ("file contents…")
    internet    → dict  ({"title": "…", "url": "…"})
    llm         → str   ("Here is the answer…")

The Executor, Reflection engine, and Memory system would each need special
cases for every tool. That's fragile and hard to extend.

With TaskResult, every tool returns one consistent shape:

    result.success          → True / False
    result.output           → the actual value (any type — see below)
    result.error            → error message or None
    result.tool             → which tool produced this
    result.execution_time   → seconds taken
    result.metadata         → extra structured information
    result.timestamp        → when the result was created

Now every downstream module (Executor, Reflection, Memory, Planner) can
check result.success and act accordingly — without caring which tool ran.

────────────────────────────────────────────────────────────────────────────────
Design decision: output is typed Any, not str
────────────────────────────────────────────────────────────────────────────────

Can every tool return only text? No.
    - Calculator produces numbers  (42, 3.14)
    - Internet search returns dicts or lists of results
    - Project scanner returns a list of file paths
    - Future vision tools may return image objects or numpy arrays

Forcing str would require every tool to stringify its result immediately,
discarding structure that Reflection, Memory, and the Planner need.

output: Any  preserves the raw value.
to_str()     converts to text when display is needed.

────────────────────────────────────────────────────────────────────────────────
Usage
────────────────────────────────────────────────────────────────────────────────

Successful result:
    result = TaskResult.success_result(
        output=42,
        tool="calculator",
        execution_time=0.02,
    )

Failed result:
    result = TaskResult.failure_result(
        error="File not found",
        tool="file_reader",
        execution_time=0.01,
    )

Downstream consumption (Executor, Reflection):
    if result.success:
        memory.store(result.to_str())
    else:
        logger.error(result.error)
        retry_or_skip(task)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _now() -> str:
    """Return the current time as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class TaskResult:
    """
    Standardised output of a single task execution.

    Every tool and every LLM call returns a TaskResult so that
    Executor, Reflection, Memory, and Planner always work with
    the same structure regardless of which tool ran.

    Attributes:
        success:        True if the task completed without error.
        output:         The actual result value.
                        Typed Any — tools return numbers, strings, dicts, lists, etc.
                        Use to_str() when you need a text representation.
        error:          Human-readable error message, or None on success.
        tool:           Name of the tool or handler that produced this result.
        execution_time: Wall-clock seconds the execution took (float).
        metadata:       Optional structured extra data (e.g. token counts,
                        file paths, search result count). Defaults to {}.
        timestamp:      ISO-style string of when this result was created.
    """

    success:        bool
    output:         Any             = None
    error:          str | None      = None
    tool:           str             = "unknown"
    execution_time: float           = 0.0
    metadata:       dict            = field(default_factory=dict)
    timestamp:      str             = field(default_factory=_now)

    # ── Display ───────────────────────────────────────────────────────────────

    def to_str(self) -> str:
        """
        Return a text representation of the output suitable for display,
        logging, or injection into a prompt.

        - None        → empty string
        - str         → returned as-is
        - everything else → str(output)
        """
        if self.output is None:
            return ""
        if isinstance(self.output, str):
            return self.output
        return str(self.output)

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        tool   = self.tool or "unknown"
        time   = f"{self.execution_time:.3f}s"
        if self.success:
            preview = repr(self.output)[:80]
            return f"TaskResult({status} {tool} | {time} | output={preview})"
        return f"TaskResult({status} {tool} | {time} | error={self.error!r})"

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def success_result(
        cls,
        output: Any,
        tool:           str   = "unknown",
        execution_time: float = 0.0,
        metadata:       dict  | None = None,
    ) -> TaskResult:
        """
        Construct a successful TaskResult.

        Args:
            output:         The value produced by the tool (any type).
            tool:           Name of the tool that ran.
            execution_time: Seconds taken.
            metadata:       Optional extra data dict.

        Example:
            result = TaskResult.success_result(
                output=42,
                tool="calculator",
                execution_time=0.02,
            )
        """
        return cls(
            success        = True,
            output         = output,
            error          = None,
            tool           = tool,
            execution_time = execution_time,
            metadata       = metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error:          str,
        tool:           str   = "unknown",
        execution_time: float = 0.0,
        metadata:       dict  | None = None,
    ) -> TaskResult:
        """
        Construct a failed TaskResult.

        Args:
            error:          Human-readable description of what went wrong.
            tool:           Name of the tool that failed.
            execution_time: Seconds taken before failure.
            metadata:       Optional extra data dict.

        Example:
            result = TaskResult.failure_result(
                error="File not found: /path/to/file.txt",
                tool="file_reader",
                execution_time=0.01,
            )
        """
        return cls(
            success        = False,
            output         = None,
            error          = error,
            tool           = tool,
            execution_time = execution_time,
            metadata       = metadata or {},
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """
        Serialise to a JSON-compatible dict.

        Note: output is converted to str via to_str() because arbitrary
        Python objects (numpy arrays, custom classes) are not JSON-serialisable.
        Store the raw output in memory; use to_dict() only for logging/persistence.
        """
        return {
            "success":        self.success,
            "output":         self.to_str(),
            "error":          self.error,
            "tool":           self.tool,
            "execution_time": round(self.execution_time, 4),
            "metadata":       self.metadata,
            "timestamp":      self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskResult:
        """Deserialise from a persisted dict (output will be a string)."""
        return cls(
            success        = bool(data.get("success", False)),
            output         = data.get("output"),
            error          = data.get("error"),
            tool           = data.get("tool", "unknown"),
            execution_time = float(data.get("execution_time", 0.0)),
            metadata       = dict(data.get("metadata", {})),
            timestamp      = data.get("timestamp", _now()),
        )
