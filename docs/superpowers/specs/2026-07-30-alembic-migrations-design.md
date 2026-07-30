# Alembic 마이그레이션 도입

> Phase 4(DB 저장)에서 명시적으로 이월된 항목("Phase 4에서 Alembic 마이그레이션을 도입하기 전까지는 create_all로 초기화한다" — `core/src/musicna_core/store/db.py` 상단 주석). 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.

## 배경·목적

지금 `core/src/musicna_core/store/db.py`의 `create_session_factory()`는 `Base.metadata.create_all(engine)`으로만 스키마를 초기화한다. 이 방식은 새 테이블 추가는 자동으로 처리되지만, 기존 컬럼의 삭제·이름 변경·타입 변경 같은 실제 스키마 변경은 전혀 지원하지 않는다 — 앞으로 이런 변경이 필요해지면 실사용 데이터가 쌓인 `data/musicna.db`(git 미추적, 실제 캡처·분석 이력 보관 중)를 안전하게 다룰 방법이 없다.

이 설계는 Alembic을 도입해 ① 스키마 변경을 버전 관리되는 마이그레이션 스크립트로 표현하고 ② `create_session_factory()`를 부르는 모든 진입점(api 시작, `musicna-analyze` CLI, 테스트)이 자동으로 최신 스키마까지 적용받도록 하며 ③ 기존 `data/musicna.db`는 실제 ALTER 없이 "이미 최신"으로 stamp만 하여 데이터 손실 위험 없이 전환한다.

## 핵심 결정 사항

- **동기는 향후 스키마 변경 시 기존 `data/musicna.db` 보존** — 다수 머신 간 동기화나 다른 목적은 이번 범위 밖
- **마이그레이션은 `create_session_factory()` 내부에서 실행** — "api 시작 시 자동 적용"을 만족시키면서, `musicna-analyze`(`api/batch.py`) 등 다른 진입점도 동일한 코드 경로로 안전해짐(DRY). 별도의 "api 전용 시작 훅"을 만들지 않는다
- **`create_all()` 완전 제거** — 스키마의 유일한 소스는 이제 마이그레이션 스크립트. `create_all`과 마이그레이션이 동시에 존재하면 드리프트 위험이 생기므로 병행하지 않는다
- **초기 마이그레이션은 현재 7개 테이블(tracks/analyses/sections/chords/moods/section_chord_summaries/chord_loops)을 그대로 생성** — `create_all()`이 만들던 결과와 동일해야 함(자동 검증 방법은 아래 "테스트 영향" 참조)
- **기존 `data/musicna.db`는 `alembic stamp head`로만 처리** — 실제 ALTER 명령 실행 없이 `alembic_version` 테이블에 초기 리비전 ID만 기록. 이 작업은 실캡처 데이터가 있는 실제 파일에 손대는 것이므로, 구현 완료 후 실행 직전에 사용자 확인을 받는다(자동화하지 않음)
- **마이그레이션 스크립트는 패키지 내부(`core/src/musicna_core/store/migrations/`)에 위치** — `core/alembic/`처럼 `src/` 밖에 두면 `hatchling`의 `packages = ["src/musicna_core"]` 빌드 설정에 포함되지 않아, 향후 `musicna-core`가 설치된 환경(워크스페이스 editable install이 아닌 곳)에서 마이그레이션 파일을 못 찾는 문제가 생길 수 있다. 패키지 내부에 두면 `Path(__file__).parent`로 항상 정확히 위치를 찾을 수 있고, 빌드에도 자동 포함된다

## 아키텍처

```
core/pyproject.toml
    dependencies에 "alembic>=1.13" 추가 (base — extra 아님)

core/alembic.ini                                  (신규, 개발자가 CLI로 리비전 작성할 때만 사용)
    [alembic]
    script_location = src/musicna_core/store/migrations

core/src/musicna_core/store/migrations/            (신규 — 패키지에 포함됨)
    env.py                                          Base.metadata를 target_metadata로 사용
    script.py.mako                                  alembic init 기본 템플릿
    versions/
        <rev>_initial_schema.py                     tracks~chord_loops 7개 테이블 생성

core/src/musicna_core/store/db.py
    create_session_factory(db_path):
        engine = create_engine(f"sqlite:///{db_path}")
        _run_migrations(engine)      # ← create_all() 대체
        return sessionmaker(bind=engine)

    def _run_migrations(engine):
        cfg = Config()
        cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        cfg.set_main_option("sqlalchemy.url", str(engine.url))
        command.upgrade(cfg, "head")
```

호출부(`api/main.py`, `api/batch.py`)는 무수정 — 이미 `create_session_factory()`만 호출하고 있어 내부 구현 교체만으로 자동 적용된다.

## 컴포넌트별 상세

### `core/pyproject.toml`

`dependencies`에 `"alembic>=1.13"` 추가. Extra가 아니라 base 의존성으로 — `create_session_factory()`가 항상 이 경로를 타므로 optional일 수 없다.

