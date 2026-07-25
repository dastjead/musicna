"""MIDI 기반 키 추정 (music21 Krumhansl-Schmuckler).

Phase 3 전체 파이프라인 중 원격(Linux) 환경에서 먼저 구현·검증 가능한 조각.
오디오(chroma) 기반 키 추정과의 교차 검증은 librosa 통합 시 추가한다.
"""

from pathlib import Path

from music21 import converter
from music21.analysis.discrete import DiscreteAnalysisException


def estimate_key_from_midi(midi_path: Path) -> tuple[str, str, float] | None:
    """MIDI 파일에서 (키 으뜸음, 모드, 신뢰도)를 돌려준다. 예: ("C", "major", 0.92)

    노트가 없는 MIDI(저레벨 캡처의 전사 결과 등)는 None을 돌려준다.
    """
    score = converter.parse(str(midi_path))
    try:
        key = score.analyze("key")
    except DiscreteAnalysisException:
        return None
    return key.tonic.name, key.mode, round(key.correlationCoefficient, 4)
