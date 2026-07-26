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
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from musicna_api import player, remote_capture, system
from musicna_api.live import broadcaster
from musicna_core.models import AnalysisResult, LiveEvent, live_event_adapter
from musicna_core.store import create_session_factory, list_latest_analyses

app = FastAPI(title="musicna", version="0.1.0")
app.include_router(player.router)
app.include_router(system.router)
app.include_router(remote_capture.router)


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


# ── 실시간 미리보기 (Phase 6) ──────────────────────────────────────────


@app.post("/live/ingest", status_code=202)
async def live_ingest(events: list[LiveEvent]) -> dict[str, int]:  # async: 이벤트 루프에서 큐 조작
    """전사 프로세스(musicna-live)가 보내는 이벤트를 검증해 WS 구독자에게 중계한다.

    로컬(개인용) 사용 전제 — 서버를 외부에 노출한다면 인증을 붙일 것.
    """
    for event in events:
        broadcaster.publish(live_event_adapter.dump_json(event).decode())
    return {"accepted": len(events), "subscribers": broadcaster.subscriber_count}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    """실시간 이벤트 스트림 — LiveEvent JSON을 순서대로 내보낸다 (웹/iOS 공용 계약)."""
    await ws.accept()
    q = broadcaster.subscribe()
    try:
        while True:
            await ws.send_text(await q.get())
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unsubscribe(q)


# 웹 UI 정적 서빙 — API 라우트 등록 뒤에 마운트해야 /tracks 등이 우선한다.
# 저장소 루트가 아닌 곳에서 실행하면 MUSICNA_WEB으로 web/ 경로를 지정한다.
_web_dir = Path(os.environ.get("MUSICNA_WEB", "web"))
if _web_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dir), html=True), name="web")
