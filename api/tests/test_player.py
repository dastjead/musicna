"""player.py의 spotify_player JSON 출력 파서 테스트.

fixture 문자열은 실제 `spotify_player get key playback`/`get key devices` 실행 결과
(2026-07-26, spotify_player 0.24.1, macOS)를 그대로 반영한 축약형이다.
"""

from musicna_api.player import PlayerDevice, PlayerStatus, parse_devices_json, parse_playback_json

PLAYBACK_JSON = """
{
  "device": {"id": "c119de5b-0e0c-4771-b5ce-f7163dd216c0", "is_active": true,
             "is_private_session": false, "is_restricted": false,
             "name": "spotify-player", "type": "Speaker", "volume_percent": 75},
  "repeat_state": "off", "shuffle_state": true,
  "context": {"uri": "spotify:playlist:37i9dQZF1DZ06evO08h9Zv"},
  "timestamp": 1784999240879, "progress_ms": 5614, "is_playing": true,
  "item": {
    "album": {"name": "Test Album"},
    "artists": [{"name": "Test Artist"}],
    "duration_ms": 219413, "name": "Test Track"
  },
  "currently_playing_type": "track"
}
"""

DEVICES_JSON = """
[{"id": "c119de5b-0e0c-4771-b5ce-f7163dd216c0", "is_active": false,
  "is_private_session": false, "is_restricted": false,
  "name": "spotify-player", "type": "Speaker", "volume_percent": 75}]
"""


def test_parse_playback_returns_status():
    status = parse_playback_json(PLAYBACK_JSON)
    assert status == PlayerStatus(
        is_playing=True,
        item_title="Test Track",
        item_artist="Test Artist",
        item_album="Test Album",
        item_duration_s=219.413,
        progress_s=5.614,
        volume_percent=75,
        device_name="spotify-player",
        shuffle=True,
        repeat_state="off",
    )


def test_parse_playback_null_returns_none():
    """아무것도 재생 중이 아니면 spotify_player가 JSON null을 출력한다."""
    assert parse_playback_json("null") is None


def test_parse_playback_missing_item_returns_status_without_track():
    raw = '{"device": null, "is_playing": false, "shuffle_state": false, "repeat_state": "off"}'
    status = parse_playback_json(raw)
    assert status is not None
    assert status.is_playing is False
    assert status.item_title is None
    assert status.device_name is None


def test_parse_devices_returns_list():
    devices = parse_devices_json(DEVICES_JSON)
    assert devices == [
        PlayerDevice(id="c119de5b-0e0c-4771-b5ce-f7163dd216c0", name="spotify-player",
                      is_active=False, volume_percent=75)
    ]


def test_parse_devices_empty_list():
    assert parse_devices_json("[]") == []


# Task 2: CLI wrapper tests
import subprocess

import pytest

from musicna_api.player import (
    SpotifyPlayerError, connect_device, get_status, list_devices,
    next_track, pause, play, play_pause, previous_track, set_volume,
)


class _FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


@pytest.fixture
def fake_run(monkeypatch):
    calls: list[list[str]] = []

    def _fake(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1:] == ["get", "key", "devices"]:
            return _FakeCompleted(stdout='[{"id":"d1","name":"spotify-player","is_active":true,"volume_percent":50}]')
        if cmd[1:] == ["get", "key", "playback"]:
            return _FakeCompleted(stdout="null")
        return _FakeCompleted(stdout="")

    monkeypatch.setattr(subprocess, "run", _fake)
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    return calls


def test_play_invokes_playback_play(fake_run):
    play()
    assert fake_run[-1][1:] == ["playback", "play"]


def test_pause_invokes_playback_pause(fake_run):
    pause()
    assert fake_run[-1][1:] == ["playback", "pause"]


def test_play_pause_invokes_playback_play_pause(fake_run):
    play_pause()
    assert fake_run[-1][1:] == ["playback", "play-pause"]


def test_next_track_invokes_playback_next(fake_run):
    next_track()
    assert fake_run[-1][1:] == ["playback", "next"]


