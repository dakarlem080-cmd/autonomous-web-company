import asyncio

import pytest


def test_tool_registry_denies_unapproved_tool():
    from app.tool_registry import default_registry

    registry = default_registry()
    assert registry.allowed("read_github", ["read"])
    assert not registry.allowed("write_github", ["read"])
    with pytest.raises(PermissionError):
        asyncio.run(
            registry.execute(
                "write_github",
                ["read"],
                credentials={},
                name="x",
                description="x",
            )
        )


def test_qa_missing_workspace_fails():
    from app.qa import run_qa_sync

    result = run_qa_sync("/definitely/missing/autonomous-workspace")
    assert result.passed is False
    assert "workspace_missing" in result.errors
