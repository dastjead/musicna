"""메타데이터 폴링 테스트.

- Apple Music: AppleScript(osascript) 출력 파싱 (parse_now_playing)
- Spotify: spotify_player 상태 폴링 (poll_now_playing_via_spotify_player) — musicna이 직접
  Spotify Connect 기기가 되므로(Phase 7), AppleScript는 더 이상 "spotify" 소스에 쓰이지 않는다
"""

from musicna_api.player import PlayerStatus, SpotifyPlayerError
from musicna_api.session.metadata import (
    FIELD_SEP, NowPlaying, parse_now_playing, poll_now_playing_via_spotify_player,
)


def _osa_line(*fields: str) -> str:
    return FIELD_SEP.join(fields)


def test_parse_playing_track():
    out = _osa_line("playing", "Canon in D", "Pachelbel", "Baroque Hits", "223.5", "12.3")
    now = parse_now_playing(out, source="apple_music")
    assert now == NowPlaying(
        state="playing",
        title="Canon in D",
        artist="Pachelbel",
        album="Baroque Hits",
        duration_s=223.5,
        position_s=12.3,
        source="apple_music",
    )
    assert now.track_key == "Pachelbel\x1fCanon in D"


def test_parse_paused_track_keeps_state():
    out = _osa_line("paused", "Canon in D", "Pachelbel", "", "223.5", "0.0")
    now = parse_now_playing(out, source="apple_music")
    assert now is not None
    assert now.state == "paused"
    assert now.album is None
    assert not now.is_playing


def test_parse_empty_output_returns_none():
    assert parse_now_playing("", source="apple_music") is None
    assert parse_now_playing("\n", source="apple_music") is None


def test_parse_stopped_returns_none():
    assert parse_now_playing("stopped", source="apple_music") is None


def test_spotify_player_now_playing_maps_status(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "get_status",
        lambda: PlayerStatus(
            is_playing=True, item_title="Test Track", item_artist="Test Artist",
            item_album="Test Album", item_duration_s=200.0, progress_s=10.0,
        ),
    )
    now = poll_now_playing_via_spotify_player()
    assert now == NowPlaying(
        state="playing", title="Test Track", artist="Test Artist", album="Test Album",
        duration_s=200.0, position_s=10.0, source="spotify",
    )


def test_spotify_player_paused_maps_state(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "get_status",
        lambda: PlayerStatus(is_playing=False, item_title="Test Track"),
    )
    now = poll_now_playing_via_spotify_player()
    assert now is not None
    assert now.state == "paused"


def test_spotify_player_none_status_returns_none(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(metadata, "get_status", lambda: None)
    assert poll_now_playing_via_spotify_player() is None


def test_spotify_player_no_track_title_returns_none(monkeypatch):
    """기기는 활성이지만 재생 중인 곡이 없는 경우(item 없음)."""
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(metadata, "get_status", lambda: PlayerStatus(is_playing=False))
    assert poll_now_playing_via_spotify_player() is None


def test_spotify_player_error_returns_none(monkeypatch):
    """데몬 미기동·인증 전 등 오류 시 크래시 없이 None(재생 없음 취급)."""
    import musicna_api.session.metadata as metadata

    def _raise():
        raise SpotifyPlayerError("daemon not running")

    monkeypatch.setattr(metadata, "get_status", _raise)
    assert poll_now_playing_via_spotify_player() is None


def test_poll_now_playing_routes_spotify_to_spotify_player(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "poll_now_playing_via_spotify_player",
        lambda: NowPlaying(state="playing", title="X", source="spotify"),
    )
    result = metadata.poll_now_playing("spotify")
    assert result is not None
    assert result.title == "X"
