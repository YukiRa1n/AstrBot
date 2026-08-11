"""Commands for selecting runtime LLM configuration."""

import click

from ..connection import send_message
from ..output import output_response
from .common import CliCommand, CliGroup, json_option


@click.group(cls=CliGroup, help="查看或切换当前 Provider、模型和 API Key。")
def config() -> None:
    """Manage runtime LLM selections."""


@config.command(cls=CliCommand, help="查看列表，或按序号切换 Provider。")
@click.argument("index", type=click.IntRange(min=1), required=False, metavar="[序号]")
@json_option
def provider(index: int | None, use_json: bool) -> None:
    """Show or select a provider.

    Args:
        index: Optional one-based provider index.
        use_json: Whether to emit the raw JSON response.
    """
    command = "/provider" if index is None else f"/provider {index}"
    output_response(send_message(command), use_json)


@config.command(cls=CliCommand, hidden=True)
@click.argument("index_or_name", required=False, metavar="[序号或名称]")
@json_option
def model(index_or_name: str | None, use_json: bool) -> None:
    """Show or select a model.

    Args:
        index_or_name: Optional model index or name.
        use_json: Whether to emit the raw JSON response.
    """
    del index_or_name, use_json
    raise click.ClickException(
        "当前服务端已不再提供 /model 指令；请使用 astr config provider。"
    )


@config.command(name="key", cls=CliCommand, hidden=True)
@click.argument("index", type=click.IntRange(min=1), required=False, metavar="[序号]")
@json_option
def key(index: int | None, use_json: bool) -> None:
    """Show or select an API key.

    Args:
        index: Optional one-based API key index.
        use_json: Whether to emit the raw JSON response.
    """
    del index, use_json
    raise click.ClickException(
        "当前服务端已不再提供 /key 指令；请在 Dashboard 中管理 API Key。"
    )
