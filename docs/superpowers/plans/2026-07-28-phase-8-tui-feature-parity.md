# Phase 8 — TUI 기능 동등화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TUI(`tui/`)에 검색·플레이리스트 재생, 실시간 분석 뷰(코드+노트 활동), 라이브러리 브라우저를 추가해 웹 UI로 할 수 있는 모든 열람·재생 작업을 TUI에서도 수행 가능하게 한다.

**Architecture:** `api/player.py`에 `search()`/`list_playlists()`/`play_playlist()` 함수 + 신규 REST 라우트 3개를 추가한다. `tui/client.py`에 대응 메서드를 추가하고, `tui/widgets/`에 라이브러리 브라우저(`DataTable` 기반, `/tracks` 폴링)와 실시간 분석 뷰(`websockets` 클라이언트로 `/ws/live` 구독) 위젯을, `tui/widgets/`에 검색·플레이리스트 모달 화면(`ModalScreen`)을 신설해 `app.py`에 조립한다. 기존 `PlayerPanel`/`SessionStatus`와 동일하게 위젯은 `ApiClient`만 통해 api와 통신한다.

**Tech Stack:** Python 3.11+, Textual 8.x(`DataTable`, `Input`, `ModalScreen`), `websockets>=12`(신규 tui 의존성, api가 이미 쓰는 것과 동일 계열), FastAPI, httpx.

## Global Constraints

