"""배치 분석 파이프라인 — 구조(allin1), 코드(MIDI+오디오 교차), 키, 무드(CLAP). Phase 3에서 구현.

모든 무거운 의존성은 optional extra(analyze, mood)로 분리되어 있으며 import 시점에 요구하지 않는다.
"""

from pathlib import Path

from musicna_core.models import AnalysisResult, TrackMeta


def analyze_track(audio_path: Path, midi_path: Path | None, meta: TrackMeta) -> AnalysisResult:
    """오디오(+선택적 MIDI)를 분석하여 AnalysisResult를 돌려준다.

    Phase 3 구현 순서 (docs/PLAN.md 참조):
    1. allin1 → bpm, sections
    2. 코드 진행: music21/chorder(MIDI) + madmom chroma(오디오) 교차 검증 → chords
    3. librosa/music21 → key, mode
    4. CLAP zero-shot → moods (스파이크로 품질 검증 후 확정)
    """
    raise NotImplementedError("Phase 3에서 구현")
