"""분석 결과의 Pydantic 모델 — API 계약의 단일 정의.

이 모델들이 core 파이프라인의 출력이자 FastAPI 응답 스키마가 된다.
추후 iOS 클라이언트는 FastAPI가 생성하는 OpenAPI 스펙에서 이 스키마를 그대로 소비한다.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CaptureSource(StrEnum):
    SPOTIFY = "spotify"
    APPLE_MUSIC = "apple_music"
    YOUTUBE_MUSIC = "youtube_music"
    FILE = "file"
    UNKNOWN = "unknown"


class ChordSource(StrEnum):
    """코드 추출 경로 — MIDI 기반, 오디오(chroma) 기반, 두 결과의 병합."""

    MIDI = "midi"
    AUDIO = "audio"
    MERGED = "merged"


class TrackMeta(BaseModel):
    """캡처 시점에 확보되는 트랙 메타데이터."""

    title: str
    artist: str | None = None
    album: str | None = None
    source: CaptureSource = CaptureSource.UNKNOWN
    duration_s: float | None = None
    captured_at: datetime | None = None


class Section(BaseModel):
    """곡 구조 구간 (intro/verse/chorus/bridge/outro 등)."""

    label: str
    start_s: float
    end_s: float


class ChordEvent(BaseModel):
    chord: str  # 예: "Am7", "F#dim", "N" (no chord)
    start_s: float
    end_s: float
    source: ChordSource
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MoodTag(BaseModel):
    tag: str  # 예: "energetic", "melancholic"
    score: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    """한 곡에 대한 배치 분석의 최종 산출물. DB 저장과 API 응답의 원천."""

    track: TrackMeta
    bpm: float | None = None
    key: str | None = None  # 예: "C", "F#"
    mode: str | None = None  # "major" / "minor"
    time_signature: str | None = None  # 예: "4/4"
    sections: list[Section] = []
    chords: list[ChordEvent] = []
    moods: list[MoodTag] = []
    midi_path: str | None = None
    engine_versions: dict[str, str] = {}  # 예: {"muscriptor": "...", "allin1": "..."}
    analyzed_at: datetime | None = None
