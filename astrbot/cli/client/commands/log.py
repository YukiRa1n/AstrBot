"""Command for reading AstrBot logs from disk or the CLI socket."""

import os
import re
from collections import deque
from pathlib import Path

import click

from ..connection import get_data_path, get_logs
from .common import CliCommand

LOG_LEVELS = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARN",
    "WARN": "WARN",
    "ERROR": "ERRO",
    "CRITICAL": "CRIT",
}


@click.command(name="logs", cls=CliCommand, help="读取并筛选 AstrBot 日志。")
@click.option(
    "-n",
    "--lines",
    type=click.IntRange(min=1, max=1000),
    default=100,
    metavar="数量",
    help="返回的日志行数，默认 100。",
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(tuple(LOG_LEVELS), case_sensitive=False),
    metavar="级别",
    help="按日志级别过滤。",
)
@click.option("-p", "--pattern", metavar="文本", help="按文本或正则表达式过滤。")
@click.option("-r", "--regex", is_flag=True, help="将 --pattern 解析为正则表达式。")
@click.option(
    "--socket", "use_socket", is_flag=True, help="通过运行中的 AstrBot 获取日志。"
)
@click.option(
    "-t",
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=30.0,
    metavar="秒",
    help="Socket 模式的超时时间，默认 30 秒。",
)
def logs(
    lines: int,
    level: str | None,
    pattern: str | None,
    regex: bool,
    use_socket: bool,
    timeout: float,
) -> None:
    """Read and filter AstrBot logs.

    Args:
        lines: Maximum number of matching lines.
        level: Optional log level filter.
        pattern: Optional text or regular expression filter.
        regex: Whether to interpret the pattern as a regular expression.
        use_socket: Whether to fetch logs from the running instance.
        timeout: Socket request timeout in seconds.

    Raises:
        click.UsageError: If ``--regex`` is used without a valid pattern.
        click.ClickException: If logs cannot be fetched or read.
    """
    if regex and not pattern:
        raise click.UsageError("--regex 必须与 --pattern 一起使用。")
    if regex:
        try:
            re.compile(pattern or "")
        except re.error as error:
            raise click.UsageError(f"无效的正则表达式：{error}") from error

    normalized_level = level or ""
    normalized_pattern = pattern or ""
    if use_socket:
        response = get_logs(
            None,
            timeout,
            lines,
            normalized_level,
            normalized_pattern,
            regex,
        )
        if response.get("status") != "success":
            raise click.ClickException(response.get("error", "未知错误"))
        click.echo(response.get("response") or response.get("message", ""))
        return

    _read_log_from_file(lines, normalized_level, normalized_pattern, regex)


def _read_log_from_file(
    lines: int,
    level: str,
    pattern: str,
    use_regex: bool,
) -> None:
    """Read matching log lines directly from the data directory.

    Args:
        lines: Maximum number of matching lines.
        level: Optional log level filter.
        pattern: Optional text or regular expression filter.
        use_regex: Whether to interpret the pattern as a regular expression.

    Raises:
        click.ClickException: If the log file is unavailable.
    """
    level_filter = LOG_LEVELS.get(level.upper(), level.upper())
    log_path = Path(get_data_path()) / "logs" / "astrbot.log"
    if not log_path.exists():
        raise click.ClickException(
            f"日志文件不存在：{log_path}。请启用 log_file_enable，或添加 --socket。"
        )

    try:
        matched_lines: deque[str] = deque(maxlen=lines)
        with log_path.open(encoding="utf-8", errors="ignore") as source:
            for raw_line in source:
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue
                if level_filter and not re.search(
                    rf"\[{re.escape(level_filter)}\]", line
                ):
                    continue
                if pattern and (
                    (use_regex and not re.search(pattern, line))
                    or (not use_regex and pattern not in line)
                ):
                    continue
                matched_lines.append(line)
    except OSError as error:
        raise click.ClickException(f"读取日志文件失败：{error}") from error

    for line in matched_lines:
        click.echo(line)


log = logs


def _find_hl() -> str | None:
    """Locate the hl.exe log analyzer (optional fast backend)."""
    import shutil

    candidates = [
        os.environ.get("ASTRBOT_HL"),
        r"C:\Users\29594\tools\hl\hl.exe",
        shutil.which("hl"),
        shutil.which("hl.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


@click.command(
    name="log-json",
    cls=CliCommand,
    help="分析 JSONL 日志（配合 hl 高性能日志工具；未装 hl 时用内置解析兜底）。",
)
@click.option(
    "-n",
    "--lines",
    type=click.IntRange(min=1, max=10000),
    default=50,
    metavar="数量",
    help="返回的最大行数，默认 50。",
)
@click.option(
    "-l",
    "--level",
    type=click.Choice(tuple(LOG_LEVELS), case_sensitive=False),
    metavar="级别",
    help="按日志级别过滤（如 ERROR）。",
)
@click.option("-p", "--pattern", metavar="文本", help="按消息文本子串过滤。")
@click.option(
    "--jsonl",
    "jsonl_path",
    metavar="路径",
    help="JSONL 日志路径，默认 data/logs/astrbot.jsonl。",
)
@click.option(
    "--hl",
    "hl_path",
    metavar="路径",
    help="hl.exe 路径（自动探测，可显式指定）。",
)
def log_json(
    lines: int,
    level: str | None,
    pattern: str | None,
    jsonl_path: str | None,
    hl_path: str | None,
) -> None:
    """Filter and analyze the JSONL log produced by ``log_json.enable``.

    Uses hl.exe (``~\\tools\\hl\\hl.exe`` or ``ASTRBOT_HL``) when present for
    fast filtering; otherwise falls back to a Python-side parse.
    """
    import json as _json
    import subprocess

    log_path = Path(jsonl_path or (Path(get_data_path()) / "logs" / "astrbot.jsonl"))
    if not log_path.exists():
        raise click.ClickException(f"JSONL 日志不存在：{log_path}（请先开启 log_json.enable）")

    resolver = hl_path or _find_hl()
    if resolver:
        # 快速路径：交给 hl。loguru serialize 的嵌套字段被 hl 扁平化为 record.*。
        args = [resolver, "-P"]
        if level:
            args += ["-f", f"record.level.name={level.upper()}"]
        if pattern:
            args += ["-f", f"record.message~={pattern}"]
        args.append(str(log_path))
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            out = proc.stdout
            if proc.returncode != 0 and not out:
                raise click.ClickException(
                    f"hl 执行失败：{proc.stderr.strip()[:200] or proc.returncode}"
                )
        except OSError as error:
            raise click.ClickException(f"调用 hl 失败：{error}") from error
        matched = [ln for ln in out.splitlines() if ln.strip()]
    else:
        # 兜底：纯 Python 解析 JSONL。
        matched = []
        level_filter = level.upper() if level else None
        try:
            with open(log_path, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        rec = _json.loads(ln).get("record", {})
                    except ValueError:
                        continue
                    if level_filter and rec.get("level", {}).get("name") != level_filter:
                        continue
                    if pattern and pattern not in rec.get("message", ""):
                        continue
                    matched.append(ln)
        except OSError as error:
            raise click.ClickException(f"读取 JSONL 日志失败：{error}") from error

    for ln in matched[-lines:]:
        click.echo(ln)


__all__ = ["log", "log_json", "logs"]
