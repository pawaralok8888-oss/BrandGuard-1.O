from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_conn
from app.routes.review import router
from app.security import current_user


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def execute(self, *args, **kwargs):
        return _FakeResult({"pending_review": 2, "changes_requested": 1})


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: _FakeConn()
    app.dependency_overrides[current_user] = lambda: {
        "id": "user-reviewer", "name": "Priya Shah", "role": "reviewer",
    }
    return TestClient(app)


def test_summary_shape_and_counts():
    res = _client().get("/api/review/summary")
    assert res.status_code == 200
    assert res.json() == {"pendingReview": 2, "changesRequested": 1}
