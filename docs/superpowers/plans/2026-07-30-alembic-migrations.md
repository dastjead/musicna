# Alembic 마이그레이션 도입 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `core/src/musicna_core/store/db.py`의 `Base.metadata.create_all()` 기반 스키마 초기화를 Alembic 마이그레이션으로 교체해, 향후 스키마 변경 시 실사용 데이터가 쌓인 `data/musicna.db`를 안전하게 다룰 수 있게 한다.

**Architecture:** 마이그레이션 스크립트를 `core/src/musicna_core/store/migrations/`(패키지 내부, 빌드에 자동 포함)에 두고, `create_session_factory()`가 내부적으로 `alembic upgrade head`를 프로그래매틱으로 실행하도록 바꾼다. 호출부(`api/main.py`, `api/batch.py`)는 무수정.

**Tech Stack:** Alembic(신규 base 의존성), 기존 SQLAlchemy 2.0 선언형 모델 그대로 재사용.

## Global Constraints

- 마이그레이션 코드는 반드시 `core/src/musicna_core/store/migrations/`(src 내부)에 위치한다 — src 밖(`core/alembic/` 등)에 두면 `core/pyproject.toml`의 `packages = ["src/musicna_core"]` 빌드 설정에 포함되지 않는다
- `create_session_factory(db_path: str = "data/musicna.db") -> sessionmaker` 시그니처는 변경하지 않는다 — 기존 호출부(`api/main.py:35`, `api/batch.py:28`, 다수 테스트)를 전부 무수정으로 유지
- `Base.metadata.create_all()` 호출은 완전히 제거한다 — 마이그레이션과 병행하지 않는다(스키마의 유일한 소스는 마이그레이션)
- Alembic은 `core/pyproject.toml`의 base `dependencies`에 추가한다(optional extra 아님) — `create_session_factory()`가 항상 이 경로를 타므로
- 기존 `data/musicna.db`(실캡처 데이터 보관 중, git 미추적)에 대한 `alembic stamp head` 실행은 **이 계획의 Task 범위 밖**이다 — 구현·리뷰가 전부 끝난 뒤 컨트롤러가 사용자 확인을 받고 직접 실행한다. 어떤 Task도 실제 `data/musicna.db` 파일을 건드리지 않는다(전부 `tmp_path`/`/tmp` 스크래치 경로만 사용)

---

## Task 1: Alembic 의존성 추가 + 마이그레이션 스캐폴딩

**Files:**
- Modify: `core/pyproject.toml`
- Create: `core/alembic.ini`
- Create: `core/src/musicna_core/store/migrations/env.py`
- Create: `core/src/musicna_core/store/migrations/script.py.mako`
- Create: `core/src/musicna_core/store/migrations/versions/.gitkeep`

**Interfaces:**
- Produces: `core/src/musicna_core/store/migrations/`(script_location으로 Task 2가 리비전을 생성할 위치), `env.py`의 `target_metadata = Base.metadata`(Task 2의 autogenerate가 이걸 기준으로 diff)

- [ ] **Step 1: `core/pyproject.toml`에 alembic 의존성 추가**

`core/pyproject.toml`의 `dependencies` 배열(`"pydantic>=2.7"`, `"sqlalchemy>=2.0"`, `"music21>=9"`가 있는 곳)에 추가:

```toml
dependencies = [
    "pydantic>=2.7",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "music21>=9",       # MIDI 키/코드 분석 (순수 Python이라 base에 포함)
]
```

- [ ] **Step 2: 설치**

Run: `cd /Users/dastjead/Codes/projects/musicna && uv sync --all-packages --extra transcribe --extra analyze --extra mood`
Expected: alembic이 설치됨 — `cd core && uv run python -c "import alembic; print(alembic.__version__)"`로 버전 출력 확인

- [ ] **Step 3: 마이그레이션 디렉터리 생성**

Run: `mkdir -p core/src/musicna_core/store/migrations/versions && touch core/src/musicna_core/store/migrations/versions/.gitkeep`

- [ ] **Step 4: `core/alembic.ini` 작성**

