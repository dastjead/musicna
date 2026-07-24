"""/tracks 엔드포인트 테스트 — 임시 SQLite에 저장한 분석이 API 계약대로 응답되는지."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from musicna_core.models import AnalysisResult, ChordEvent, ChordSource, TrackMeta
from musicna_core.store import create_session_factory, save_analysis


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "api.db"))
    import musicna_api.main as main

    main._session_factory.cache_clear()  # 이전 테스트의 DB 경로 캐시 무효화
    return TestClient(main.app)


def test_tracks_empty(client):
    r = client.get("/tracks")
    assert r.status_code == 200
    assert r.json() == []


def test_tracks_returns_saved_analysis(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    result = AnalysisResult(
        track=TrackMeta(title="Song", artist="Tester", captured_at=datetime(2026, 7, 25, 10, 0)),
        key="C",
        mode="major",
        chords=[ChordEvent(chord="C", start_s=0.0, end_s=2.0, source=ChordSource.MIDI)],
    )
    with factory() as session:
        save_analysis(session, result)

    body = client.get("/tracks").json()
    assert len(body) == 1
    assert body[0]["track"]["title"] == "Song"
    assert body[0]["chords"][0]["chord"] == "C"
    # 응답이 공용 계약 모델로 역직렬화 가능해야 한다 (iOS/웹 클라이언트 관점)
    assert AnalysisResult.model_validate(body[0]).key == "C"
