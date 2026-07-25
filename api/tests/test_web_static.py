"""웹 UI 정적 서빙 테스트 — /가 index.html을 반환하고 API 라우트가 우선하는지."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "web.db"))
    import musicna_api.main as main

    main._session_factory.cache_clear()
    return TestClient(main.app)


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "musicna" in r.text
    assert "text/html" in r.headers["content-type"]


def test_api_route_takes_precedence(client):
    r = client.get("/tracks")
    assert r.status_code == 200
    assert r.json() == []  # 정적 파일이 아닌 API 응답
