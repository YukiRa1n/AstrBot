"""Commands for sending messages to a running AstrBot instance."""

import sys
from pathlib import Path

import click

from ..connection import send_message
from ..output import fix_git_bash_path, output_response
from .common import CliCommand, json_option


@click.command(cls=CliCommand, help="发送一条消息，或从文件批量发送。")
@click.argument("message", nargs=-1, metavar="[消息]...")
@click.option(
    "-f",
    "--file",
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="文件",
    help="逐行发送 UTF-8 文本文件中的消息。",
)
@click.option(
    "-s", "--socket", "socket_path", metavar="路径", help="Unix Socket 路径。"
)
@click.option(
    "-t",
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=120.0,
    metavar="秒",
    help="单条消息的超时时间，默认 120 秒。",
)
@json_option
def send(
    message: tuple[str, ...],
    input_file: Path | None,
    socket_path: str | None,
    timeout: float,
    use_json: bool,
) -> None:
    """Send a message or a UTF-8 batch file.

    Args:
        message: Message tokens supplied on the command line.
        input_file: Optional batch file containing one message per line.
        socket_path: Optional Unix socket override.
        timeout: Request timeout in seconds.
        use_json: Whether to emit the raw JSON response.

    Raises:
        click.UsageError: If message input is missing or ambiguous.
    """
    if input_file is not None:
        if message:
            raise click.UsageError("MESSAGE 与 --file 不能同时使用。")
        send_file(input_file, socket_path, timeout, use_json)
        return

    if message:
        text = fix_git_bash_path(" ".join(message))
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        raise click.UsageError("请提供消息内容，或使用 --file 指定批量文件。")

    if not text:
        raise click.UsageError("消息内容不能为空。")
    do_send(text, socket_path, timeout, use_json)


def send_file(
    input_file: Path,
    socket_path: str | None,
    timeout: float,
    use_json: bool,
) -> None:
    """Send non-empty, non-comment lines from a UTF-8 file.

    Args:
        input_file: File containing one message per line.
        socket_path: Optional Unix socket override.
        timeout: Request timeout in seconds.
        use_json: Whether to emit raw JSON responses.
    """
    try:
        with input_file.open(encoding="utf-8") as source:
            for line_number, raw_line in enumerate(source, start=1):
                text = raw_line.strip()
                if not text or text.startswith("#"):
                    continue
                if not use_json:
                    click.echo(f"[{line_number}] > {text}")
                do_send(
                    text,
                    socket_path,
                    timeout,
                    use_json,
                    compact_json=use_json,
                )
                if not use_json:
                    click.echo()
    except (OSError, UnicodeError) as error:
        raise click.ClickException(f"读取批量文件失败：{error}") from error


def do_send(
    text: str,
    socket_path: str | None,
    timeout: float,
    use_json: bool,
    *,
    compact_json: bool = False,
) -> None:
    """Send one message and render its response.

    Args:
        text: Message text.
        socket_path: Optional Unix socket override.
        timeout: Request timeout in seconds.
        use_json: Whether to emit the raw JSON response.
        compact_json: Whether JSON output must occupy exactly one line.
    """
    output_response(
        send_message(text, socket_path, timeout),
        use_json,
        compact_json=compact_json,
    )


@click.command(name="batch", cls=CliCommand, hidden=True)
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="文件",
)
@json_option
def batch(file: Path, use_json: bool) -> None:
    """Run the legacy batch command.

    Args:
        file: File containing one message per line.
        use_json: Whether to emit raw JSON responses.
    """
    send_file(file, None, 120.0, use_json)


__all__ = ["batch", "do_send", "send", "send_file"]
