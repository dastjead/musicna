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

    # 재실행 시 중복 분석 없이 건너뛴다
    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 0, "skipped": 1, "failed": 0}


def test_batch_without_sidecar_is_skipped(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    audio_dir.mkdir(parents=True)
    (audio_dir / "orphan.wav").write_bytes(b"RIFF-dummy")
    counts = analyze_captured(audio_dir, midi_dir, str(tmp_path / "b.db"))
    assert counts == {"analyzed": 0, "skipped": 1, "failed": 0}
