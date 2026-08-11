"""Commands for inspecting and calling registered function tools."""

import json

import click

from ..connection import call_tool, list_tools
from ..output import output_response
from .common import CliCommand, CliGroup, json_option


@click.group(cls=CliGroup, aliases={"ls": "list"}, help="查看和调用已注册的函数工具。")
def tool() -> None:
    """Inspect and call registered function tools."""


@tool.command(name="list", cls=CliCommand, help="列出所有注册的函数工具。")
@click.option(
    "-o",
    "--origin",
    type=str,
    default="",
    metavar="来源",
    help="按来源过滤：plugin/mcp/builtin。",
)
@json_option
def tool_list(origin: str, use_json: bool) -> None:
    """List registered tools.

    Args:
        origin: Optional tool origin filter.
        use_json: Whether to emit the raw JSON response.
    """
    resp = list_tools()

    if resp.get("status") != "success":
        output_response(resp, use_json)

    tools = resp.get("tools", [])
    if not tools:
        raw = resp.get("response", "")
        if raw:
            try:
                tools = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    if origin:
        tools = [
            t
            for t in tools
            if t.get("origin") == origin or t.get("origin_name") == origin
        ]

    if use_json:
        json_response = {**resp, "tools": tools}
        json_response["response"] = json.dumps(tools, ensure_ascii=False)
        output_response(json_response, True)
        return

    if not tools:
        click.echo("没有注册的函数工具。")
        return

    click.echo(f"{'名称':<25} {'来源':<10} {'来源名':<18} {'状态':<6} {'描述'}")
    click.echo("-" * 90)
    for t in tools:
        name = t.get("name", "?")
        ori = t.get("origin", "?")
        ori_name = t.get("origin_name", "?")
        active = "启用" if t.get("active", True) else "停用"
        desc = (t.get("description") or "")[:40]
        click.echo(f"{name:<25} {ori:<10} {ori_name:<18} {active:<6} {desc}")

    click.echo(f"\n共 {len(tools)} 个工具")


@tool.command(name="info", cls=CliCommand, help="查看工具详细信息。")
@click.argument("name", metavar="工具名")
def tool_info(name: str) -> None:
    """Show details for one tool.

    Args:
        name: Registered tool name.
    """
    resp = list_tools()

    if resp.get("status") != "success":
        raise click.ClickException(resp.get("error", "未知错误"))

    tools = resp.get("tools", [])
    if not tools:
        raw = resp.get("response", "")
        if raw:
            try:
                tools = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    matched = [t for t in tools if t.get("name") == name]
    if not matched:
        raise click.ClickException(f"未找到工具: {name}")

    t = matched[0]
    click.echo(f"名称:     {t.get('name')}")
    click.echo(f"描述:     {t.get('description', '无')}")
    click.echo(f"来源:     {t.get('origin', '?')} ({t.get('origin_name', '?')})")
    click.echo(f"状态:     {'启用' if t.get('active', True) else '停用'}")

    params = t.get("parameters")
    if params:
        click.echo("参数:")
        props = params.get("properties", {})
        required = params.get("required", [])
        for pname, pinfo in props.items():
            req_mark = "*" if pname in required else " "
            ptype = pinfo.get("type", "any")
            pdesc = pinfo.get("description", "")
            click.echo(f"  {req_mark} {pname} ({ptype}): {pdesc}")


@tool.command(name="call", cls=CliCommand, help="调用指定的函数工具。")
@click.argument("name", metavar="工具名")
@click.argument("args_json", required=False, default="{}", metavar="[参数JSON]")
@click.option(
    "-t",
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=60.0,
    metavar="秒",
    help="超时时间，默认 60 秒。",
)
def tool_call(name: str, args_json: str, timeout: float) -> None:
    """Call a registered function tool.

    Args:
        name: Registered tool name.
        args_json: Tool arguments encoded as a JSON object.
        timeout: Request timeout in seconds.
    """
    try:
        tool_args = json.loads(args_json)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"参数 JSON 格式错误: {e}") from e

    if not isinstance(tool_args, dict):
        raise click.ClickException("参数必须是 JSON 对象")

    resp = call_tool(name, tool_args, timeout=timeout)

    if resp.get("status") != "success":
        raise click.ClickException(resp.get("error", "未知错误"))

    click.echo(resp.get("response", "(无返回值)"))


tool_ls = tool_list

__all__ = ["tool", "tool_call", "tool_info", "tool_list", "tool_ls"]
