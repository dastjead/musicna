"""세션 매니저 CLI의 순수 로직 테스트 — 스트림 읽기, 무음 폴백 트랙 명명."""

import io

from musicna_api.session.cli import fallback_now_playing, read_exact


def test_read_exact_reassembles_partial_reads():
    class OneByOne(io.RawIOBase):
        def __init__(self, data: bytes):
            self._buf = io.BytesIO(data)

        def read(self, n: int = -1) -> bytes:
            return self._buf.read(1)  # 항상 1바이트씩만 반환

    stream = OneByOne(b"abcdef")
    assert read_exact(stream, 4) == b"abcd"
    assert read_exact(stream, 2) == b"ef"


def test_read_exact_returns_remainder_at_eof():
    stream = io.BytesIO(b"abc")
    assert read_exact(stream, 8) == b"abc"
    assert read_exact(stream, 8) == b""


def test_fallback_now_playing_numbers_tracks():
    first = fallback_now_playing(1)
    second = fallback_now_playing(2)
    assert first.is_playing
    assert first.title == "Untitled 001"
    assert second.title == "Untitled 002"
    assert first.track_key != second.track_key
    assert first.source == "unknown"