- `core/`는 무수정(이번 Phase는 `api/`·`tui/`만 건드린다).
- `tui/`는 api만 호출한다 — 위젯이 subprocess·파일에 직접 접근하지 않는다(`tui/src/musicna_tui/client.py` 상단 docstring 원칙 유지).
- 신규 REST 엔드포인트는 기존 `api/player.py`의 `router = APIRouter(prefix="/player", ...)`에 추가한다(신규 라우터 파일 생성 안 함) — 설계 스펙(`docs/superpowers/specs/2026-07-26-tui-player-orchestration-design.md`)이 `/player/search`, `/player/playlists`, `/player/playlists/{id}/play`로 명시.
- **spotify_player CLI 문법·JSON 스키마의 출처 고지**: 이 계획의 `search`/`get key user-playlists`/`playback start context playlist` 문법과 그 JSON 응답 필드(특히 `duration: {secs, nanos}`, `owner: [name, user_id]`, id 필드가 평문 문자열이라는 점)는 2026-07-28 기준 [aome510/spotify-player](https://github.com/aome510/spotify-player) master 브랜치 소스(`spotify_player/src/cli/commands.rs`, `cli/client.rs`, `state/model.rs`)를 직접 읽어 도출한 것이며, 기존 `player.py`의 playback/devices 파서처럼 macOS 실기기에서 직접 실행해 확인한 것은 **아니다**(이 세션은 Linux 컨테이너라 `spotify_player` 바이너리 자체가 없음). **Task 1·2의 macOS 실기기 검증 단계에서 반드시** `spotify_player search "아무 검색어"`와 `spotify_player get key user-playlists`를 실제로 실행해 이 계획의 fixture JSON과 실제 출력을 비교하고, 설치된 버전이 달라 필드가 다르면 파서를 그에 맞게 조정할 것.
- 검색 결과 중 **재생 가능한 것은 플레이리스트뿐**이다(설계 스펙이 `play_playlist(id)`만 명시, 트랙 단건 재생 함수는 범위 밖) — 검색 화면에서 트랙/아티스트/앨범 결과에 재생 동작을 추가하지 말 것. 이미 승인된 설계 범위를 벗어나는 확장이다.
- 터미널은 그래픽을 그릴 수 없으므로, 웹의 캔버스 피아노 롤을 TUI에서 텍스트로 흉내내려 하지 않는다 — 현재 코드·직전 진행·울리는 노트 개수로 "실시간 분석"의 기능적 동등성(열람 가능)을 충족한다(각 클라이언트는 독립 인터페이스이되 기능은 동등하다는 기존 설계 원칙, 픽셀 단위 동일함을 요구하지 않음).

---

## Task 1: `api/player.py` — search / list_playlists 파서 + CLI 래퍼

**Files:**
- Modify: `api/src/musicna_api/player.py`
- Test: `api/tests/test_player.py`

**Interfaces:**
- Produces: `SearchTrack`, `SearchArtist`, `SearchAlbum`, `SearchPlaylist`, `SearchResults`, `Playlist` (Pydantic `BaseModel`), `parse_search_json(raw: str) -> SearchResults`, `parse_playlists_json(raw: str) -> list[Playlist]`, `search(query: str) -> SearchResults`, `list_playlists() -> list[Playlist]`, `play_playlist(playlist_id: str) -> None` — 전부 `musicna_api.player`에서 import 가능해야 함(Task 2가 라우트에서 사용).

- [ ] **Step 1: 실패하는 파서 테스트를 작성**

`api/tests/test_player.py` 상단 import 블록(`from musicna_api.player import PlayerDevice, PlayerStatus, parse_devices_json, parse_playback_json`) 다음에 추가:

```python
from musicna_api.player import (
    Playlist, SearchResults, parse_playlists_json, parse_search_json,
)

# fixture는 aome510/spotify-player master 소스(state/model.rs의 SearchResults/Track/Playlist
# 구조체, cli/client.rs의 serde_json 직렬화 경로)를 읽어 구성한 것 — macOS 실기기 미검증.
# duration은 std::time::Duration의 serde 기본 표현({"secs", "nanos"})을 그대로 반영한다.
SEARCH_JSON = """
{
  "tracks": [
    {"id": "4y4VO05kYgUTo2bzbox1an", "name": "Test Song",
     "artists": [{"id": "a1", "name": "Test Artist"}],
     "album": {"id": "al1", "release_date": "2020-01-01", "name": "Test Album",
               "artists": [{"id": "a1", "name": "Test Artist"}], "typ": "album", "added_at": 0},
     "duration": {"secs": 219, "nanos": 413000000}, "explicit": false}
  ],
  "artists": [{"id": "a1", "name": "Test Artist"}],
  "albums": [{"id": "al1", "release_date": "2020-01-01", "name": "Test Album",
              "artists": [{"id": "a1", "name": "Test Artist"}], "typ": "album", "added_at": 0}],
  "playlists": [
    {"id": "37i9dQZF1DZ06evO08h9Zv", "collaborative": false, "name": "Test Playlist",
     "owner": ["Test User", "user123"], "desc": "", "current_folder_id": 0, "snapshot_id": "snap1"}
  ],
  "shows": [], "episodes": []
}
"""

USER_PLAYLISTS_JSON = """
[
  {"id": "37i9dQZF1DZ06evO08h9Zv", "collaborative": false, "name": "Liked Songs Radio",
   "owner": ["Test User", "user123"], "desc": "", "current_folder_id": 0, "snapshot_id": "snap1"},
  {"id": "5abcXYZ123", "collaborative": true, "name": "Shared Mix",
   "owner": ["Friend", "user456"], "desc": "collab playlist", "current_folder_id": 0, "snapshot_id": "snap2"}
]
"""


def test_parse_search_returns_tracks_artists_albums_playlists():
    result = parse_search_json(SEARCH_JSON)
    assert result.tracks[0].id == "4y4VO05kYgUTo2bzbox1an"
    assert result.tracks[0].name == "Test Song"
    assert result.tracks[0].artists == ["Test Artist"]
    assert result.tracks[0].album == "Test Album"
    assert result.tracks[0].duration_s == 219.413
    assert result.artists[0].name == "Test Artist"
    assert result.albums[0].name == "Test Album"
    assert result.playlists[0].id == "37i9dQZF1DZ06evO08h9Zv"
    assert result.playlists[0].owner == "Test User"


def test_parse_search_empty_query_returns_empty_results():
    assert parse_search_json(
        '{"tracks": [], "artists": [], "albums": [], "playlists": [], "shows": [], "episodes": []}'
    ) == SearchResults()


def test_parse_search_track_without_album_has_none_album():
    raw = """
    {"tracks": [{"id": "t1", "name": "X", "artists": [], "album": null,
                 "duration": {"secs": 10, "nanos": 0}, "explicit": false}],
     "artists": [], "albums": [], "playlists": [], "shows": [], "episodes": []}
    """
    assert parse_search_json(raw).tracks[0].album is None


def test_parse_playlists_returns_list():
    playlists = parse_playlists_json(USER_PLAYLISTS_JSON)
    assert playlists == [
        Playlist(id="37i9dQZF1DZ06evO08h9Zv", name="Liked Songs Radio",
                  owner="Test User", collaborative=False),
        Playlist(id="5abcXYZ123", name="Shared Mix", owner="Friend", collaborative=True),
    ]


def test_parse_playlists_empty_list():
    assert parse_playlists_json("[]") == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: FAIL — `ImportError: cannot import name 'Playlist'`(또는 `SearchResults` 등, 아직 정의되지 않은 이름들)

- [ ] **Step 3: `api/src/musicna_api/player.py`에 모델·파서·CLI 함수 추가**

`class PlayerDevice(BaseModel): ...` 블록(파일 37~42번째 줄 부근) 다음, `def parse_playback_json` 이전에 추가:

```python
class SearchTrack(BaseModel):
    id: str
    name: str
    artists: list[str] = []
    album: str | None = None
    duration_s: float | None = None


class SearchArtist(BaseModel):
    id: str
    name: str


class SearchAlbum(BaseModel):
    id: str
    name: str


class SearchPlaylist(BaseModel):
    id: str
    name: str
    owner: str | None = None


class SearchResults(BaseModel):
    tracks: list[SearchTrack] = []
    artists: list[SearchArtist] = []
    albums: list[SearchAlbum] = []
    playlists: list[SearchPlaylist] = []


class Playlist(BaseModel):
    id: str
    name: str
    owner: str | None = None
    collaborative: bool = False
```

`def parse_devices_json` 함수 다음, `class SpotifyPlayerError` 이전에 추가:

```python
def _duration_to_seconds(duration: dict | None) -> float | None:
    """spotify_player가 `std::time::Duration`을 serde 기본 표현({"secs","nanos"})으로 직렬화한다."""
    if not duration:
        return None
    return duration.get("secs", 0) + duration.get("nanos", 0) / 1e9


def parse_search_json(raw: str) -> SearchResults:
    """`spotify_player search "<query>"` 출력을 파싱."""
    data = json.loads(raw)
    return SearchResults(
        tracks=[
            SearchTrack(
                id=t["id"], name=t["name"],
                artists=[a["name"] for a in t.get("artists", [])],
                album=(t.get("album") or {}).get("name"),
                duration_s=_duration_to_seconds(t.get("duration")),
            )
            for t in data.get("tracks", [])
        ],
        artists=[SearchArtist(id=a["id"], name=a["name"]) for a in data.get("artists", [])],
        albums=[SearchAlbum(id=a["id"], name=a["name"]) for a in data.get("albums", [])],
        playlists=[
            SearchPlaylist(id=p["id"], name=p["name"], owner=(p.get("owner") or [None])[0])
            for p in data.get("playlists", [])
        ],
    )


def parse_playlists_json(raw: str) -> list[Playlist]:
    """`spotify_player get key user-playlists` 출력을 파싱."""
    data = json.loads(raw)
    return [
        Playlist(
            id=p["id"], name=p["name"],
            owner=(p.get("owner") or [None])[0],
            collaborative=p.get("collaborative", False),
        )
        for p in data
    ]
```

`def get_status() -> PlayerStatus | None: ...` 함수 다음, `class SpotifyPlayerDaemon` 이전에 추가:

```python
def search(query: str) -> SearchResults:
    return parse_search_json(_run_cli("search", query))


def list_playlists() -> list[Playlist]:
    return parse_playlists_json(_run_cli("get", "key", "user-playlists"))


def play_playlist(playlist_id: str) -> None:
    _run_cli("playback", "start", "context", "playlist", "--id", playlist_id)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: PASS — 전부(기존 테스트 + 신규 6개)

- [ ] **Step 5: 전체 api 테스트로 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add api/src/musicna_api/player.py api/tests/test_player.py
git commit -m "feat: player.py에 search/list_playlists/play_playlist 파서·CLI 래퍼 추가"
```

---

## Task 2: `api/player.py` — `/player/search`, `/player/playlists`, `/player/playlists/{id}/play` 라우트

**Files:**
- Modify: `api/src/musicna_api/player.py`
- Test: `api/tests/test_player_routes.py`

**Interfaces:**
- Consumes: `search`, `list_playlists`, `play_playlist`, `SearchResults`, `Playlist`(Task 1)
- Produces: `GET /player/search?query=<str>` → `SearchResults`. `GET /player/playlists` → `list[Playlist]`. `POST /player/playlists/{playlist_id}/play` → `{"status": "ok"}`. 셋 다 `SpotifyPlayerError` 시 503.

- [ ] **Step 1: 실패하는 라우트 테스트를 작성**

`api/tests/test_player_routes.py` 파일 끝에 추가:

```python
from musicna_api.player import Playlist, SearchResults


def test_search_returns_results(monkeypatch, client):
    monkeypatch.setattr(
        player, "search",
        lambda query: SearchResults(playlists=[{"id": "p1", "name": "X", "owner": None}]),
    )
    r = client.get("/player/search", params={"query": "test"})
    assert r.status_code == 200
    assert r.json()["playlists"][0]["id"] == "p1"


def test_search_failure_returns_503(monkeypatch, client):
    def _raise(query):
        raise SpotifyPlayerError("no active device")
    monkeypatch.setattr(player, "search", _raise)
    r = client.get("/player/search", params={"query": "test"})
    assert r.status_code == 503


def test_playlists_returns_list(monkeypatch, client):
    monkeypatch.setattr(player, "list_playlists",
                         lambda: [Playlist(id="p1", name="X", owner="Y", collaborative=False)])
    r = client.get("/player/playlists")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "p1"


def test_play_playlist_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "play_playlist", lambda playlist_id: calls.append(playlist_id))
    r = client.post("/player/playlists/p1/play")
    assert r.status_code == 200
    assert calls == ["p1"]


