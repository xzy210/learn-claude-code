import json
import os
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic, RateLimitError as AnthropicRateLimitError
from openai import OpenAI, RateLimitError as OpenAIRateLimitError


DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@dataclass
class TextBlock:
    type: str
    text: str
    extra_content: dict | None = None


@dataclass
class ToolUseBlock:
    type: str
    id: str
    name: str
    input: dict
    extra_content: dict | None = None


class CompatResponse:
    def __init__(self, content: list[Any], stop_reason: str):
        self.content = content
        self.stop_reason = stop_reason


def is_rate_limit_error(exc: Exception) -> bool:
    return isinstance(exc, (AnthropicRateLimitError, OpenAIRateLimitError))


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _convert_assistant_blocks_to_openai(content: Any) -> dict:
    if isinstance(content, str):
        return {"role": "assistant", "content": content}

    text_parts = []
    tool_calls = []
    for block in content or []:
        block_type = getattr(block, "type", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")

        if block_type == "text":
            text = getattr(block, "text", None)
            extra_content = getattr(block, "extra_content", None)
            if text is None and isinstance(block, dict):
                text = block.get("text", "")
                extra_content = extra_content or block.get("extra_content")
            if text:
                text_parts.append(text)
        elif block_type == "tool_use":
            tool_id = getattr(block, "id", None)
            tool_name = getattr(block, "name", None)
            tool_input = getattr(block, "input", None)
            extra_content = getattr(block, "extra_content", None)
            if isinstance(block, dict):
                tool_id = tool_id or block.get("id")
                tool_name = tool_name or block.get("name")
                tool_input = tool_input if tool_input is not None else block.get("input", {})
                extra_content = extra_content or block.get("extra_content")
            tool_call = {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_input or {}, ensure_ascii=False),
                },
            }
            if extra_content:
                tool_call["extra_content"] = extra_content
            tool_calls.append(tool_call)

    message = {"role": "assistant", "content": "\n".join(text_parts) if text_parts else None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def _convert_messages_to_openai(system: str | None, messages: list[dict]) -> list[dict]:
    converted = []
    if system:
        converted.append({"role": "system", "content": system})

    for message in messages:
        role = message["role"]
        content = message["content"]

        if role == "assistant":
            converted.append(_convert_assistant_blocks_to_openai(content))
            continue

        if role == "user" and isinstance(content, list):
            tool_results = []
            for item in content:
                item_type = item.get("type") if isinstance(item, dict) else None
                if item_type != "tool_result":
                    tool_results = []
                    break
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": item["tool_use_id"],
                        "content": _stringify_content(item.get("content", "")),
                    }
                )
            if tool_results:
                converted.extend(tool_results)
                continue

        converted.append({"role": role, "content": _stringify_content(content)})

    return converted


def _convert_tools_to_openai(tools: list[dict] | None) -> list[dict]:
    if not tools:
        return []
    converted = []
    for tool in tools:
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
        )
    return converted


def _convert_openai_response(response: Any) -> CompatResponse:
    choice = response.choices[0]
    message = choice.message

    content = []
    if message.content:
        content.append(TextBlock(type="text", text=message.content))

    for tool_call in message.tool_calls or []:
        try:
            parsed_args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            parsed_args = {"raw_arguments": tool_call.function.arguments}
        extra_content = getattr(tool_call, "extra_content", None)
        if extra_content is None:
            model_extra = getattr(tool_call, "model_extra", None) or {}
            extra_content = model_extra.get("extra_content")
        content.append(
            ToolUseBlock(
                type="tool_use",
                id=tool_call.id,
                name=tool_call.function.name,
                input=parsed_args,
                extra_content=extra_content,
            )
        )

    stop_reason = "tool_use" if message.tool_calls else (choice.finish_reason or "end_turn")
    return CompatResponse(content=content, stop_reason=stop_reason)


class GeminiMessagesAdapter:
    def __init__(self, client: OpenAI):
        self.client = client

    def create(
        self,
        *,
        model: str,
        system: str | None = None,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> CompatResponse:
        request = {
            "model": model,
            "messages": _convert_messages_to_openai(system, messages),
        }
        if tools:
            request["tools"] = _convert_tools_to_openai(tools)
            request["tool_choice"] = "auto"
        if max_tokens is not None:
            request["max_tokens"] = max_tokens

        reasoning_effort = os.getenv("GEMINI_REASONING_EFFORT", "").strip()
        if reasoning_effort:
            request["reasoning_effort"] = reasoning_effort

        request.update(kwargs)
        response = self.client.chat.completions.create(**request)
        return _convert_openai_response(response)


class CompatClient:
    def __init__(self, provider: str):
        self.provider = provider
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
            base_url = os.getenv("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE_URL).strip() or DEFAULT_GEMINI_BASE_URL
            openai_client = OpenAI(api_key=api_key, base_url=base_url)
            self.messages = GeminiMessagesAdapter(openai_client)
        elif provider == "anthropic":
            if os.getenv("ANTHROPIC_BASE_URL"):
                os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
            anthropic_client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
            self.messages = anthropic_client.messages
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def create_client() -> CompatClient:
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower() or "anthropic"
    return CompatClient(provider)
