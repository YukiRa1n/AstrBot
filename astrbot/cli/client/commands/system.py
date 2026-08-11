"""Operational and diagnostic commands for the AstrBot client."""

import time
from pathlib import Path

import click

from ..connection import (
    get_capabilities,
    get_data_path,
    load_auth_token,
    load_connection_info,
    ping_server,
    send_message,
)
from ..output import output_response
from .common import CliCommand, CliGroup, json_option
from .log import log_json, logs


@click.group(
    cls=CliGroup,
    aliases={"log": "logs"},
    help="查看连接状态、日志并执行诊断。",
)
def system() -> None:
    """Inspect and diagnose the AstrBot client connection."""


@system.command(cls=CliCommand, help="查看连接配置、协议版本与服务可用性。")
@json_option
def status(use_json: bool) -> None:
    """Show connection configuration and service availability."""
    data_directory = get_data_path()
    connection_info = load_connection_info(data_directory)
    token = load_auth_token()
    started_at = time.perf_counter()
    response = get_capabilities(timeout=5.0)
    elapsed = (time.perf_counter() - started_at) * 1000
    online = response.get("status") == "success" and isinstance(
        response.get("protocol_version"), int
    )
    result = {
        "status": "success" if online else "error",
        "response": "online" if online else "offline",
        "data_path": data_directory,
        "connection": connection_info,
        "token_configured": bool(token),
        "latency_ms": round(elapsed),
        "protocol_version": response.get("protocol_version"),
        "astrbot_version": response.get("astrbot_version"),
        "capabilities": response.get("capabilities", []),
    }
    if not online:
        result["error"] = response.get("error", "服务端未返回有效的 CLI 协议信息")

    if use_json:
        output_response(result, True)
        return

    if connection_info is None:
        click.echo("连接文件: 未找到 (.cli_connection)")
    elif connection_info.get("type") == "unix":
        socket_value = connection_info.get("path")
        click.echo("连接类型: Unix Socket")
        if isinstance(socket_value, str) and socket_value.strip():
            socket_path = Path(socket_value)
            click.echo(f"路径: {socket_path}")
            click.echo(f"文件存在: {'是' if socket_path.exists() else '否'}")
        else:
            click.echo("路径: 未配置")
            click.echo("文件存在: 否")
    elif connection_info.get("type") == "tcp":
        click.echo("连接类型: TCP Socket")
        click.echo(
            f"地址: {connection_info.get('host', 'N/A')}:"
            f"{connection_info.get('port', 'N/A')}"
        )
    else:
        click.echo(f"连接类型: {connection_info.get('type', '未知')} (未知)")
    click.echo(f"Token: {'已配置' if token else '未配置'}")
    click.echo("---")
    if online:
        click.echo(f"服务状态: 在线 ({elapsed:.0f}ms)")
        click.echo(f"AstrBot: {result['astrbot_version']}")
        click.echo(f"CLI 协议: v{result['protocol_version']}")
    else:
        click.echo(f"服务状态: 离线或协议不兼容 ({result['error']})")
        raise SystemExit(1)


@system.command(cls=CliCommand, help="测试与 AstrBot 的连通性和延迟。")
@click.option(
    "-c",
    "--count",
    type=click.IntRange(min=1),
    default=1,
    metavar="次数",
    help="测试次数，默认 1。",
)
def ping(count: int) -> None:
    """Measure request latency.

    Args:
        count: Number of requests to send.

    Raises:
        click.ClickException: If a request fails.
    """
    for _ in range(count):
        started_at = time.perf_counter()
        response = ping_server(timeout=5.0)
        elapsed = (time.perf_counter() - started_at) * 1000
        if response.get("status") != "success" or response.get("response") != "pong":
            raise click.ClickException(response.get("error", "未知错误"))
        click.echo(f"pong: {elapsed:.0f}ms")


@system.command(cls=CliCommand, help="查看服务端 CLI 协议及可用能力。")
@json_option
def capabilities(use_json: bool) -> None:
    """Show the server's CLI protocol capabilities."""
    response = get_capabilities()
    if use_json:
        output_response(response, True)
        return
    if response.get("status") != "success":
        output_response(response, False)
    protocol_version = response.get("protocol_version", "未知")
    astrbot_version = response.get("astrbot_version", "未知")
    click.echo(f"AstrBot: {astrbot_version}")
    click.echo(f"CLI 协议: v{protocol_version}")
    click.echo("能力:")
    for capability in response.get("capabilities", []):
        click.echo(f"  - {capability}")


@click.group(
    cls=CliGroup,
    aliases={"echo": "message"},
    help="执行消息与插件命令回环测试。",
)
def test() -> None:
    """Run client message diagnostics."""


@test.command(name="message", cls=CliCommand, help="发送消息并显示完整回环结果。")
@click.argument("message", nargs=-1, required=True, metavar="消息...")
@json_option
def test_message(message: tuple[str, ...], use_json: bool) -> None:
    """Send a message and display its full response.

    Args:
        message: Message tokens to send.
        use_json: Whether to emit the raw JSON response.

    Raises:
        click.ClickException: If the request fails.
    """
    text = " ".join(message)
    response = send_message(text)
    if use_json:
        output_response(response, True)
        return
    if response.get("status") != "success":
        raise click.ClickException(response.get("error", "未知错误"))
    click.echo(f"发送: {text}")
    click.echo(f"响应: {response.get('response', '')}")


@test.command(name="plugin", cls=CliCommand, help="拼接并测试一条插件指令。")
@click.argument("name", metavar="指令名")
@click.argument("arguments", nargs=-1, metavar="[参数]...")
@json_option
def test_plugin(name: str, arguments: tuple[str, ...], use_json: bool) -> None:
    """Send a slash command registered by a plugin.

    Args:
        name: Registered slash command name.
        arguments: Command argument tokens.
        use_json: Whether to emit the raw JSON response.
    """
    text = f"/{name}"
    if arguments:
        text += f" {' '.join(arguments)}"
    output_response(send_message(text), use_json)


system.add_command(logs)
system.add_command(log_json)
system.add_command(test)

test_echo = test_message

__all__ = [
    "capabilities",
    "ping",
    "status",
    "system",
    "test",
    "test_echo",
    "test_message",
    "test_plugin",
]
