"""
core/events.py

Lightweight pub/sub event bus for decoupled communication between modules.
"""

from collections import defaultdict
from typing import Callable


class EventBus:
    """
    Simple publish/subscribe event bus.

    Modules subscribe to named events with a callback.
    Other modules emit those events to trigger all registered callbacks.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Register a callback to be invoked when event_name is emitted."""
        self._listeners[event_name].append(callback)

    def emit(self, event_name: str, data=None) -> None:
        """Invoke all callbacks registered for the given event_name."""
        for callback in self._listeners[event_name]:
            callback(data)