### `core/src/musicna_core/store/migrations/env.py`

표준 alembic 템플릿을 기반으로, `target_metadata`를 `musicna_core.store.db.Base.metadata`로 지정해 향후 `alembic revision --autogenerate`가 모델 변경을 자동 감지하게 한다. `sqlalchemy.url`은 `env.py`가 직접 하드코딩하지 않고, 실행 시점에 `Config` 객체를 통해 주입받는다(테스트마다 다른 임시 DB 경로를 쓰므로).

### `core/src/musicna_core/store/migrations/versions/<rev>_initial_schema.py`

`alembic revision --autogenerate -m "initial schema"`로 생성 — 현재 `db.py`의 7개 모델 클래스가 정의하는 테이블·컬럼·FK를 그대로 반영한다. 생성 후 실제로 `create_all()`이 만들던 스키마와 동일한지 diff로 확인(아래 "테스트 영향" 참조).

### `core/src/musicna_core/store/db.py`

- `create_session_factory()`에서 `Base.metadata.create_all(engine)` 호출을 제거하고, 새 private 함수 `_run_migrations(engine)`을 추가해 그 자리에서 호출
- `_run_migrations()`는 `alembic.config.Config()`를 코드로 구성(ini 파일 읽지 않음 — cwd에 의존하지 않기 위해) 후 `alembic.command.upgrade(cfg, "head")` 실행
- 상단의 "Phase 4에서 Alembic 마이그레이션을 도입하기 전까지는" 주석 제거(더 이상 사실이 아님)

### `core/alembic.ini`

개발자가 향후 스키마를 바꿀 때 `cd core && alembic revision --autogenerate -m "..."`로 새 리비전을 만들기 위한 용도. 런타임 코드 경로(`_run_migrations`)는 이 파일을 읽지 않는다 — 순수히 CLI 편의용.

## 기존 `data/musicna.db` 전환 절차 (구현 완료 후 수동 실행, 사용자 확인 필요)

`env.py`는 CLI 단독 실행 시(런타임 `_run_migrations()` 경로가 아닐 때) `MUSICNA_DB` 환경 변수로 대상 DB 경로를 받는다 — `api/main.py`가 이미 같은 이름의 환경 변수로 DB 경로를 받고 있어(`os.environ.get("MUSICNA_DB", "data/musicna.db")`) 기존 관례와 일치시킨다:

```bash
cd core
MUSICNA_DB=../data/musicna.db alembic -c alembic.ini stamp head
```

실행 전 `data/musicna.db`를 백업 복사해두고, `alembic_version` 테이블에 초기 리비전 ID가 정확히 1행 기록됐는지, 기존 테이블 7개가 그대로인지(스키마 변경 없음) 확인 후 진행한다.

## 테스트 영향

- `core/tests/test_repository.py`·`test_scaffold.py`, `api/tests/test_tracks_endpoint.py`, `api/tests/test_batch.py` 등 `create_session_factory(tmp_path / "*.db")`를 쓰는 기존 테스트들이 전부 새 마이그레이션 경로를 타게 됨 — 즉, "빈 SQLite 파일 → `alembic upgrade head` → 기존 `create_all()`과 동일한 스키마"라는 것이 매 테스트 실행마다 간접 검증됨. 별도의 마이그레이션 전용 테스트를 추가로 요구하지 않음(YAGNI) — 다만 초기 리비전 작성 직후 한 번은 `alembic upgrade head`로 만든 스키마와 `create_all()`이 만들던 스키마를 `sqlite_master` 조회 등으로 직접 비교해 동일함을 눈으로 확인하는 단계를 구현 계획에 포함
- 워크스페이스 전체 테스트(`uv run pytest core/tests api/tests tui/tests`, 현재 232 passed·1 skipped) 실행 시간에 미치는 영향은 미미할 것으로 예상(SQLite 파일당 테이블 7개 생성은 수 ms 수준) — 구현 완료 후 실측 확인

## 알려진 한계 (범위 밖)

- 여러 프로세스가 동시에 같은 SQLite 파일에 대해 `alembic upgrade head`를 동시 실행하면 레이스가 생길 수 있음(예: api와 `musicna-analyze`를 정확히 같은 순간에 처음 실행). 1인 개발 머신 환경에서 발생 가능성이 낮고, 발생해도 SQLite 파일 락으로 인한 재시도 실패 정도이지 데이터 손상은 아니므로 이번 범위에서 별도 처리하지 않음
- 컬럼 타입 변경·삭제처럼 SQLite가 네이티브로 지원하지 않는 ALTER는 Alembic의 `batch_alter_table` 모드가 필요 — 이번 초기 마이그레이션은 테이블 생성만 하므로 해당 없음. 향후 그런 변경이 필요해지면 그때 리비전 작성 시 `batch_alter_table`을 쓰도록 기억해둘 것(이 스펙에서 별도 장치를 만들지는 않음)
