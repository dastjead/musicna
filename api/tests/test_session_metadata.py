"""AppleScript(osascript) now-playing 출력 파싱 테스트."""

from musicna_api.session.metadata import FIELD_SEP, NowPlaying, parse_now_playing


def _osa_line(*fields: str) -> str:
    return FIELD_SEP.join(fields)


def test_parse_playing_track():
    out = _osa_line("playing", "Canon in D", "Pachelbel", "Baroque Hits", "223.5", "12.3")
    now = parse_now_playing(out, source="spotify")
    assert now == NowPlaying(
        state="playing",
        title="Canon in D",
        artist="Pachelbel",
        album="Baroque Hits",
        duration_s=223.5,
        position_s=12.3,
        source="spotify",
    )
    assert now.track_key == "Pachelbel\x1fCanon in D"


def test_parse_paused_track_keeps_state():
    out = _osa_line("paused", "Canon in D", "Pachelbel", "", "223.5", "0.0")
    now = parse_now_playing(out, source="spotify")
    assert now is not None
    assert now.state == "paused"
    assert now.album is None
    assert not now.is_playing


def test_parse_empty_output_returns_none():
    assert parse_now_playing("", source="spotify") is None
    assert parse_now_playing("\n", source="spotify") is None


def test_parse_stopped_returns_none():
    # 앱은 실행 중이나 재생 중인 트랙이 없는 경우 상태만 온다
    assert parse_now_playing("stopped", source="spotify") is None
