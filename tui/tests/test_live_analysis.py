"""LiveAnalysisWidget 테스트 — websockets.connect를 가짜 비동기 이터레이터로 대체."""

import json

import pytest
from textual.app import App, ComposeResult

from musicna_tui.widgets.live_analysis import LiveAnalysisWidget


class _FakeClient:
    live_ws_url = "ws://fake/ws/live"


class _FakeWebSocket:
    """`async with websockets.connect(url) as ws: async for msg in ws: ...` 형태를 흉내낸다."""

    def __init__(self, messages):
        self._messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


def _events_to_messages(events):
    return [json.dumps(e) for e in events]


class _LiveApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield LiveAnalysisWidget(self.client)


@pytest.mark.asyncio
async def test_shows_current_chord_after_chord_event(monkeypatch):
    events = [
        {"type": "track_started", "track": {"title": "X"}},
        {"type": "chord", "chord": "Cmaj7", "start_s": 0.0, "confidence": 0.9},
    ]
    monkeypatch.setattr(
        "musicna_tui.widgets.live_analysis.websockets.connect",
        lambda url: _FakeWebSocket(_events_to_messages(events)),
    )
    app = _LiveApp(_FakeClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        widget = pilot.app.query_one(LiveAnalysisWidget)
        assert "Cmaj7" in str(widget.render())


@pytest.mark.asyncio
async def test_shows_chord_history(monkeypatch):
    events = [
        {"type": "track_started", "track": {"title": "X"}},
        {"type": "chord", "chord": "C", "start_s": 0.0, "confidence": 0.9},
        {"type": "chord", "chord": "F", "start_s": 1.0, "confidence": 0.9},
        {"type": "chord", "chord": "G7", "start_s": 2.0, "confidence": 0.9},
    ]
    monkeypatch.setattr(
        "musicna_tui.widgets.live_analysis.websockets.connect",
        lambda url: _FakeWebSocket(_events_to_messages(events)),
    )
    app = _LiveApp(_FakeClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        widget = pilot.app.query_one(LiveAnalysisWidget)
        rendered = str(widget.render())
        assert "G7" in rendered  # 현재 코드
        assert "C" in rendered and "F" in rendered  # 히스토리


@pytest.mark.asyncio
async def test_tracks_active_note_count(monkeypatch):
    events = [
        {"type": "track_started", "track": {"title": "X"}},
        {"type": "note_on", "index": 1, "pitch": 60, "start_s": 0.0},
        {"type": "note_on", "index": 2, "pitch": 64, "start_s": 0.1},
    ]
    monkeypatch.setattr(
        "musicna_tui.widgets.live_analysis.websockets.connect",
        lambda url: _FakeWebSocket(_events_to_messages(events)),
    )
    app = _LiveApp(_FakeClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        widget = pilot.app.query_one(LiveAnalysisWidget)
        assert "2" in str(widget.render())


@pytest.mark.asyncio
async def test_note_off_reduces_active_count(monkeypatch):
    events = [
        {"type": "track_started", "track": {"title": "X"}},
        {"type": "note_on", "index": 1, "pitch": 60, "start_s": 0.0},
        {"type": "note_on", "index": 2, "pitch": 64, "start_s": 0.1},
        {"type": "note_off", "index": 1, "end_s": 0.5},
    ]
    monkeypatch.setattr(
        "musicna_tui.widgets.live_analysis.websockets.connect",
        lambda url: _FakeWebSocket(_events_to_messages(events)),
    )
    app = _LiveApp(_FakeClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        widget = pilot.app.query_one(LiveAnalysisWidget)
        assert "1" in str(widget.render())


@pytest.mark.asyncio
async def test_track_started_resets_state(monkeypatch):
    events = [
        {"type": "track_started", "track": {"title": "X"}},
        {"type": "chord", "chord": "G7", "start_s": 0.0, "confidence": 0.9},
        {"type": "track_started", "track": {"title": "Y"}},
    ]
    monkeypatch.setattr(
        "musicna_tui.widgets.live_analysis.websockets.connect",
        lambda url: _FakeWebSocket(_events_to_messages(events)),
    )
    app = _LiveApp(_FakeClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.pause()
        widget = pilot.app.query_one(LiveAnalysisWidget)
        assert "G7" not in str(widget.render())
