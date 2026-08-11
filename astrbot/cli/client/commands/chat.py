"""Commands for managing the active chat context."""

import click

from ..connection import send_message
from ..output import output_response
from .common import CliCommand, CliGroup, json_option


@click.group(
    cls=CliGroup,
    aliases={"ls": "list", "new": "create", "del": "delete", "rm": "delete"},
    help="管理当前 CLI 会话。",
)
def chat() -> None:
    """Manage conversations in the active session."""


@chat.command(name="list", cls=CliCommand, hidden=True)
@click.argument("page", type=click.IntRange(min=1), required=False, metavar="[页码]")
@json_option
def chat_list(page: int | None, use_json: bool) -> None:
    """List conversations in the active session.

    Args:
        page: Optional result page number.
        use_json: Whether to emit the raw JSON response.
    """
    del page, use_json
    raise click.ClickException("该命令已移除；请使用 astr session list。")


@chat.command(name="create", cls=CliCommand, help="创建并切换到新对话。")
@json_option
def chat_create(use_json: bool) -> None:
    """Create a conversation and make it active.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    output_response(send_message("/new"), use_json)


@chat.command(name="switch", cls=CliCommand, hidden=True)
@click.argument("index", type=click.IntRange(min=1), metavar="序号")
@json_option
def chat_switch(index: int, use_json: bool) -> None:
    """Switch to a conversation by list index.

    Args:
        index: One-based conversation index.
        use_json: Whether to emit the raw JSON response.
    """
    del index, use_json
    raise click.ClickException("当前服务端不支持按序号切换对话。")


@chat.command(name="delete", cls=CliCommand, hidden=True)
@json_option
def chat_delete(use_json: bool) -> None:
    """Delete the active conversation.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    del use_json
    raise click.ClickException("当前服务端不支持通过 CLI 删除当前对话。")


@chat.command(name="rename", cls=CliCommand, hidden=True)
@click.argument("name", nargs=-1, required=True, metavar="名称...")
@json_option
def chat_rename(name: tuple[str, ...], use_json: bool) -> None:
    """Rename the active conversation.

    Args:
        name: New conversation name tokens.
        use_json: Whether to emit the raw JSON response.
    """
    del name, use_json
    raise click.ClickException("当前服务端不支持通过 CLI 重命名当前对话。")


@chat.command(name="reset", cls=CliCommand, help="清除当前对话的 LLM 上下文。")
@json_option
def chat_reset(use_json: bool) -> None:
    """Reset the active conversation context.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    output_response(send_message("/reset"), use_json)


@chat.command(name="history", cls=CliCommand, hidden=True)
@click.argument("page", type=click.IntRange(min=1), required=False, metavar="[页码]")
@json_option
def chat_history(page: int | None, use_json: bool) -> None:
    """Show message history for the active conversation.

    Args:
        page: Optional result page number.
        use_json: Whether to emit the raw JSON response.
    """
    del page, use_json
    raise click.ClickException(
        "该命令已移除；请使用 astr session history <会话ID>。"
    )


@chat.command(name="id", cls=CliCommand, help="查看当前会话 ID 和管理员 ID。")
@json_option
def chat_id(use_json: bool) -> None:
    """Show identifiers for the active session.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    output_response(send_message("/sid"), use_json)


@chat.command(name="commands", cls=CliCommand, help="查看服务端内置指令。")
@json_option
def chat_commands(use_json: bool) -> None:
    """Show commands registered by the running AstrBot instance.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    output_response(send_message("/help"), use_json)


@chat.command(name="t2i", cls=CliCommand, hidden=True)
@json_option
def chat_t2i(use_json: bool) -> None:
    """Toggle text-to-image output for the active session.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    del use_json
    raise click.ClickException("当前服务端已不再提供 /t2i 指令。")


@chat.command(name="tts", cls=CliCommand, hidden=True)
@json_option
def chat_tts(use_json: bool) -> None:
    """Toggle text-to-speech output for the active session.

    Args:
        use_json: Whether to emit the raw JSON response.
    """
    del use_json
    raise click.ClickException("当前服务端已不再提供 /tts 指令。")


@chat.command(name="stats", cls=CliCommand, help="查看当前对话的 Token 使用统计。")
@json_option
def chat_stats(use_json: bool) -> None:
    """Show token usage statistics for the active conversation."""
    output_response(send_message("/stats"), use_json)


@chat.command(name="stop", cls=CliCommand, help="停止当前会话正在执行的 Agent。")
@json_option
def chat_stop(use_json: bool) -> None:
    """Stop the agent currently running for this session."""
    output_response(send_message("/stop"), use_json)
