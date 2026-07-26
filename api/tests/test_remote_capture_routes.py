"""remote_capture.py의 /remote/audio/* 엔드포인트 — FastAPI TestClient, manager는 fake로 교체."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from musicna_api import remote_capture
from musicna_api.remote_capture import RemoteCaptureManager


def _fake_transcribe(samples, sample_rate):
    return iter([])  # 노트 없음 — 라우팅·응답 형태만 검증


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "remote.db"))
    import musicna_api.main as main

    main._session_factory.cache_clear()
    fake_manager = RemoteCaptureManager(out_dir=tmp_path / "audio", transcribe_chunk=_fake_transcribe)
    monkeypatch.setattr(remote_capture, "manager", fake_manager)
    return TestClient(main.app)


def _silence_bytes(seconds, sample_rate=16000):
    import numpy as np

    return np.zeros(int(sample_rate * seconds), dtype=np.float32).tobytes()


def test_full_session_lifecycle(client):
    meta = {"title": "테스트곡", "artist": "테스트", "source": "unknown"}
    r = client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r = client.post(
        f"/remote/audio/sessions/{session_id}/chunk",
        content=_silence_bytes(1.0),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 202

    r = client.post(f"/remote/audio/sessions/{session_id}/end")
    assert r.status_code == 200
    wav_path = Path(r.json()["wav_path"])
    assert wav_path.exists()
    assert wav_path.with_suffix(".json").exists()


def test_chunk_unknown_session_returns_404(client):
    r = client.post("/remote/audio/sessions/does-not-exist/chunk", content=_silence_bytes(0.1))
    assert r.status_code == 404


def test_end_unknown_session_returns_404(client):
    r = client.post("/remote/audio/sessions/does-not-exist/end")
    assert r.status_code == 404


def test_session_start_broadcasts_track_started(client):
    with client.websocket_connect("/ws/live") as ws:
        meta = {"title": "곡", "source": "unknown"}
        client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
        event = ws.receive_json()
        assert event["type"] == "track_started"
        assert event["track"]["title"] == "곡"


def test_session_end_broadcasts_track_ended(client):
    meta = {"title": "곡", "source": "unknown"}
    r = client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
    session_id = r.json()["session_id"]
    with client.websocket_connect("/ws/live") as ws:
        client.post(f"/remote/audio/sessions/{session_id}/end")
        event = ws.receive_json()
        assert event == {"type": "track_ended"}
