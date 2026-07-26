"""배치 분석 파이프라인 — WAV(+MIDI) → AnalysisResult.

설치된 의존성에 따라 단계적으로 동작한다:
- 키·코드 진행(MIDI 기반): base 의존성(music21)만으로 동작 — Linux CI 포함 어디서나
- 구조/BPM(allin1), 무드(CLAP): optional extra 설치 시에만 채워지고, 없으면 건너뛴다

교차 검증(오디오 chroma 기반 코드)과 CLAP 무드는 macOS 스파이크 후 통합 예정 (docs/PROGRESS.md).
"""

import logging
from datetime import datetime
from importlib.metadata import version as pkg_version
from pathlib import Path

from musicna_core.analyze.chord_structure import build_roman_sequence, find_chord_loops, summarize_sections
from musicna_core.analyze.chords import extract_chords_from_midi, merge_chord_tracks
from musicna_core.analyze.keys import estimate_key_from_midi
from musicna_core.models import AnalysisResult, ChordEvent, MoodTag, Section, TrackMeta

logger = logging.getLogger(__name__)

__all__ = ["analyze_track", "extract_chords_from_midi", "estimate_key_from_midi", "merge_chord_tracks"]


def _patch_natten_torch_compat() -> None:
    """natten 0.15.1은 torch 2.13에서 제거된 `torch.cuda._device_t`를 import한다 — 타입 별칭 재주입.

    natten 0.15는 allin1이 쓰는 구 함수형 API(natten1dqkrpb 등)를 가진 마지막 PyPI 계열이라
    업그레이드로는 해결 불가 (0.17에서 구 API 제거). torch가 별칭을 되살리면 no-op.
    torch 자체가 없는 환경(원격 Linux 등)에서는 아무것도 하지 않는다 — allin1 import가 판정한다."""
    try:
        import torch.cuda
    except ImportError:
        return

    if not hasattr(torch.cuda, "_device_t"):
        from typing import Union

        torch.cuda._device_t = Union[torch.device, int, str, None]  # type: ignore[attr-defined]


def _analyze_structure(audio_path: Path) -> tuple[float | None, list[Section], str | None]:
    """allin1 구조 분석. 미설치/실패 시 (None, [], None)."""
    try:
        _patch_natten_torch_compat()
        import allin1
    except ImportError:
        logger.info("allin1 미설치 — 구조/BPM 분석 건너뜀 (uv sync --extra analyze)")
        return None, [], None
    try:
        # multiprocess=True(기본)는 spawn 환경(macOS)에서 호출자에 __main__ 가드를 요구하고
        # 교착 사례가 있어 비활성화. 부산물(demix/spec)은 cwd 오염 방지를 위해 임시 디렉터리로
        import tempfile

        with tempfile.TemporaryDirectory(prefix="allin1-") as tmp:
            result = allin1.analyze(
                str(audio_path),
                demix_dir=f"{tmp}/demix",
                spec_dir=f"{tmp}/spec",
                multiprocess=False,
            )
    except Exception:
        logger.exception("allin1 구조 분석 실패 — 구조/BPM 없이 진행: %s", audio_path.name)
        return None, [], None
    sections = [Section(label=seg.label, start_s=seg.start, end_s=seg.end) for seg in result.segments]
    # 준무음 오디오에서는 비트 검출 실패로 bpm이 None일 수 있다
    bpm = float(result.bpm) if result.bpm is not None else None
    return bpm, sections, pkg_version("allin1")


def _analyze_audio_chords(audio_path: Path) -> tuple[list[ChordEvent], str | None]:
    """오디오(chroma) 코드 추출. librosa 미설치/실패 시 ([], None)."""
    if not audio_path.exists():
        return [], None
    try:
        from musicna_core.analyze.chords_audio import extract_chords_from_audio

        events = extract_chords_from_audio(audio_path)
    except ImportError:
        logger.info("librosa 미설치 — 오디오 코드 교차 검증 건너뜀 (uv sync --extra chroma)")
        return [], None
    except Exception:
        logger.exception("오디오 코드 추출 실패 — MIDI 코드만 사용: %s", audio_path.name)
        return [], None
    return events, pkg_version("librosa")


def _analyze_moods(audio_path: Path) -> tuple[list[MoodTag], str | None]:
    """CLAP zero-shot 무드 태깅. 미설치/실패 시 ([], None)."""
    try:
        from musicna_core.analyze.moods import tag_moods

        moods = tag_moods(audio_path)
    except ImportError:
        logger.info("laion-clap 미설치 — 무드 분석 건너뜀 (uv sync --extra mood)")
        return [], None
    except Exception:
        logger.exception("CLAP 무드 분석 실패 — 무드 없이 진행: %s", audio_path.name)
        return [], None
    return moods, pkg_version("laion-clap")


def analyze_track(audio_path: Path, midi_path: Path | None, meta: TrackMeta) -> AnalysisResult:
    """오디오(+선택적 MIDI)를 분석하여 AnalysisResult를 돌려준다."""
    versions: dict[str, str] = {"music21": pkg_version("music21")}

    key = mode = None
    chords = []
    if midi_path is not None:
        if key_result := estimate_key_from_midi(midi_path):
            key, mode, _ = key_result
        else:
            logger.warning("MIDI에 노트가 없어 키 추정 건너뜀: %s", midi_path.name)
        chords = extract_chords_from_midi(midi_path)

    # 교차 검증: 오디오(chroma) 코드가 있으면 MIDI 코드와 병합(MERGED), MIDI가 없으면 대체(AUDIO)
    audio_chords, librosa_ver = _analyze_audio_chords(audio_path)
    if librosa_ver:
        versions["librosa"] = librosa_ver
    if chords and audio_chords:
        chords = merge_chord_tracks(chords, audio_chords)
    elif audio_chords:
        chords = audio_chords

    bpm, sections, allin1_ver = _analyze_structure(audio_path)
    if allin1_ver:
        versions["allin1"] = allin1_ver
    moods, clap_ver = _analyze_moods(audio_path)
    if clap_ver:
        versions["laion-clap"] = clap_ver

    section_chord_summaries: list = []
    chord_loops: list = []
    if key is not None and sections:
        roman_sequence = build_roman_sequence(chords, key, mode)
        section_chord_summaries = summarize_sections(roman_sequence, sections)
        chord_loops = find_chord_loops(roman_sequence, min_length=4)

    return AnalysisResult(
        track=meta,
        bpm=bpm,
        key=key,
        mode=mode,
        sections=sections,
        chords=chords,
        moods=moods,
        section_chord_summaries=section_chord_summaries,
        chord_loops=chord_loops,
        midi_path=str(midi_path) if midi_path else None,
        engine_versions=versions,
        analyzed_at=datetime.now(),
    )
