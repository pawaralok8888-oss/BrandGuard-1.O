"""Tests for the vision client and prompt. A fake `post` replaces the network, so nothing is sent."""
import base64
import json

import pytest

from app.ai.vision_client import (
    ALLOWED_IMAGE_MIME,
    VisionError,
    build_body,
    call_vision,
    extract_text,
    image_part,
    parse_reply,
)
from app.ai.vision_prompt import SYSTEM_PROMPT, build_user_prompt

PNG = b"\x89PNG fake image bytes"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _reply(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}


def test_image_part_encodes_base64_with_mime():
    part = image_part("image/png", PNG)
    assert part["inlineData"]["mimeType"] == "image/png"
    assert base64.b64decode(part["inlineData"]["data"]) == PNG


def test_unsupported_mime_and_empty_image_refused():
    with pytest.raises(VisionError):
        image_part("application/pdf", PNG)
    with pytest.raises(VisionError):
        image_part("image/png", b"")
    assert ALLOWED_IMAGE_MIME == {"image/png", "image/jpeg", "image/webp"}


def test_body_has_system_text_then_user_text_then_images():
    body = build_body("SYS", "USER", [("image/png", PNG), ("image/jpeg", b"jpg")])
    assert body["systemInstruction"]["parts"][0]["text"] == "SYS"
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": "USER"}
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert parts[2]["inlineData"]["mimeType"] == "image/jpeg"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["temperature"] == 0


def test_extract_text_reads_first_candidate():
    assert extract_text(_reply('{"facts": []}')) == '{"facts": []}'


def test_extract_text_refuses_blocked_and_empty_answers():
    with pytest.raises(VisionError):
        extract_text({"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(VisionError):
        extract_text({"candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": "x"}]}}]})
    with pytest.raises(VisionError):
        extract_text(_reply("   "))
    with pytest.raises(VisionError):
        extract_text("not a dict")


def test_parse_reply_requires_one_json_object():
    assert parse_reply('{"facts": [], "findings": []}') == {"facts": [], "findings": []}
    with pytest.raises(VisionError):
        parse_reply("Here is the JSON: {}")
    with pytest.raises(VisionError):
        parse_reply("[1, 2, 3]")


def test_call_vision_returns_parsed_object_and_sends_key_header():
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json, timeout=timeout)
        return FakeResponse(_reply('{"facts": [], "findings": [], "notFound": []}'))

    result = call_vision("gemini-test", "KEY", SYSTEM_PROMPT, "hello", [("image/png", PNG)], post=fake_post)
    assert result == {"facts": [], "findings": [], "notFound": []}
    assert seen["url"].endswith("/models/gemini-test:generateContent")
    assert seen["headers"]["x-goog-api-key"] == "KEY"
    assert seen["timeout"] == 60


def test_call_vision_turns_transport_errors_into_vision_error_without_content():
    def failing_post(url, headers, json, timeout):
        return FakeResponse({}, status=500)

    with pytest.raises(VisionError) as info:
        call_vision("m", "KEY", "s", "SECRET POST TEXT", [("image/png", PNG)], post=failing_post)
    assert "SECRET" not in str(info.value)
    assert "KEY" not in str(info.value)


def test_call_vision_refuses_without_key():
    with pytest.raises(VisionError):
        call_vision("m", "", "s", "u", [], post=lambda *a, **k: None)


def test_user_prompt_lists_allowed_ids_and_text_to_quote_from():
    prompt = build_user_prompt(
        guidelines=[{"id": "G-012", "title": "Claims", "text": "No absolute claims."}],
        texts=["Protect your skin all day."],
        content_title="SPF launch",
    )
    assert "Allowed guideline ids: G-012" in prompt
    assert "[G-012] Claims: No absolute claims." in prompt
    assert "Protect your skin all day." in prompt
    assert "SPF launch" in prompt


def test_user_prompt_needs_a_guideline_and_skips_blank_text():
    with pytest.raises(ValueError):
        build_user_prompt(guidelines=[])
    prompt = build_user_prompt(guidelines=[{"id": "G-1", "title": "T", "text": "x"}], texts=["", "   "])
    assert "--- text" not in prompt


def test_system_prompt_demands_one_json_object_and_exact_quotes():
    assert "ONE JSON object" in SYSTEM_PROMPT
    assert "EXACTLY" in SYSTEM_PROMPT
    assert "Never invent a guideline id" in SYSTEM_PROMPT
