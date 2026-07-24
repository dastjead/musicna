"""오디오 → MIDI 전사 (muscriptor 래퍼). Phase 2에서 구현.

muscriptor는 `pip install musicna-core[transcribe]`로 설치되는 optional 의존성이며,
Apple Metal 가속은 macOS에서만 동작한다. 이 모듈은 import 시점에 muscriptor를 요구하지 않는다.
"""

from pathlib import Path


def transcribe_to_midi(audio_path: Path, midi_path: Path, model_size: str = "large") -> Path:
    """오디오 파일을 MIDI로 전사하여 저장하고 저장 경로를 돌려준다.

    Phase 2: muscriptor 전체 전사 (배치 확정 분석용, large 모델).
    Phase 6: 5초 청크 스트리밍 API를 별도 함수로 추가 (small 모델).
    """
    raise NotImplementedError("Phase 2에서 muscriptor 통합과 함께 구현")
