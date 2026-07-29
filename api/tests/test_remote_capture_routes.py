"""remote_capture.py의 /remote/audio/* 엔드포인트 — FastAPI TestClient, manager는 fake로 교체."""

import asyncio
import threading
import time
from pathlib import Path

import httpx
import numpy as np
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


def test_concurrent_chunk_uploads_for_same_session_do_not_overlap(tmp_path, monkeypatch):
    """같은 session_id에 대한 동시 /chunk 요청은 RemoteCaptureSession 상태(WAV writer·
    pending 버퍼·chord tracker)를 직렬화해서 건드려야 한다 — run_in_threadpool 오프로드로
    사라진 "같은 세션 동시 처리 배제" 보장을 session_id별 lock으로 복원하는지 확인한다
    (Phase 8.5 최종 리뷰에서 park된 이슈, Phase 10 착수 전 선행 조건).
    """
    intervals: list[tuple[float, float]] = []
    record_lock = threading.Lock()

    def slow_transcribe(samples, sample_rate):
        start = time.monotonic()
        time.sleep(0.05)
        end = time.monotonic()
        with record_lock:
            intervals.append((start, end))
        return iter([])

    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "remote.db"))
    import musicna_api.main as main

    main._session_factory.cache_clear()
    fake_manager = RemoteCaptureManager(
        out_dir=tmp_path / "audio", transcribe_chunk=slow_transcribe
    )
    monkeypatch.setattr(remote_capture, "manager", fake_manager)

    # /remote/audio/sessions는 chunk_s를 노출하지 않아 RemoteCaptureManager.start()의
    # 기본값(5.0초)이 적용된다 — process_chunk를 실제로 트리거하려면 그만큼 채워야 한다
    five_seconds_of_silence = np.zeros(16000 * 5, dtype=np.float32).tobytes()

    async def run() -> None:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            meta = {"title": "곡", "source": "unknown"}
            r = await async_client.post(
                "/remote/audio/sessions",
                json={"meta": meta, "sample_rate": 16000, "channels": 1},
            )
            session_id = r.json()["session_id"]
            chunk_url = f"/remote/audio/sessions/{session_id}/chunk"
            responses = await asyncio.gather(
                async_client.post(chunk_url, content=five_seconds_of_silence),
                async_client.post(chunk_url, content=five_seconds_of_silence),
            )
            for r in responses:
                assert r.status_code == 202

    asyncio.run(run())

    assert len(intervals) == 2
    (s1, e1), (s2, e2) = sorted(intervals)
    assert e1 <= s2, f"동시 feed() 호출이 겹쳤다: {intervals}"
