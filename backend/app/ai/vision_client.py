"""Gemini call for images (phase 2, plan sections 5.3 and 7).

This is a separate module from app/ai/client.py on purpose: that file is shared with
phase 1, so it stays unchanged. The request format and auth header match client.py.

Nothing here calls the network unless call_vision() is given no `post` function. Tests pass
a fake `post`, so CI never calls Gemini. The budget (10 calls per submission) is counted by
the caller with CallBudget, one consume() per call_vision().
"""
from __future__ import annotations

import base64
import json
from typing import Any, Callable, Iterable

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 60
ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/webp"}


class VisionError(Exception):
    """The model could not give a usable answer. The message holds no image or post text."""


def image_part(mime_type: str, data: bytes) -> dict:
    if mime_type not in ALLOWED_IMAGE_MIME:
        raise VisionError(f"unsupported image type: {mime_type}")
    if not data:
        raise VisionError("empty image")
    return {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(data).decode("ascii")}}


def build_body(system: str, user_text: str, images: Iterable[tuple[str, bytes]]) -> dict:
    """The JSON body for generateContent: system text, then the user text and each image."""
    parts: list[dict] = [{"text": user_text}]
    for mime_type, data in images:
        parts.append(image_part(mime_type, data))
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }


def extract_text(response: Any) -> str:
    """The model's text from a generateContent response. Raises VisionError if it is missing or blocked."""
    if not isinstance(response, dict):
        raise VisionError("unexpected response shape")
    candidates = response.get("candidates") or []
    if not candidates:
        block = (response.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
        raise VisionError(f"model returned no answer ({block})")
    candidate = candidates[0]
    if candidate.get("finishReason") in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        raise VisionError(f"model stopped the answer ({candidate.get('finishReason')})")
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
    if not text.strip():
        raise VisionError("model returned empty text")
    return text


def parse_reply(text: str) -> dict:
    """The reply must be one JSON object. Anything else is an error."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VisionError(f"reply is not valid JSON (line {exc.lineno}, column {exc.colno})") from None
    if not isinstance(value, dict):
        raise VisionError("reply is not a JSON object")
    return value


def call_vision(
    model: str,
    api_key: str,
    system: str,
    user_text: str,
    images: Iterable[tuple[str, bytes]],
    post: Callable[..., Any] | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> dict:
    """One model call. Returns the parsed JSON object. Raises VisionError on any problem."""
    if not api_key:
        raise VisionError("no Gemini API key is configured")
    body = build_body(system, user_text, images)
    if post is None:
        import httpx  # imported here so the module loads without the network stack

        post = httpx.post
    try:
        resp = post(
            GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except VisionError:
        raise
    except Exception as exc:  # network, HTTP status, or bad JSON from the transport
        raise VisionError(f"model call failed: {type(exc).__name__}") from None
    return parse_reply(extract_text(payload))
