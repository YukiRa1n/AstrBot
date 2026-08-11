"""Commands for browsing conversations across platform sessions."""

import json

import click

from ..connection import (
    get_session_history,
    list_session_conversations,
    list_sessions,
)
from ..output import output_response
from .common import CliCommand, CliGroup, json_option


@click.group(
    cls=CliGroup,
    aliases={"ls": "list", "convs": "conversations"},
    help="跨平台浏览会话、对话和聊天记录。",
)
def session() -> None:
    """Browse sessions across all configured platforms."""


@session.command(name="list", cls=CliCommand, help="列出所有平台会话。")
@click.option(
    "-p",
    "--page",
    type=click.IntRange(min=1),
    default=1,
    metavar="页码",
    help="结果页码，默认 1。",
)
@click.option(
    "-s",
    "--size",
    type=click.IntRange(min=1),
    default=20,
    metavar="数量",
    help="每页数量，默认 20。",
)
@click.option("-P", "--platform", type=str, metavar="平台", help="按平台过滤。")
@click.option("-q", "--search", type=str, metavar="关键词", help="按关键词搜索。")
@json_option
def session_list(
    page: int,
    size: int,
    platform: str | None,
    search: str | None,
    use_json: bool,
) -> None:
    """List sessions across platforms.

    Args:
        page: Result page number.
        size: Number of sessions per page.
        platform: Optional platform filter.
        search: Optional keyword filter.
        use_json: Whether to emit the raw JSON response.
    """
    response = list_sessions(
        page=page,
        page_size=size,
        platform=platform,
        search_query=search,
    )
    if response.get("status") != "success":
        output_response(response, use_json)

    if use_json:
        click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        return

    sessions = response.get("sessions", [])
    if not sessions:
        click.echo("没有找到会话。")
        return

    click.echo(f"{'#':<4} {'会话 ID':<45} {'当前对话标题':<20} {'人设'}")
    click.echo("-" * 90)
    for index, item in enumerate(sessions, start=(page - 1) * size + 1):
        session_id = item.get("session_id", "?")
        title = item.get("title") or "(无标题)"
        persona = item.get("persona_name") or "-"
        if len(session_id) > 43:
            session_id = session_id[:40] + "..."
        if len(title) > 18:
            title = title[:15] + "..."
        click.echo(f"{index:<4} {session_id:<45} {title:<20} {persona}")

    total = response.get("total", 0)
    total_pages = response.get("total_pages", 0)
    click.echo(f"\n共 {total} 个会话，第 {page}/{total_pages} 页")


@session.command(
    name="conversations",
    cls=CliCommand,
    help="列出指定会话中的对话。",
)
@click.argument("session_id", metavar="会话ID")
@click.option(
    "-p",
    "--page",
    type=click.IntRange(min=1),
    default=1,
    metavar="页码",
    help="结果页码，默认 1。",
)
@click.option(
    "-s",
    "--size",
    type=click.IntRange(min=1),
    default=20,
    metavar="数量",
    help="每页数量，默认 20。",
)
@json_option
def session_conversations(
    session_id: str,
    page: int,
    size: int,
    use_json: bool,
) -> None:
    """List conversations belonging to a session.

    Args:
        session_id: Platform session identifier.
        page: Result page number.
        size: Number of conversations per page.
        use_json: Whether to emit the raw JSON response.
    """
    response = list_session_conversations(
        session_id=session_id,
        page=page,
        page_size=size,
    )
    if response.get("status") != "success":
        output_response(response, use_json)

    if use_json:
        click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        return

    conversations = response.get("conversations", [])
    if not conversations:
        click.echo(f"会话 {session_id} 没有对话。")
        return

    click.echo(f"会话: {session_id}")
    click.echo(f"当前对话: {response.get('current_cid', '无')}\n")
    click.echo(f"{'#':<4} {'对话 ID':<38} {'标题':<20} {'Token':<8} {'当前'}")
    click.echo("-" * 80)
    for index, item in enumerate(conversations, start=(page - 1) * size + 1):
        conversation_id = item.get("cid", "?")
        title = item.get("title") or "(无标题)"
        if len(title) > 18:
            title = title[:15] + "..."
        token_usage = item.get("token_usage", 0)
        current = "*" if item.get("is_current") else ""
        click.echo(
            f"{index:<4} {conversation_id:<38} {title:<20} {token_usage:<8} {current}"
        )

    total = response.get("total", 0)
    total_pages = response.get("total_pages", 0)
    click.echo(f"\n共 {total} 个对话，第 {page}/{total_pages} 页")


@session.command(name="history", cls=CliCommand, help="查看指定会话的聊天记录。")
@click.argument("session_id", metavar="会话ID")
@click.option(
    "-c",
    "--conversation-id",
    metavar="对话ID",
    help="对话 ID；默认使用当前对话。",
)
@click.option(
    "-p",
    "--page",
    type=click.IntRange(min=1),
    default=1,
    metavar="页码",
    help="结果页码，默认 1。",
)
@click.option(
    "-s",
    "--size",
    type=click.IntRange(min=1),
    default=10,
    metavar="数量",
    help="每页数量，默认 10。",
)
@json_option
def session_history(
    session_id: str,
    conversation_id: str | None,
    page: int,
    size: int,
    use_json: bool,
) -> None:
    """Show message history for a platform session.

    Args:
        session_id: Platform session identifier.
        conversation_id: Optional conversation identifier.
        page: Result page number.
        size: Number of messages per page.
        use_json: Whether to emit the raw JSON response.
    """
    response = get_session_history(
        session_id=session_id,
        conversation_id=conversation_id,
        page=page,
        page_size=size,
    )
    if response.get("status") != "success":
        output_response(response, use_json)

    if use_json:
        click.echo(json.dumps(response, ensure_ascii=False, indent=2))
        return

    _render_history(response, session_id, page)


def _render_history(response: dict, session_id: str, page: int) -> None:
    """Render alternating user and assistant messages.

    Args:
        response: Successful session history response.
        session_id: Platform session identifier.
        page: Current result page number.
    """
    history = response.get("history", [])
    total_pages = response.get("total_pages", 0)
    conversation_id = response.get("conversation_id")

    click.echo(f"会话: {session_id}")
    click.echo(f"对话: {conversation_id or '(无)'}  页码: {page}/{total_pages}")
    click.echo("-" * 60)
    if not history:
        click.echo("(无聊天记录)")
        return

    for message in history:
        if isinstance(message, dict):
            role = message.get("role", "?")
            label = "You" if role == "user" else "AI"
            click.echo(f"{label}: {message.get('text', '')}")
        else:
            click.echo(message)
        click.echo()


session_ls = session_list
session_convs = session_conversations

__all__ = [
    "session",
    "session_conversations",
    "session_convs",
    "session_history",
    "session_list",
    "session_ls",
]
