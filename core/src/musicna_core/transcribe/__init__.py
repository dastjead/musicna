"""오디오 → MIDI 전사 (muscriptor 래퍼).

muscriptor는 optional extra: `uv sync --extra transcribe`
- 모델 가중치는 HuggingFace gated — `hf auth login`(또는 HF_TOKEN) + 모델 페이지 라이선스 동의 필요
- Apple Silicon에서는 MPS(Metal)로 자동 실행, float16 기본
- 이 모듈은 import 시점에 muscriptor를 요구하지 않는다 (지연 import)

배치 확정 분석은 large(1.4B), 실시간 미리보기(Phase 6)는 small(103M)을 사용한다 (PLAN.md 참조).
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

_MODEL_CACHE: dict[str, Any] = {}


def _load_model(model_size: str) -> Any:
    try:
        from muscriptor import TranscriptionModel
    except ImportError as e:
        raise ImportError(
            "muscriptor가 설치되지 않았습니다. `uv sync --extra transcribe`로 설치하고 "
            "HuggingFace 로그인(hf auth login) 후 사용하세요."
        ) from e

    if model_size not in _MODEL_CACHE:
        _MODEL_CACHE[model_size] = TranscriptionModel.load_model(model_size)
    return _MODEL_CACHE[model_size]


def transcribe_to_midi(audio_path: Path, midi_path: Path, model_size: str = "large") -> Path:
    """오디오 파일 전체를 MIDI로 전사하여 midi_path에 저장하고 그 경로를 돌려준다."""
    model = _load_model(model_size)
    midi_bytes = model.transcribe_to_midi(str(audio_path))
    midi_path.parent.mkdir(parents=True, exist_ok=True)
    midi_path.write_bytes(midi_bytes)
    return midi_path


def stream_events(
    audio_path: Path,
    model_size: str = "small",
    instruments: list[str] | None = None,
) -> Iterator[Any]:
    """전사 이벤트(NoteStart/NoteEnd/Progress)를 순서대로 산출한다.

    Phase 6 실시간 미리보기용 — API 계층이 이 이벤트를 WebSocket JSON으로 변환해 내보낸다.
    """
    model = _load_model(model_size)
    yield from model.transcribe(str(audio_path), instruments=instruments)
