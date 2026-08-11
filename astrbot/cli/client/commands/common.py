"""Shared Click primitives for the AstrBot client CLI."""

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import click

CommandFunction = TypeVar("CommandFunction", bound=Callable[..., Any])


class ChineseHelpMixin:
    """Render consistent Chinese option headings and help text."""

    def format_options(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Write command options with a Chinese section heading.

        Args:
            ctx: Active Click context.
            formatter: Help formatter receiving the option records.
        """
        records = []
        for parameter in self.get_params(ctx):
            record = parameter.get_help_record(ctx)
            if record is not None:
                records.append(record)

        if records:
            with formatter.section("选项"):
                formatter.write_dl(records)

    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        """Return Click's standard help option with localized text.

        Args:
            ctx: Active Click context.

        Returns:
            The localized help option, or ``None`` when help is disabled.
        """
        option = super().get_help_option(ctx)
        if option is not None:
            option.help = "显示此帮助并退出。"
        return option


class CliCommand(ChineseHelpMixin, click.Command):
    """Click command using the AstrBot help style."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a command with localized usage placeholders.

        Args:
            *args: Positional arguments forwarded to ``click.Command``.
            **kwargs: Keyword arguments forwarded to ``click.Command``.
        """
        kwargs.setdefault("options_metavar", "[选项]")
        super().__init__(*args, **kwargs)

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Normalize the former long JSON option without showing it in help.

        Args:
            ctx: Active Click context.
            args: Command arguments.

        Returns:
            Remaining arguments returned by Click.
        """
        supports_json = any(
            isinstance(parameter, click.Option) and "--json" in parameter.opts
            for parameter in self.params
        )
        if supports_json:
            args = [
                "--json" if argument == "--json-output" else argument
                for argument in args
            ]
        return super().parse_args(ctx, args)


class CliGroup(ChineseHelpMixin, click.Group):
    """Click group with hidden compatibility aliases."""

    def __init__(
        self,
        *args: Any,
        aliases: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a command group.

        Args:
            *args: Positional arguments forwarded to ``click.Group``.
            aliases: Hidden alias-to-command mapping used during parsing.
            **kwargs: Keyword arguments forwarded to ``click.Group``.
        """
        kwargs.setdefault("options_metavar", "[选项]")
        kwargs.setdefault("subcommand_metavar", "命令 [参数]...")
        super().__init__(*args, **kwargs)
        self.aliases = dict(aliases or {})

    def format_options(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Write localized options followed by visible commands.

        Args:
            ctx: Active Click context.
            formatter: Help formatter receiving help records.
        """
        ChineseHelpMixin.format_options(self, ctx, formatter)
        self.format_commands(ctx, formatter)

    def get_command(
        self,
        ctx: click.Context,
        cmd_name: str,
    ) -> click.Command | None:
        """Resolve canonical command names and hidden aliases.

        Args:
            ctx: Active Click context.
            cmd_name: Command name provided by the user.

        Returns:
            The resolved Click command, if one exists.
        """
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        target = self.aliases.get(cmd_name)
        return super().get_command(ctx, target) if target else None

    def format_commands(
        self,
        ctx: click.Context,
        formatter: click.HelpFormatter,
    ) -> None:
        """Write visible commands under a Chinese section heading.

        Args:
            ctx: Active Click context.
            formatter: Help formatter receiving the command records.
        """
        rows = []
        for command_name in self.list_commands(ctx):
            command = self.get_command(ctx, command_name)
            if command is None or command.hidden:
                continue
            rows.append((command_name, command.get_short_help_str()))

        if rows:
            with formatter.section("命令"):
                formatter.write_dl(rows)


def json_option(function: CommandFunction) -> CommandFunction:
    """Add the standard JSON output option to a command.

    Args:
        function: Command callback to decorate.

    Returns:
        The decorated command callback.
    """
    return click.option(
        "-j",
        "--json",
        "use_json",
        is_flag=True,
        help="输出 JSON。",
    )(function)
