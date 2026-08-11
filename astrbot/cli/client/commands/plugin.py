"""Commands for controlling plugins in a running AstrBot instance."""

import click

from ..connection import list_plugins, reload_plugin, set_plugin_enabled
from ..output import output_response
from .common import CliCommand, CliGroup, json_option


@click.group(
    cls=CliGroup,
    aliases={"ls": "list", "on": "enable", "off": "disable", "help": "info"},
    help="查看和控制运行中实例的插件。",
    epilog="持续监听插件代码变化：astrbot run --reload",
)
def plugin() -> None:
    """Control plugins loaded by the running instance."""


def _get_plugins(use_json: bool) -> tuple[dict, list[dict]]:
    """Fetch plugins and normalize the structured response."""
    response = list_plugins()
    if response.get("status") != "success":
        output_response(response, use_json)
    plugins = response.get("plugins", [])
    if not isinstance(plugins, list):
        raise click.ClickException("服务端返回了无效的插件列表")
    return response, [item for item in plugins if isinstance(item, dict)]


@plugin.command(name="list", cls=CliCommand, help="列出运行中实例加载的插件。")
@click.option(
    "--status",
    type=click.Choice(("enabled", "disabled", "failed"), case_sensitive=False),
    metavar="状态",
    help="按 enabled/disabled/failed 过滤。",
)
@json_option
def plugin_list(status: str | None, use_json: bool) -> None:
    """List plugins loaded by the running instance."""
    response, plugins = _get_plugins(use_json)
    if status:
        normalized_status = status.lower()
        plugins = [item for item in plugins if item.get("status") == normalized_status]

    if use_json:
        json_response = {**response, "plugins": plugins}
        output_response(json_response, True)
        return
    if not plugins:
        click.echo("没有匹配的插件。")
        return

    click.echo(f"{'名称':<28} {'版本':<12} {'状态':<10} {'类型':<8} {'作者'}")
    click.echo("-" * 80)
    for item in plugins:
        name = str(item.get("name") or item.get("id") or "?")
        version = str(item.get("version") or "-")
        plugin_status = str(item.get("status") or "unknown")
        plugin_type = "内置" if item.get("reserved") else "用户"
        author = str(item.get("author") or "-")
        click.echo(
            f"{name[:26]:<28} {version[:10]:<12} "
            f"{plugin_status:<10} {plugin_type:<8} {author}"
        )
    click.echo(f"\n共 {len(plugins)} 个插件")


@plugin.command(name="info", cls=CliCommand, help="查看一个运行时插件的详细信息。")
@click.argument("name", metavar="插件名")
@json_option
def plugin_info(name: str, use_json: bool) -> None:
    """Show details for one runtime plugin."""
    response, plugins = _get_plugins(use_json)
    folded = name.casefold()
    matches = [
        item
        for item in plugins
        if folded
        in {
            str(item.get(key)).casefold()
            for key in ("id", "plugin_id", "name")
            if item.get(key)
        }
    ]
    if len(matches) != 1:
        if not matches:
            raise click.ClickException(f"未找到插件: {name}")
        raise click.ClickException(f"插件标识不唯一: {name}")

    item = matches[0]
    if use_json:
        output_response({**response, "plugin": item}, True)
        return
    click.echo(f"名称: {item.get('name', '-')}")
    click.echo(f"ID: {item.get('id', '-')}")
    click.echo(f"插件 ID: {item.get('plugin_id', '-')}")
    click.echo(f"版本: {item.get('version') or '-'}")
    click.echo(f"作者: {item.get('author') or '-'}")
    click.echo(f"状态: {item.get('status', 'unknown')}")
    click.echo(f"类型: {'内置插件' if item.get('reserved') else '用户插件'}")
    click.echo(f"描述: {item.get('description') or '-'}")
    if error := item.get("error"):
        click.echo(f"错误: {error}")


def _set_enabled(name: str, *, enabled: bool, use_json: bool) -> None:
    """Change one plugin's enabled state and render the response."""
    response = set_plugin_enabled(name, enabled=enabled)
    output_response(response, use_json)


@plugin.command(name="enable", cls=CliCommand, help="启用并重新加载指定插件。")
@click.argument("name", metavar="插件名")
@json_option
def plugin_enable(name: str, use_json: bool) -> None:
    """Enable one runtime plugin."""
    _set_enabled(name, enabled=True, use_json=use_json)


@plugin.command(name="disable", cls=CliCommand, help="停用指定插件。")
@click.argument("name", metavar="插件名")
@json_option
def plugin_disable(name: str, use_json: bool) -> None:
    """Disable one runtime plugin."""
    _set_enabled(name, enabled=False, use_json=use_json)


@plugin.command(name="reload", cls=CliCommand, help="立即重载一个或全部插件。")
@click.argument("name", required=False, metavar="[插件名]")
@click.option(
    "--all",
    "reload_all",
    is_flag=True,
    help="显式重载全部插件。",
)
@click.option(
    "-t",
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=180.0,
    metavar="秒",
    help="重载超时时间，默认 180 秒。",
)
@json_option
def plugin_reload(
    name: str | None,
    reload_all: bool,
    timeout: float,
    use_json: bool,
) -> None:
    """Reload one plugin or all plugins when explicitly requested."""
    if bool(name) == reload_all:
        raise click.UsageError("请提供插件名，或显式使用 --all（二者只能选一项）。")
    response = reload_plugin(name, reload_all=reload_all, timeout=timeout)
    output_response(response, use_json)


plugin_ls = plugin_list
plugin_on = plugin_enable
plugin_off = plugin_disable

__all__ = [
    "plugin",
    "plugin_disable",
    "plugin_enable",
    "plugin_info",
    "plugin_list",
    "plugin_ls",
    "plugin_off",
    "plugin_on",
    "plugin_reload",
]
