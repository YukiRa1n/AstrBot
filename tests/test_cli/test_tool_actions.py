"""CLI socket tool-call action regression tests."""

import asyncio
import json
from unittest.mock import MagicMock, patch

import mcp
import pytest

from astrbot.core.agent.tool import FunctionTool, ToolSet
from astrbot.core.platform.sources.cli.cli_event import MessageConverter
from astrbot.core.platform.sources.cli.socket_handler import SocketClientHandler
from astrbot.core.provider.func_tool_manager import _PermissionGuardedTool


class _FakeToolManager:
    """Provide the manager surface used by the socket action."""

    def __init__(self, tool: FunctionTool, permission_error: str | None = None):
        self.tool = tool
        self.permission_error = permission_error
        self.guarded_tool = _PermissionGuardedTool(tool, self)

    def get_func(self, name: str) -> FunctionTool | None:
        return self.tool if name == self.tool.name else None

    def get_full_tool_set(self) -> ToolSet:
        return ToolSet([self.guarded_tool])

    def _check_tool_permission(self, _name: str, _context) -> str | None:
        return self.permission_error


def _make_handler() -> SocketClientHandler:
    """Build a socket handler with a real CLI message converter."""
    return SocketClientHandler(
        token_manager=MagicMock(),
        message_converter=MessageConverter(),
        session_manager=MagicMock(),
        platform_meta=MagicMock(),
        output_queue=asyncio.Queue(),
        event_committer=MagicMock(),
    )


@pytest.mark.asyncio
async def test_call_tool_rejects_permission_denied_before_execution() -> None:
    """CLI calls cannot bypass the standard per-tool permission check."""
    called = False

    async def handler(_event):
        nonlocal called
        called = True
        return "should not run"

    tool = FunctionTool(
        name="admin_tool",
        description="",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )
    manager = _FakeToolManager(tool, "error: Permission denied")

    with patch(
        "astrbot.core.provider.func_tool_manager.get_func_tool_manager",
        return_value=manager,
    ):
        response = await _make_handler()._call_tool(
            {"tool_name": "admin_tool", "tool_args": {}},
            "request-1",
        )

    data = json.loads(response)
    assert data["status"] == "error"
    assert "Permission denied" in data["error"]
    assert called is False


@pytest.mark.asyncio
async def test_call_tool_supports_async_generator_handlers() -> None:
    """Async-generator plugin tools execute without an invalid await."""

    async def handler(_event):
        yield "first"
        yield "last"

    tool = FunctionTool(
        name="streaming_tool",
        description="",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )
    manager = _FakeToolManager(tool)

    with patch(
        "astrbot.core.provider.func_tool_manager.get_func_tool_manager",
        return_value=manager,
    ):
        response = await _make_handler()._call_tool(
            {"tool_name": "streaming_tool", "tool_args": {}},
            "request-2",
        )

    data = json.loads(response)
    assert data["status"] == "success"
    assert data["response"] == "last"


@pytest.mark.asyncio
async def test_call_tool_supports_handlerless_call_override() -> None:
    """Handlerless tools such as MCPTool dispatch through their call override."""

    class OverrideTool(FunctionTool):
        async def call(self, context, **kwargs):
            assert context.tool_call_timeout == 120
            return mcp.types.CallToolResult(
                content=[mcp.types.TextContent(type="text", text=kwargs["value"])]
            )

    tool = OverrideTool(
        name="mcp_style_tool",
        description="",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
        },
    )
    manager = _FakeToolManager(tool)

    with patch(
        "astrbot.core.provider.func_tool_manager.get_func_tool_manager",
        return_value=manager,
    ):
        response = await _make_handler()._call_tool(
            {"tool_name": "mcp_style_tool", "tool_args": {"value": "ok"}},
            "request-3",
        )

    data = json.loads(response)
    assert data["status"] == "success"
    assert data["response"] == "ok"


@pytest.mark.asyncio
async def test_call_tool_rejects_non_object_arguments() -> None:
    """Tool arguments must follow the JSON object protocol."""
    tool = FunctionTool(
        name="tool",
        description="",
        parameters={"type": "object", "properties": {}},
        handler=MagicMock(),
    )
    manager = _FakeToolManager(tool)

    with patch(
        "astrbot.core.provider.func_tool_manager.get_func_tool_manager",
        return_value=manager,
    ):
        response = await _make_handler()._call_tool(
            {"tool_name": "tool", "tool_args": []},
            "request-4",
        )

    data = json.loads(response)
    assert data["status"] == "error"
    assert "JSON 对象" in data["error"]
