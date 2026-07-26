"""저장소 패턴 — Pydantic(AnalysisResult) ↔ SQLAlchemy 행 변환.

파이프라인 출력(AnalysisResult)을 그대로 저장하고, API가 같은 모델로 다시 읽는다.
"""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from musicna_core.models import (
    AnalysisResult,
    ChordEvent,
    ChordLoop,
    MoodTag,
    Section,
    SectionChordSummary,
    TrackMeta,
)
from musicna_core.store.db import Analysis, Chord, ChordLoopRow, Mood, SectionChordSummaryRow, SectionRow, Track


def save_analysis(session: Session, result: AnalysisResult, audio_path: str | None = None) -> Track:
    """분석 결과를 저장한다. 같은 (title, artist, captured_at) 트랙이 있으면 재사용하고
    분석만 추가한다(엔진 버전업 재분석 이력 유지)."""
    meta = result.track
    track = session.scalars(
        select(Track).where(
            Track.title == meta.title,
            Track.artist == meta.artist,
            Track.captured_at == meta.captured_at,
        )
    ).first()
    if track is None:
        track = Track(
            title=meta.title,
            artist=meta.artist,
            album=meta.album,
            source=meta.source.value,
            duration_s=meta.duration_s,
            captured_at=meta.captured_at,
            audio_path=audio_path,
        )
        session.add(track)
    if result.midi_path:
        track.midi_path = result.midi_path

    analysis = Analysis(
        track=track,
        engine_versions=json.dumps(result.engine_versions),
        bpm=result.bpm,
        key=result.key,
        mode=result.mode,
        time_signature=result.time_signature,
        analyzed_at=result.analyzed_at or datetime.now(),
    )
    analysis.sections = [SectionRow(label=s.label, start_s=s.start_s, end_s=s.end_s) for s in result.sections]
    analysis.chords = [
        Chord(chord=c.chord, start_s=c.start_s, end_s=c.end_s, source=c.source.value, confidence=c.confidence)
        for c in result.chords
    ]
    analysis.moods = [Mood(tag=m.tag, score=m.score) for m in result.moods]
    analysis.section_chord_summaries = [
        SectionChordSummaryRow(
            section_label=s.section_label, start_s=s.start_s, end_s=s.end_s,
            roman_progression=json.dumps(s.roman_progression), repeats_of=s.repeats_of,
        )
        for s in result.section_chord_summaries
    ]
    analysis.chord_loops = [
        ChordLoopRow(pattern=json.dumps(loop.pattern), occurrences=json.dumps(loop.occurrences))
        for loop in result.chord_loops
    ]
    session.add(analysis)
    session.commit()
    return track


def _to_result(analysis: Analysis) -> AnalysisResult:
    track = analysis.track
    return AnalysisResult(
        track=TrackMeta(
            title=track.title,
            artist=track.artist,
            album=track.album,
            source=track.source,
            duration_s=track.duration_s,
            captured_at=track.captured_at,
        ),
        bpm=analysis.bpm,
        key=analysis.key,
        mode=analysis.mode,
        time_signature=analysis.time_signature,
        sections=[Section(label=s.label, start_s=s.start_s, end_s=s.end_s) for s in analysis.sections],
        chords=[
            ChordEvent(chord=c.chord, start_s=c.start_s, end_s=c.end_s, source=c.source, confidence=c.confidence)
            for c in analysis.chords
        ],
        moods=[MoodTag(tag=m.tag, score=m.score) for m in analysis.moods],
        section_chord_summaries=[
            SectionChordSummary(
                section_label=s.section_label, start_s=s.start_s, end_s=s.end_s,
                roman_progression=json.loads(s.roman_progression), repeats_of=s.repeats_of,
            )
            for s in analysis.section_chord_summaries
        ],
        chord_loops=[
            ChordLoop(pattern=json.loads(loop.pattern), occurrences=json.loads(loop.occurrences))
            for loop in analysis.chord_loops
        ],
        midi_path=track.midi_path,
        engine_versions=json.loads(analysis.engine_versions or "{}"),
        analyzed_at=analysis.analyzed_at,
    )


def has_analysis(session: Session, meta: TrackMeta) -> bool:
    """같은 (title, artist, captured_at) 트랙의 분석이 이미 있는지 — 배치 재실행 시 중복 방지용."""
    track = session.scalars(
        select(Track).where(
            Track.title == meta.title,
            Track.artist == meta.artist,
            Track.captured_at == meta.captured_at,
        )
    ).first()
    return track is not None and len(track.analyses) > 0


def list_latest_analyses(session: Session) -> list[AnalysisResult]:
    """트랙마다 최신 분석 1건씩, 캡처 시각 역순으로 돌려준다."""
    tracks = session.scalars(select(Track).order_by(Track.captured_at.desc(), Track.id.desc())).all()
    results = []
    for track in tracks:
        if track.analyses:
            latest = max(track.analyses, key=lambda a: (a.analyzed_at or datetime.min, a.id))
            results.append(_to_result(latest))
    return results
