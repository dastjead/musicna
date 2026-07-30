"""Alembic 마이그레이션 환경.

target_metadata를 musicna_core.store.db.Base로 지정해 autogenerate가 모델
변경을 자동 감지하게 한다. 이 프로젝트는 오프라인(--sql) 마이그레이션을 쓰지
않으므로 온라인 모드만 지원한다.

sqlalchemy.url이 Config에 이미 설정돼 있으면(런타임에서 프로그래매틱으로
Config를 구성하는 경우, 예: db.py의 _run_migrations) 그 값을 그대로 쓰고,
없으면(CLI로 직접 alembic을 실행하는 경우) MUSICNA_DB 환경 변수 또는
기본값 "data/musicna.db"로 대체한다.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from musicna_core.store.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if not config.get_main_option("sqlalchemy.url"):
    db_path = os.environ.get("MUSICNA_DB", "data/musicna.db")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
