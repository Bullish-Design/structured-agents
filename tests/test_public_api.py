"""Tests for public API surface."""


def test_all_exports_importable() -> None:
    """Verify all __all__ exports are importable."""
    import structured_agents

    for name in structured_agents.__all__:
        obj = getattr(structured_agents, name)
        assert obj is not None, f"Export {name} is None"


def test_version_exists() -> None:
    import structured_agents

    assert hasattr(structured_agents, "__version__")
    assert isinstance(structured_agents.__version__, str)


def test_core_classes_importable() -> None:
    from structured_agents import (
        AgentKernel,
        FunctionGemmaPlugin,
        KernelConfig,
        Message,
        PythonBackend,
        ToolCall,
        ToolResult,
        ToolSchema,
        load_bundle,
    )

    assert KernelConfig.__name__ == "KernelConfig"
    assert AgentKernel.__name__ == "AgentKernel"
    assert ToolCall.__name__ == "ToolCall"
    assert ToolResult.__name__ == "ToolResult"
    assert ToolSchema.__name__ == "ToolSchema"
    assert FunctionGemmaPlugin.__name__ == "FunctionGemmaPlugin"
    assert PythonBackend.__name__ == "PythonBackend"
    assert Message.__name__ == "Message"
    assert load_bundle.__name__ == "load_bundle"
