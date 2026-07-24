"""FastAPI 서버.

실행: uv run uvicorn musicna_api.main:app --reload
OpenAPI 스펙(/openapi.json)이 웹/iOS 클라이언트의 계약이 된다.
DB 경로는 환경변수 MUSICNA_DB (기본 data/musicna.db).

Phase 5에서 웹 UI 서빙, Phase 6에서 실시간 WebSocket을 붙인다.
macOS 캡처 세션 매니저(musicna_api.session)는 이 패키지에 두되 core에는 절대 넣지 않는다
(docs/PLAN.md '코어 분리' 절 참조).
"""

import os
from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from musicna_core.models import AnalysisResult
from musicna_core.store import create_session_factory, list_latest_analyses

app = FastAPI(title="musicna", version="0.1.0")


@lru_cache(maxsize=1)
def _session_factory():
    return create_session_factory(os.environ.get("MUSICNA_DB", "data/musicna.db"))


def get_db() -> Iterator[Session]:
    with _session_factory()() as session:
        yield session


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tracks", response_model=list[AnalysisResult])
def list_tracks(db: Session = Depends(get_db)) -> list[AnalysisResult]:
    """트랙별 최신 분석 결과, 캡처 시각 역순."""
    return list_latest_analyses(db)
