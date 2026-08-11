"""Runtime plugin control and CLI socket action regression tests."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.platform.sources.cli.cli_event import MessageConverter
from astrbot.core.platform.sources.cli.plugin_control import (
    PluginControlError,
    PluginController,
)
from astrbot.core.platform.sources.cli.socket_handler import SocketClientHandler
from astrbot.core.star.star import StarMetadata


def _plugin(*, activated: bool = True) -> StarMetadata:
    """Build representative plugin metadata."""
    return StarMetadata(
        name="demo",
        author="tester",
        version="1.0.0",
        root_dir_name="astrbot_plugin_demo",
        activated=activated,
        short_desc="Demo plugin",
    )


def _controller(plugin: StarMetadata | None = None) -> tuple[PluginController, MagicMock]:
    """Build a controller backed by an asynchronous manager mock."""
    manager = MagicMock()
    manager.context.get_all_stars.return_value = [plugin or _plugin()]
    manager.failed_plugin_dict = {}
    manager.turn_on_plugin = AsyncMock()
    manager.turn_off_plugin = AsyncMock()
    manager.reload = AsyncMock(return_value=(True, None))
    manager.reload_failed_plugin = AsyncMock(return_value=(True, None))
    controller = PluginController(manager)
    controller._sync_skills = AsyncMock()
    return controller, manager


def _handler(plugin_controller=None) -> SocketClientHandler:
    """Build a socket handler with the optional plugin control surface."""
    return SocketClientHandler(
        token_manager=MagicMock(),
        message_converter=MessageConverter(),
        session_manager=MagicMock(),
        platform_meta=MagicMock(),
        output_queue=asyncio.Queue(),
        event_committer=MagicMock(),
        plugin_controller=plugin_controller,
    )


def test_list_plugins_returns_structured_runtime_state() -> None:
    """Plugin listings expose canonical identifiers and activation state."""
    controller, _manager = _controller()

    records = controller.list_plugins()

    assert records == [
        {
            "id": "astrbot_plugin_demo",
            "plugin_id": "tester/demo",
            "name": "demo",
            "display_name": None,
            "version": "1.0.0",
            "author": "tester",
            "description": "Demo plugin",
            "enabled": True,
            "reserved": False,
            "status": "enabled",
        }
    ]


@pytest.mark.asyncio
async def test_reload_rejects_unknown_plugin_without_reloading_all() -> None:
    """A typo must never fall through to PluginManager.reload(None)."""
    controller, manager = _controller()

    with pytest.raises(PluginControlError, match="插件不存在"):
        await controller.reload("typo")

    manager.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_reload_one_and_all_use_distinct_manager_calls() -> None:
    """Single and global reload scopes remain explicit at the manager boundary."""
    controller, manager = _controller()

    one = await controller.reload("ASTRBOT_PLUGIN_DEMO")
    all_plugins = await controller.reload(None, reload_all=True)

    assert one == {"plugin": "demo", "all": False}
    assert all_plugins == {"plugin": "all", "all": True}
    assert manager.reload.await_args_list[0].args == ("demo",)
    assert manager.reload.await_args_list[1].args == ()


@pytest.mark.asyncio
async def test_set_enabled_uses_canonical_plugin_name() -> None:
    """Directory and plugin IDs resolve to the manager's canonical name."""
    plugin = _plugin(activated=False)
    controller, manager = _controller(plugin)

    result = await controller.set_enabled("tester/demo", enabled=True)

    manager.turn_on_plugin.assert_awaited_once_with("demo")
    manager.turn_off_plugin.assert_not_awaited()
    assert result["name"] == "demo"


def test_capability_handshake_only_advertises_bound_plugin_actions() -> None:
    """Clients can discover whether runtime plugin operations are available."""
    without_plugins = json.loads(_handler()._get_capabilities("request-1"))
    controller, _manager = _controller()
    with_plugins = json.loads(
        _handler(controller)._get_capabilities("request-2")
    )

    assert without_plugins["protocol_version"] == 2
    assert "reload_plugin" not in without_plugins["capabilities"]
    assert "reload_plugin" in with_plugins["capabilities"]


@pytest.mark.asyncio
async def test_socket_reload_action_returns_structured_result() -> None:
    """The authenticated socket action forwards explicit reload scope."""
    controller = MagicMock()
    controller.reload = AsyncMock(return_value={"plugin": "demo", "all": False})
    handler = _handler(controller)

    response = json.loads(
        await handler._reload_plugin(
            {"plugin": "demo", "reload_all": False},
            "request-3",
        )
    )

    assert response["status"] == "success"
    assert response["reload"] == {"plugin": "demo", "all": False}
    controller.reload.assert_awaited_once_with("demo", reload_all=False)
