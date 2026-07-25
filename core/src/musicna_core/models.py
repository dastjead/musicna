"""분석 결과의 Pydantic 모델 — API 계약의 단일 정의.

이 모델들이 core 파이프라인의 출력이자 FastAPI 응답 스키마가 된다.
추후 iOS 클라이언트는 FastAPI가 생성하는 OpenAPI 스펙에서 이 스키마를 그대로 소비한다.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


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


# ── 실시간 미리보기 (Phase 6) — WebSocket /ws/live 이벤트 계약 ──────────────
# 웹/iOS 어느 클라이언트든 같은 JSON 스키마를 구독한다. type 필드로 판별.


class LiveTrackStarted(BaseModel):
    type: Literal["track_started"] = "track_started"
    track: "TrackMeta"


class LiveNoteOn(BaseModel):
    type: Literal["note_on"] = "note_on"
    index: int  # note_off와 짝을 맞추는 전사 스트림 내 노트 식별자
    pitch: int  # MIDI 피치 (0~127)
    instrument: str | None = None
    start_s: float  # 트랙 시작 기준 초


class LiveNoteOff(BaseModel):
    type: Literal["note_off"] = "note_off"
    index: int
    end_s: float


class LiveChord(BaseModel):
    type: Literal["chord"] = "chord"
    chord: str
    start_s: float
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class LiveProgress(BaseModel):
    type: Literal["progress"] = "progress"
    chunk_start_s: float  # 처리 완료된 청크의 시작 시각
    chunk_end_s: float


class LiveTrackEnded(BaseModel):
    type: Literal["track_ended"] = "track_ended"


LiveEvent = Annotated[
    Union[LiveTrackStarted, LiveNoteOn, LiveNoteOff, LiveChord, LiveProgress, LiveTrackEnded],
    Field(discriminator="type"),
]
live_event_adapter: TypeAdapter[LiveEvent] = TypeAdapter(LiveEvent)


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
