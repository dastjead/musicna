"""오케스트레이션 — spotify_player 데몬과 캡처 세션 프로세스의 시작/중지/상태 조회.

TUI·미래의 macOS/iOS 앱은 이 모듈이 노출하는 REST(/system/*)만 호출한다 — 백그라운드
프로세스 관리 로직을 클라이언트마다 중복 구현하지 않는다 (docs/PLAN.md 코어 분리 전략).
"""

import signal
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from musicna_api import player


class SystemStatus(BaseModel):
    spotify_player_daemon: bool
    session_capturing: bool


class SystemOrchestrator:
    """spotify_player 데몬 + `musicna-session` 캡처 프로세스의 생명주기를 관리."""

    def __init__(self, audio_dir: Path = Path("data/audio")) -> None:
        self.audio_dir = audio_dir
        self._session_proc: subprocess.Popen | None = None

    def session_capturing(self) -> bool:
        return self._session_proc is not None and self._session_proc.poll() is None

    def start(self) -> None:
        player.daemon.start()
        if self.session_capturing():
            return
        self._session_proc = subprocess.Popen(
            [sys.executable, "-m", "musicna_api.session.cli",
             "--source", "spotify", "--out", str(self.audio_dir), "--system-audio"]
        )

    def stop(self, timeout: float = 10.0) -> None:
        if self.session_capturing():
            assert self._session_proc is not None
            # SIGTERM(기본 terminate())은 세션의 `except KeyboardInterrupt` 핸들러를
            # 트리거하지 않아 녹음 중이던 WAV가 마무리 저장되지 않는다 — SIGINT 필요.
            self._session_proc.send_signal(signal.SIGINT)
            try:
                self._session_proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._session_proc.kill()
                self._session_proc.wait(timeout=timeout)
        player.daemon.stop()

    def status(self) -> SystemStatus:
        return SystemStatus(
            spotify_player_daemon=player.daemon.is_running(),
            session_capturing=self.session_capturing(),
        )


orchestrator = SystemOrchestrator()


router = APIRouter(prefix="/system", tags=["system"])


@router.post("/start", response_model=SystemStatus)
def api_start() -> SystemStatus:
    try:
        orchestrator.start()
    except player.SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return orchestrator.status()


@router.post("/stop", response_model=SystemStatus)
def api_stop() -> SystemStatus:
    orchestrator.stop()
    return orchestrator.status()


@router.get("/status", response_model=SystemStatus)
def api_status() -> SystemStatus:
    return orchestrator.status()