```ini
[alembic]
script_location = src/musicna_core/store/migrations

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

(이 ini는 `alembic revision --autogenerate` 등 개발자 CLI 용도로만 쓰인다 — 런타임 코드는 이 파일을 읽지 않고 `Config()`를 코드로 구성한다. Task 3 참조.)

- [ ] **Step 5: `core/src/musicna_core/store/migrations/env.py` 작성**

```python
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
```

- [ ] **Step 6: `core/src/musicna_core/store/migrations/script.py.mako` 작성**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 7: 스캐폴딩이 실제로 로드·실행되는지 검증**

리비전이 아직 하나도 없는 상태에서 `env.py`가 정상 로드되고(=`musicna_core.store.db` import 성공, `Base.metadata` 접근 성공) `command.upgrade`가 에러 없이 끝나는지 직접 확인한다(테이블은 아직 안 생김 — 리비전이 없으므로):

Run:
```bash
cd core
rm -f /tmp/musicna_alembic_scaffold_check.db
uv run python -c "
from pathlib import Path
from alembic.config import Config
from alembic import command

cfg = Config()
cfg.set_main_option('script_location', str(Path('src/musicna_core/store/migrations').resolve()))
cfg.set_main_option('sqlalchemy.url', 'sqlite:////tmp/musicna_alembic_scaffold_check.db')
command.upgrade(cfg, 'head')
print('OK: scaffolding loads and runs with zero revisions')
"
```
Expected: `OK: scaffolding loads and runs with zero revisions` 출력, 에러 없이 종료

- [ ] **Step 8: 커밋**

```bash
git add core/pyproject.toml uv.lock core/alembic.ini core/src/musicna_core/store/migrations/
git commit -m "feat: Alembic 마이그레이션 스캐폴딩 — env.py, script.py.mako, alembic.ini"
```

---

## Task 2: 초기 마이그레이션 생성 + 스키마 재현 회귀 테스트

**Files:**
- Create: `core/tests/test_migrations.py`
- Create: `core/src/musicna_core/store/migrations/versions/<autogenerated>_initial_schema.py`(파일명은 autogenerate가 리비전 해시로 정함)

**Interfaces:**
- Consumes: Task 1의 `core/src/musicna_core/store/migrations/`(script_location), `Base.metadata`(`core/src/musicna_core/store/db.py`의 7개 모델 클래스: `Track`, `Analysis`, `SectionRow`, `Chord`, `Mood`, `SectionChordSummaryRow`, `ChordLoopRow`)
- Produces: 초기 리비전 파일(Task 3가 이 리비전이 실제로 `create_session_factory()` 경로에서 적용됨을 검증) — `test_migrations.py`의 `EXPECTED_TABLES` 상수(Task 3가 같은 파일에 테스트를 추가하며 재사용)

- [ ] **Step 1: 실패하는 테스트 작성**

`core/tests/test_migrations.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd core && uv run pytest tests/test_migrations.py -v`
Expected: FAIL — 리비전이 아직 없어 `tables`가 빈 집합(`set()`)이라 `EXPECTED_TABLES`와 다름

- [ ] **Step 3: 초기 리비전 autogenerate**

Run:
```bash
cd core
rm -f /tmp/musicna_alembic_autogen.db
MUSICNA_DB=/tmp/musicna_alembic_autogen.db uv run alembic -c alembic.ini revision --autogenerate -m "initial schema"
```
Expected: `Generating .../versions/<hash>_initial_schema.py ... done` 출력, `core/src/musicna_core/store/migrations/versions/`에 새 파일 생성

- [ ] **Step 4: 생성된 리비전 파일 수동 검증**

`core/src/musicna_core/store/migrations/versions/<hash>_initial_schema.py`를 열어 다음을 전부 확인한다:

- `down_revision = None`(이 프로젝트의 첫 리비전이므로)
- `upgrade()` 안에 `op.create_table(...)` 호출이 정확히 7개 있고, 테이블명이 `tracks`·`analyses`·`sections`·`chords`·`moods`·`section_chord_summaries`·`chord_loops`를 전부 포함
- FK가 반영됐는지: `analyses` 테이블 정의에 `tracks.id`를 가리키는 `ForeignKeyConstraint`(또는 컬럼의 `sa.ForeignKey`), `sections`·`chords`·`moods`·`section_chord_summaries`·`chord_loops`는 각각 `analyses.id`를 가리키는 FK
- `downgrade()` 안에 `op.drop_table(...)`이 7개, 생성의 역순(FK 자식 테이블 먼저)으로 있는지
- 만약 이 중 하나라도 빠져 있거나 잘못됐다면(autogenerate가 놓친 경우) 리비전 파일을 직접 수정해 맞춘다 — 이 프로젝트의 유일한 초기 리비전이므로 정확해야 함

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `cd core && uv run pytest tests/test_migrations.py -v`
Expected: PASS — `tables`가 `EXPECTED_TABLES`(7개 실제 테이블 + `alembic_version`)와 정확히 일치

- [ ] **Step 6: 커밋**

```bash
git add core/tests/test_migrations.py core/src/musicna_core/store/migrations/versions/
git commit -m "feat: 초기 Alembic 리비전 생성 — tracks~chord_loops 7개 테이블"
```

---

## Task 3: `create_session_factory()`를 마이그레이션 경로로 교체

**Files:**
- Modify: `core/src/musicna_core/store/db.py`
- Modify: `core/tests/test_migrations.py`

**Interfaces:**
- Consumes: Task 2의 `core/src/musicna_core/store/migrations/`(이제 초기 리비전 포함), `EXPECTED_TABLES`(`test_migrations.py`)
- Produces: `create_session_factory(db_path: str = "data/musicna.db") -> sessionmaker`(시그니처 무변경, 내부 구현만 교체) — `api/main.py`·`api/batch.py`·기존 모든 테스트가 무수정으로 계속 동작해야 함

- [ ] **Step 1: 실패하는 테스트를 `test_migrations.py`에 추가**

`core/tests/test_migrations.py` 상단 import에 추가:

```python
from musicna_core.store import create_session_factory
```

파일 끝에 추가:

```python
def test_create_session_factory_applies_migrations(tmp_path):
    db_path = tmp_path / "factory.db"
    create_session_factory(str(db_path))
    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert tables == EXPECTED_TABLES
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd core && uv run pytest tests/test_migrations.py::test_create_session_factory_applies_migrations -v`
Expected: FAIL — `create_session_factory()`가 아직 `Base.metadata.create_all()`을 쓰고 있어 7개 테이블은 생기지만 `alembic_version` 테이블이 없어 `EXPECTED_TABLES`와 불일치

- [ ] **Step 3: `core/src/musicna_core/store/db.py` 수정**

파일 상단 docstring과 import를 교체:

```python
"""DB 스키마 — docs/PLAN.md 'DB 스키마' 절의 SQLAlchemy 구현.

스키마 초기화·변경은 Alembic 마이그레이션(store/migrations/)으로 관리한다.
"""

