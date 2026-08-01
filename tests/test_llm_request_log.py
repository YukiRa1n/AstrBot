import json
from pathlib import Path

from astrbot.core.agent.message import ImageURLPart, Message, TextPart
from astrbot.core.agent.tool import FunctionTool, ToolSet
from astrbot.core.provider.entities import LLMResponse, TokenUsage
from astrbot.core.utils.llm_request_log import LLMRequestLogger


def test_llm_request_logger_does_not_write_when_disabled(tmp_path):
    log_path = tmp_path / "llm.log"
    logger = LLMRequestLogger({"llm_request_log_enable": False})

    logger.record(
        provider_id="provider-a",
        provider_type="openai",
        model="gpt-test",
        session_id="session-a",
        messages=[Message(role="user", content="hello")],
        func_tool=None,
        extra_user_content_parts=[],
        response=LLMResponse(role="assistant", completion_text="hi"),
        log_path=log_path,
    )

    assert not log_path.exists()


def test_llm_request_logger_writes_sanitized_jsonl(tmp_path):
    log_path = tmp_path / "logs" / "llm.log"
    logger = LLMRequestLogger({"llm_request_log_enable": True})
    tool_set = ToolSet(
        tools=[
            FunctionTool(
                name="search",
                description="Search things",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                },
                handler=None,
            )
        ]
    )
    messages = [
        Message(role="system", content="system prompt"),
        Message(
            role="user",
            content=[
                TextPart(text="look"),
                ImageURLPart(
                    image_url=ImageURLPart.ImageURL(
                        url="data:image/png;base64," + ("a" * 200),
                        id="img-1",
                    )
                ),
            ],
        ),
    ]
    response = LLMResponse(
        role="assistant",
        completion_text="done",
        tools_call_name=["search"],
        tools_call_args=[{"query": "astrbot"}],
        tools_call_ids=["call-1"],
        reasoning_content="reasoning",
        usage=TokenUsage(input_other=3, input_cached=2, output=4),
    )

    logger.record(
        provider_id="provider-a",
        provider_type="openai",
        model="gpt-test",
        session_id="session-a",
        messages=messages,
        func_tool=tool_set,
        extra_user_content_parts=[TextPart(text="extra")],
        response=response,
        log_path=log_path,
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())

    assert payload["provider"]["id"] == "provider-a"
    assert payload["provider"]["model"] == "gpt-test"
    assert payload["request"]["messages"][0]["content"] == "system prompt"
    image_url = payload["request"]["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url == "<base64 image omitted>"
    assert payload["request"]["tools"][0]["name"] == "search"
    assert payload["request"]["extra_user_content_parts"] == [
        {"type": "text", "text": "extra"}
    ]
    assert payload["response"]["completion_text"] == "done"
    assert payload["response"]["reasoning_content"] == "reasoning"
    assert payload["response"]["tool_calls"][0]["name"] == "search"
    assert payload["response"]["usage"] == {
        "input": 5,
        "input_other": 3,
        "input_cached": 2,
        "output": 4,
        "total": 9,
    }


def test_llm_request_logger_resolves_relative_path_under_data_dir(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("ASTRBOT_ROOT", str(tmp_path))
    logger = LLMRequestLogger(
        {
            "llm_request_log_enable": True,
            "llm_request_log_path": "logs/custom.llm.log",
        }
    )

    logger.record(
        provider_id="provider-a",
        provider_type="openai",
        model="gpt-test",
        session_id="session-a",
        messages=[Message(role="user", content="hello")],
        func_tool=None,
        extra_user_content_parts=[],
        response=LLMResponse(role="assistant", completion_text="hi"),
    )

    assert (Path(tmp_path) / "data" / "logs" / "custom.llm.log").exists()
