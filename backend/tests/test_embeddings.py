"""Embeddings: storing vectors for facts and guidelines, and ranking evidence by similarity.

No network calls: httpx.post is replaced, and the database is a fake connection.
"""
from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import app.ai.embeddings as emb
import app.ai.evidence as evidence
import app.services.ai_check as ai_check
from app.ai.embeddings import EMBEDDING_DIMENSIONS, EmbeddingUnavailable


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return self._rows


class FakeConn:
    """Answers each SQL statement with a canned result chosen by a handler."""

    def __init__(self, handler=None):
        self.calls = []
        self.handler = handler or (lambda sql, params: FakeResult())

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        return self.handler(sql, params)

    @contextmanager
    def transaction(self):
        yield


def _settings(**overrides):
    base = {"gemini_api_key": "key", "embedding_model": "gemini-embedding-001", "evidence_top_k": 25}
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------- vector text and the embedding call ----------

def test_to_pgvector_writes_a_plain_numeric_list():
    assert emb.to_pgvector([0.5, -1.0, 2]) == "[0.5,-1.0,2.0]"


def test_embed_text_returns_the_vector_from_the_api(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(json=json, url=url)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}},
        )

    monkeypatch.setattr(emb.httpx, "post", fake_post)
    values = emb.embed_text("Face wash is natural.", "RETRIEVAL_DOCUMENT")

    assert len(values) == EMBEDDING_DIMENSIONS
    assert captured["json"]["outputDimensionality"] == EMBEDDING_DIMENSIONS
    assert captured["json"]["taskType"] == "RETRIEVAL_DOCUMENT"


def test_embed_text_rejects_a_wrong_dimension(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    monkeypatch.setattr(emb.httpx, "post", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"embedding": {"values": [0.1, 0.2]}}))
    with pytest.raises(EmbeddingUnavailable):
        emb.embed_text("x", "RETRIEVAL_QUERY")


def test_embed_text_without_a_key_makes_no_call(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(gemini_api_key=""))

    def boom(*a, **k):
        raise AssertionError("no network call expected")

    monkeypatch.setattr(emb.httpx, "post", boom)
    with pytest.raises(EmbeddingUnavailable):
        emb.embed_text("x", "RETRIEVAL_QUERY")


# ---------- storing ----------

def test_index_item_embeds_the_masked_text_not_the_original(monkeypatch):
    monkeypatch.setattr(emb, "load_confidential_terms", lambda conn: ["ProjectOrion"])
    sent = {}

    def fake_embed(text, task_type):
        sent["text"] = text
        return [0.0] * EMBEDDING_DIMENSIONS

    monkeypatch.setattr(emb, "embed_text", fake_embed)
    conn = FakeConn()

    assert emb.index_item(conn, "fact", "F-001", 2, "Launch is ProjectOrion in May.") is True
    assert "ProjectOrion" not in sent["text"]
    kind, source_id, version, vector = conn.calls[-1][1]
    assert (kind, source_id, version) == ("fact", "F-001", 2)
    assert vector.startswith("[0.0,")


def test_index_item_fails_closed_when_confidential_terms_are_unavailable(monkeypatch):
    def broken(conn):
        raise RuntimeError("db down")

    monkeypatch.setattr(emb, "load_confidential_terms", broken)
    monkeypatch.setattr(emb, "embed_text", lambda *a: pytest.fail("must not embed unmasked text"))
    assert emb.index_item(FakeConn(), "guideline", "G-001", 1, "text") is False


def test_index_item_returns_false_when_the_api_fails_and_does_not_raise(monkeypatch):
    monkeypatch.setattr(emb, "load_confidential_terms", lambda conn: [])

    def unavailable(text, task_type):
        raise EmbeddingUnavailable("timeout")

    monkeypatch.setattr(emb, "embed_text", unavailable)
    assert emb.index_item(FakeConn(), "fact", "F-001", 1, "x") is False