def test_play_playlist_failure_returns_503(monkeypatch, client):
    def _raise(playlist_id):
        raise SpotifyPlayerError("daemon not running")
    monkeypatch.setattr(player, "play_playlist", _raise)
    r = client.post("/player/playlists/p1/play")
    assert r.status_code == 503
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_player_routes.py -v`
Expected: FAIL — 라우트가 없어 404 (또는 `AttributeError: module has no attribute 'search'`)

- [ ] **Step 3: `api/src/musicna_api/player.py`에 라우트 3개 추가**

`@router.get("/status", response_model=PlayerStatus | None)` 블록(파일 끝) 다음에 추가:

```python
@router.get("/search", response_model=SearchResults)
def api_search(query: str) -> SearchResults:
    try:
        return search(query)
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/playlists", response_model=list[Playlist])
def api_list_playlists() -> list[Playlist]:
    try:
        return list_playlists()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/playlists/{playlist_id}/play")
def api_play_playlist(playlist_id: str) -> dict[str, str]:
    try:
        play_playlist(playlist_id)
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests/test_player_routes.py -v`
Expected: PASS — 전부(기존 + 신규 5개)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add api/src/musicna_api/player.py api/tests/test_player_routes.py
git commit -m "feat: GET /player/search, GET /player/playlists, POST /player/playlists/{id}/play 라우트 추가"
```

---

## Task 3: `tui/client.py` — 검색·플레이리스트·라이브러리 메서드 추가

**Files:**
- Modify: `tui/src/musicna_tui/client.py`
- Test: `tui/tests/test_client.py`

**Interfaces:**
- Consumes: `GET /player/search`, `GET /player/playlists`, `POST /player/playlists/{id}/play`, `GET /tracks`(Task 1·2, 기존 `/tracks`는 이미 존재)
- Produces: `ApiClient.tracks() -> list[dict]`, `ApiClient.player_search(query: str) -> dict`, `ApiClient.player_playlists() -> list[dict]`, `ApiClient.player_play_playlist(playlist_id: str) -> None`, `ApiClient.live_ws_url -> str`(property) — Task 4~7이 이 메서드들을 씀.

- [ ] **Step 1: 실패하는 테스트를 작성**

`tui/tests/test_client.py` 파일 끝에 추가:

