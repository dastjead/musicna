"""SystemOrchestrator 테스트 — spotify_player 데몬과 세션 캡처 서브프로세스를 모두 모킹."""

import signal
import subprocess

import pytest

from musicna_api import player
from musicna_api.system import SystemOrchestrator, SystemStatus


class _FakeSessionProc:
    def __init__(self):
        self.signals_received: list[int] = []
        self._exited = False

    def poll(self):
        return None if not self._exited else 0

    def send_signal(self, sig):
        self.signals_received.append(sig)
        self._exited = True  # SIGINT를 받으면 정상 종료된다고 가정

    def kill(self):
        self._exited = True

    def wait(self, timeout=None):
        if not self._exited:
            raise subprocess.TimeoutExpired(cmd="musicna-session", timeout=timeout)


@pytest.fixture
def orch(monkeypatch, tmp_path):
    monkeypatch.setattr(player.daemon, "start", lambda *a, **kw: None)
    monkeypatch.setattr(player.daemon, "stop", lambda *a, **kw: None)
    monkeypatch.setattr(player.daemon, "is_running", lambda: True)
    return SystemOrchestrator(audio_dir=tmp_path)


def test_start_starts_daemon_and_session(monkeypatch, orch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeSessionProc())

    orch.start()

    assert "musicna_api.session.cli" in spawned[0]
    assert "--source" in spawned[0] and "spotify" in spawned[0]
    assert orch.session_capturing()


def test_start_is_idempotent_for_session(monkeypatch, orch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeSessionProc())

    orch.start()
    orch.start()

    assert len(spawned) == 1


def test_stop_sends_sigint_not_sigterm(monkeypatch, orch):
    """SIGTERM(기본 terminate())은 세션의 KeyboardInterrupt 핸들러를 트리거하지 않아
    녹음 중이던 WAV가 마무리 저장되지 않는다 — 반드시 SIGINT를 보내야 한다."""
    fake_proc = _FakeSessionProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: fake_proc)

    orch.start()
    orch.stop()

    assert fake_proc.signals_received == [signal.SIGINT]
    assert not orch.session_capturing()


def test_stop_when_not_capturing_is_noop(orch):
    orch.stop()  # 예외 없이 조용히 반환
    assert not orch.session_capturing()


def test_status_reports_both_components(monkeypatch, orch):
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _FakeSessionProc())
    orch.start()
    assert orch.status() == SystemStatus(spotify_player_daemon=True, session_capturing=True)
