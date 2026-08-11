"""Tests for the public ``astr`` command tree and compatibility routing."""

import importlib
import json

import pytest
from click.testing import CliRunner

from astrbot.cli.__main__ import cli as astrbot_cli
from astrbot.cli.client.__main__ import main


@pytest.fixture
def sent_messages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record messages sent by command modules.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        Mutable list containing every sent message.
    """
    messages: list[str] = []

    def fake_send_message(message: str, *_args, **_kwargs) -> dict[str, str]:
        messages.append(message)
        return {"status": "success", "response": "ok"}

    module_names = (
        "astrbot.cli.client.commands.chat",
        "astrbot.cli.client.commands.config",
        "astrbot.cli.client.commands.send",
        "astrbot.cli.client.commands.system",
    )
    for module_name in module_names:
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "send_message", fake_send_message)
    return messages


def test_root_help_is_concise_and_grouped() -> None:
    """Root help exposes only stable domain entry points."""
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "常用:" in result.output
    assert "管理:" in result.output
    assert "运维与开发:" in result.output
    assert "\n  send " in result.output
    assert "\n  chat " in result.output
    assert "\n  config " in result.output
    assert "\n  system " in result.output
    assert "\n  conv " not in result.output
    assert "\n  provider " not in result.output
    assert "命令总览" not in result.output
    assert "astrbot --help" in result.output
    assert len(result.output.splitlines()) < 40


def test_astrbot_help_links_back_to_runtime_client() -> None:
    """The service CLI exposes one canonical plugin verb and links to astr."""
    runner = CliRunner()

    result = runner.invoke(astrbot_cli, ["--help"])
    legacy = runner.invoke(astrbot_cli, ["plug", "--help"])

    assert result.exit_code == 0
    assert "astr --help" in result.output
    assert "\n  plugin " in result.output
    assert "\n  plug " not in result.output
    assert legacy.exit_code == 0


@pytest.mark.parametrize(
    ("arguments", "visible", "hidden"),
    [
        (
            ["chat", "--help"],
            ("create", "reset", "id", "commands", "stats", "stop"),
            ("list", "switch", "delete", "rename", "history"),
        ),
        (
            ["plugin", "--help"],
            ("list", "info", "enable", "disable", "reload"),
            ("ls", "on", "off", "help"),
        ),
        (
            ["session", "--help"],
            ("list", "conversations", "history"),
            ("ls", "convs"),
        ),
        (["tool", "--help"], ("list", "info", "call"), ("ls",)),
    ],
)
def test_group_help_shows_full_verbs_only(
    arguments: list[str],
    visible: tuple[str, ...],
    hidden: tuple[str, ...],
) -> None:
    """Group help hides abbreviated compatibility aliases.

    Args:
        arguments: CLI arguments opening the target help page.
        visible: Canonical command names expected in the command table.
        hidden: Compatibility aliases excluded from the command table.
    """
    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 0
    for name in visible:
        assert f"\n  {name}" in result.output
    for name in hidden:
        assert f"\n  {name} " not in result.output


@pytest.mark.parametrize(
    ("arguments", "expected_message"),
    [
        (["conv", "new"], "/new"),
        (["provider", "2"], "/provider 2"),
        (["sid"], "/sid"),
        (["test", "echo", "hello", "world"], "hello world"),
        (["help"], "/help"),
    ],
)
def test_legacy_commands_route_to_canonical_tree(
    sent_messages: list[str],
    arguments: list[str],
    expected_message: str,
) -> None:
    """Former command names remain executable but hidden.

    Args:
        sent_messages: Recorded messages sent by patched command modules.
        arguments: Legacy CLI arguments.
        expected_message: Expected server command after routing.
    """
    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 0
    assert sent_messages == [expected_message]


@pytest.mark.parametrize(
    ("arguments", "expected_message"),
    [
        (["chat", "create"], "/new"),
        (["chat", "stats"], "/stats"),
        (["system", "test", "plugin", "probe", "cpu"], "/probe cpu"),
        (["hello", "from", "astr"], "hello from astr"),
    ],
)
def test_canonical_commands_send_expected_messages(
    sent_messages: list[str],
    arguments: list[str],
    expected_message: str,
) -> None:
    """Canonical commands preserve the expected server protocol.

    Args:
        sent_messages: Recorded messages sent by patched command modules.
        arguments: Canonical CLI arguments.
        expected_message: Expected server command.
    """
    result = CliRunner().invoke(main, arguments)

    assert result.exit_code == 0
    assert sent_messages == [expected_message]


def test_send_file_replaces_visible_batch_command(
    tmp_path,
    sent_messages: list[str],
) -> None:
    """The send command handles batch files while the legacy route still works."""
    batch_file = tmp_path / "commands.txt"
    batch_file.write_text(
        "# comment\nfirst message\n\nsecond message\n", encoding="utf-8"
    )
    runner = CliRunner()

    result = runner.invoke(main, ["send", "--file", str(batch_file)])
    assert result.exit_code == 0
    assert sent_messages == ["first message", "second message"]

    sent_messages.clear()
    legacy_result = runner.invoke(main, ["batch", str(batch_file)])
    assert legacy_result.exit_code == 0
    assert sent_messages == ["first message", "second message"]


def test_former_json_output_option_is_hidden_but_supported(
    sent_messages: list[str],
) -> None:
    """Scripts using ``--json-output`` continue to work."""
    result = CliRunner().invoke(main, ["chat", "create", "--json-output"])

    assert result.exit_code == 0
    assert sent_messages == ["/new"]
    assert '"status": "success"' in result.output


def test_help_is_localized() -> None:
    """Root and command help use the same localized labels."""
    runner = CliRunner()
    for arguments in (["--help"], ["send", "--help"], ["chat", "--help"]):
        result = runner.invoke(main, arguments)
        assert result.exit_code == 0
        assert "选项:" in result.output
        assert "显示此帮助并退出。" in result.output


def test_json_error_keeps_machine_readable_output_and_fails(monkeypatch) -> None:
    """JSON mode must preserve a non-zero exit code for server errors."""
    send_module = importlib.import_module("astrbot.cli.client.commands.send")
    monkeypatch.setattr(
        send_module,
        "send_message",
        lambda *_args, **_kwargs: {"status": "error", "error": "offline"},
    )

    result = CliRunner().invoke(main, ["send", "--json", "hello"])

    assert result.exit_code == 1
    assert json.loads(result.output) == {"status": "error", "error": "offline"}


def test_implicit_send_accepts_equals_style_options(sent_messages: list[str]) -> None:
    """Root routing recognizes long send options written with an equals sign."""
    result = CliRunner().invoke(main, ["--timeout=3", "hello"])

    assert result.exit_code == 0
    assert sent_messages == ["hello"]


def test_batch_json_is_valid_ndjson(tmp_path, sent_messages: list[str]) -> None:
    """Batch JSON output contains one compact response object per line."""
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text("first\n# ignored\nsecond\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["send", "--json", "--file", str(batch_file)],
    )

    assert result.exit_code == 0
    assert sent_messages == ["first", "second"]
    assert [json.loads(line) for line in result.output.splitlines()] == [
        {"status": "success", "response": "ok"},
        {"status": "success", "response": "ok"},
    ]


def test_status_reports_missing_unix_path_and_fails_offline(monkeypatch) -> None:
    """Status must not treat an empty socket path as the current directory."""
    system_module = importlib.import_module("astrbot.cli.client.commands.system")
    monkeypatch.setattr(
        system_module,
        "load_connection_info",
        lambda _data_dir: {"type": "unix", "path": ""},
    )
    monkeypatch.setattr(system_module, "load_auth_token", lambda: "")
    monkeypatch.setattr(
        system_module,
        "get_capabilities",
        lambda **_kwargs: {"status": "error", "error": "offline"},
    )

    result = CliRunner().invoke(main, ["system", "status"])

    assert result.exit_code == 1
    assert "路径: 未配置" in result.output
    assert "文件存在: 否" in result.output
    assert "服务状态: 离线" in result.output


def test_socket_log_uses_server_message_when_log_is_empty(monkeypatch) -> None:
    """Socket log diagnostics remain visible when the response body is empty."""
    log_module = importlib.import_module("astrbot.cli.client.commands.log")
    monkeypatch.setattr(
        log_module,
        "get_logs",
        lambda *_args, **_kwargs: {
            "status": "success",
            "response": "",
            "message": "日志文件未找到",
        },
    )

    result = CliRunner().invoke(main, ["system", "logs", "--socket"])

    assert result.exit_code == 0
    assert "日志文件未找到" in result.output