from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
```

(모델 클래스 정의 `Base`~`ChordLoopRow`는 무수정)

파일 하단의 `create_session_factory` 정의를 교체:

```python
def _run_migrations(db_path: str) -> None:
    """Alembic으로 db_path의 스키마를 최신 리비전까지 적용한다."""
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def create_session_factory(db_path: str = "data/musicna.db") -> sessionmaker:
    """SQLite 파일 경로로 세션 팩토리를 만들고 마이그레이션을 최신까지 적용한다."""
    _run_migrations(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd core && uv run pytest tests/test_migrations.py -v`
Expected: PASS — 3개 테스트 전부(Task 2의 1개 + Task 3의 1개... 정확히는 파일에 2개 테스트 함수: `test_alembic_upgrade_head_creates_expected_schema`, `test_create_session_factory_applies_migrations`)

- [ ] **Step 5: 워크스페이스 전체 테스트 실행**

Run: `cd /Users/dastjead/Codes/projects/musicna && uv run pytest core/tests api/tests tui/tests`
Expected: 234 passed, 1 skipped(기존 232 passed·1 skipped + 이번 Task에서 추가된 `test_migrations.py`의 신규 테스트 2개 — Task 2에서 1개, Task 3에서 1개)

- [ ] **Step 6: 커밋**

```bash
git add core/src/musicna_core/store/db.py core/tests/test_migrations.py
git commit -m "feat: create_session_factory가 create_all 대신 Alembic 마이그레이션을 적용하도록 교체"
```

---

## Task 4: 문서 갱신

**Files:**
- Modify: `docs/PLAN.md`
- Modify: `docs/PROGRESS.md`

**Interfaces:** 없음.

- [ ] **Step 1: `docs/PLAN.md` 갱신**

DB 관련 절(`| DB | SQLite + SQLAlchemy + Alembic | 개인용, 파일 하나, 추후 서버 이전 용이 |`이 있는 표 근처)에 Alembic이 실제로 도입됐다는 완료 표시를 추가한다. 정확한 위치는 구현 시점의 `docs/PLAN.md` 실제 내용을 열어 확인하고, 그 표/절의 기존 서술 스타일에 맞춰 "Alembic 마이그레이션 도입 완료(2026-07-30 이후, 실제 완료일로 갱신) — `core/src/musicna_core/store/migrations/`" 같은 한 줄을 자연스럽게 추가한다.

- [ ] **Step 2: `docs/PROGRESS.md` 갱신**

Phase 4 체크리스트에서 `- [ ] Alembic 마이그레이션 (스키마 변경 발생 시 도입)` 항목을 찾아 `[x]`로 바꾸고, 완료 설명을 덧붙인다:

```markdown
- [x] Alembic 마이그레이션 도입 — `core/src/musicna_core/store/migrations/`, `create_session_factory()`가 `create_all()` 대신 `alembic upgrade head`를 적용. 초기 리비전이 기존 7개 테이블을 그대로 생성. 회귀 테스트: `core/tests/test_migrations.py`. **주의**: 기존 `data/musicna.db`에 대한 `alembic stamp head`(실제 ALTER 없이 "이미 적용됨" 표시)는 이 구현에 포함되지 않음 — 실캡처 데이터가 있는 실제 파일이라 별도로 사용자 확인 후 수동 실행 필요(설계 스펙 참조)
```

"## 현재 상태"의 "다음 할 일 (원격 전용 작업이 필요하다면)" 줄(`Alembic 마이그레이션 도입`)을 제거하거나, "완료 — 기존 `data/musicna.db` stamp만 남음"으로 갱신한다.

작업 로그 표 마지막 행 다음에 실행 시점의 실제 커밋 해시로 갱신해 추가:

```markdown
| 2026-07-30 | Alembic 마이그레이션 도입 — `create_session_factory()`가 `create_all()` 대신 마이그레이션 적용, 초기 리비전이 기존 스키마 그대로 재현. 설계: [2026-07-30-alembic-migrations-design.md](superpowers/specs/2026-07-30-alembic-migrations-design.md) | 워크스페이스 232→234 passed. 기존 `data/musicna.db` stamp는 별도 수동 작업(컨트롤러가 사용자 확인 후 직접 실행) |
```

- [ ] **Step 3: 커밋 및 푸시**

```bash
git add docs/PLAN.md docs/PROGRESS.md
git commit -m "docs: Alembic 마이그레이션 도입 완료 반영"
git push
```

---

## 계획 범위 밖 — 컨트롤러가 별도 수행

이 계획의 모든 Task는 `tmp_path`/`/tmp` 스크래치 DB만 사용한다. 실제 `data/musicna.db`(git 미추적, 실캡처 데이터 보관)에 대한 처리는 이 계획에 포함되지 않으며, Task 1~4가 전부 완료·리뷰·병합된 뒤 컨트롤러가 다음을 사용자 확인 후 직접 실행한다:

```bash
cd core
cp ../data/musicna.db ../data/musicna.db.bak   # 백업
MUSICNA_DB=../data/musicna.db uv run alembic -c alembic.ini stamp head
```

실행 후 `alembic_version` 테이블에 초기 리비전 ID가 1행만 기록됐는지, 기존 7개 테이블과 데이터가 그대로인지 확인한다.

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙(`2026-07-30-alembic-migrations-design.md`)의 모든 핵심 결정 사항이 Task에 매핑됨 — "마이그레이션은 create_session_factory 내부에서 실행"(Task 3), "create_all 완전 제거"(Task 3), "초기 마이그레이션이 현재 7개 테이블 재현"(Task 2), "마이그레이션은 패키지 내부 위치"(Task 1), "기존 DB는 stamp만"(범위 밖 절에 명시).
- **플레이스홀더 스캔**: 없음 — 리비전 파일의 정확한 생성 코드만 autogenerate 도구가 만들므로 리터럴로 못 박지 않았지만, 그 대신 Step 4에 정확한 검증 체크리스트를 제공하고 Step 1~2의 테스트가 최종적으로 그 정확성을 자동 검증하므로 "구현 없이 손으로 확인하라"는 식의 방치가 아님.
- **타입/시그니처 일관성**: `create_session_factory(db_path: str = "data/musicna.db") -> sessionmaker` 시그니처가 Task 1~3 전체에서 동일하게 유지됨. `_run_migrations(db_path: str) -> None`은 Task 3에서 신규 정의·사용, 다른 Task가 이 이름을 참조하지 않으므로 불일치 위험 없음.
- **기존 진입점 영향**: `api/main.py:35`·`api/batch.py:28`은 `create_session_factory()`만 호출하고 있어 Task 3 완료 후 무수정으로 자동 적용됨 — 별도 Task 불필요(Global Constraints에 명시).
