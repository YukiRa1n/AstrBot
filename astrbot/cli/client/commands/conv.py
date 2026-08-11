"""Compatibility exports for the former ``conv`` command module."""

from .chat import (
    chat as conv,
)
from .chat import (
    chat_create as conv_new,
)
from .chat import (
    chat_delete as conv_del,
)
from .chat import (
    chat_history as conv_history,
)
from .chat import (
    chat_list as conv_ls,
)
from .chat import (
    chat_rename as conv_rename,
)
from .chat import (
    chat_reset as conv_reset,
)
from .chat import (
    chat_switch as conv_switch,
)

__all__ = [
    "conv",
    "conv_del",
    "conv_history",
    "conv_ls",
    "conv_new",
    "conv_rename",
    "conv_reset",
    "conv_switch",
]
