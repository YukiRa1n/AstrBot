import json
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from astrbot import logger
from astrbot.core.agent.message import ContentPart, Message
from astrbot.core.agent.tool import ToolSet
from astrbot.core.provider.entities import LLMResponse, TokenUsage
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

BASE64_OMITTED = "<base64 image omitted>"
DEFAULT_LOG_PATH = "logs/astrbot.llm.log"


class LLMRequestLogger:
    def __init__(self, config: dict | None) -> None:
        self.config = config or {}

    def enabled(self) -> bool:
        return bool(self.config.get("llm_request_log_enable", False))

    def record(
        self,
        *,
        provider_id: str,
        provider_type: str,
        model: str | None,
        session_id: str | None,
        messages: list[Message],
        func_tool: ToolSet | None,
        extra_user_content_parts: list[ContentPart],
        response: LLMResponse,
        error: str | None = None,
        log_path: str | Path | None = None,
    ) -> None:
        if not self.enabled():
            return

        target_path = self._resolve_path(log_path)
        payload = {
            "type": "llm_request",
            "time": time.time(),
            "provider": {
                "id": provider_id,
                "type": provider_type,
                "model": model,
            },
            "session_id": session_id,
            "request": {
                "messages": self._sanitize(messages),
                "tools": self._serialize_tools(func_tool),
                "extra_user_content_parts": self._sanitize(extra_user_content_parts),
            },
            "response": self._serialize_response(response),
        }
        if error:
            payload["error"] = error

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with target_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._rotate_if_needed(target_path)
        except Exception as exc:
            logger.warning("Failed to write LLM request log: %s", exc, exc_info=True)

    def _resolve_path(self, log_path: str | Path | None = None) -> Path:
        configured_path = log_path or self.config.get(
            "llm_request_log_path", DEFAULT_LOG_PATH
        )
        path = Path(configured_path)
        if path.is_absolute():
            return path
        return Path(get_astrbot_data_path()) / path

    def _rotate_if_needed(self, log_path: Path) -> None:
        max_mb = self.config.get("llm_request_log_max_mb", 20)
        try:
            max_bytes = int(max_mb) * 1024 * 1024
        except (TypeError, ValueError):
            max_bytes = 20 * 1024 * 1024
        if max_bytes <= 0 or not log_path.exists():
            return
        if log_path.stat().st_size <= max_bytes:
            return

        rotated_path = log_path.with_suffix(log_path.suffix + ".1")
        if rotated_path.exists():
            rotated_path.unlink()
        os.replace(log_path, rotated_path)

    def _serialize_tools(self, func_tool: ToolSet | None) -> list[dict[str, Any]]:
        if not func_tool:
            return []
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "active": getattr(tool, "active", True),
            }
            for tool in func_tool.tools
        ]

    def _serialize_response(self, response: LLMResponse) -> dict[str, Any]:
        return {
            "role": response.role,
            "completion_text": response.completion_text,
            "reasoning_content": response.reasoning_content,
            "reasoning_signature": response.reasoning_signature,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "name": tool_name,
                    "arguments": tool_args,
                    "extra_content": response.tools_call_extra_content.get(
                        tool_call_id
                    ),
                }
                for tool_call_id, tool_name, tool_args in zip(
                    response.tools_call_ids,
                    response.tools_call_name,
                    response.tools_call_args,
                )
            ],
            "usage": self._serialize_usage(response.usage),
            "raw_completion_type": (
                type(response.raw_completion).__name__
                if response.raw_completion is not None
                else None
            ),
        }

    def _serialize_usage(self, usage: TokenUsage | None) -> dict[str, int] | None:
        if usage is None:
            return None
        return {
            "input": usage.input,
            "input_other": usage.input_other,
            "input_cached": usage.input_cached,
            "output": usage.output,
            "total": usage.total,
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            return self._sanitize(value.model_dump())
        elif isinstance(value, list):
            return [self._sanitize(item) for item in value]
        elif isinstance(value, tuple):
            return [self._sanitize(item) for item in value]
        elif isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}

        if isinstance(value, str) and self._is_data_image(value):
            return BASE64_OMITTED
        return value

    def _is_data_image(self, value: str) -> bool:
        return value.startswith("data:image/") and ";base64," in value
