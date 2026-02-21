"""Tests for history management."""

from structured_agents.history import KeepAllHistory, SlidingWindowHistory
from structured_agents.types import Message


class TestSlidingWindowHistory:
    def test_no_trim_needed(self) -> None:
        strategy = SlidingWindowHistory()
        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi!"),
        ]
        result = strategy.trim(messages, max_messages=5)
        assert result == messages

    def test_trim_preserves_system_prompt(self) -> None:
        strategy = SlidingWindowHistory()
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Msg 1"),
            Message(role="assistant", content="Msg 2"),
            Message(role="user", content="Msg 3"),
            Message(role="assistant", content="Msg 4"),
            Message(role="user", content="Msg 5"),
        ]
        result = strategy.trim(messages, max_messages=3)

        assert len(result) == 3
        assert result[0].content == "System prompt"
        assert result[1].content == "Msg 4"
        assert result[2].content == "Msg 5"

    def test_trim_no_system_prompt(self) -> None:
        strategy = SlidingWindowHistory()
        messages = [
            Message(role="user", content="Msg 1"),
            Message(role="assistant", content="Msg 2"),
            Message(role="user", content="Msg 3"),
            Message(role="assistant", content="Msg 4"),
        ]
        result = strategy.trim(messages, max_messages=2)

        assert len(result) == 2
        assert result[0].content == "Msg 3"
        assert result[1].content == "Msg 4"

    def test_empty_list(self) -> None:
        strategy = SlidingWindowHistory()
        result = strategy.trim([], max_messages=5)
        assert result == []


class TestKeepAllHistory:
    def test_keeps_everything(self) -> None:
        strategy = KeepAllHistory()
        messages = [Message(role="user", content=f"Msg {i}") for i in range(100)]
        result = strategy.trim(messages, max_messages=5)
        assert len(result) == 100