```python
def test_tracks_returns_list():
    def handler(request):
        assert request.url.path == "/tracks"
        return httpx.Response(200, json=[{"id": 1, "track": {"title": "X"}}])
    tracks = _client_with(handler).tracks()
    assert tracks == [{"id": 1, "track": {"title": "X"}}]


def test_player_search_sends_query_param():
    def handler(request):
        assert request.url.path == "/player/search"
        assert request.url.params["query"] == "test song"
        return httpx.Response(200, json={"tracks": [], "artists": [], "albums": [], "playlists": []})
    result = _client_with(handler).player_search("test song")
    assert result == {"tracks": [], "artists": [], "albums": [], "playlists": []}


def test_player_playlists_returns_list():
    def handler(request):
        assert request.url.path == "/player/playlists"
        return httpx.Response(200, json=[{"id": "p1", "name": "X", "owner": None, "collaborative": False}])
    playlists = _client_with(handler).player_playlists()
    assert playlists[0]["id"] == "p1"


def test_player_play_playlist_posts_to_correct_path():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_play_playlist("p1")
    assert calls == ["/player/playlists/p1/play"]


def test_live_ws_url_derived_from_http_base_url():
    client = ApiClient(base_url="http://mac-mini.tailnet.ts.net:8000")
    assert client.live_ws_url == "ws://mac-mini.tailnet.ts.net:8000/ws/live"


def test_live_ws_url_uses_wss_for_https_base_url():
    client = ApiClient(base_url="https://mac-mini.tailnet.ts.net:8000")
    assert client.live_ws_url == "wss://mac-mini.tailnet.ts.net:8000/ws/live"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_client.py -v`
Expected: FAIL — `AttributeError: 'ApiClient' object has no attribute 'tracks'`(등)

- [ ] **Step 3: `tui/src/musicna_tui/client.py`에 메서드 추가**

`def system_status(self) -> dict: ...` 메서드 다음, `@property\n    def base_url(self) -> str: ...` 이전에 추가:

```python
    def tracks(self) -> list[dict]:
        r = self._http.get("/tracks")
        r.raise_for_status()
        return r.json()

    def player_search(self, query: str) -> dict:
        r = self._http.get("/player/search", params={"query": query})
        r.raise_for_status()
        return r.json()

    def player_playlists(self) -> list[dict]:
        r = self._http.get("/player/playlists")
        r.raise_for_status()
        return r.json()

    def player_play_playlist(self, playlist_id: str) -> None:
        self._http.post(f"/player/playlists/{playlist_id}/play").raise_for_status()

    @property
    def live_ws_url(self) -> str:
        ws_scheme = "wss" if self.base_url.startswith("https://") else "ws"
        rest = self.base_url.split("://", 1)[1].rstrip("/")
        return f"{ws_scheme}://{rest}/ws/live"
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_client.py -v`
Expected: PASS — 전부(기존 + 신규 6개)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/client.py tui/tests/test_client.py
git commit -m "feat: ApiClient에 tracks/player_search/player_playlists/player_play_playlist/live_ws_url 추가"
```

---

## Task 4: `tui/widgets/library_browser.py` — 라이브러리 브라우저 위젯

**Files:**
- Create: `tui/src/musicna_tui/widgets/library_browser.py`
- Test: `tui/tests/test_library_browser.py`

**Interfaces:**
- Consumes: `ApiClient.tracks()`(Task 3)
- Produces: `LibraryBrowserWidget(DataTable)` — `__init__(self, client: ApiClient)`. Task 8이 `app.py`의 `compose()`에서 이 클래스를 사용.

- [ ] **Step 1: 실패하는 테스트를 작성**

`tui/tests/test_library_browser.py` 신규 작성:

```python
"""LibraryBrowserWidget 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from musicna_tui.widgets.library_browser import LibraryBrowserWidget


class _FakeClient:
    def __init__(self, tracks=None, raise_on_fetch=False):
        self._tracks = tracks or []
        self._raise = raise_on_fetch

    def tracks(self):
        if self._raise:
            raise RuntimeError("connection refused")
        return self._tracks


class _BrowserApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield LibraryBrowserWidget(self.client)


@pytest.mark.asyncio
async def test_populates_rows_from_tracks():
    tracks = [
        {"id": 1, "track": {"title": "Song A", "artist": "Artist A"},
         "bpm": 120.0, "key": "C", "mode": "major", "moods": [{"tag": "happy", "score": 0.8}]},
        {"id": 2, "track": {"title": "Song B", "artist": None},
         "bpm": None, "key": None, "mode": None, "moods": []},
    ]
    app = _BrowserApp(_FakeClient(tracks=tracks))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.row_count == 2
        row0 = table.get_row_at(0)
        assert row0[0] == "Song A"
        assert row0[1] == "Artist A"
        assert row0[2] == "120"
        assert row0[3] == "C major"
        assert row0[4] == "happy"
        row1 = table.get_row_at(1)
        assert row1[1] == "-"
        assert row1[2] == "-"
        assert row1[3] == "-"
        assert row1[4] == "-"


@pytest.mark.asyncio
async def test_shows_error_row_when_fetch_fails():
    app = _BrowserApp(_FakeClient(raise_on_fetch=True))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.row_count == 1
        assert "api 연결" in table.get_row_at(0)[0]


@pytest.mark.asyncio
async def test_cursor_type_is_row():
    app = _BrowserApp(_FakeClient(tracks=[]))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.cursor_type == "row"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_library_browser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_tui.widgets.library_browser'`

- [ ] **Step 3: `tui/src/musicna_tui/widgets/library_browser.py` 작성**

```python
"""라이브러리 브라우저 위젯 — /tracks 폴링, 웹 라이브러리 브라우저와 동등한 정보를 표 형태로."""

from textual.widgets import DataTable

from musicna_tui.client import ApiClient


class LibraryBrowserWidget(DataTable):
    """`/tracks`를 주기적으로 폴링해 트랙 목록을 표로 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__(cursor_type="row")
        self.client = client

    def on_mount(self) -> None:
        self.add_columns("제목", "아티스트", "BPM", "키", "무드")
        self.refresh_tracks()
        self.set_interval(5.0, self.refresh_tracks)

    def refresh_tracks(self) -> None:
        try:
            tracks = self.client.tracks()
        except Exception:
            self.clear()
            self.add_row("api 연결 실패", "", "", "", "")
            return
        self.clear()
        for t in tracks:
            bpm = f"{t['bpm']:.0f}" if t.get("bpm") else "-"
            key = f"{t['key']} {t['mode']}" if t.get("key") else "-"
            mood = t["moods"][0]["tag"] if t.get("moods") else "-"
            self.add_row(
                t["track"]["title"],
                t["track"].get("artist") or "-",
                bpm, key, mood,
                key=str(t["id"]),
            )
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_library_browser.py -v`
Expected: PASS — 전부(3개)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/widgets/library_browser.py tui/tests/test_library_browser.py
git commit -m "feat: LibraryBrowserWidget 신설 — /tracks 폴링 표 뷰"
```

