"""FastAPI 스켈레톤.

실행: uv run uvicorn musicna_api.main:app --reload
OpenAPI 스펙(/openapi.json)이 웹/iOS 클라이언트의 계약이 된다.

Phase 4에서 DB 연동, Phase 5에서 웹 UI 서빙, Phase 6에서 실시간 WebSocket을 붙인다.
macOS 캡처 세션 매니저(캡처 프로세스 관리, AppleScript 메타데이터)도 이 서버 프로세스에 얹되
core에는 절대 넣지 않는다 (docs/PLAN.md '코어 분리' 절 참조).
"""

from fastapi import FastAPI

from musicna_core.models import AnalysisResult

app = FastAPI(title="musicna", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tracks", response_model=list[AnalysisResult])
def list_tracks() -> list[AnalysisResult]:
    """분석된 트랙 목록. Phase 4에서 SQLite 조회로 구현."""
    return []
