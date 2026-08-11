#!/usr/bin/env python3
"""Command-line client for communicating with a running AstrBot instance."""

import sys
from collections.abc import Sequence

import click

from astrbot import __version__

from .commands.common import CliGroup

if sys.platform == "win32" and "pytest" not in sys.modules:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass


ROOT_SECTIONS = (
    ("常用", ("send", "chat")),
    ("管理", ("session", "config", "plugin")),
    ("运维与开发", ("system", "tool")),
)

LEGACY_ROUTES: dict[str, tuple[str, ...]] = {
    "conv": ("chat",),
    "provider": ("config", "provider"),
    "model": ("config", "model"),
    "key": ("config", "key"),
    "log": ("system", "logs"),
    "ping": ("system", "ping"),
    "status": ("system", "status"),
    "test": ("system", "test"),
    "help": ("chat", "commands"),
    "sid": ("chat", "id"),
    "t2i": ("chat", "t2i"),
    "tts": ("chat", "tts"),
}


class AstrGroup(CliGroup):
    """Root group providing concise sections and legacy command routing."""

    _send_options = {
        "-f",
        "--file",
        "-j",
        "--json",
        "-t",
        "--timeout",
        "-s",
        "--socket",
        "--json-output",
    }
    _send_short_options = {"-f", "-j", "-t", "-s"}

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Normalize legacy syntax before Click resolves the command.

        Args:
            ctx: Active Click context.
            args: Raw command-line arguments.

        Returns:
            Remaining arguments returned by Click.
        """
        if args:
            first = args[0]
            if first == "--log":
                args = ["system", "logs", *args[1:]]
            elif route := LEGACY_ROUTES.get(first):
                args = [*route, *args[1:]]
            elif first not in self.commands and (
                not first.startswith("-")
                or first.split("=", 1)[0] in self._send_options
                or (len(first) > 2 and first[:2] in self._send_short_options)
            ):
                args = ["send", *args]
        return super().parse_args(ctx, args)

    def format_commands(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Write root commands in stable domain sections.

        Args:
            ctx: Active Click context.
            formatter: Help formatter receiving the command records.
        """
        for heading, command_names in ROOT_SECTIONS:
            rows = []
            for command_name in command_names:
                command = self.get_command(ctx, command_name)
                if command is not None and not command.hidden:
                    rows.append((command_name, command.get_short_help_str()))
            if rows:
                with formatter.section(heading):
                    formatter.write_dl(rows)


@click.group(
    cls=AstrGroup,
    invoke_without_command=True,
    options_metavar="[选项]",
    subcommand_metavar="[消息] | 命令 [参数]...",
    epilog="""\b
快速开始:
  astr "你好"
  astr "总结这段内容"
  astr chat --help

连接与维护:
  运行状态与日志: astr system status
  服务启停、离线配置与插件安装: astrbot --help
""",
)
@click.version_option(
    __version__,
    "-V",
    "--version",
    prog_name="astr",
    help="显示版本并退出。",
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """通过命令或自然语言消息与 AstrBot 交互。"""
    if ctx.invoked_subcommand is not None:
        return

    if not sys.stdin.isatty():
        message = sys.stdin.read().strip()
        if message:
            from .commands.send import do_send

            do_send(message, None, 120.0, False)
            return
    click.echo(ctx.get_help())


from .commands import register_commands  # noqa: E402

register_commands(main)


def cli(args: Sequence[str] | None = None) -> None:
    """Run the AstrBot client CLI.

    Args:
        args: Optional argument sequence used by embedders and tests.
    """
    main.main(args=args, prog_name="astr")


if __name__ == "__main__":
    cli()
