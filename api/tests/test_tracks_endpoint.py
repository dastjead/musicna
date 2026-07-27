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


def test_get_track_by_id_returns_analysis(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Song", artist="Tester", captured_at=datetime(2026, 7, 25, 10, 0)),
            key="C", mode="major",
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == track_id
    assert body["track"]["title"] == "Song"


def test_get_track_by_id_404_when_missing(client):
    r = client.get("/tracks/999")
    assert r.status_code == 404


def test_get_track_midi_serves_file(client, tmp_path):
    midi_path = tmp_path / "song.mid"
    midi_path.write_bytes(b"MThd fake midi bytes")
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Song", captured_at=datetime(2026, 7, 25, 10, 0)),
            midi_path=str(midi_path),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 200
    assert r.content == b"MThd fake midi bytes"
    assert r.headers["content-type"] == "audio/midi"


def test_get_track_midi_404_when_no_midi_path(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="NoMidi", captured_at=datetime(2026, 7, 25, 10, 0)),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 404


def test_get_track_midi_404_when_file_missing_on_disk(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    missing_midi = tmp_path / "gone.mid"  # 저장은 됐지만 실제 파일은 없는 상황(재분석 도중 삭제된 경우 등)
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Ghost", captured_at=datetime(2026, 7, 25, 10, 0)),
            midi_path=str(missing_midi),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 404


def test_get_track_midi_404_when_track_missing(client):
    r = client.get("/tracks/999/midi")
    assert r.status_code == 404
