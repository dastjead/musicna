"""배치 오케스트레이터 테스트 — 합성 MIDI를 미리 두어 전사 없이 전 구간(스캔→분석→DB) 검증."""

import sys
from datetime import datetime

import pytest
from music21 import chord as m21chord
from music21 import stream

from musicna_api.batch import analyze_captured
from musicna_core.models import TrackMeta
from musicna_core.store import create_session_factory, list_latest_analyses


@pytest.fixture(autouse=True)
def no_ml_extras(monkeypatch):
    """extras가 설치된 환경에서도 미설치 경로를 검증한다 — 실모델 로드(다운로드 수 GB) 방지."""
    monkeypatch.setitem(sys.modules, "allin1", None)
    monkeypatch.setitem(sys.modules, "laion_clap", None)


def _prepare_capture(audio_dir, midi_dir, stem="001 - Tester - Song"):
    audio_dir.mkdir(parents=True, exist_ok=True)
    midi_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / f"{stem}.wav").write_bytes(b"RIFF-dummy")  # 오디오는 MIDI가 있으면 열지 않는다
    meta = TrackMeta(title="Song", artist="Tester", source="spotify", captured_at=datetime(2026, 7, 25, 10, 0))
    (audio_dir / f"{stem}.json").write_text(meta.model_dump_json(), encoding="utf-8")

    s = stream.Stream()
    for name in ["C4 E4 G4", "G3 B3 D4"]:
        c = m21chord.Chord(name)
        c.quarterLength = 4.0
        s.append(c)
    s.write("midi", fp=str(midi_dir / f"{stem}.mid"))


def test_batch_analyzes_and_skips_on_rerun(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 1, "skipped": 0, "failed": 0}

    with create_session_factory(db)() as session:
        [result] = list_latest_analyses(session)
    assert result.track.title == "Song"
    assert result.key == "C" and len(result.chords) >= 2

    # WAV는 분석 성공 직후 삭제되므로, 재실행 시 스캔 대상 자체가 없어 아무 것도 처리되지 않는다
    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 0, "skipped": 0, "failed": 0}


def test_batch_without_sidecar_is_skipped(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    audio_dir.mkdir(parents=True)
    (audio_dir / "orphan.wav").write_bytes(b"RIFF-dummy")
    counts = analyze_captured(audio_dir, midi_dir, str(tmp_path / "b.db"))
    assert counts == {"analyzed": 0, "skipped": 1, "failed": 0}


def test_batch_deletes_wav_after_successful_analysis(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)
    wav_path = audio_dir / "001 - Tester - Song.wav"
    json_path = audio_dir / "001 - Tester - Song.json"

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 1, "skipped": 0, "failed": 0}
    assert not wav_path.exists()  # 분석 성공 직후 WAV 삭제
    assert json_path.exists()     # 사이드카 JSON은 유지(재스캔 무의미 판단·디버깅용)


def test_batch_counts_as_analyzed_even_if_wav_unlink_fails(tmp_path, monkeypatch):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)
    wav_path = audio_dir / "001 - Tester - Song.wav"

    from pathlib import Path

    def _raise_unlink(self, *args, **kwargs):
        raise PermissionError("boom")

    monkeypatch.setattr(Path, "unlink", _raise_unlink)

    counts = analyze_captured(audio_dir, midi_dir, db)
    # 분석·저장은 이미 성공했으므로 WAV 삭제 실패는 failed로 오분류되지 않는다
    assert counts == {"analyzed": 1, "skipped": 0, "failed": 0}
    with create_session_factory(db)() as session:
        [result] = list_latest_analyses(session)
    assert result.track.title == "Song"
    assert wav_path.exists()  # 삭제 실패했으므로 디스크에 남아있음(안전한 상태)


def test_batch_keeps_wav_when_analysis_fails(tmp_path, monkeypatch):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)
    wav_path = audio_dir / "001 - Tester - Song.wav"

    import musicna_api.batch as batch_mod

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(batch_mod, "analyze_track", _raise)

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 0, "skipped": 0, "failed": 1}
    assert wav_path.exists()  # 분석 실패 시 WAV는 삭제하지 않는다(재시도 가능하도록)
