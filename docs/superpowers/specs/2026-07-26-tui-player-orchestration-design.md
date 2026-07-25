# musicna 터미널 UI(TUI) + 재생 엔진 설계

> Phase 7(재생 엔진·오케스트레이션) · Phase 8(TUI 기능 동등화)의 설계 스펙.
> 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.

## 배경·목적

지금 musicna를 쓰려면 터미널 4개(`musicna-session`, `musicna-analyze`, `uvicorn`, `musicna-capture | musicna-live`)와 브라우저 2개 화면을 오가야 한다. 이를 하나의 터미널 UI(TUI)로 통합하는 것이 목적이다. 참고 프로젝트는 [aome510/spotify-player](https://github.com/aome510/spotify-player) — librespot 기반 터미널 Spotify 클라이언트.

핵심 결정 사항(브레인스토밍에서 확정):

- TUI는 **통합 대시보드** — 플레이어 제어, 캡처 세션 상태, 실시간 분석, 라이브러리 브라우저를 한 화면에서
- Spotify 제어는 **완전한 재생기**(spotify-player 수준) — musicna가 직접 Spotify Connect 기기가 되어 재생
- 재생 엔진은 **`spotify_player` 바이너리(Homebrew)를 서브프로세스로 임베딩** — 자체 Rust/librespot 코드를 작성하지 않는다. `spotify_player`는 daemon 모드(`-d`)와 소켓 기반 CLI 원격제어를 이미 지원하고, OAuth도 자체 처리한다(Spotify 개발자 앱 등록 불필요)
- **자체 스트리밍 모드**를 쓴다(원격제어 모드 아님) — musicna가 직접 재생 주체가 되므로, 기존 AppleScript 기반 "spotify" 소스 메타데이터 폴링이 spotify_player 상태 폴링으로 교체된다. Apple Music 소스는 영향 없음
- TUI 기술 스택은 **Python + Textual**
- 오케스트레이션(백그라운드 프로세스 기동/종료)은 **`api/`가 소유**하고 REST로 노출한다 — TUI·미래의 macOS 앱·iOS 앱이 전부 같은 엔드포인트를 호출하는 클라이언트가 된다. TUI만 갖는 특수 역할은 로컬 `api/`(uvicorn) 서버가 안 떠 있을 때 부트스트랩하는 것뿐
- **모든 클라이언트(웹·TUI·macOS·iOS)는 독립 인터페이스이되 기능은 동등**하게 유지한다 — 어느 하나에만 있는 기능을 만들지 않는다
- 구현은 **Phase 7 → Phase 8** 2단계로 진행. Phase 7: 재생 엔진 통합(핵심 재생 제어: play/pause/next/previous/volume/기기전환) + 오케스트레이션 + 메타데이터 교체 + 최소 TUI 셸(플레이어 패널·세션 상태). Phase 8: 검색·플레이리스트를 포함한 TUI 기능 동등화(실시간 분석 뷰·라이브러리 브라우저 추가)

이 설계는 캡처 파이프라인(ScreenCaptureKit → WAV) 자체는 건드리지 않는다. librespot을 이용한 PCM 직접 탭(ScreenCaptureKit 대체)은 별도 검토 대상으로 미룬다(아래 "범위 밖" 참조).

## 아키텍처

```
tui/  (신규, Python/Textual)          — api만 호출. spotify_player·session을 직접 건드리지 않음
    ↓ REST + WebSocket (127.0.0.1:8000)
api/  (기존 확장)
    ├─ player.py         (신규) — spotify_player 데몬 구동·CLI 제어 래퍼
    ├─ system.py         (신규) — 오케스트레이션(/system/*): 데몬·세션 시작/중지, 상태 조회
    ├─ session/metadata.py (확장) — "spotify" 소스 조회를 spotify_player 상태 폴링으로 교체
    │                        (Apple Music 소스는 기존 AppleScript 그대로 유지)
    ├─ main.py            (확장) — /player/*, /system/* 라우트 등록
    └─ live.py, batch.py, session/  (기존, 무수정)
core/                                  — 무수정
capture-macos/                         — 무수정 (ScreenCaptureKit 캡처는 그대로)
```

`core/`의 "macOS API import 금지" 원칙은 그대로 유지된다 — `spotify_player` 오케스트레이션과 새 메타데이터 공급자는 전부 `api/`에 속한다(기존 AppleScript 폴링과 같은 위치).

## 컴포넌트

### `api/src/musicna_api/player.py` (신규)

- `SpotifyPlayerDaemon`: `spotify_player -d` 서브프로세스 생명주기 관리(시작·헬스체크·종료). 미설치 시 명확한 오류(`brew install spotify_player` 안내)
- 명령 래퍼 함수: `play() / pause() / next_track() / previous_track() / set_volume(n) / list_devices() / connect_device(id) / status()` — 전부 `spotify_player <subcommand>` 서브프로세스 호출 후 출력 파싱
- Phase 8에서 `search(query)` / `list_playlists()` / `play_playlist(id)` 추가

### `api/src/musicna_api/system.py` (신규)

- `POST /system/start` — spotify_player 데몬 + 세션 캡처 기동(멱등, 이미 떠 있으면 no-op)
- `POST /system/stop` — 정리 종료
- `GET /system/status` — `{spotify_player_daemon: bool, session_capturing: bool, live_preview_attached: bool}`

### `api/src/musicna_api/session/metadata.py` (확장)

- 기존 `NowPlaying` Pydantic 모델(title/artist/album/duration_s/position_s/state/source)은 변경 없음
- `poll_now_playing(source)`의 `"spotify"` 분기를 spotify_player 상태 폴링 기반 구현으로 교체 — `player.status()`의 출력을 `NowPlaying`으로 매핑
- `"apple_music"` 분기는 기존 AppleScript 그대로 유지(무수정)
- 세션 매니저의 트랙 분할·무음 감지 로직은 `NowPlaying` 계약만 소비하므로 무수정

### 신규 REST 엔드포인트 (`api/main.py`)

Phase 7: `POST /player/play|pause|next|previous`, `POST /player/volume`, `GET /player/devices`, `POST /player/connect`, `GET /player/status`
Phase 8 추가: `GET /player/search`, `GET /player/playlists`, `POST /player/playlists/{id}/play`

### `tui/` (신규 최상위 패키지, Python/Textual)

- `tui/src/musicna_tui/client.py` — api 호출 전담 얇은 클라이언트(httpx + websockets). 위젯은 이것만 통해 api와 통신, 직접 subprocess나 파일 접근 없음
- `tui/src/musicna_tui/app.py` — Textual `App`, 기동 시 `GET /health` 확인 → 실패 시 로컬 `uvicorn` 서브프로세스 부트스트랩 → `POST /system/start` 호출
- 위젯(Phase 7): `PlayerPanel`(현재 곡·재생 컨트롤·볼륨·기기 목록), `SessionStatusWidget`(캡처 중 여부·현재 저장 중인 트랙)
- 위젯(Phase 8): `LiveAnalysisWidget`(`/ws/live` 구독, `live.js`와 동일 이벤트 계약 소비, 코드·피아노 롤 표시), `LibraryBrowserWidget`(`/tracks` 폴링, 웹 라이브러리 브라우저와 동등한 정보)

## 데이터 흐름·생명주기

1. **TUI 기동**: `GET /health` → 없으면 `uvicorn` 서브프로세스 기동 후 헬스체크 대기 → `POST /system/start`(멱등)
2. **재생 명령**: 위젯 → REST `POST /player/*` → `player.py` → `spotify_player playback ...` 서브프로세스 → 파싱된 응답으로 위젯 갱신
3. **트랙 경계 감지**: 세션 매니저 폴링 루프가 (spotify 소스일 때) `player.status()`를 주기 폴링 — 이벤트 구독이 없는 spotify_player 특성상 기존 AppleScript 폴링과 동일한 폴링 패턴 유지
4. **실시간 뷰·라이브러리(Phase 8)**: 기존 `/ws/live`·`/tracks`를 웹과 동일하게 재사용 — 신규 api 불필요, TUI 쪽 렌더링만 추가

## 오류 처리

- `spotify_player` 미설치/데몬 기동 실패 → `/system/status`가 명확한 오류 메시지 반환, TUI는 플레이어 패널만 비활성 배너로 표시(다른 패널은 계속 사용 가능)
- Spotify Premium 미보유 등 spotify_player 자체 오류 → 그 메시지를 그대로 TUI에 노출(가공하지 않음)
- 인증 전이라 상태 조회 실패 → 세션 매니저는 "재생 없음"으로 처리(오늘 AppleScript가 None을 돌려줄 때와 동일 동작), 크래시 없음
- TUI가 로컬 `uvicorn` 부트스트랩에 실패 → 부트스트랩 서브프로세스의 stderr를 그대로 보여주는 오류 화면

## 테스트

- `player.py` / 메타데이터 교체: 서브프로세스를 스텁으로 대체하는 기존 패턴(`test_transcribe.py`, `test_live_cli` 스타일)으로 단위 테스트 — 명령 구성·응답 파싱·데몬 상태 전이 검증
- `system.py`: FastAPI `TestClient`로 오케스트레이션 엔드포인트 검증(서브프로세스 관리는 모킹)
- `tui/`: Textual pilot 테스트로 위젯 렌더·상호작용 스냅샷 검증
- 실제 spotify_player 연동(데몬 기동, OAuth, 실제 재생, Premium 필요 기능)은 Phase 1·2·6과 동일하게 **macOS 실기기 수동 검증** — 합성 fixture로 대체 불가능한 영역

## 범위 밖 (이번 스펙에서 다루지 않음)

- **librespot PCM 직접 탭으로 캡처 파이프라인 교체**: ScreenCaptureKit·AppleScript(Apple Music 소스)·TCC 권한을 없애고 spotify_player가 디코딩한 PCM을 직접 파이프라인에 공급하는 방식. Phase 1(이미 실기기 검증 완료)을 재설계하는 별도 대규모 작업이라 이번 범위에서 제외. 향후 seed로 남겨둔다
- 검색·플레이리스트는 Phase 8로 미룸(위 결정 사항 참조)

## 로드맵 반영

PLAN.md의 단계별 마일스톤에 다음을 추가·확장한다:

- **Phase 7 — 재생 엔진·오케스트레이션**: 위 "핵심 결정 사항" 중 Phase 7 범위. 마일스톤: TUI에서 재생/일시정지/다음곡/볼륨 조작 시 실제 Spotify 재생이 반응하고, 그 재생이 기존 캡처·트랙 분할에 그대로 반영됨(실기기 검증)
- **Phase 8 — TUI 기능 동등화**: 검색·플레이리스트, 실시간 분석 뷰, 라이브러리 브라우저를 TUI에 추가. 마일스톤: 웹 UI로 할 수 있는 모든 열람 작업을 TUI에서도 수행 가능
- **Phase 9 — macOS 네이티브 앱** (신규, 이후 로드맵): 웹·TUI와 동일하게 `api/`만 호출하는 독립 클라이언트. 같은 패턴(기능 동등화, 단계별 실기기 검증)을 따름
- **Phase 10 — iOS 뷰어 앱** (기존 "이후 — iOS 뷰어 앱" 섹션을 승격·확장): `api/`만 호출, Mac이 캡처·분석·재생 서버 역할(기존 PLAN.md "iOS에서의 역할" 서술과 일치). 같은 패턴을 따름