---

## Task 5: `tui/widgets/live_analysis.py` — 실시간 분석 뷰 위젯

**Files:**
- Modify: `tui/pyproject.toml`
- Create: `tui/src/musicna_tui/widgets/live_analysis.py`
- Test: `tui/tests/test_live_analysis.py`

**Interfaces:**
- Consumes: `ApiClient.live_ws_url`(Task 3), `/ws/live` 이벤트 계약(`core/src/musicna_core/models.py`의 `LiveEvent` — `track_started`/`note_on`/`note_off`/`chord`/`progress`/`track_ended`, `type` 필드로 판별)
- Produces: `LiveAnalysisWidget(Static)` — `__init__(self, client: ApiClient)`. Task 8이 `app.py`에서 사용.

- [ ] **Step 1: `websockets` 의존성 추가**

`tui/pyproject.toml`의 `dependencies = [...]` 배열에 추가:

```toml
dependencies = [
    "textual>=0.60",
    "httpx>=0.28",
    "websockets>=12",
]
```

Run: `uv sync --package musicna-tui`
Expected: `websockets` 설치(이미 `musicna-api`가 같은 버전대를 쓰므로 워크스페이스 venv에 이미 있을 수 있으나, `tui` 패키지 자체의 선언 의존성으로 명시하는 것)

- [ ] **Step 2: 실패하는 테스트를 작성**

`tui/tests/test_live_analysis.py` 신규 작성:

```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_live_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_tui.widgets.live_analysis'`

- [ ] **Step 3: `tui/src/musicna_tui/widgets/live_analysis.py` 작성**

```python
"""실시간 분석 뷰 위젯 — /ws/live 구독, 현재 코드+진행 히스토리+울리는 노트 개수를 표시.

터미널은 웹의 캔버스 피아노 롤을 그릴 수 없으므로, 코드·노트 활동을 텍스트로 보여주는 것으로
기능적 동등성을 삼는다(각 클라이언트는 독립 인터페이스이되 기능은 동등하다는 설계 원칙).
"""

import json

import websockets
from textual.widgets import Static

from musicna_tui.client import ApiClient

RECONNECT_DELAY_S = 2.0
HISTORY_LIMIT = 8


class LiveAnalysisWidget(Static):
    """`/ws/live`를 구독해 현재 코드·직전 진행·울리는 노트 개수를 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        self._connected = False
        self._current_chord: str | None = None
        self._chord_history: list[str] = []
        self._active_notes: set[int] = set()

    def on_mount(self) -> None:
        self._render_state()
        self.run_worker(self._listen(), exclusive=True)

    async def _listen(self) -> None:
        import asyncio

        while True:
            try:
                async with websockets.connect(self.client.live_ws_url) as ws:
                    self._connected = True
                    self._render_state()
                    async for raw in ws:
                        self._handle_event(json.loads(raw))
                        self._render_state()
            except Exception:
                self._connected = False
                self._render_state()
                await asyncio.sleep(RECONNECT_DELAY_S)

    def _handle_event(self, event: dict) -> None:
        match event.get("type"):
            case "track_started":
                self._current_chord = None
                self._chord_history = []
                self._active_notes = set()
            case "note_on":
                self._active_notes.add(event["index"])
            case "note_off":
                self._active_notes.discard(event["index"])
            case "chord":
                if self._current_chord is not None:
                    self._chord_history.append(self._current_chord)
                    self._chord_history = self._chord_history[-HISTORY_LIMIT:]
                self._current_chord = event["chord"]
            case "track_ended":
                self._active_notes = set()

    def _render_state(self) -> None:
        conn = "연결됨" if self._connected else "재연결 중…"
        chord = self._current_chord or "—"
        history = " → ".join(self._chord_history) if self._chord_history else "(없음)"
        notes = len(self._active_notes)
        self.update(f"[{conn}] 현재 코드: {chord}  |  진행: {history}  |  울리는 노트: {notes}개")
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_live_analysis.py -v`
Expected: PASS — 전부(5개: 현재 코드·노트 개수·note_off 감소·track_started 리셋·히스토리)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/pyproject.toml tui/src/musicna_tui/widgets/live_analysis.py tui/tests/test_live_analysis.py
git commit -m "feat: LiveAnalysisWidget 신설 — /ws/live 구독, 코드·노트 활동 표시"
```

---

## Task 6: `tui/widgets/playlists_screen.py` — 플레이리스트 모달 화면

**Files:**
- Create: `tui/src/musicna_tui/widgets/playlists_screen.py`
- Test: `tui/tests/test_playlists_screen.py`

**Interfaces:**
- Consumes: `ApiClient.player_playlists()`, `ApiClient.player_play_playlist()`(Task 3)
- Produces: `PlaylistsScreen(ModalScreen[None])` — `__init__(self, client: ApiClient)`. Task 8이 `app.py`에서 `self.push_screen(PlaylistsScreen(self.client))`로 사용.

- [ ] **Step 1: 실패하는 테스트를 작성**

`tui/tests/test_playlists_screen.py` 신규 작성:

```python
"""PlaylistsScreen 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from musicna_tui.widgets.playlists_screen import PlaylistsScreen


class _FakeClient:
    def __init__(self, playlists=None):
        self._playlists = playlists or []
        self.played = []

    def player_playlists(self):
        return self._playlists

    def player_play_playlist(self, playlist_id):
        self.played.append(playlist_id)


class _HostApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield from ()


@pytest.mark.asyncio
async def test_lists_playlists_on_mount():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        assert table.row_count == 1
        assert table.get_row_at(0)[0] == "Chill"


@pytest.mark.asyncio
async def test_enter_plays_selected_playlist_and_dismisses():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == ["p1"]
        assert len(pilot.app.screen_stack) == 1


@pytest.mark.asyncio
async def test_escape_dismisses_without_playing():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert client.played == []
        assert len(pilot.app.screen_stack) == 1
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_playlists_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_tui.widgets.playlists_screen'`

- [ ] **Step 3: `tui/src/musicna_tui/widgets/playlists_screen.py` 작성**

```python
"""플레이리스트 모달 — 내 플레이리스트 목록에서 골라 바로 재생."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable

