"""Check which Gemini model reads images, and that it answers on a real image.

Run from the backend folder, after setting the key for this session:

    $env:GEMINI_API_KEY = "<your key>"
    python scripts/check_vision_model.py path\\to\\image.png
    python scripts/check_vision_model.py path\\to\\image.png gemini-2.5-flash

It sends one request to Gemini. It does not write anything to the database.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import httpx

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROMPT = "List every piece of printed text you can read in this image, one per line. Then say in one sentence what product it shows."


def _mime_for(path: Path) -> str:
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(
        path.suffix.lower(), "application/octet-stream")


def list_image_models(api_key: str) -> list[str]:
    resp = httpx.get(MODELS_URL, headers={"x-goog-api-key": api_key}, timeout=30)
    resp.raise_for_status()
    names = []
    for model in resp.json().get("models", []):
        methods = model.get("supportedGenerationMethods", [])
        name = model.get("name", "").removeprefix("models/")
        if "generateContent" in methods and "gemini" in name and "embedding" not in name:
            names.append(name)
    return sorted(names)


ATTEMPTS = 3
WAIT_BETWEEN_SECONDS = 20
REQUEST_TIMEOUT_SECONDS = 120


def ask_image(api_key: str, model: str, image_path: Path) -> dict:
    """Retries on timeouts and on 503 (overloaded). Other errors are raised immediately."""
    import time

    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return _ask_once(api_key, model, image_path)
        except httpx.TimeoutException as exc:
            last_error = exc
            print(f"  attempt {attempt}: timed out")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 503:
                raise
            last_error = exc
            print(f"  attempt {attempt}: model overloaded (503)")
        if attempt < ATTEMPTS:
            time.sleep(WAIT_BETWEEN_SECONDS)
    assert last_error is not None
    raise last_error


def _ask_once(api_key: str, model: str, image_path: Path) -> dict:
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": PROMPT},
                {"inlineData": {"mimeType": _mime_for(image_path), "data": data}},
            ],
        }],
        "generationConfig": {"temperature": 0},
    }
    resp = httpx.post(GENERATE_URL.format(model=model),
                      headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                      json=body, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


def main(argv: list[str]) -> int:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("GEMINI_API_KEY is not set in this PowerShell session.")
        return 2
    if not argv:
        print(__doc__)
        return 2
    image_path = Path(argv[0])
    if not image_path.is_file():
        print(f"Image not found: {image_path}")
        return 2

    print("Image models available to this key:")
    try:
        models = list_image_models(api_key)
    except httpx.HTTPError as exc:
        print(f"Could not list models: {exc}")
        return 1
    for name in models:
        print("  ", name)

    model = argv[1] if len(argv) > 1 else os.getenv("BRANDGUARD_VISION_MODEL", "")
    if not model:
        print("\nPass a model name as the second argument, for example gemini-2.5-flash.")
        return 2

    print(f"\nSending {image_path.name} to {model} ...")
    try:
        result = ask_image(api_key, model, image_path)
    except httpx.HTTPStatusError as exc:
        print(f"Model call failed with HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        return 1
    except httpx.HTTPError as exc:
        print(f"Model call failed after {ATTEMPTS} attempts: {type(exc).__name__}")
        return 1

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        print("Model replied, but without text:")
        print(json.dumps(result, indent=2)[:800])
        return 1

    print("\nReply:\n" + text)
    usage = result.get("usageMetadata", {})
    print(f"\nTokens: input {usage.get('promptTokenCount', '?')}, output {usage.get('candidatesTokenCount', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
