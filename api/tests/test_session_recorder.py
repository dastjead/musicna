"""트랙 레코더 테스트 — 메타데이터 변화에 따라 트랙별 WAV + 사이드카 JSON 저장."""

import json
import wave

import numpy as np

from musicna_api.session.metadata import NowPlaying
from musicna_api.session.recorder import TrackRecorder

SR = 48000
CH = 2


def _now(title: str, artist: str = "Tester", state: str = "playing") -> NowPlaying:
    return NowPlaying(
        state=state, title=title, artist=artist, album=None,
        duration_s=200.0, position_s=1.0, source="spotify",
    )


def _audio(seconds: float) -> bytes:
    return (0.5 * np.ones(int(SR * seconds) * CH, dtype=np.float32)).tobytes()


def test_track_change_finalizes_wav_and_sidecar(tmp_path):
    rec = TrackRecorder(out_dir=tmp_path, sample_rate=SR, channels=CH)

    rec.update_metadata(_now("Song A"))
    rec.feed(_audio(1.0))
    rec.update_metadata(_now("Song B"))  # 트랙 전환 → Song A 확정
    rec.feed(_audio(0.5))
    finished = rec.finalize()

    wavs = sorted(tmp_path.glob("*.wav"))
    assert len(wavs) == 2
    assert len(finished) == 2

    with wave.open(str(wavs[0]), "rb") as w:
        assert w.getframerate() == SR
        assert w.getnchannels() == CH
        assert w.getsampwidth() == 2  # int16
        assert w.getnframes() == SR  # 1.0초

    sidecar = json.loads(wavs[0].with_suffix(".json").read_text())
    assert sidecar["title"] == "Song A"
    assert sidecar["artist"] == "Tester"
    assert sidecar["source"] == "spotify"


def test_audio_without_active_track_is_dropped(tmp_path):
    rec = TrackRecorder(out_dir=tmp_path, sample_rate=SR, channels=CH)
    rec.feed(_audio(1.0))  # 아직 재생 중 트랙 없음
    assert rec.finalize() == []
    assert list(tmp_path.glob("*.wav")) == []


def test_pause_does_not_split_track(tmp_path):
    rec = TrackRecorder(out_dir=tmp_path, sample_rate=SR, channels=CH)
    rec.update_metadata(_now("Song A"))
    rec.feed(_audio(0.5))
    rec.update_metadata(_now("Song A", state="paused"))
    rec.update_metadata(_now("Song A"))
    rec.feed(_audio(0.5))
    finished = rec.finalize()
    assert len(finished) == 1


def test_filenames_are_sanitized_and_ordered(tmp_path):
    rec = TrackRecorder(out_dir=tmp_path, sample_rate=SR, channels=CH)
    rec.update_metadata(_now("A/B: C?"))
    rec.feed(_audio(0.1))
    rec.update_metadata(_now("Next"))
    rec.feed(_audio(0.1))
    rec.finalize()

    names = sorted(p.name for p in tmp_path.glob("*.wav"))
    assert names[0].startswith("001")
    assert names[1].startswith("002")
    assert "/" not in names[0].replace(".wav", "") and "?" not in names[0]
