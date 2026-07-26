"""DB 스키마 — docs/PLAN.md 'DB 스키마' 절의 SQLAlchemy 구현.

Phase 4에서 Alembic 마이그레이션을 도입하기 전까지는 create_all로 초기화한다.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    artist: Mapped[str | None] = mapped_column(String, nullable=True)
    album: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="unknown")
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    midi_path: Mapped[str | None] = mapped_column(String, nullable=True)

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="track")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    engine_versions: Mapped[str | None] = mapped_column(String, nullable=True)  # JSON 문자열
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    key: Mapped[str | None] = mapped_column(String, nullable=True)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    time_signature: Mapped[str | None] = mapped_column(String, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    track: Mapped[Track] = relationship(back_populates="analyses")
    sections: Mapped[list["SectionRow"]] = relationship(back_populates="analysis")
    chords: Mapped[list["Chord"]] = relationship(back_populates="analysis")
    moods: Mapped[list["Mood"]] = relationship(back_populates="analysis")
    section_chord_summaries: Mapped[list["SectionChordSummaryRow"]] = relationship(back_populates="analysis")
    chord_loops: Mapped[list["ChordLoopRow"]] = relationship(back_populates="analysis")


class SectionRow(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    label: Mapped[str] = mapped_column(String)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)

    analysis: Mapped[Analysis] = relationship(back_populates="sections")


class Chord(Base):
    __tablename__ = "chords"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    chord: Mapped[str] = mapped_column(String)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)  # midi / audio / merged
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="chords")


class Mood(Base):
    __tablename__ = "moods"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    tag: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)

    analysis: Mapped[Analysis] = relationship(back_populates="moods")


class SectionChordSummaryRow(Base):
    __tablename__ = "section_chord_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    section_label: Mapped[str] = mapped_column(String)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    roman_progression: Mapped[str] = mapped_column(String)  # JSON 리스트 문자열
    repeats_of: Mapped[int | None] = mapped_column(Integer, nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="section_chord_summaries")


class ChordLoopRow(Base):
    __tablename__ = "chord_loops"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    pattern: Mapped[str] = mapped_column(String)      # JSON 리스트 문자열
    occurrences: Mapped[str] = mapped_column(String)  # JSON 리스트[[start,end],...] 문자열

    analysis: Mapped[Analysis] = relationship(back_populates="chord_loops")


def create_session_factory(db_path: str = "data/musicna.db") -> sessionmaker:
    """SQLite 파일 경로로 세션 팩토리를 만들고 스키마를 초기화한다."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