def test_previous_track_invokes_playback_previous(fake_run):
    previous_track()
    assert fake_run[-1][1:] == ["playback", "previous"]


def test_set_volume_invokes_playback_volume(fake_run):
    set_volume(42)
    assert fake_run[-1][1:] == ["playback", "volume", "42"]


def test_set_volume_rejects_out_of_range():
    with pytest.raises(ValueError):
        set_volume(150)


def test_connect_device_invokes_connect_with_id(fake_run):
    connect_device("d1")
    assert fake_run[-1][1:] == ["connect", "--id", "d1"]


def test_list_devices_parses_output(fake_run):
    devices = list_devices()
    assert devices[0].id == "d1"
    assert fake_run[-1][1:] == ["get", "key", "devices"]


def test_get_status_returns_none_when_nothing_playing(fake_run):
    assert get_status() is None
    assert fake_run[-1][1:] == ["get", "key", "playback"]


def test_missing_binary_raises_helpful_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(SpotifyPlayerError, match="brew install spotify_player"):
        play()


def test_nonzero_exit_raises_with_stderr(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "run",
                         lambda cmd, **kw: _FakeCompleted(stderr="no active device", returncode=1))
    with pytest.raises(SpotifyPlayerError, match="no active device"):
        play()


def test_timeout_raises_spotify_player_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")

    def _timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 5))

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(SpotifyPlayerError, match="응답 시간 초과"):
        play()


# Task 3: SpotifyPlayerDaemon tests
import time

from musicna_api.player import SpotifyPlayerDaemon


class _FakeProc:
    def __init__(self):
        self._terminated = False

    def poll(self):
        return None if not self._terminated else 0

    def terminate(self):
        self._terminated = True

    def kill(self):
        self._terminated = True

    def wait(self, timeout=None):
        if not self._terminated:
            raise subprocess.TimeoutExpired(cmd="spotify_player", timeout=timeout)


def test_daemon_start_spawns_and_waits_ready(monkeypatch):
    spawned_cmds = []

    def _fake_popen(cmd, **kwargs):
        spawned_cmds.append(cmd)
        return _FakeProc()

    ready_after = {"n": 0}

    def _fake_list_devices():
        ready_after["n"] += 1
        if ready_after["n"] < 2:
            raise SpotifyPlayerError("not ready yet")
        return []

    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr("musicna_api.player.list_devices", _fake_list_devices)
    monkeypatch.setattr(time, "sleep", lambda s: None)  # 재시도 대기 스킵

    d = SpotifyPlayerDaemon()
    d.start(ready_timeout=5.0)

    assert spawned_cmds[0][1:] == ["-d", "-o", "enable_media_control=false"]
    assert d.is_running()


def test_daemon_start_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    d = SpotifyPlayerDaemon()
    with pytest.raises(SpotifyPlayerError, match="brew install"):
        d.start()


def test_daemon_start_process_exits_immediately_raises(monkeypatch):
    class _DeadProc(_FakeProc):
        def poll(self):
            return 1  # 즉시 종료

    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _DeadProc())
    d = SpotifyPlayerDaemon()
    with pytest.raises(SpotifyPlayerError, match="종료"):
        d.start(ready_timeout=1.0)


def test_daemon_start_idempotent_when_already_running(monkeypatch):
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: calls.append(1) or _FakeProc())
    monkeypatch.setattr("musicna_api.player.list_devices", lambda: [])

    d = SpotifyPlayerDaemon()
    d.start()
    d.start()  # 두 번째 호출은 재기동하지 않아야 함
    assert len(calls) == 1


def test_daemon_stop_terminates_process(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _FakeProc())
    monkeypatch.setattr("musicna_api.player.list_devices", lambda: [])

    d = SpotifyPlayerDaemon()
    d.start()
    d.stop()
    assert not d.is_running()


def test_daemon_stop_when_not_running_is_noop():
    d = SpotifyPlayerDaemon()
    d.stop()  # 예외 없이 조용히 반환
    assert not d.is_running()
