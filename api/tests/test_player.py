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