def test_carry_forward_copies_the_vector_to_the_new_version_without_an_api_call():
    conn = FakeConn()
    emb.carry_forward(conn, "fact", "F-001", previous_version=1, version=2)
    sql, params = conn.calls[-1]
    assert "INSERT INTO embeddings" in sql and "SELECT kind, source_id" in sql
    assert params == (2, "fact", "F-001", 1)


# ---------- ranking evidence ----------

def _evidence_conn(distances, embedded_keys):
    """Facts F-001..F-003 and no guidelines. distances maps source_id to a distance."""
    facts = [
        {"id": "F-001", "version": 1, "text": "one"},
        {"id": "F-002", "version": 1, "text": "two"},
        {"id": "F-003", "version": 1, "text": "three"},
    ]

    def handler(sql, params):
        if "FROM facts" in sql:
            return FakeResult(facts)
        if "FROM guidelines" in sql:
            return FakeResult([])
        if "FROM embeddings" in sql:
            return FakeResult([
                {"source_id": sid, "version": 1, "distance": distances[sid]}
                for sid in embedded_keys
            ])
        return FakeResult()

    return FakeConn(handler)


def test_evidence_keeps_the_closest_items_and_always_keeps_unembedded_ones(monkeypatch):
    monkeypatch.setattr(evidence, "get_settings", lambda: _settings(evidence_top_k=1))
    monkeypatch.setattr(evidence, "embed_query", lambda text: [0.0] * EMBEDDING_DIMENSIONS)
    conn = _evidence_conn(
        distances={"F-001": 0.9, "F-002": 0.1},  # F-003 has no vector yet
        embedded_keys=["F-001", "F-002"],
    )

    kept = [e["source_id"] for e in evidence.get_evidence(conn, "Website", query_text="post")]

    assert "F-002" in kept          # closest vector
    assert "F-003" in kept          # no vector: never hidden
    assert "F-001" not in kept      # further away than the top-k cut


def test_evidence_without_a_query_returns_everything_unchanged(monkeypatch):
    monkeypatch.setattr(evidence, "get_settings", lambda: _settings(evidence_top_k=1))
    monkeypatch.setattr(evidence, "embed_query", lambda text: pytest.fail("no query, no embedding"))
    conn = _evidence_conn(distances={}, embedded_keys=[])
    kept = [e["source_id"] for e in evidence.get_evidence(conn, "Website")]
    assert kept == ["F-001", "F-002", "F-003"]


def test_evidence_returns_all_items_when_the_query_cannot_be_embedded(monkeypatch):
    monkeypatch.setattr(evidence, "get_settings", lambda: _settings(evidence_top_k=1))
    monkeypatch.setattr(evidence, "embed_query", lambda text: None)
    conn = _evidence_conn(distances={}, embedded_keys=[])
    kept = [e["source_id"] for e in evidence.get_evidence(conn, "Website", query_text="post")]
    assert kept == ["F-001", "F-002", "F-003"]


def test_small_catalogues_skip_embedding_entirely(monkeypatch):
    monkeypatch.setattr(evidence, "get_settings", lambda: _settings(evidence_top_k=25))
    monkeypatch.setattr(evidence, "embed_query", lambda text: pytest.fail("not needed under the limit"))
    conn = _evidence_conn(distances={}, embedded_keys=[])
    assert len(evidence.get_evidence(conn, "Website", query_text="post")) == 3


# ---------- the AI stage ranks by the masked post ----------

def test_ai_stage_passes_the_masked_post_as_the_evidence_query(monkeypatch):
    captured = {}

    def capture(conn, channel, query_text=None):
        captured["query"] = query_text
        return []  # no evidence: the stage returns early

    monkeypatch.setattr(ai_check, "get_evidence", capture)
    ai_check.run_ai_stage(FakeConn(), "Our ProjectOrion launch is huge.", "Website", [], ["ProjectOrion"])

    assert captured["query"] is not None
    assert "ProjectOrion" not in captured["query"]