from musicna_tui.client import ApiClient


class PlaylistsScreen(ModalScreen[None]):
    """`GET /player/playlists` 목록을 표로 보여주고, Enter로 선택한 플레이리스트를 재생한다."""

    BINDINGS = [("escape", "dismiss_screen", "닫기")]

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("이름", "소유자")
        try:
            playlists = self.client.player_playlists()
        except Exception:
            playlists = []
        for p in playlists:
            table.add_row(p["name"], p.get("owner") or "-", key=p["id"])
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        playlist_id = event.row_key.value
        try:
            self.client.player_play_playlist(playlist_id)
        except Exception:
            pass
        self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_playlists_screen.py -v`
Expected: PASS — 전부(3개)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/widgets/playlists_screen.py tui/tests/test_playlists_screen.py
git commit -m "feat: PlaylistsScreen 모달 신설 — 플레이리스트 목록·선택 재생"
```

---

## Task 7: `tui/widgets/search_screen.py` — 검색 모달 화면

**Files:**
- Create: `tui/src/musicna_tui/widgets/search_screen.py`
- Test: `tui/tests/test_search_screen.py`

**Interfaces:**
- Consumes: `ApiClient.player_search()`, `ApiClient.player_play_playlist()`(Task 3)
- Produces: `SearchScreen(ModalScreen[None])` — `__init__(self, client: ApiClient)`. Task 8이 `app.py`에서 `self.push_screen(SearchScreen(self.client))`로 사용.

- [ ] **Step 1: 실패하는 테스트를 작성**

`tui/tests/test_search_screen.py` 신규 작성:

```python
"""SearchScreen 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input

from musicna_tui.widgets.search_screen import SearchScreen


class _FakeClient:
    def __init__(self, results=None):
        self._results = results or {"tracks": [], "artists": [], "albums": [], "playlists": []}
        self.played = []

    def player_search(self, query):
        self._last_query = query
        return self._results

    def player_play_playlist(self, playlist_id):
        self.played.append(playlist_id)


class _HostApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield from ()


@pytest.mark.asyncio
async def test_submitting_query_populates_results_table():
    client = _FakeClient(results={
        "tracks": [{"id": "t1", "name": "Song", "artists": ["A"], "album": "Al", "duration_s": 200.0}],
        "artists": [{"id": "a1", "name": "Artist"}],
        "albums": [{"id": "al1", "name": "Album"}],
        "playlists": [{"id": "p1", "name": "Playlist", "owner": "Me"}],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.query_one(Input)
        input_widget.value = "test"
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        assert table.row_count == 4  # 트랙 1 + 아티스트 1 + 앨범 1 + 플레이리스트 1


@pytest.mark.asyncio
async def test_selecting_playlist_row_plays_it_and_dismisses():
    client = _FakeClient(results={
        "tracks": [], "artists": [], "albums": [],
        "playlists": [{"id": "p1", "name": "Playlist", "owner": "Me"}],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.query_one(Input)
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == ["p1"]
        assert len(pilot.app.screen_stack) == 1


@pytest.mark.asyncio
async def test_selecting_track_row_does_not_play_anything():
    """설계 스펙 범위: 트랙/아티스트/앨범 결과는 열람만 가능, 재생 동작 없음."""
    client = _FakeClient(results={
        "tracks": [{"id": "t1", "name": "Song", "artists": ["A"], "album": "Al", "duration_s": 200.0}],
        "artists": [], "albums": [], "playlists": [],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.query_one(Input)
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_search_screen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_tui.widgets.search_screen'`

- [ ] **Step 3: `tui/src/musicna_tui/widgets/search_screen.py` 작성**

