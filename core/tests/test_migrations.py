"""Alembic 마이그레이션이 db.py의 스키마를 정확히 재현하는지 검증한다."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "src" / "musicna_core" / "store" / "migrations"

EXPECTED_TABLES = {
    "tracks",
    "analyses",
    "sections",
    "chords",
    "moods",
    "section_chord_summaries",
    "chord_loops",
    "alembic_version",
}


def _upgrade_to_head(db_path: Path) -> set[str]:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    return set(inspect(engine).get_table_names())


def test_alembic_upgrade_head_creates_expected_schema(tmp_path):
    tables = _upgrade_to_head(tmp_path / "migrated.db")
    assert tables == EXPECTED_TABLES
