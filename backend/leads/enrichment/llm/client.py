from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from leads.enrichment._json import extract_json_object

logger = logging.getLogger(__name__)

_MODEL_ENV_VAR = "GEMINI_MODEL"
_DEFAULT_MODEL = "gemini-2.5-flash"
_TIMEOUT = 30.0
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_HTTP_ATTEMPTS = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_JSON_RETRY_REMINDER = (
    "\n\nIMPORTANT: Return valid JSON only. Do not include markdown, commentary, or code fences. "
    "The JSON must exactly match the required schema."
)

_ResponseModelT = TypeVar("_ResponseModelT", bound=BaseModel)


def _api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""


def _model_name() -> str:
    return os.environ.get(_MODEL_ENV_VAR, _DEFAULT_MODEL)


def _endpoint_url() -> str:
    return f"{_BASE_URL}/{quote(_model_name(), safe='')}:generateContent"


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    text_parts: list[str] = []
    for part in parts:
        text = (part or {}).get("text")
        if text:
            text_parts.append(text)
    return "".join(text_parts).strip()


def _validate_json_response(text: str, response_model: type[_ResponseModelT]) -> dict:
    payload = _load_json_payload(text)
    validated = response_model.model_validate(payload)
    return validated.model_dump()


def _load_json_payload(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        payload = json.loads(extract_json_object(cleaned))

    if not isinstance(payload, dict):
        raise json.JSONDecodeError("Expected JSON object", cleaned, 0)
    return payload


async def _call_generate_content(
    system: str,
    user: str,
    response_model: Optional[type[BaseModel]],
    max_tokens: int,
) -> str:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured.")

    payload: dict = {
        "systemInstruction": {
            "parts": [{"text": system}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }
    if response_model is not None:
        payload["generationConfig"]["responseMimeType"] = "application/json"
        payload["generationConfig"]["responseJsonSchema"] = response_model.model_json_schema()

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_HTTP_ATTEMPTS + 1):
            try:
                response = await client.post(_endpoint_url(), headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in _RETRYABLE_STATUS_CODES or attempt == _MAX_HTTP_ATTEMPTS:
                    raise
                logger.warning(
                    "gemini request failed with status=%s on attempt %s/%s; retrying",
                    exc.response.status_code,
                    attempt,
                    _MAX_HTTP_ATTEMPTS,
                )
                await asyncio.sleep(0.75 * attempt)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt == _MAX_HTTP_ATTEMPTS:
                    raise
                logger.warning(
                    "gemini request timed out on attempt %s/%s; retrying",
                    attempt,
                    _MAX_HTTP_ATTEMPTS,
                )
                await asyncio.sleep(0.75 * attempt)
        else:
            assert last_error is not None
            raise last_error
    return _extract_text(data)


async def call_gemini(
    system: str,
    user: str,
    response_model: Optional[type[BaseModel]] = None,
    max_tokens: int = 1024,
) -> dict | str:
    """
    Call Gemini generateContent and optionally validate a structured JSON response.

    If structured output parsing fails, retry once with a stricter JSON reminder.
    """
    if response_model is None:
        return await _call_generate_content(system, user, None, max_tokens)

    attempts = [
        user,
        user + _JSON_RETRY_REMINDER,
    ]
    last_error: Optional[Exception] = None

    for index, user_message in enumerate(attempts, start=1):
        text = await _call_generate_content(system, user_message, response_model, max_tokens)
        try:
            return _validate_json_response(text, response_model)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "gemini structured parse failed on attempt %s with model=%s: %s",
                index,
                _model_name(),
                exc,
            )

    assert last_error is not None
    raise last_error


async def call_claude(
    system: str,
    user: str,
    response_model: Optional[type[BaseModel]] = None,
    max_tokens: int = 1024,
) -> dict | str:
    """
    Backward-compatible alias for the previous Anthropic-based interface.
    """
    return await call_gemini(system, user, response_model=response_model, max_tokens=max_tokens)
