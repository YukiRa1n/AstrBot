"""Registration for the public AstrBot client command tree."""

import click

from .chat import chat
from .config import config
from .plugin import plugin
from .send import batch, send
from .session import session
from .system import system
from .tool import tool

PUBLIC_COMMANDS = (send, chat, session, config, plugin, system, tool)


def register_commands(group: click.Group) -> None:
    """Register the public command groups and hidden compatibility commands.

    Args:
        group: Root Click group receiving the commands.
    """
    for command in PUBLIC_COMMANDS:
        group.add_command(command)
    group.add_command(batch)


__all__ = ["PUBLIC_COMMANDS", "register_commands"]
