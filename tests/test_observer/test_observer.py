"""Tests for the observer system."""

import pytest

from structured_agents.observer import (
    CompositeObserver,
    ModelRequestEvent,
    NullObserver,
)


class RecordingObserver:
    """Test observer that records all events."""

    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    async def on_kernel_start(self, event: object) -> None:
        self.events.append(("kernel_start", event))

    async def on_model_request(self, event: object) -> None:
        self.events.append(("model_request", event))

    async def on_model_response(self, event: object) -> None:
        self.events.append(("model_response", event))

    async def on_tool_call(self, event: object) -> None:
        self.events.append(("tool_call", event))

    async def on_tool_result(self, event: object) -> None:
        self.events.append(("tool_result", event))

    async def on_turn_complete(self, event: object) -> None:
        self.events.append(("turn_complete", event))

    async def on_kernel_end(self, event: object) -> None:
        self.events.append(("kernel_end", event))

    async def on_error(self, error: Exception, context: str | None = None) -> None:
        self.events.append(("error", error, context))


class FailingObserver:
    """Observer that raises exceptions."""

    async def on_kernel_start(self, event: object) -> None:
        pass

    async def on_model_request(self, event: object) -> None:
        raise ValueError("Intentional failure")

    async def on_model_response(self, event: object) -> None:
        pass

    async def on_tool_call(self, event: object) -> None:
        pass

    async def on_tool_result(self, event: object) -> None:
        pass

    async def on_turn_complete(self, event: object) -> None:
        pass

    async def on_kernel_end(self, event: object) -> None:
        pass

    async def on_error(self, error: Exception, context: str | None = None) -> None:
        pass


class TestNullObserver:
    @pytest.mark.asyncio
    async def test_all_methods_are_noop(self) -> None:
        obs = NullObserver()
        event = ModelRequestEvent(turn=1, messages_count=2, tools_count=3, model="test")
        await obs.on_model_request(event)
        await obs.on_error(ValueError("test"))


class TestCompositeObserver:
    @pytest.mark.asyncio
    async def test_forwards_to_all_observers(self) -> None:
        obs1 = RecordingObserver()
        obs2 = RecordingObserver()
        composite = CompositeObserver([obs1, obs2])

        event = ModelRequestEvent(turn=1, messages_count=2, tools_count=3, model="test")
        await composite.on_model_request(event)

        assert len(obs1.events) == 1
        assert len(obs2.events) == 1
        assert obs1.events[0] == ("model_request", event)
        assert obs2.events[0] == ("model_request", event)

    @pytest.mark.asyncio
    async def test_continues_on_observer_failure(self) -> None:
        failing = FailingObserver()
        recording = RecordingObserver()
        composite = CompositeObserver([failing, recording])

        event = ModelRequestEvent(turn=1, messages_count=2, tools_count=3, model="test")
        await composite.on_model_request(event)

        assert len(recording.events) == 1

    @pytest.mark.asyncio
    async def test_empty_composite(self) -> None:
        composite = CompositeObserver([])
        event = ModelRequestEvent(turn=1, messages_count=2, tools_count=3, model="test")
        await composite.on_model_request(event)
