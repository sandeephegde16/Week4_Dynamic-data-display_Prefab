"""Claude client wrapper."""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from app.debug import log_event
from app.llm.json_utils import parse_json_object
from app.settings import Settings


class ClaudeClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.claude_configured:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model

    def json_completion(self, prompt: str, *, max_tokens: int = 4096) -> dict[str, Any]:
        log_event("Calling Claude.", {"model": self._model, "prompt_chars": len(prompt)})
        text = self._complete(prompt, max_tokens=max_tokens)
        log_event("Claude response received.", {"chars": len(text), "preview": text[:1000]})
        try:
            parsed = parse_json_object(text)
        except Exception as exc:
            log_event(
                "Claude response was not valid JSON. Retrying JSON-only conversion.",
                {"error": str(exc), "response_chars": len(text), "preview": text[:1000]},
            )
            retry_prompt = _json_retry_prompt(original_prompt=prompt, invalid_response=text, error=str(exc))
            text = self._complete(retry_prompt, max_tokens=max_tokens)
            log_event("Claude JSON retry response received.", {"chars": len(text), "preview": text[:1000]})
            parsed = parse_json_object(text)
        log_event("Claude JSON parsed.", parsed)
        return parsed

    def _complete(self, prompt: str, *, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,
            system="Return valid JSON only. Do not include markdown fences or commentary.",
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_text(response)


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _json_retry_prompt(*, original_prompt: str, invalid_response: str, error: str) -> str:
    return f"""\
Your previous response could not be parsed as JSON.

Parse error:
{error}

Return exactly one valid JSON object that satisfies the original task's requested schema.
Do not include prose, markdown fences, comments, or SQL outside JSON string fields.
Use only information already present in your previous response and the original task.

Original task:
{original_prompt}

Previous invalid response:
{invalid_response}
"""
