"""Tests for the visual read. A fake `call` replaces the model, so nothing is sent."""
import pytest

from app.ai.vision_client import VisionError
from app.services.vision_check import (
    HOLD_MESSAGE,
    ImageInput,
    plan_batches,
    run_visual_read,
)
from app.services.vision_safeguards import CallBudget

GUIDELINES = [{"id": "G-012", "title": "Claims", "text": "No absolute claims."}]
TEXTS = ["Protect your skin up to 2 hours."]


def _img(n):
    return ImageInput(attachment_id=f"ATT-{n:04d}", mime_type="image/png", data=b"png-bytes")


def _reply(fact="F1", guideline="G-012", confidence=0.9, quote="up to 2 hours"):
    return {
        "facts": [{"id": fact, "kind": "text", "value": "SPF", "bbox": [0.1, 0.1, 0.2, 0.1], "confidence": 0.9}],
        "findings": [{"factIds": [fact], "type": "claim", "severity": "warning", "title": "Claim",
                      "quote": quote, "reason": "r", "guidelineId": guideline, "suggestedFix": "f",
                      "confidence": confidence}],
        "notFound": ["IF-011"],
    }


def _run(images, call, budget=None, terms=(), scan_texts=None):
    return run_visual_read(
        scan_texts=scan_texts if scan_texts is not None else TEXTS,
        visible_texts=TEXTS,
        guidelines=GUIDELINES,
        images=images,
        terms=terms,
        model="m",
        api_key="k",
        budget=budget,
        call=call,
    )


def test_batches_of_four_keep_order():
    batches = plan_batches([_img(i) for i in range(9)])
    assert [len(b) for b in batches] == [4, 4, 1]
    assert batches[0][0].attachment_id == "ATT-0000"


def test_confidential_match_holds_and_calls_nothing():
    calls = []
    result = _run([_img(1)], call=lambda *a, **k: calls.append(a) or _reply(), terms=["Project Nightingale"],
                  scan_texts=["draft for Project Nightingale"])
    assert result.status == "held"
    assert result.message == HOLD_MESSAGE
    assert calls == []
    assert result.unread_attachment_ids == ["ATT-0001"]
    assert "Nightingale" not in repr(result)


def test_ready_path_keeps_findings_and_tags_attachments():
    result = _run([_img(1), _img(2)], call=lambda *a, **k: _reply())
    assert result.status == "ready"
    assert result.calls_used == 1
    assert len(result.findings) == 1
    assert result.findings[0]["attachmentIds"] == ["ATT-0001", "ATT-0002"]
    assert result.not_found == ["IF-011"]


def test_no_images_means_ready_with_no_calls():
    calls = []
    result = _run([], call=lambda *a, **k: calls.append(a) or _reply())
    assert result.status == "ready"
    assert calls == []


def test_budget_stops_and_reports_unread_images_as_partial():
    seen = []

    def call(*args, **kwargs):
        seen.append(len(args[4]))
        return _reply()

    images = [_img(i) for i in range(9)]  # batches of 4, 4, 1
    result = _run(images, call=call, budget=CallBudget(limit=2))
    assert result.calls_used == 2
    assert result.status == "partial"
    assert result.unread_attachment_ids == ["ATT-0008"]
    assert seen == [4, 4]


def test_one_failed_batch_is_partial_and_others_still_run():
    state = {"n": 0}

    def call(*args, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            raise VisionError("model call failed: HTTPStatusError")
        return _reply()

    result = _run([_img(i) for i in range(5)], call=call)
    assert result.status == "partial"
    assert result.failed_attachment_ids == ["ATT-0000", "ATT-0001", "ATT-0002", "ATT-0003"]
    assert len(result.findings) == 1
    assert result.findings[0]["attachmentIds"] == ["ATT-0004"]


def test_all_calls_failing_is_failed():
    def call(*args, **kwargs):
        raise VisionError("model call failed")

    result = _run([_img(1)], call=call)
    assert result.status == "failed"
    assert result.failed_attachment_ids == ["ATT-0001"]
    assert "Reprocess" in result.message


def test_unknown_guideline_and_bad_quote_are_dropped_and_counted():
    bad = _reply(guideline="G-999")
    result = _run([_img(1)], call=lambda *a, **k: bad)
    assert result.findings == []
    assert result.dropped == {"unknown_guideline": 1}

    not_in_text = _reply(quote="all day protection")
    result = _run([_img(1)], call=lambda *a, **k: not_in_text)
    assert result.dropped == {"quote_not_found": 1}


def test_empty_guidelines_is_a_caller_error():
    with pytest.raises(ValueError):
        run_visual_read(scan_texts=[], visible_texts=[], guidelines=[], images=[_img(1)],
                        terms=[], model="m", api_key="k", call=lambda *a, **k: _reply())