```python
"""검색 모달 — 트랙/아티스트/앨범/플레이리스트 열람, 플레이리스트만 선택 시 바로 재생.

설계 범위: `player.py`가 제공하는 재생 액션은 `play_playlist()`뿐이므로(트랙 단건 재생
함수는 이번 Phase 범위 밖), 트랙/아티스트/앨범 결과 행은 열람 전용이다.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input

from musicna_tui.client import ApiClient

_PLAYLIST_KEY_PREFIX = "playlist:"


class SearchScreen(ModalScreen[None]):
    """검색어를 입력하면 `GET /player/search` 결과를 표로 보여준다."""

    BINDINGS = [("escape", "dismiss_screen", "닫기")]

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield Input(placeholder="검색어 입력 후 Enter")
        yield DataTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("종류", "이름", "부가정보")
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        table = self.query_one(DataTable)
        table.clear()
        try:
            results = self.client.player_search(event.value)
        except Exception:
            return
        for t in results.get("tracks", []):
            extra = f"{t.get('album') or '-'} · {', '.join(t.get('artists', [])) or '-'}"
            table.add_row("트랙", t["name"], extra, key=f"track:{t['id']}")
        for a in results.get("artists", []):
            table.add_row("아티스트", a["name"], "-", key=f"artist:{a['id']}")
        for a in results.get("albums", []):
            table.add_row("앨범", a["name"], "-", key=f"album:{a['id']}")
        for p in results.get("playlists", []):
            table.add_row("플레이리스트", p["name"], p.get("owner") or "-",
                           key=f"{_PLAYLIST_KEY_PREFIX}{p['id']}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value or ""
        if not row_key.startswith(_PLAYLIST_KEY_PREFIX):
            return
        playlist_id = row_key[len(_PLAYLIST_KEY_PREFIX):]
        try:
            self.client.player_play_playlist(playlist_id)
        except Exception:
            pass
        self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_search_screen.py -v`
Expected: PASS — 전부(3개)

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/widgets/search_screen.py tui/tests/test_search_screen.py
git commit -m "feat: SearchScreen 모달 신설 — 트랙/아티스트/앨범/플레이리스트 검색, 플레이리스트만 재생 가능"
```

---

## Task 8: `tui/app.py` — 신규 위젯·모달 조립

**Files:**
- Modify: `tui/src/musicna_tui/app.py`
- Modify: `tui/tests/test_app.py`

**Interfaces:**
- Consumes: `LibraryBrowserWidget`(Task 4), `LiveAnalysisWidget`(Task 5), `PlaylistsScreen`(Task 6), `SearchScreen`(Task 7)
- Produces: 없음(최상위 조립).

- [ ] **Step 1: 실패하는 테스트를 작성**

`tui/tests/test_app.py`의 `test_app_composes_player_panel_and_session_status` 테스트를 아래로 교체(신규 위젯 2개도 함께 조립되는지 확인):

```python
@pytest.mark.asyncio
async def test_app_composes_all_widgets(monkeypatch):
    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    monkeypatch.setattr(app.client, "tracks", lambda: [])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert pilot.app.query_one(PlayerPanel) is not None
        assert pilot.app.query_one(SessionStatus) is not None
        assert pilot.app.query_one(LiveAnalysisWidget) is not None
        assert pilot.app.query_one(LibraryBrowserWidget) is not None
```

파일 끝에 추가:

```python
@pytest.mark.asyncio
async def test_slash_key_opens_search_screen(monkeypatch):
    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    monkeypatch.setattr(app.client, "tracks", lambda: [])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(pilot.app.screen, SearchScreen)


@pytest.mark.asyncio
async def test_u_key_opens_playlists_screen(monkeypatch):
    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    monkeypatch.setattr(app.client, "tracks", lambda: [])
    monkeypatch.setattr(app.client, "player_playlists", lambda: [])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("u")
        await pilot.pause()
        assert isinstance(pilot.app.screen, PlaylistsScreen)
```

파일 상단 import에 추가:

```python
from musicna_tui.widgets.library_browser import LibraryBrowserWidget
from musicna_tui.widgets.live_analysis import LiveAnalysisWidget
from musicna_tui.widgets.playlists_screen import PlaylistsScreen
from musicna_tui.widgets.search_screen import SearchScreen
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_app.py -v`
Expected: FAIL — `AssertionError`(신규 위젯이 아직 `compose()`에 없음) 또는 바인딩 없음으로 화면 전환 안 됨

- [ ] **Step 3: `tui/src/musicna_tui/app.py` 수정**

전체 파일을 아래로 교체:

```python
"""musicna TUI 진입점 — 상시 구동 중인 api 서버에 접속해 통합 대시보드를 표시한다.

api/system.py가 오케스트레이션(spotify_player 데몬·세션 캡처)을 소유한다. 이 앱은
웹 UI와 동일하게 api에 접속만 하는 순수 클라이언트다(Phase 8.5) — api는 Mac mini에서
launchd로 상시 구동되며, MUSICNA_API_URL 환경변수로 접속 주소를 지정한다
(기본값은 로컬 개발용, docs/PLAN.md 참조).
"""

import os

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from musicna_tui.client import ApiClient
from musicna_tui.widgets.library_browser import LibraryBrowserWidget
from musicna_tui.widgets.live_analysis import LiveAnalysisWidget
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.playlists_screen import PlaylistsScreen
from musicna_tui.widgets.search_screen import SearchScreen
from musicna_tui.widgets.session_status import SessionStatus

DEFAULT_API_URL = "http://127.0.0.1:8000"


class MusicnaApp(App):
    """musicna 통합 대시보드 — 재생 제어 + 세션 상태 + 실시간 분석 + 라이브러리."""

    CSS = """
    PlayerPanel { height: 3; border: round $accent; padding: 0 1; }
    SessionStatus { height: 3; border: round $accent; padding: 0 1; }
    LiveAnalysisWidget { height: 3; border: round $accent; padding: 0 1; }
    LibraryBrowserWidget { height: 1fr; border: round $accent; }
    """

    BINDINGS = [
        ("/", "open_search", "검색"),
        ("u", "open_playlists", "플레이리스트"),
    ]

    def __init__(self) -> None:
        super().__init__()
        base_url = os.environ.get("MUSICNA_API_URL", DEFAULT_API_URL)
        self.client = ApiClient(base_url=base_url)

    def compose(self) -> ComposeResult:
        yield Header()
        yield PlayerPanel(self.client)
        yield SessionStatus(self.client)
        yield LiveAnalysisWidget(self.client)
        yield LibraryBrowserWidget(self.client)
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.client.system_start()
        except Exception as e:
            self.exit(message=f"musicna 기동 실패: {e}")

    def action_open_search(self) -> None:
        self.push_screen(SearchScreen(self.client))

    def action_open_playlists(self) -> None:
        self.push_screen(PlaylistsScreen(self.client))

    def on_unmount(self) -> None:
        self.client.close()


