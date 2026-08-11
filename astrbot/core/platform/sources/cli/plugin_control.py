"""Authenticated runtime plugin operations exposed to the CLI socket."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from astrbot import logger
from astrbot.core import DEMO_MODE

if TYPE_CHECKING:
    from astrbot.core.star.star import StarMetadata
    from astrbot.core.star.star_manager import PluginManager


class PluginControlError(Exception):
    """Raised when a requested runtime plugin operation is invalid."""


class PluginController:
    """Provide a narrow, testable control surface over ``PluginManager``."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        self.plugin_manager = plugin_manager

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return registered and failed plugins as serializable records."""
        records = [
            self._serialize_plugin(plugin)
            for plugin in self.plugin_manager.context.get_all_stars()
        ]
        registered_roots = {
            plugin.root_dir_name
            for plugin in self.plugin_manager.context.get_all_stars()
            if plugin.root_dir_name
        }
        for root_dir_name, failed in self.plugin_manager.failed_plugin_dict.items():
            if root_dir_name in registered_roots:
                continue
            info = failed if isinstance(failed, dict) else {}
            records.append(
                {
                    "id": root_dir_name,
                    "name": info.get("name") or root_dir_name,
                    "display_name": info.get("display_name"),
                    "version": info.get("version"),
                    "author": info.get("author"),
                    "description": info.get("desc") or info.get("short_desc") or "",
                    "enabled": False,
                    "reserved": bool(info.get("reserved", False)),
                    "status": "failed",
                    "error": info.get("error") or str(failed),
                }
            )
        return sorted(records, key=lambda item: str(item["name"]).casefold())

    async def set_enabled(self, identifier: str, *, enabled: bool) -> dict[str, Any]:
        """Enable or disable one registered plugin."""
        self._ensure_mutation_allowed()
        plugin = self._resolve_registered(identifier)
        plugin_name = self._plugin_name(plugin)
        if enabled:
            await self.plugin_manager.turn_on_plugin(plugin_name)
        else:
            await self.plugin_manager.turn_off_plugin(plugin_name)
        await self._sync_skills()
        current = self._resolve_registered(plugin_name)
        return self._serialize_plugin(current)

    async def reload(
        self,
        identifier: str | None,
        *,
        reload_all: bool = False,
    ) -> dict[str, Any]:
        """Reload one plugin, one failed plugin, or all plugins."""
        self._ensure_mutation_allowed()
        if reload_all:
            if identifier:
                raise PluginControlError("插件名称与 reload_all 不能同时提供")
            success, error = await self.plugin_manager.reload()
            label = "all"
        else:
            if not identifier:
                raise PluginControlError("缺少插件名称；重载全部插件请显式使用 --all")
            failed_root = self._resolve_failed_root(identifier)
            if failed_root is not None:
                success, error = await self.plugin_manager.reload_failed_plugin(
                    failed_root
                )
                label = failed_root
            else:
                plugin = self._resolve_registered(identifier)
                plugin_name = self._plugin_name(plugin)
                success, error = await self.plugin_manager.reload(plugin_name)
                label = plugin_name

        if not success:
            raise PluginControlError(error or f"插件 {label} 重载失败")
        await self._sync_skills()
        return {"plugin": label, "all": reload_all}

    def _resolve_registered(self, identifier: str) -> StarMetadata:
        normalized = identifier.strip()
        if not normalized:
            raise PluginControlError("插件名称不能为空")

        plugins = self.plugin_manager.context.get_all_stars()
        exact = [
            plugin
            for plugin in plugins
            if normalized
            in {
                plugin.name,
                plugin.root_dir_name,
                plugin.plugin_id,
            }
        ]
        if len(exact) == 1:
            return exact[0]

        folded = normalized.casefold()
        fuzzy = [
            plugin
            for plugin in plugins
            if folded
            in {
                str(value).casefold()
                for value in (plugin.name, plugin.root_dir_name, plugin.plugin_id)
                if value
            }
        ]
        if len(fuzzy) == 1:
            return fuzzy[0]
        if len(exact) > 1 or len(fuzzy) > 1:
            raise PluginControlError(f"插件标识不唯一: {identifier}")
        raise PluginControlError(f"插件不存在: {identifier}")

    @staticmethod
    def _plugin_name(plugin: StarMetadata) -> str:
        if not plugin.name:
            raise PluginControlError("插件元数据缺少名称")
        return plugin.name

    def _resolve_failed_root(self, identifier: str) -> str | None:
        normalized = identifier.strip()
        folded = normalized.casefold()
        matches = []
        for root_dir_name, failed in self.plugin_manager.failed_plugin_dict.items():
            info = failed if isinstance(failed, dict) else {}
            values = {
                root_dir_name,
                info.get("name"),
                info.get("plugin_id"),
            }
            if normalized in values or folded in {
                str(value).casefold() for value in values if value
            }:
                matches.append(root_dir_name)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise PluginControlError(f"失败插件标识不唯一: {identifier}")
        return None

    @staticmethod
    def _serialize_plugin(plugin: StarMetadata) -> dict[str, Any]:
        return {
            "id": plugin.root_dir_name or plugin.name or plugin.plugin_id,
            "plugin_id": plugin.plugin_id,
            "name": plugin.name or plugin.root_dir_name or "unknown",
            "display_name": plugin.display_name,
            "version": plugin.version,
            "author": plugin.author,
            "description": plugin.short_desc or plugin.desc or "",
            "enabled": bool(plugin.activated),
            "reserved": bool(plugin.reserved),
            "status": "enabled" if plugin.activated else "disabled",
        }

    @staticmethod
    def _ensure_mutation_allowed() -> None:
        if DEMO_MODE:
            raise PluginControlError("演示模式下不允许修改插件状态")

    @staticmethod
    async def _sync_skills() -> None:
        try:
            from astrbot.core.computer.computer_client import (
                sync_skills_to_active_sandboxes,
            )

            await sync_skills_to_active_sandboxes()
        except Exception:
            logger.warning("Failed to sync plugin-provided skills after CLI action.")
