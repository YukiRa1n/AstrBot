"""AstrBot CLI entry point"""

import click

from . import __version__
from .commands import conf, init, password, plug, restart, run, stop


class AstrBotGroup(click.Group):
    """Root group with a hidden compatibility alias for ``plug``."""

    def get_command(
        self,
        ctx: click.Context,
        cmd_name: str,
    ) -> click.Command | None:
        """Resolve the former ``plug`` name without listing it in help."""
        if cmd_name == "plug":
            cmd_name = "plugin"
        return super().get_command(ctx, cmd_name)


@click.group(
    cls=AstrBotGroup,
    epilog="与运行中的 AstrBot 实例交互：astr --help",
)
@click.version_option(__version__, prog_name="AstrBot")
def cli() -> None:
    """启动、配置并维护 AstrBot。"""


@click.command()
@click.argument("command_name", required=False, type=str)
def help(command_name: str | None) -> None:
    """Display help information for commands

    If COMMAND_NAME is provided, display detailed help for that command.
    Otherwise, display general help information.
    """
    ctx = click.get_current_context()
    if command_name:
        # Find the specified command
        command = cli.get_command(ctx, command_name)
        if command:
            # Display help for the specific command
            click.echo(command.get_help(ctx))
        else:
            click.echo(f"Unknown command: {command_name}")
            raise click.ClickException(f"Unknown command: {command_name}")
    else:
        # Display general help information
        click.echo(cli.get_help(ctx))


cli.add_command(init)
cli.add_command(run)
cli.add_command(restart)
cli.add_command(stop)
cli.add_command(help)
cli.add_command(plug, name="plugin")
cli.add_command(conf)
cli.add_command(password)

if __name__ == "__main__":
    cli()
