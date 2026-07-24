"""transcribe 래퍼 단위 테스트 — muscriptor를 sys.modules 스텁으로 대체해 래퍼 로직만 검증.

실제 모델 실행 검증은 macOS(Metal) + HF 인증 환경에서 수동으로 수행한다 (docs/PROGRESS.md).
"""

import sys
import types

import pytest

import musicna_core.transcribe as tr


class FakeModel:
    loaded: list[str] = []

    def transcribe_to_midi(self, path: str) -> bytes:
        return b"MThd-fake-midi"

    def transcribe(self, path: str, instruments=None):
        yield {"type": "note_start", "pitch": 60}
        yield {"type": "note_end"}


@pytest.fixture
def fake_muscriptor(monkeypatch):
    mod = types.ModuleType("muscriptor")

    class TranscriptionModel:
        @staticmethod
        def load_model(size: str) -> FakeModel:
            FakeModel.loaded.append(size)
            return FakeModel()

    mod.TranscriptionModel = TranscriptionModel
    monkeypatch.setitem(sys.modules, "muscriptor", mod)
    monkeypatch.setattr(tr, "_MODEL_CACHE", {})
    FakeModel.loaded.clear()


def test_transcribe_to_midi_writes_file(fake_muscriptor, tmp_path):
    out = tr.transcribe_to_midi(tmp_path / "in.wav", tmp_path / "midi" / "out.mid")
    assert out.read_bytes() == b"MThd-fake-midi"
    assert FakeModel.loaded == ["large"]


def test_model_cache_reuses_instance(fake_muscriptor, tmp_path):
    tr.transcribe_to_midi(tmp_path / "a.wav", tmp_path / "a.mid", model_size="small")
    tr.transcribe_to_midi(tmp_path / "b.wav", tmp_path / "b.mid", model_size="small")
    assert FakeModel.loaded == ["small"]  # 두 번째 호출은 캐시 사용


def test_stream_events_passthrough(fake_muscriptor, tmp_path):
    events = list(tr.stream_events(tmp_path / "in.wav"))
    assert events[0]["type"] == "note_start"
    assert FakeModel.loaded == ["small"]


def test_missing_muscriptor_raises_helpful_error(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "muscriptor", None)  # import 실패 유도
    monkeypatch.setattr(tr, "_MODEL_CACHE", {})
    with pytest.raises(ImportError, match="uv sync --extra transcribe"):
        tr.transcribe_to_midi(tmp_path / "in.wav", tmp_path / "out.mid")