def run() -> None:
    MusicnaApp().run()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_app.py -v`
Expected: PASS — 전부

- [ ] **Step 5: 전체 워크스페이스 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/app.py tui/tests/test_app.py
git commit -m "feat: MusicnaApp에 LibraryBrowserWidget·LiveAnalysisWidget·검색·플레이리스트 모달 조립"
```

---

## Task 9: 문서 갱신

**Files:**
- Modify: `docs/PROGRESS.md`

**Interfaces:** 없음.

- [ ] **Step 1: Phase 8 체크리스트 갱신**

"### Phase 8 — TUI 기능 동등화" 섹션을 아래로 교체:

```markdown
### Phase 8 — TUI 기능 동등화
- [x] 검색·플레이리스트(`/player/search`, `/player/playlists`) — 실행 시 실제 테스트·통과 개수로 갱신할 것(2026-07-28 추가)
- [x] 실시간 분석 뷰(코드·피아노 롤)를 TUI에 추가 (`/ws/live` 재사용) — 터미널 제약상 캔버스 피아노 롤 대신 현재 코드·진행 히스토리·울리는 노트 개수로 기능적 동등성 구현
- [x] 라이브러리 브라우저를 TUI에 추가 (`/tracks` 재사용) — `DataTable` 기반 표 뷰
- [x] TUI의 "자체 로컬 api 부트스트랩"(Phase 7) 제거 → 상시 중앙 api(Phase 8.5)에 접속만 하는 클라이언트로 전환 (2026-07-26, 커밋 `9d57f78`)
- [ ] **(macOS)** 마일스톤: TUI에서 검색→플레이리스트 재생, 라이브러리 브라우저 열람, 실시간 분석 뷰 표시가 실제 Spotify 재생·캡처와 함께 정상 동작하는지 실기기 검증(spotify_player search/get key user-playlists CLI 출력이 이 계획의 fixture와 다르면 파서 조정 포함)
```

(실행 시 실제 테스트 통과 개수·커밋 해시로 위 문구를 구체화할 것 — 위는 자리표시가 아니라 갱신 지침이다.)

- [ ] **Step 2: 작업 로그 표에 한 줄 추가**

`## 작업 로그` 표의 마지막 행 다음에 추가(실제 실행 시점의 테스트 총계·커밋 해시로 숫자를 갱신할 것):

```markdown
| 2026-07-28 | **Phase 8 구현** — `api/player.py`에 search/list_playlists/play_playlist + 3개 라우트, `tui/client.py`에 대응 메서드, `tui/widgets/`에 LibraryBrowserWidget(DataTable)·LiveAnalysisWidget(/ws/live 구독)·PlaylistsScreen·SearchScreen(둘 다 ModalScreen) 신설, `app.py`에 조립(`/` 검색, `u` 플레이리스트 바인딩) | search/get key user-playlists CLI 문법·JSON 스키마는 aome510/spotify-player 소스 직접 확인(실측 아님) — macOS 실기기에서 재확인 필요. 트랙 단건 재생은 설계 범위 밖(플레이리스트만 재생 가능). 워크스페이스 196→__ passed |
```

- [ ] **Step 3: 커밋 및 푸시**

```bash
git add docs/PROGRESS.md
git commit -m "docs: Phase 8(TUI 기능 동등화) 구현 완료 반영"
git push
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙(`2026-07-26-tui-player-orchestration-design.md`)의 Phase 8 3항목(검색·플레이리스트, 실시간 분석 뷰, 라이브러리 브라우저)이 Task 1~8에 전부 매핑됨. `GET /player/search`·`GET /player/playlists`·`POST /player/playlists/{id}/play`(Task 1·2), `LiveAnalysisWidget`(Task 5), `LibraryBrowserWidget`(Task 4)이 각각 대응.
- **플레이스홀더 스캔**: "TBD"/"나중에 구현"/내용 없는 테스트 패턴 없음 — 전 Task의 테스트가 실제 assert를 포함.
- **타입 일관성**: `ApiClient.tracks/player_search/player_playlists/player_play_playlist/live_ws_url`(Task 3에서 정의)가 Task 4·5·6·7의 위젯에서 쓰는 시그니처와 일치. `Playlist`/`SearchResults`(Task 1에서 정의)가 Task 2 라우트의 `response_model`과 일치.
- **기존 테스트 변경 사항 명시**: `tui/tests/test_app.py`의 `test_app_composes_player_panel_and_session_status`를 `test_app_composes_all_widgets`로 교체(Task 8) — 신규 위젯 2개가 함께 조립되는지 검증하도록 확장된 것이며, 기존 검증 내용(PlayerPanel·SessionStatus 존재)은 그대로 유지.
- **실측 한계 고지**: search/list_playlists의 CLI 문법·JSON 스키마는 GitHub 소스 코드 확인 기반이며 macOS 실기기 미검증이라는 점을 Global Constraints·Task 1 fixture 주석·Task 9 작업 로그에 반복 명시했다 — 이 계획을 실행하는 에이전트가 "실측 완료"로 잘못 보고하지 않도록.
