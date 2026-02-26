"""Observer protocol and implementations."""

from __future__ import annotations
from typing import Protocol
from structured_agents.events.types import Event


class Observer(Protocol):
    """Receives agent lifecycle events with single emit method."""

    async def emit(self, event: Event) -> None: ...


class NullObserver:
    """No-op observer that discards all events."""

    async def emit(self, event: Event) -> None:
        pass
