# musicna — 진행 상황 (PROGRESS)

> 작업 재개·서브에이전트 협업용 단일 진실 소스(single source of truth).
> **규칙**: 작업 단계를 시작/완료할 때마다 이 파일을 갱신하고 즉시 커밋·푸시한다.
> 계획 자체는 [PLAN.md](PLAN.md) 참조. 계획 변경은 PLAN.md에, 실행 기록은 여기에.

## 현재 상태

- **현재 Phase**: Phase 0~8.5·"코드 진행 추상화 구조"·"트랙 저장·보존 정책"·Phase 8(TUI 기능 동등화)·Phase 10 선행조건(remote_capture 동시성 lock)까지 전부 `main`에 병합 완료(2026-07-28). **Phase 9(macOS 네이티브 앱)는 Task 1~8 구현 완료(2026-07-30)** — `MusicnaKit` 순수 Swift 패키지(Models·APIClient·LiveEventClient·3개 스토어, 27 tests 통과) + XcodeGen 기반 App 타겟(MenuBarExtra·라이브러리 창·설정, `xcodebuild` 빌드 성공 확인). 브랜치 `phase-9-macos-native-app`, 아직 `main` 미병합. **남은 건 실기기(macOS) 마일스톤 검증뿐**(실제 Spotify 재생에 메뉴바가 반응하는지 등 — 이 세션엔 GUI 자동화 도구가 없어 미실시, 아래 Phase 9 체크리스트 참조)
- **⚠️ 환경 정정(2026-07-30 갱신)**: 이 머신은 이 프로젝트의 실제 macOS 개발 머신(Mac mini)이며, **2026-07-29 세션에서 "전체 Xcode.app 미설치"로 기록했던 것은 오판이었다** — 실제로는 Xcode 26.6이 외장 볼륨(`/Volumes/External/Applications/Xcode.app`)에 설치돼 있었고, 활성 개발자 디렉터리로 선택돼 있지 않았을 뿐. `sudo xcode-select -s /Volumes/External/Applications/Xcode.app/Contents/Developer`로 전환하고 Homebrew로 `xcodegen`(2.46.0)을 설치해 Phase 9 Task 5~8(Xcode 프로젝트 필요)까지 같은 세션에서 이어서 완료했다. 앞으로 "Xcode 필요라 불가능"으로 보이는 항목이 있으면 `xcode-select -p`로 활성 디렉터리부터 먼저 확인할 것(외장 볼륨 마운트 여부도 함께 확인)
- **작업 브랜치**: `main`은 위 병합 내역까지 최신. `phase-9-macos-native-app`이 유일하게 진행 중인 미병합 브랜치 — 설계·계획 문서에 더해 Task 1~8 코드 구현(MusicnaKit 패키지 + Xcode 앱 타겟)까지 커밋·push 완료
- **분담**: `capture-macos/`·`api/session/`은 macOS 로컬 담당, 원격은 `core/`·문서 담당 — 단, 위 환경 정정에 따라 이 구분 자체가 최근엔 느슨해짐(둘 다 같은 머신에서 진행 중)
- **다음 할 일 (macOS)**: ① Phase 9 실기기 마일스톤 검증(아래 "### Phase 9" 체크리스트의 미체크 항목) — 메뉴바에서 재생/일시정지·다음곡·볼륨 조작 시 실제 Spotify 재생 반응, 캡처 상태·실시간 코드가 실제 재생과 함께 갱신, 라이브러리 창에 실제 캡처 트랙 표시되는지 확인 ② `MUSICNA_API_URL`을 Tailscale 주소로 지정해 `uv run musicna-tui`가 원격 api에 정상 접속·재생 제어되는지 확인(Phase 8.5 Task 7 Step 1) ③ Mac mini 실제 재부팅 후 `launchd`가 api를 자동 복구하는지 확인 ④ Phase 8 마일스톤 검증: TUI에서 검색(`/`)→플레이리스트 재생, 라이브러리 브라우저 열람, 실시간 분석 뷰가 실제 Spotify 재생·캡처와 함께 정상 동작하는지 확인 — `spotify_player search "..."`/`get key user-playlists` 실제 CLI 출력을 계획의 fixture와 대조(GitHub 소스만으로 도출한 것이라 미검증)하고 다르면 `api/player.py`의 파서 조정 ⑤ 정상 레벨 곡 추가 캡처·축적. **주의**: 기본 오디오 출력 장치가 HDMI 등 볼륨 API 미지원 장치면 `--system-audio` 캡처가 조용히 실패한다 — 캡처 전 `SwitchAudioSource -c -t output`으로 확인, 필요시 내장 스피커로 전환(아래 Phase 7 기록 참조)
- **다음 할 일 (원격 전용 작업이 필요하다면)**: Alembic 마이그레이션 도입

### 다음 세션 재개 체크리스트 (일반)

1. `git pull` — 원격이 이 문서보다 앞서 있을 수 있음
2. `uv sync --all-packages --extra transcribe --extra analyze --extra mood` — **주의**: extras 없이 `uv sync`/`uv run pytest`를 여러 번 반복하면 이 명령으로 깔린 ML 스택(torch/natten/setuptools/cmake/ninja)이 조용히 제거된다(아래 "환경 이슈" 참조) — Phase 3~7 관련 작업 전엔 항상 이 커맨드로 먼저 확인
3. `uv run pytest core/tests api/tests tui/tests` → 232 passed, 1 skipped 기대(2026-07-28 Phase 10 선행조건 완료 기준 최신 수치, `main` 기준)
4. macOS에서 spotify_player/TUI 작업 시: `export PATH="$HOME/.cargo/bin:$PATH"`(이미 `.zshrc`에 추가돼 있으면 새 셸에서 자동), `spotify_player --version`으로 daemon feature 포함 여부 확인(`spotify_player --help`에 `-d`/`--daemon`이 보여야 함 — 안 보이면 아래 "spotify_player 설치 절차"부터 재수행)
5. Phase 8·8.5는 구현·리뷰·`main` 병합까지 완료. Phase 9(macOS 네이티브 앱)는 Task 1~8 구현 완료(브랜치 `phase-9-macos-native-app`, `main` 미병합) — 남은 건 "다음 할 일 (macOS)"의 실기기 마일스톤 검증뿐. macOS 앱을 다시 빌드하려면 `xcode-select -p`로 활성 Xcode가 여전히 잡혀 있는지 먼저 확인할 것(외장 볼륨 마운트 필요)

## Phase 체크리스트

### Phase 0 — 프로젝트 스캐폴딩
- [x] 프로젝트 방향 논의 및 PLAN.md 작성
- [x] muscriptor / allin1 / Essentia 등 핵심 기술 조사 (결과는 PLAN.md에 반영)
- [x] 모노레포 디렉터리 구조 생성 (capture-macos/, core/, api/, web/, docs/, data/)
- [x] uv 워크스페이스 + core/api 패키지 스캐폴딩 (pyproject.toml)
- [x] core: Pydantic 결과 모델(API 계약) 정의 — `AnalysisResult`, `Section`, `ChordEvent`, `MoodTag` (`core/src/musicna_core/models.py`)
- [x] core: SQLAlchemy DB 모델 초안 (`core/src/musicna_core/store/db.py`)
- [x] api: FastAPI 스켈레톤 (/health, /tracks 스텁) (`api/src/musicna_api/main.py`)
- [x] README 아키텍처 문서화, .gitignore
- [x] 스모크 테스트 통과 (`uv run pytest core/tests` — 2 passed)
- [x] 커밋·푸시

### Phase 1 — 캡처 + 트랙 분할 (macOS 실기기 필요)
- [x] Swift 캡처 헬퍼 (ScreenCaptureKit → PCM stdout) — `capture-macos/`, swift build 성공
- [x] Python 세션 매니저: PCM 수신 → 트랙별 WAV 저장 — `api/src/musicna_api/session/`, TDD 테스트 17개
- [x] AppleScript 메타데이터 (Spotify/Apple Music) + 무음 감지 폴백
- [x] 마일스톤: Spotify 재생 시 곡 단위 WAV 자동 저장 — 실기기 검증 통과 (트랙 전환 시 자동 분할, WAV+JSON 사이드카 저장 확인)

### Phase 2 — MIDI 변환
- [x] ML 의존성 패키지명 PyPI 실재 검증 (muscriptor 0.2.2, allin1 1.1.0, chorder, laion-clap, music21, librosa, madmom)
- [x] muscriptor API 조사: `TranscriptionModel.load_model(size)` / `transcribe_to_midi()` / 스트리밍 `transcribe()` 이벤트 API(Phase 6에 사용)
- [x] core/transcribe 래퍼 구현 (지연 import, 모델 캐시, 배치=large·스트림=small) + 스텁 기반 단위 테스트 4건
- [x] Python 3.12 고정 (muscriptor가 3.10~3.12만 지원, `.python-version`)
- [x] **(macOS)** muscriptor 실설치 (`uv sync --package musicna-core --extra transcribe`) — import·torch 2.2.2 MPS available 확인
- [x] **(macOS, 사용자)** HF 로그인 + muscriptor 가중치 라이선스 동의 (small/large 모델 페이지 각각)
- [x] torch를 arm64에서 2.3+로 상향 — 2.2.2의 MPS는 FFT(`aten::_fft_r2c`) 미구현으로 전사 불가 (`core/pyproject.toml` 참조)
- [x] 마일스톤: 캡처된 곡 WAV → .mid 생성, 피아노롤로 확인 — large 모델로 28.5초 캡처 전사(708노트, guitar/bass/drums/voice 트랙 분리), MPS 정상 동작

### Phase 3 — 배치 분석
- [x] MIDI 기반 키 추정 구현 (`core/analyze/keys.py`, music21 Krumhansl-Schmuckler) + 합성 MIDI 테스트 2건
- [x] 키 추정 견고성: 노트 없는 MIDI(저레벨 캡처 전사 결과)에서 None 반환 — 실기기 E2E에서 발견된 크래시 수정 (테스트 2건 추가)
- [x] 코드 진행 추출(MIDI 기반): `core/analyze/chords.py` — 초 단위 창·지속시간 가중 피치클래스 집계, music21 harmony 라벨링, 연속 코드 병합. 합성 MIDI 테스트 3건 (triad 진행·7th·빈 MIDI)
- [x] analyze 파이프라인 조립: `analyze_track()` — 키+코드(base 의존성만으로 동작) + allin1/CLAP은 설치 시에만 채워지는 graceful degradation. 테스트 2건
- [x] 코드 진행 오디오(chroma) 교차 검증: `core/analyze/chords_audio.py`(librosa chroma_cqt + 장/단 3화음 템플릿 24개 코사인 매칭) + `merge_chord_tracks()`(코드 가족[루트+장/단] 일치→MERGED·신뢰도 보너스, 불일치→고신뢰 쪽 채택·페널티, 경계 분할 병합). librosa는 `chroma` extra 또는 analyze extra로 설치. 테스트 10건
- [x] **(macOS)** allin1 실설치·구조/BPM 검증 — natten 0.15.1 소스 빌드·madmom git 핀으로 설치 확립, 실캡처 곡 BPM 118·구간 2개 검출 (45.6s/28.7s 오디오, CPU)
- [x] **(macOS)** 스파이크: CLAP 무드 태깅 품질 검증 → `core/analyze/moods.py` 구현 — music 특화 체크포인트, zero-shot 12태그, 업템포 곡=happy/energetic·잔잔한 곡=dreamy/calm으로 청감 일치. 스텁 테스트 3건
- [x] 마일스톤: 곡 1개 전체 분석 — 001 트랙에 bpm/key/코드 23개/구간 2개/무드 5개 전 항목 채워짐 (DB와 /tracks JSON으로 확인)
- [x] 코드 진행 추상화 구조(2026-07-26 추가) — `core/analyze/chord_structure.py`: 섹션 단위 로마자 진행 요약(`SectionChordSummary`, 동일 진행 섹션 연결)·구간 무관 반복 패턴 탐지(`ChordLoop`, 최소 4코드). 설계: [2026-07-26-chord-structure-abstraction-design.md](superpowers/specs/2026-07-26-chord-structure-abstraction-design.md), 계획: [2026-07-26-chord-structure-abstraction.md](superpowers/plans/2026-07-26-chord-structure-abstraction.md)

### Phase 4 — DB 저장
- [x] 저장소 패턴: `save_analysis`/`list_latest_analyses`/`has_analysis` (`core/store/repository.py`) — AnalysisResult↔DB 왕복, 재분석 이력 누적, 트랙 재사용. 테스트 3건
- [x] api `/tracks`를 DB 조회로 교체 (env `MUSICNA_DB`, 기본 data/musicna.db) + TestClient 테스트 2건
- [x] 배치 오케스트레이터 `musicna-analyze` (`api/batch.py`): WAV+JSON 스캔 → (필요시 전사) → 분석 → DB. 중복 건너뜀/--force, muscriptor 미설치 시 MIDI 없이 진행. 테스트 2건
- [ ] Alembic 마이그레이션 (스키마 변경 발생 시 도입)
- [x] **(macOS)** 마일스톤: 재생→분석→DB 자동 축적 — 실캡처 2트랙 `uv run musicna-analyze` E2E 통과 (분석 2·실패 0, 재실행 시 중복 건너뜀, /tracks가 DB 결과 반환)
- [x] 트랙 저장·보존 정책(2026-07-27 추가) — WAV는 분석 성공 직후 삭제(용량 절약, JSON 사이드카는 유지), MIDI는 `data/midi/` 파일로 영구 보관. `AnalysisResult.id` 노출 + `GET /tracks/{id}`(단건 조회)·`GET /tracks/{id}/midi`(MIDI 서빙) 신설 — 원격 클라이언트가 파일시스템 접근 없이 API만으로 MIDI를 받을 수 있음. 설계: [2026-07-27-track-storage-retention-design.md](superpowers/specs/2026-07-27-track-storage-retention-design.md), 계획: [2026-07-27-track-storage-retention.md](superpowers/plans/2026-07-27-track-storage-retention.md). **알려진 트레이드오프**: WAV 삭제로 `--force` 재분석 시 오디오 기반 코드/무드 재추출 불가(MIDI 기반 재추출만 가능)

### Phase 5 — 웹 UI
- [x] 라이브러리 브라우저 (`web/` 바닐라 HTML/CSS/JS, 빌드 도구 없음): 트랙 목록(키·BPM·무드 배지), 스탯 타일, 구조 타임라인(직접 라벨+범례+시간축), 코드 진행 레인(호버 툴팁)+텍스트 스트립, 무드 점수 바, 표 뷰(접근성), 라이트/다크
- [x] api가 `web/` 정적 서빙 (`MUSICNA_WEB`, API 라우트 우선) + 테스트 2건
- [x] 렌더 검수: 데모 DB 시드 → Playwright 스크린샷(라이트/다크/강등 상태/툴팁) 확인. dataviz 팔레트 검증 통과(구간 라벨 고정 색 매핑)
- [x] **(macOS)** 실캡처 DB로 브라우저 확인 — 트랙 목록·BPM/키 배지·구조 타임라인·코드 진행 레인·무드 바 전부 정상 렌더 (Playwright 스크린샷 확인, 콘솔 오류 없음)
- [ ] (선택) 라이브러리 통계 화면 — 무드 분포·키 분포 (트랙이 쌓인 뒤)

### Phase 6 — 실시간 미리보기
- [x] WS 이벤트 계약: `LiveEvent` discriminated union (`core/models.py`) — track_started/note_on/note_off/chord/progress/track_ended, 웹·iOS 공용
- [x] 실시간 코드 추정기 `LiveChordTracker` (`core/analyze/live_chords.py`) — 롤링 창, 배치와 동일한 라벨링 로직 공유(`label_weighted_pcs` 리팩터), 변화 시점만 산출
- [x] api: `LiveBroadcaster`(asyncio pub/sub) + `POST /live/ingest` + `GET /ws/live` (uvicorn용 websockets 의존성 추가)
- [x] `musicna-live` CLI (`api/live_cli.py`): 캡처 PCM stdin → 5초 청크 모노 다운믹스 → muscriptor(small) 전사 → 이벤트 변환·코드 추정 → ingest POST. 전송 실패에도 루프 지속
- [x] core/transcribe: 메모리 청크 전사 `stream_chunk_events` ((tensor, sr) 입력)
- [x] 웹 실시간 뷰 `live.html`: 현재 코드 대형 표시+히스토리, 30초 스크롤 피아노 롤(canvas), 자동 재접속
- [x] 검증(원격): 테스트 12건 + Playwright E2E(시뮬레이션 이벤트 주입 → C/F/G7 표시·피아노 롤 렌더 확인)
- [x] **(macOS)** 실기기 마일스톤 검증 통과: `musicna-capture | uv run musicna-live` + Spotify 실재생 → live.html에 실시간 코드(예: Gm7/B-)·히스토리·피아노 롤(109노트) 렌더 확인. 청크 17개 평균 1.79s(5초 청크 대비 2.8배 여유), small 모델 실시간성 확보 — 상세는 아래 검증 기록

### Phase 7 — 재생 엔진·오케스트레이션
- [x] `api/player.py`: `spotify_player`(Homebrew/cargo, librespot 기반) CLI 파서·명령 래퍼(`play/pause/next/previous/volume/connect/list_devices/get_status`) + `SpotifyPlayerDaemon`(헤드리스 데몬 생명주기)
- [x] `api/session/metadata.py`: "spotify" 소스 메타데이터를 AppleScript에서 spotify_player 폴링으로 교체(Apple Music 소스는 무수정)
- [x] `api/system.py`: `SystemOrchestrator`(데몬+세션 캡처 프로세스 관리, 세션 정지는 SIGINT로 WAV 마무리 저장 보장) + `/system/start|stop|status`
- [x] `/player/*`(play/pause/next/previous/volume/devices/connect/status) REST 엔드포인트, `main.py` 등록
- [x] `tui/` 신규 패키지(Textual): `ApiClient`, `PlayerPanel`(space/n/p 키 제어), `SessionStatus`, `MusicnaApp`(로컬 api 부트스트랩), `musicna-tui` 콘솔 스크립트
- [x] 설계·계획 문서: [docs/superpowers/specs/2026-07-26-tui-player-orchestration-design.md](superpowers/specs/2026-07-26-tui-player-orchestration-design.md), [docs/superpowers/plans/2026-07-26-tui-player-orchestration.md](superpowers/plans/2026-07-26-tui-player-orchestration.md)
- [x] **(macOS)** 마일스톤 검증 통과: TUI/API에서 재생·일시정지·다음곡·볼륨 조작 시 실제 Spotify 재생이 반응하고, 그 재생이 기존 캡처·트랙 분할에 실시간으로 반영됨(다음곡 전환마다 정확히 트랙 분리 저장 확인) — 상세는 아래 검증 기록
- [ ] 검색·플레이리스트는 Phase 8로 이월

### Phase 8 — TUI 기능 동등화
- [x] 검색·플레이리스트(`/player/search`, `/player/playlists`) — `api/player.py` search/list_playlists/play_playlist + 라우트 3개(커밋 `7ce7162`·`1524f0d`), TUI `ApiClient` 대응 메서드(커밋 `a177cb5`), `SearchScreen`·`PlaylistsScreen`(ModalScreen, 커밋 `712c012`·`8b16888`), `app.py` 조립(`/` 검색·`u` 플레이리스트 바인딩, 커밋 `a8225a2`) — 워크스페이스 225 passed, 1 skipped(2026-07-28 구현·리뷰 완료)
- [x] 실시간 분석 뷰(코드·피아노 롤)를 TUI에 추가 (`/ws/live` 재사용) — 터미널 제약상 캔버스 피아노 롤 대신 현재 코드·진행 히스토리·울리는 노트 개수로 기능적 동등성 구현 (`LiveAnalysisWidget`, 커밋 `66c0675`)
- [x] 라이브러리 브라우저를 TUI에 추가 (`/tracks` 재사용) — `DataTable` 기반 표 뷰 (`LibraryBrowserWidget`, 커밋 `d8101f3`)
- [x] TUI의 "자체 로컬 api 부트스트랩"(Phase 7) 제거 → 상시 중앙 api(Phase 8.5)에 접속만 하는 클라이언트로 전환 (2026-07-26, 커밋 `9d57f78`)
- [x] **최종 전체 브랜치 리뷰(opus) → fix wave → main 병합**(2026-07-28): Task 1~9를 subagent-driven-development로 실행, 그 과정에서 계획 브리프 자체의 버그 3건을 구현자들이 실측으로 발견·수정(Task 5: `LiveAnalysisWidget` 재연결 대기가 `except` 안에만 있어 이벤트 루프를 독점하는 busy loop — 공통 경로로 이동해 수정; Task 6·7: Textual `pilot.app.query_one`이 모달(ModalScreen) 내부를 못 찾는 문제 — `pilot.app.screen.query_one`로 수정, 테스트 코드만 변경; Task 8: `LibraryBrowserWidget`이 `compose()`에 들어가며 스테일 서버 응답으로 기존 테스트가 크래시 — 네트워크 모킹으로 격리). 최종 리뷰는 Critical 0건, Important 2건 중 사용자 선택으로 1건(3개 위젯의 KeyError 위험 — fetch만 감싸고 행 생성 루프는 안 감쌈)을 fix wave로 수정 → 스코프된 재리뷰 통과 → `main`으로 fast-forward 병합, `phase-8-tui-parity` 브랜치 로컬·원격 삭제. **park된 Important 1건**: `LibraryBrowserWidget`의 5초 폴링이 동기 HTTP 호출로 이벤트 루프를 블로킹해 `LiveAnalysisWidget`의 websocket 워커와 경합 가능 — 기존 `PlayerPanel`/`SessionStatus`(Phase 7)도 동일한 동기 폴링 패턴이라 이번 브랜치의 신규 회귀는 아니라고 판단, **아래 macOS 마일스톤 검증 시 실사용 체감 확인 후 필요하면 스레드 워커로 전환**
- [ ] **(macOS)** 마일스톤: TUI에서 검색→플레이리스트 재생, 라이브러리 브라우저 열람, 실시간 분석 뷰 표시가 실제 Spotify 재생·캡처와 함께 정상 동작하는지 실기기 검증(spotify_player search/get key user-playlists CLI 출력이 이 계획의 fixture와 다르면 파서 조정 포함, 위 park된 이벤트 루프 경합 이슈도 실사용 체감 확인)

### Phase 8.5 — 중앙 배포 인프라 (신규, 2026-07-26 설계)
> 설계: [2026-07-26-central-deployment-ios-player-design.md](superpowers/specs/2026-07-26-central-deployment-ios-player-design.md). 구현 계획: [2026-07-26-phase-8-5-central-deployment.md](superpowers/plans/2026-07-26-phase-8-5-central-deployment.md)(7개 Task, subagent-driven-development로 실행 중).
> **구현 진행 상황** (세션 재개용 — 이 계획의 SDD 원장은 `.superpowers/sdd/2026-07-26-phase-8-5-central-deployment/progress.md`, git-ignored이므로 저장소 밖에서도 아래 표만으로 재개 가능해야 함):
> | Task | 내용 | 상태 | 커밋 |
> |---|---|---|---|
> | 1 | `process_chunk` 추출(live_cli.py 리팩터) | ✅ 완료, 리뷰 통과 | `6e49cd0` |
> | 2 | `RemoteCaptureManager`/`Session` 구현 | ✅ 완료, fix round 1(비정렬 PCM 청크 가드 추가)後 리뷰 통과 | `6afbf2d`, `22a4a5c` |
> | 3 | `/remote/audio/*` REST 엔드포인트 | ✅ 완료, fix round 1(start_session/end_session async 전환)後 리뷰 통과 | `89ad83f`, `9950013` |
> | 4 | TUI 자체 부팅 제거 | ✅ 완료, 리뷰 통과(수정 없음) | `9d57f78` |
> | 5 | launchd LaunchAgent | ✅ 완료 — 사용자가 직접 설치·헬스체크·재부팅 복구까지 확인. 운영 매뉴얼: [deploy/macos/README.md](../deploy/macos/README.md) | `aaeb595` |
> | 6 | Tailscale 설정 | ✅ 완료 — Mac mini(js-m4-mini)+iPhone 원격 접속 확인. 발견: iPhone이 로그인만으로는 VPN 미연결(137일 오프라인), iOS VPN 토글 별도 확인 필요 | 코드 변경 없음 |
> | 7 | 전체 마일스톤 검증 + 최종 전체 브랜치 리뷰 | ✅ 완료 — 라이브러리 원격 조회 확인(TUI 원격 접속·재부팅 복구는 백로그). 최종 리뷰(opus)에서 Important 1건+실질 버그 1건 fix wave로 수정, 새로 발견된 동시성 이슈 1건은 **park**(Phase 10 착수 전 lock 추가 필요, 상세는 구현 계획 파일) | `0a68f27` |
- [x] Tailscale 설치·설정(Mac mini + 클라이언트 기기), MagicDNS 호스트네임 확보 (2026-07-26, [운영 매뉴얼](../deploy/macos/README.md#원격-접근-tailscale)의 iOS VPN 토글 문제 참조)
- [ ] Mac mini 자동 로그인 설정 (재부팅 복구용) — **미확인, 백로그**: 재부팅 복구 테스트(Task 7 Step 3)로 함께 검증 예정
- [x] `launchd` LaunchAgent plist 작성 — `uvicorn musicna_api.main:app` 상시 구동, KeepAlive로 크래시 재시작 (2026-07-26, 설치·검증 완료, [운영 매뉴얼](../deploy/macos/README.md))
- [x] 원격 오디오 인제스트 엔드포인트 신설 — PCM 청크 수신 → 실시간 미리보기(`musicna-live` 파이프라인 재사용) + 트랙 종료 시 WAV 완성 저장(`musicna-analyze` 배치가 그대로 집어감) (Task 2·3, 2026-07-26)
- [ ] **(macOS)** 마일스톤: 집 밖에서 Tailscale로 api 접속 → 라이브러리 조회(✅ 확인)·**재생 원격제어(TUI, 백로그)** 확인

### Phase 9 — macOS 네이티브 앱
> 설계: [2026-07-29-phase-9-macos-native-app-design.md](superpowers/specs/2026-07-29-phase-9-macos-native-app-design.md). 구현 계획: [2026-07-29-phase-9-macos-native-app.md](superpowers/plans/2026-07-29-phase-9-macos-native-app.md)(Task 1~9, Task 9는 이 문서 갱신). Task 1~8 구현 완료, 브랜치 `phase-9-macos-native-app`(아직 `main` 미병합) — 커밋: `da47ba9`(Task1) `63a9cc5`(Task2) `1e22b6a`(Task3) `f9cf7d8`+`c8fc508`(Task4) `e23227f`(Task5) `9289cbb`(Task6) `7aec127`(Task7) `ad981e4`(Task8).
- [x] `MusicnaKit` 패키지(순수 Swift, SwiftUI/AppKit 무의존) — `Models.swift`(PlayerStatus/SystemStatus/TrackMeta/MoodTag/AnalysisResult/LiveEvent)·`APIClient.swift`(REST)·`LiveEventClient.swift`(WebSocket, 재연결 busy loop 방지)·`PlayerStatusStore`/`LiveAnalysisStore`/`LibraryStore`(ObservableObject 스토어) — `cd macos-app/MusicnaKit && swift test` 27 tests 통과
- [x] Xcode 프로젝트(XcodeGen `project.yml`) + MenuBarExtra 앱 구조 — `xcodebuild -project macos-app/Musicna.xcodeproj -scheme Musicna -configuration Debug build` → `** BUILD SUCCEEDED **`
- [x] `MenuBarView`(재생 제어·세션 상태·실시간 코드) + `LibraryWindowView`(트랙 목록 Table) + `PreferencesView`(api 주소 설정, UserDefaults)
- [ ] **(macOS)** 마일스톤: 메뉴바에서 재생/일시정지·다음곡·볼륨 조작 시 실제 Spotify 재생 반응, 캡처 상태·실시간 코드가 실제 재생과 함께 갱신, 라이브러리 창에 실제 캡처 트랙 표시 — 이 세션엔 네이티브 macOS 앱을 조작할 GUI 자동화 도구가 없어 미실시, 다음 세션에서 사용자 또는 GUI 도구로 확인 필요

### Phase 10 — iOS 앱 (범위 확정, 2026-07-26)
> 설계·타당성 조사: [2026-07-26-central-deployment-ios-player-design.md](superpowers/specs/2026-07-26-central-deployment-ios-player-design.md) — cpal iOS 지원 확인, `librespot-golang`/gomobile 레퍼런스 발견, iOS 백그라운드 정책 리스크 조사 포함
- [ ] SwiftUI + OpenAPI 생성 클라이언트, 라이브러리 뷰어 겸 원격 제어(기존 계획)
- [x] **(선행 조건, 완료)** `api/src/musicna_api/remote_capture.py`에 `session_id`별 동시성 lock 추가(2026-07-28, 브랜치 `fix-remote-capture-session-lock`, TDD로 구현) — Phase 8.5 최종 리뷰(2026-07-26)에서 발견된 park된 이슈. `RemoteCaptureManager`에 `session_id`별 `asyncio.Lock`을 `start()`에서 생성·`end()`에서 정리, `/chunk`·`/end` 라우트가 실제 작업(threadpool 오프로드 포함) 전에 lock을 획득하도록 수정. 레이스를 실제로 재현하는 회귀 테스트(`asyncio.gather`+`httpx.AsyncClient`, 수정 전 코드로 실패 확인 후 수정)로 검증. 코드 리뷰 통과(Critical/Important 0건 — 문서 갱신만 요청받아 이 커밋으로 반영), 워크스페이스 232 passed·1 skipped
- [ ] **(신규)** `librespot-golang`+gomobile 임베딩 스파이크 — iOS 앱이 실제 Spotify Connect 기기로 인식되는지부터 검증(가장 큰 미검증 영역)
- [ ] **(신규)** 자체 재생 중 디코딩 PCM을 원격 인제스트로 스트리밍(포그라운드 전용, 백그라운드 상주 미지원)
- [ ] **(신규)** `/ws/live` 네이티브 SwiftUI 구독 — 재생 중 실시간 코드·피아노 롤 표시(웹 `live.html`과 동일 이벤트 계약)

## 작업 로그

| 날짜 | 작업 | 비고 |
|---|---|---|
| 2026-07-24 | 프로젝트 방향 논의, 기술 조사, PLAN.md/PROGRESS.md 작성, Phase 0 착수 | muscriptor=오디오→MIDI 전사(가중치 CC BY-NC), Essentia는 arm64 휠 결함으로 CLAP 채택 |
| 2026-07-24 | Phase 0 완료: uv 워크스페이스, core(모델·DB·스텁), api(FastAPI), 문서·테스트 | ML 의존성은 optional extra로만 선언 |
| 2026-07-24 | 원격: 패키지명 PyPI 검증, muscriptor API 조사, core/transcribe 래퍼, MIDI 키 추정, Python 3.12 고정 | core 테스트 8건 통과. **muscriptor 가중치는 HF gated** — macOS에서 `hf auth login` 필요 |
| 2026-07-25 | Phase 1 구현: Swift 캡처 헬퍼(SCK→float32 PCM stdout), 세션 매니저(pcm/metadata/silence/recorder/cli, TDD 19 passed), `musicna-session` CLI | 실기기 캡처는 터미널 화면 기록 권한(TCC) 거절로 미검증 — 권한 부여 후 Spotify 재생 검증 필요. macOS 26.5 / Swift 6.3.2 CLT |
| 2026-07-25 | **Phase 1 마일스톤 검증 통과**: 화면 기록 권한 부여 후 Spotify 실캡처 → 트랙 전환 시 WAV+JSON 자동 분할 저장 확인 (2트랙). 버그 수정: AppleScript 변수명 `st`가 앱 tell 블록 내 스크립팅 용어와 충돌해 구문 오류 → `playerStateText`로 변경 | `st` 버그는 TCC 미검증 상태에서 잠복해 있던 것 — 실기기 검증의 중요성. 19 tests passed |
| 2026-07-25 | Phase 2 진행: muscriptor 실설치(transcribe extra), import·MPS available 확인 | 가중치 다운로드는 HF 로그인+라이선스 동의 필요(사용자 작업) — 완료 후 WAV→MIDI 마일스톤 검증 |
| 2026-07-25 | **Phase 2 마일스톤 검증 통과**: HF 로그인·라이선스 동의(사용자) → small/large 전사 성공, 피아노롤 확인. torch 2.2.2→2.13.0 (arm64 한정 상한 해제) | torch 2.2 MPS는 FFT 미구현(`aten::_fft_r2c`) — muscriptor의 `<2.3` 핀은 darwin x86_64 전용인데 uv가 공통 해석으로 2.2.2를 선택했던 것. large 전사: 28.5초 오디오 150초(가중치 다운로드 포함) |
| 2026-07-25 | 원격: Phase 3 코드 진행 추출(MIDI 기반) + `analyze_track` 파이프라인 조립 | 30 tests passed. chorder 대신 music21 harmony 라벨링으로 base 의존성만으로 구현(합성 MIDI에서 C/F/G/C·Am7 정확). allin1/CLAP 미설치 시 자동 건너뜀 — macOS에서 extra 설치 후 실캡처 곡 검증 필요 |
| 2026-07-25 | 원격: Phase 4 구현 — 저장소 패턴, /tracks DB 조회, `musicna-analyze` 배치 CLI | 37 tests passed. E2E 마일스톤(실캡처→DB)은 macOS에서 `uv run musicna-analyze`로 검증 필요 |
| 2026-07-25 | **Phase 4 E2E 마일스톤 검증 통과**(macOS): `musicna-analyze` 실캡처 2트랙 → SQLite 축적·중복 건너뜀·/tracks 조회 확인. 견고성 수정 2건: 노트 없는 MIDI 키 추정 크래시, allin1 bpm=None 크래시 | 002 트랙은 캡처 레벨이 준무음(-51dB RMS)이라 large 전사가 0노트 — 파이프라인은 크래시 없이 강등 처리하도록 수정. 캡처 볼륨 주의 |
| 2026-07-25 | **Phase 3 allin1·CLAP 검증 완료**(macOS): allin1 설치 확립(madmom git 핀 + natten 0.15.1 소스 빌드 + torch 호환 셈), BPM/구간 검출 확인. CLAP 무드 스파이크 → `core/analyze/moods.py` 구현 | 43 tests passed. allin1 `multiprocess=False` 필수(스폰 교착), 부산물은 임시 디렉터리로. 상세는 아래 검증 기록 |
| 2026-07-25 | 원격 동기화: Linux 호환 수정 2건 — ① natten 정적 메타데이터 선언(`[[tool.uv.dependency-metadata]]`)으로 Linux uv sync 실패 해소(크로스 플랫폼 해석이 Darwin 전용 natten sdist를 빌드하려던 문제) ② `_patch_natten_torch_compat`가 torch 부재를 허용하도록 수정 | Linux에서 40 passed, 1 skipped. macOS 설치 동작에는 영향 없음 |
| 2026-07-25 | 원격: Phase 5 웹 UI 구현 — 라이브러리 브라우저·구조 타임라인·코드 진행 뷰·무드 바, api 정적 서빙 | 42 passed, 1 skipped. Playwright 렌더 검수(라이트/다크/강등/툴팁) 완료. macOS에서 실캡처 DB로 확인 필요 |
| 2026-07-25 | 원격: 코드 진행 chroma 교차 검증 — chords_audio(템플릿 매칭) + merge_chord_tracks, analyze_track 연결 | 52 passed, 1 skipped. 합성 사인파 3화음에서 C/F/G/C·Am 정확, MIDI·오디오 일치 시 MERGED(신뢰도 보너스). `chroma` extra 신설, dev 그룹에 librosa 추가(테스트용) |
| 2026-07-25 | 원격: Phase 6 구현 — LiveEvent 계약, LiveChordTracker, WS 브로드캐스트(/live/ingest→/ws/live), `musicna-live` CLI, 웹 라이브 뷰(코드+피아노 롤) | 63 passed, 1 skipped. Playwright E2E(이벤트 시뮬레이션)로 렌더 확인. **발견**: 기본 uvicorn에 WS 백엔드 없음 → websockets 의존성 추가. muscriptor 실전사 스트림은 macOS 검증 대기 |
| 2026-07-25 | 원격: 문서 최신화 — README 전면 갱신(macOS 사용법 ①수집→②분석→③웹UI→④실시간, 개발 안내), PLAN에 현황 배너 추가 | Phase 0~6 구현 완료 시점의 문서 정리. 남은 로드맵: Phase 5·6 실기기 확인, iOS 뷰어 |
| 2026-07-26 | **Phase 5·6 실기기 마일스톤 검증 통과**(macOS): ① `musicna-analyze --force` 재분석으로 chroma 교차 검증 확인(001에 MERGED 코드 12개 발생) ② 실캡처 DB로 웹 라이브러리 브라우저 렌더 확인(Playwright) ③ Spotify 실재생 캡처→`musicna-live`→live.html 실시간 코드·피아노 롤 렌더 확인 | Phase 0~6 전체 마일스톤 실기기 검증 완료. 청크 처리 평균 1.79s(최대 7.35s, 동시 실행 중이던 Playwright 스크린샷 스크립트의 CPU 경합으로 추정) — 5초 예산 내 여유 확보 |
| 2026-07-26 | 브레인스토밍·설계·계획: TUI(`tui/`, Textual)+재생 엔진(`spotify_player` 임베딩) — Phase 7·8 스펙과 14-Task 구현 계획 작성. spotify_player 0.24.1 실바이너리로 CLI 문법·JSON 스키마 실측 확인 후 계획에 반영 | PLAN.md에 Phase 7~10 로드맵 추가(모든 클라이언트가 api/만 호출하는 동일 패턴). Homebrew 기본 빌드엔 daemon feature 없음(cargo 재빌드 필요)을 사전에 확인해 계획에 반영 |
| 2026-07-26 | **Phase 7 구현**(subagent-driven development, Task 1~11): `api/player.py`(spotify_player CLI 래퍼·SpotifyPlayerDaemon)·`api/system.py`(SystemOrchestrator)·`/player,/system` REST·`api/session/metadata.py` spotify 소스 교체·`tui/`(ApiClient·PlayerPanel·SessionStatus·MusicnaApp) 신규 패키지 | Task별 구현자+리뷰어 서브에이전트 2단계 검토, 전부 승인(Critical/Important 0건, Minor는 원장에 기록). 전체 워크스페이스 141 passed |
| 2026-07-26 | **Phase 7 마일스톤 실기기 검증 통과**(macOS): rust 1.86→1.97 업그레이드 후 spotify_player를 daemon feature로 cargo 재빌드(Homebrew 버전은 `media-control` 기본 feature가 daemon 모드와 macOS에서 상호 배타적 — 실기기에서 최초 발견). `/system/start`·`/player/play|pause|volume|next` 전부 실제 Spotify 재생에 반응, 재생이 캡처(WAV 실시간 증가)·트랙 분할(다음곡 전환마다 정확히 분리 저장)에 그대로 반영됨 확인. `/system/stop`이 SIGINT로 WAV 정상 마무리. `musicna-tui`를 `run_test()` 기반 무헤드 통합 검증으로 확인(위젯 실데이터 표시, space/n 키 → 실제 재생 제어) | **실기기 발견 버그**: `SpotifyPlayerDaemon`이 `subprocess.Popen` 핸들로 생명주기를 추적했으나 spotify_player daemon은 daemonize crate로 더블포크 데몬화 — 원래 핸들이 데몬화 직후 종료돼 `is_running()` 상시 오탐, `stop()`이 실제 데몬을 못 죽이고 좀비로 방치. `pgrep -f`/`pkill -f` 기반으로 교체(서브에이전트 fix+리뷰 통과, 84 passed) 후 재검증 완료 |
| 2026-07-26 | **최종 전체 브랜치 리뷰(opus, 13 commits) → 발견 버그 수정·재검증**: 세션 캡처가 여전히 `--app com.spotify.client`(데스크톱 앱)만 필터링 — Task 4(메타데이터)와 Task 5(오디오 캡처 대상)가 서로 다른 "spotify"를 가리키던 task-scoped 리뷰의 사각지대. 컨트롤러가 Spotify.app 완전 종료 상태로 재현해 확정 → `SystemOrchestrator.start()`에 `--system-audio` 추가로 수정(외 Minor 4건 동시 수정, 145 passed) → 스코프된 재리뷰 통과 → 컨트롤러가 재검증(도중 별개의 HDMI 출력 볼륨 API 문제 발견·회피) | 서브에이전트 기반 개발(subagent-driven-development)의 각 Task 리뷰는 자기 diff만 보므로 여러 Task에 걸친 이름은 같지만 실제로 다른 개념(메타데이터의 "spotify" vs 캡처의 "spotify")의 불일치를 못 잡음 — 전체 브랜치 최종 리뷰가 반드시 필요했던 사례 |
| 2026-07-26 | 문서 정리: PLAN.md Phase 7 완료 표시, PROGRESS.md에 재개 체크리스트·설계 결정 배경(전환 과정)·환경 이슈(uv sync가 ML extras 제거)·이 머신 영구 환경 변경사항 정리 추가 | 다른 머신에서도 이 문서만으로 Phase 7 상태를 재현·재개할 수 있도록 정리 |
| 2026-07-26 | Phase 8 착수 전 브레인스토밍: "중앙 DB/api를 실제로 어디서 운영할 것인가" 논의 → Tailscale+launchd 상시 배포 구조(Phase 8.5 신설) 결정. "spotify_player·캡처를 앱마다 따로" 제안을 검토하며 iOS는 시스템 오디오 캡처 API 자체가 없다는 제약 확인 → "iOS 앱 자신이 Spotify Connect 기기가 되면 캡처 권한 문제가 사라진다"는 대안 도출, 웹 조사로 타당성 확인(cpal iOS 지원 확인, `librespot-golang`/gomobile 레퍼런스 발견, iOS 백그라운드 정책 리스크 확인) → Phase 10 범위를 "포그라운드 전용 자체 재생·캡처 기기"로 확정. 설계 스펙 작성·커밋 후 PLAN.md·PROGRESS.md 반영 | 설계 스펙: [2026-07-26-central-deployment-ios-player-design.md](superpowers/specs/2026-07-26-central-deployment-ios-player-design.md). 논의 과정(대안 비교·기각 근거)까지 스펙 문서에 상세히 기록. 구현 계획(writing-plans)은 아직 미작성 — Phase 8.5·10 착수 시 작성 필요 |
| 2026-07-26 | **Phase 8.5 구현 계획 작성(writing-plans) + subagent-driven-development로 실행**: Task 1(process_chunk 추출)·2(RemoteCaptureManager)·3(/remote/audio/* 엔드포인트)·4(TUI 부트스트랩 제거)는 서브에이전트 구현+태스크별 리뷰(각 1회 fix round: 비정렬 PCM 청크 가드, asyncio.Queue 스레드 안전성). Task 5(launchd)는 파일 작성만 서브에이전트, 실제 설치·검증은 사용자 직접 진행. Task 6(Tailscale)은 전부 사용자 직접 진행 — iPhone 로그인만으로 VPN 미연결(137일 offline)되는 문제를 컨트롤러가 `tailscale status` 직접 조회로 진단, 토글 확인 후 해결. Task 7(마일스톤 검증)은 라이브러리 원격 조회만 확인, TUI 원격 접속·재부팅 복구는 백로그 이월 | 워크스페이스 테스트 145→160 passed. 매 Task 완료 후 계획 파일 체크박스·PROGRESS.md 진행표·작업 로그를 즉시 갱신(세션/토큰 한도로 중단되어도 재개 가능하도록). `deploy/macos/README.md` 운영 매뉴얼 신설(설치/상태확인/재시작/트러블슈팅/Tailscale). 상세는 위 "Phase 8.5 실기기 검증 상세 기록" 및 [구현 계획 파일](superpowers/plans/2026-07-26-phase-8-5-central-deployment.md) 참조 |
| 2026-07-26 | **Phase 8.5 최종 전체 브랜치 리뷰(opus, 16개 커밋)** → fix wave(커밋 `0a68f27`) → 스코프된 재리뷰 → park 후 Phase 8.5 완료 처리: `upload_chunk` 이벤트 루프 블로킹(muscriptor 전사를 동기 실행)과 원격 세션의 `captured_at` 누락 시 DB dedup 충돌 버그를 수정. 재리뷰에서 fix 자체가 도입한 새 동시성 이슈(같은 session_id 동시 요청 시 `RemoteCaptureSession` 상태 경합) 발견 → 실호출자 없어(Phase 10 미구현) park, Phase 10 착수 전 lock 추가를 선행 조건으로 PLAN.md·PROGRESS.md에 기록 | 최종 100 passed(api), 워크스페이스 전체는 재확인 필요. subagent-driven-development의 "fix wave는 1회 한정" 규칙에 따라 추가 라운드 없이 컨트롤러가 직접 adjudicate. SDD 원장(`.superpowers/sdd/2026-07-26-phase-8-5-central-deployment/progress.md`)에 전 과정 기록 후 워크스페이스 정리 예정 |
| 2026-07-27 | **코드 진행 추상화 구조 구현**(브랜치 `feature-chord-structure-abstraction`, subagent-driven-development, Task 1~6) — `chord_structure.py`(단순화·로마자 변환·섹션 요약·루프 탐지), `analyze_track()` 연결, DB 신규 테이블 2개(`section_chord_summaries`, `chord_loops`). Task 3 리뷰에서 Critical 버그 발견·수정: `find_chord_loops`가 3회 이상 반복되는 패턴을 위상만 다른 여러 중복 루프로 잘못 보고하던 문제(`claimed` 재검사 누락) — fix round 1로 수정, 회귀 테스트 4건 추가. **최종 전체 브랜치 리뷰(opus)에서 2차 버그 발견·수정**: 4회 이상 반복(특히 홀수배)에서 `find_chord_loops`가 "더 긴 패턴이 적게 반복"으로 오인식하거나 마지막 등장을 누락하던 문제 — `_is_primitive` 헬퍼로 원시 주기가 아닌 윈도우를 후보에서 제외하도록 수정. 구현자가 컨트롤러가 처방한 divisor 조건부 주기 체크의 허점(길이가 주기의 배수가 아닌 "부분 반복" 케이스 누락)을 스스로 발견해 divisor 조건 없는 일반 문자열 주기 정의로 개선 — 재리뷰에서 조합론적으로 안전함을 hand-trace로 확인 후 승인 | 신규 ML 의존성 없음(music21 base 의존성만 활용). 로마자 변환 로직은 계획 작성 단계에서 실제 music21 실행으로 사전 검증(`.figure` 대신 수동 조합 방식 채택 근거). 워크스페이스 145→185 passed. 전조 대응·기능적 유사 진행 매칭은 백로그(설계 스펙 참조). **교훈**: 루프 탐지처럼 "긴 패턴이 짧은 패턴의 반복으로 재구성 가능한지" 따지는 알고리즘은 정수배(divisor) 조건만으로는 불충분하고 일반 문자열 주기 정의가 필요하다는 게 최종 리뷰에서야 드러남 — 서브태스크 리뷰(Task 3)는 3배수 케이스만 봐서 못 잡았고, 전체 브랜치 리뷰가 4배수 이상 입력으로 실제 재현해 발견 |
| 2026-07-27 | main 병합 완료(Phase 0~8.5 + 코드 진행 추상화 구조). 브레인스토밍: "MIDI도 중앙 저장소에 저장, WAV는 용량 문제로 임시만 유지" 요청 → WAV는 분석 성공 직후 삭제·MIDI는 기존 `data/midi/` 파일 방식 유지로 확정(최초 제안했던 DB BLOB 저장은 사용자가 재검토 후 파일 유지로 결정), 원격 클라이언트를 위한 `GET /tracks/{id}`+`GET /tracks/{id}/midi` 신설 필요성 도출. 설계 스펙·구현 계획(Task 1~4) 작성 → 새 브랜치 `feature-track-storage-retention`에 커밋·푸시(구현은 미착수, 세션 종료로 다음 세션에 이어감) | `--force` 재분석 시 오디오 기반 재검증 불가라는 트레이드오프는 이미 인지·수용됨. 구현 계획은 기존 코드(models.py/repository.py/main.py/batch.py) 실제 내용을 직접 읽어 정확한 앵커 지점으로 작성 — 특히 `test_batch_analyzes_and_skips_on_rerun`의 재실행 기대값이 WAV 삭제로 바뀌는 지점을 명시 |
| 2026-07-27 | **최종 전체 브랜치 리뷰 Important 발견 수정**: `find_chord_loops`가 기본 패턴이 4회 이상 반복될 때 "긴 패턴이 2회"로 뭉개 보고하고 홀수배(5회 등)에서는 마지막 등장을 통째로 누락시키던 버그. `_is_primitive` 헬퍼를 추가해 원시(더 짧은 주기의 반복이 아닌) 패턴만 루프 후보로 받아들이도록 수정 — 리뷰가 제안한 구현(주기가 길이를 나눠떨어지게 하는 경우만 배제)을 그대로 적용했더니 새 회귀 테스트가 실패, 원인 추적 결과 나눠떨어지지 않는 "부분 반복"(예: 길이 7 안의 주기 4)도 같은 버그를 재현함을 확인 → 나눗셈 조건 없이 일반적인 문자열 주기 정의로 교체해 해결. 회귀 테스트 2건 추가(4회·5회 반복 케이스) | `core/tests/test_chord_structure.py` 20 passed(18+2), 워크스페이스 183→185 passed. 기대값은 그대로 두고 구현만 검증해 원인 확정 — 리뷰가 제안한 헬퍼 로직 자체의 사각지대를 실측으로 발견한 사례 |
| 2026-07-27 | 트랙 저장·보존 정책 구현 — WAV 분석 성공 직후 삭제(`api/batch.py`), `AnalysisResult.id` 노출 + `GET /tracks/{id}`·`GET /tracks/{id}/midi` 신설(`api/main.py`, `core/store/repository.py`) | 신규 의존성 없음. `--force` 재분석 시 오디오 기반 재검증이 안 되는 트레이드오프는 이미 인지·수용됨(설계 스펙 참조). 워크스페이스 185→195 passed |
| 2026-07-28 | **트랙 저장·보존 정책 최종 전체 브랜치 리뷰(opus) → fix wave → main 병합**: Task 1~4를 subagent-driven-development로 실행(각 Task 리뷰 통과, Task 2 fix round 1에서 브리프 범위 밖 문서 커밋+push를 되돌린 사례 1건). 최종 리뷰는 Critical/Important 0건, Minor 4건 중 사용자 선택으로 2건(WAV unlink 실패 시 오분류 버그, PROGRESS.md 수치 불일치)을 fix wave로 수정 → 스코프된 재리뷰 통과 → `main`으로 fast-forward 병합, `feature-track-storage-retention` 브랜치 로컬·원격 삭제 | `batch.py`의 `wav_path.unlink()`를 `counts["analyzed"] += 1` 뒤로 옮기고 별도 `try/except OSError`로 격리 — 삭제 실패가 이미 성공한 저장을 실패로 오분류하지 않게 함. 워크스페이스 최종 196 passed |
| 2026-07-28 | **Phase 8 구현** — `api/player.py`에 search/list_playlists/play_playlist + 3개 라우트, `tui/client.py`에 대응 메서드, `tui/widgets/`에 LibraryBrowserWidget(DataTable)·LiveAnalysisWidget(/ws/live 구독)·PlaylistsScreen·SearchScreen(둘 다 ModalScreen) 신설, `app.py`에 조립(`/` 검색, `u` 플레이리스트 바인딩) | search/get key user-playlists CLI 문법·JSON 스키마는 aome510/spotify-player 소스 직접 확인(실측 아님) — macOS 실기기에서 재확인 필요. 트랙 단건 재생은 설계 범위 밖(플레이리스트만 재생 가능). 워크스페이스 196→225 passed, 1 skipped. Task별 커밋(오래된 순): `7ce7162`(Task1)·`1524f0d`(Task2)·`a177cb5`(Task3)·`d8101f3`(Task4)·`66c0675`(Task5)·`712c012`(Task6)·`8b16888`(Task7)·`a8225a2`(Task8) |
| 2026-07-28 | **Phase 8 최종 전체 브랜치 리뷰(opus) → fix wave → main 병합**: Task 1~9를 subagent-driven-development로 실행하며 계획 브리프 자체의 실측 버그 3건을 구현자들이 발견·수정(재연결 busy loop, Textual 모달 쿼리 스코프, 스테일 서버 응답으로 인한 테스트 크래시 — 상세는 위 Phase 8 체크리스트 참조). 최종 리뷰 Important 2건 중 1건(위젯 3종 KeyError 위험)을 fix wave로 수정(커밋 `1918a09`) → 재리뷰 통과 → `main` fast-forward 병합, `phase-8-tui-parity` 브랜치 삭제. 나머지 1건(이벤트 루프 경합)은 기존 패턴과 일치해 park | 워크스페이스 최종 228 passed, 1 skipped. "계획 문서 자체에 버그가 있을 수 있다"는 전제로 각 구현자에게 "브리프를 맹신하지 말고 실제로 실행해 확인하라"고 명시적으로 지시한 것이 반복적으로 유효했던 세션 |
| 2026-07-28 | **Phase 10 선행 조건 해소** — `remote_capture.py`에 `session_id`별 `asyncio.Lock` 추가(브랜치 `fix-remote-capture-session-lock`, TDD로 직접 구현·`superpowers:requesting-code-review`로 리뷰). 레이스를 실제로 재현하는 회귀 테스트(수정 전 코드로 실패 확인 후 수정 — 리뷰어가 base 커밋에 대해 독립 재검증)로 검증. 코드 리뷰에서 Important 1건(문서 미갱신) 발견해 이 커밋에 함께 반영 | Phase 8.5 최종 리뷰(2026-07-26)에서 park됐던 이슈. 워크스페이스 232 passed, 1 skipped. PLAN.md 리스크 절의 해당 항목 제거 |
| 2026-07-29 | **Phase 9(macOS 네이티브 앱) 브레인스토밍·설계·계획 작성**: 메뉴바(재생 제어·세션 상태·실시간 코드)+별도 라이브러리 창, 네트워킹·모델·스토어를 순수 Swift 패키지 `MusicnaKit`으로 분리해 Phase 10과 공유하기로 결정. 설계 스펙·구현 계획(Task 1~9) 작성 → 브랜치 `phase-9-macos-native-app`에 커밋·push. **세션 도중 중요 정정 발견**: 작업 중이던 머신이 "원격/Linux"가 아니라 이 프로젝트의 실제 Mac mini임을 확인(`spotify_player`·`Tailscale.app`·`launchd` 서비스·실제 캡처 데이터 전부 존재) — 유일한 예외로 전체 Xcode.app 미설치(Command Line Tools만 있음)로 기록. 사용자 요청으로 이 지점에서 세션 종료(구현 미착수) | 코드 구현 0%, 문서만 존재. **이 "Xcode.app 미설치" 판단은 다음 날 세션에서 오판으로 정정됨 — 아래 2026-07-30 행 참조** |
| 2026-07-30 | **Phase 9(macOS 네이티브 앱) Task 1~8 구현**: Task 1~4는 `MusicnaKit` 순수 Swift 패키지(Models·APIClient·LiveEventClient·PlayerStatusStore/LiveAnalysisStore/LibraryStore, `swift test`로 검증, 27 tests 통과). 구현 도중 **환경 오판 정정**: "Xcode.app 미설치"는 오판이었고, 실제로는 Xcode 26.6이 외장 볼륨(`/Volumes/External/Applications/Xcode.app`)에 설치돼 있었으나 활성 개발자 디렉터리로 선택돼 있지 않았을 뿐 — 사용자가 `sudo xcode-select -s /Volumes/External/Applications/Xcode.app/Contents/Developer`로 전환, `xcodegen` 2.46.0을 Homebrew로 설치해 Task 5~8(Xcode 프로젝트·MenuBarExtra 앱·라이브러리 창·설정 화면)까지 같은 세션에서 이어서 완료. `xcodebuild -project macos-app/Musicna.xcodeproj -scheme Musicna -configuration Debug build` → `** BUILD SUCCEEDED **` 확인 | Task별 커밋: `da47ba9`(Task1)·`63a9cc5`(Task2)·`1e22b6a`(Task3)·`f9cf7d8`+`c8fc508`(Task4, fix round 1회)·`e23227f`(Task5)·`9289cbb`(Task6)·`7aec127`(Task7)·`ad981e4`(Task8). 코드 리뷰에서 발견한 사소한 항목(미확정 판단 필요, 다음 세션 참고용): `LiveAnalysisStore.isConnected`가 실제로 `true`로 설정되는 지점이 코드 어디에도 없음(계획 샘플 코드 자체의 공백, Task 1~8 어느 것도 연결 안 함), `APIClient.tracks()`(배열 통짜 디코딩)는 `LibraryStore`가 `tracksRaw()`+항목별 관대한 디코딩을 쓰게 되면서 사실상 죽은 코드(자체 테스트 커버리지 때문에 유지), 계획의 Task 6 샘플 코드가 정의 없이 참조하던 `APIClient.baseURLForOpening` 프로퍼티를 신규 추가함. 실기기(macOS) 마일스톤 검증(메뉴바가 실제 Spotify 재생에 반응하는지 등)은 GUI 자동화 도구 부재로 이 세션엔 미실시 — Phase 9의 유일한 미완료 항목 |

## 실기기 검증 상세 기록 — 2026-07-25 (macOS)

> Phase 1·2 마일스톤을 실기기(macOS 26.5, Apple Silicon, Python 3.12, Swift 6.3.2 CLT)에서 검증한 상세 절차와 발견 사항. 재현·트러블슈팅용.

### Phase 1 — Spotify 캡처 → 트랙별 WAV 자동 저장

**검증 절차**

1. 화면 기록 권한(TCC) 부여 확인: 캡처 헬퍼 단독 6초 실행 → 2,219,520바이트(≈5.8초 분량, 48kHz float32 스테레오) PCM 출력 확인
2. E2E: Spotify 재생 상태에서 `uv run musicna-session --source spotify --out data/audio` 실행 → 25초 후 AppleScript로 트랙 전환(경계 유발) → 20초 후 SIGINT
3. 결과: **2트랙이 곡 단위로 자동 분할 저장** — `001 - 中山美穂 - 世界中の誰よりきっと.wav` (28.7s) + `002 - 大滝詠一 - 君は天然色.wav` (19.5s), 각각 title/artist/album/duration/captured_at이 담긴 JSON 사이드카 동반. 일본어 곡명·파일명 처리 정상

**발견 버그: AppleScript 변수명 `st` 용어 충돌** (`api/src/musicna_api/session/metadata.py`, 커밋 fb796a2)

- 증상: 캡처는 정상이나 저장 트랙 0건. `poll_now_playing()`이 항상 None
- 원인: `tell application "Spotify"` 블록 안에서 변수명 `st`가 앱 스크립팅 용어와 충돌 → osascript 구문 오류(-2741 "표현식을 예상했지만 st을 발견"). 최소 재현: 같은 스크립트에서 `st`→`myState`로만 바꾸면 정상
- 수정: Spotify/Music 스크립트 모두 `playerStateText`로 변경
- 교훈: 단위 테스트는 osascript 출력을 모킹했기 때문에 스크립트 자체의 구문 오류는 실기기에서만 드러났다. **앱 tell 블록 내 짧은 변수명은 피할 것**

### Phase 2 — muscriptor WAV → MIDI (Apple Metal)

**환경 준비 절차 (신규 머신 재현용)**

1. `uv sync --package musicna-core --extra transcribe` — muscriptor 0.2.2 + torch 설치
2. HF 로그인: `uvx --from huggingface_hub hf auth login` — **이 세션형 터미널에서는 대화형 입력 불가 → 별도 터미널에서 실행** (토큰은 read 권한이면 충분)
3. 가중치 라이선스 동의: 로그인만으로는 403 GatedRepoError — **모델 페이지에서 각각 동의 필요** (자동 승인): [muscriptor-small](https://huggingface.co/MuScriptor/muscriptor-small), [muscriptor-large](https://huggingface.co/MuScriptor/muscriptor-large)

**발견 문제: torch 2.2.2 MPS에 FFT 미구현** (`core/pyproject.toml`, 커밋 1853f7d)

- 증상: 전사 시작 즉시 `NotImplementedError: aten::_fft_r2c is not currently implemented for the MPS device`
- 원인: muscriptor의 `torch<2.3` 핀은 **darwin x86_64 전용 마커**인데, uv의 전 플랫폼 공통 해석이 arm64에도 2.2.2를 선택. MPS FFT는 torch 2.3+에서 구현됨
- 수정: transcribe extra에 `"torch>=2.3; platform_machine == 'arm64'"` 추가 → 2.13.0으로 해석, MPS 네이티브 동작 (CPU 폴백 환경변수 불필요)

**전사 결과**

| 모델 | 입력 | 결과 | 소요 |
|---|---|---|---|
| small (103M) | 002 트랙 19.5s | 41노트 (clean electric guitar 38, drums 3) | 수 초 (가중치 다운로드 별도) |
| large (1.4B) | 001 트랙 28.5s | **708노트, 4악기 트랙 분리** (distorted electric guitar 423, electric bass 107, drums 167, voice 11) | 150.3s (가중치 다운로드 포함) |

- MIDI 길이가 WAV 길이와 일치(28.5s), 피아노롤 렌더로 시각 확인 완료
- 전사 산출물은 `data/midi/`(git 미추적)에 저장 — 캡처 음원과 파생물은 사적 이용 한정, 저장소 커밋 금지

### Phase 3·4 — 배치 분석·DB 축적 (2026-07-25 추가 검증)

**allin1 설치 확립 (macOS arm64 + torch 2.13)** — 세 가지 비호환을 순차 해결 (`core/pyproject.toml`, 루트 `pyproject.toml` 참조):

1. **madmom 미선언 의존성**: allin1은 madmom을 런타임 import하지만 의존성 선언 안 함(PyPI 0.16.1이 Py3.12 비호환이라 git 설치가 공식 안내) → analyze extra에 git 커밋 핀 추가, hatchling `allow-direct-references` 활성화
2. **natten 버전 딜레마**: allin1의 dinat 모델은 natten 구 함수형 API 사용(0.17에서 제거), 0.14.x는 torch 2.13 헤더와 C++ 컴파일 불가 → **0.15.1이 유일 접점** (구 API 유지 + 빌드 성공). 소스 빌드라 venv에 torch·cmake 선존재 필요: 신규 머신은 ① `--extra transcribe`(torch) ② `uv pip install cmake ninja` ③ `--extra analyze` 순서. 루트에 `no-build-isolation-package = ["natten"]`
3. **torch 2.13에서 제거된 `torch.cuda._device_t`**: natten 0.15.1이 import → `analyze/_patch_natten_torch_compat()`가 타입 별칭 재주입

**allin1 실행 시 주의**: `multiprocess=True`(기본)는 macOS spawn 환경에서 교착 사례 확인(30분+ 무진행, idle 워커 잔존) → core는 `multiprocess=False`로 호출. 부산물(demix/spec)은 cwd 오염 방지를 위해 임시 디렉터리 사용. 가중치는 HF `taejunkim/allinone`(공개, 로그인 불필요) + demucs

**CLAP 무드 스파이크 결과** (music 특화 ckpt `lukewys/laion_clap` 2.2GB, 로드 후 트랙당 추론 수 초):

| 트랙 | 상위 무드 (softmax τ=0.05) | 평가 |
|---|---|---|
| 001 世界中の誰よりきっと (업템포) | happy .38, energetic .35, romantic .06 | 청감 일치 |
| 002 君は天然色 (준무음 캡처) | dreamy .22, calm .20, sad .18 | 미약한 신호 기준으론 타당 |

laion-clap도 torchvision을 미선언 런타임 의존 → mood extra에 추가. 프롬프트 `"This music feels {tag}"` × 12태그, 상위 5개 저장

**실기기 E2E에서 발견·수정한 견고성 버그 2건** (원격 구현은 정상, 극단 입력에서만 발생):

- 노트 0개 MIDI(준무음 캡처의 전사 결과)에서 music21 키 추정이 `DiscreteAnalysisException` → `estimate_key_from_midi`가 None 반환하도록 수정
- 같은 입력에서 allin1이 `bpm=None` 반환 → `float(None)` 크래시 → None 허용. **교훈: 실데이터의 극단값(준무음)이 합성 fixture에는 없던 경로를 드러냄**

**최종 E2E 결과** (`uv run musicna-analyze --force`, 전 extra 설치): 분석 2·실패 0 — 001은 bpm 118.0 / D major / 코드 23 / 구간 2(intro) / 무드 5 전 항목, 002는 구간·무드만(키/코드/bpm은 정직하게 NULL). 재실행 시 건너뜀 2, `/tracks` API가 DB 내용 그대로 반환

### Phase 3(chroma)·5·6 — 원격 구현 실기기 검증 (2026-07-26)

**chroma 교차 검증**: 원격이 붙인 `chords_audio.py`+`merge_chord_tracks()`를 실캡처로 재분석(`musicna-analyze --force`). 001 트랙 코드가 23개→27개로 늘고 `source` 분포가 audio 2·merged 12·midi 13으로 갈림 — MIDI·오디오가 일치한 구간은 MERGED(신뢰도↑), 불일치는 고신뢰 쪽 채택이 실데이터에서도 동작 확인. 002(준무음)는 MIDI가 없어 전량 AUDIO(8개, 평균 신뢰도 0.656)

**웹 UI 실캡처 확인**: `uv run uvicorn musicna_api.main:app` 기동 후 Playwright로 `/`·`/live.html` 렌더·콘솔 로그 점검. 트랙 목록·BPM/키/무드 배지·구조 타임라인·코드 진행 레인·무드 바 전부 실DB 데이터로 정상 렌더, 콘솔 오류 0건. (참고: 사이드바는 키를 "D 장조"처럼 한국어 로캘로 표시 — "D major" 문자열 매칭으로 착각해 잠깐 놓칠 뻔한 부분, 실제로는 정상)

**Phase 6 실기기 마일스톤**: `./capture-macos/.build/release/musicna-capture | uv run musicna-live` + Spotify 실재생(森川美穂 ブルーウォーター) → uvicorn `/ws/live` 구독자에 실시간 이벤트 도달, live.html에 현재 코드(Gm7/B- 등)·진행 히스토리·30초 피아노 롤에 실제 노트 렌더 확인. 청크 17개 처리 시간 평균 1.79s(최소 0.63s·최대 7.35s) — 5초 청크 대비 평균 2.8배 여유로 small 모델 실시간성 확보. 최대치(7.35s)는 같은 시각 실행 중이던 Playwright 스크린샷 스크립트의 CPU 경합으로 추정, 단독 실행 시 재측정 권장

**주의**: `LiveBroadcaster`는 in-memory pub/sub이라 새 구독자(페이지를 새로고침 등)는 과거 이벤트를 못 받는다 — 페이지를 연 시점 이후의 이벤트만 보인다(설계 의도, 버그 아님). 첫 로드 시 "노트 0"으로 보여도 정상이며, 곡이 계속 재생되면 채워진다

## Phase 7 실기기 검증 상세 기록 — 2026-07-26 (macOS)

### 설계 결정 배경 (브레인스토밍 요약 — 전환 과정 포함)

Phase 7은 "터미널 UI 추가"라는 요청에서 시작해 브레인스토밍을 거치며 범위가 여러 번 좁혀졌다. 전체 논증은 [설계 스펙](superpowers/specs/2026-07-26-tui-player-orchestration-design.md)에 있고, 여기서는 나중에 왜 이 구조를 택했는지 헷갈리지 않도록 전환 지점만 요약한다:

1. **재생 엔진 아키텍처**: 처음엔 "로컬 Spotify 데스크톱 앱을 Web API로 원격제어"(기존 캡처·메타데이터 무수정, 새 런타임 의존성 없음)를 추천했으나, 사용자가 "librespot 자체 기기"(musicna이 직접 Spotify Connect 기기가 되어 데스크톱 앱 없이도 동작)를 선택 — 이 선택이 Phase 7 전체의 복잡도(메타데이터 소스 교체, 이번에 발견된 오디오 캡처 대상 버그 등)의 근원
2. **librespot 통합 방식**: 자체 Rust 헬퍼를 새로 작성하는 대신, 이미 완성된 [aome510/spotify-player](https://github.com/aome510/spotify-player) 바이너리를 서브프로세스로 임베딩하는 쪽으로 결정(자체 librespot 바인딩 코드 작성 안 함)
3. **자체 스트리밍 vs 원격 제어 모드**: spotify_player는 두 모드를 다 지원하는데(기존 기기 원격 제어만 하는 가벼운 모드도 가능), "자체 스트리밍 모드"(musicna이 진짜 재생 기기가 됨)를 선택 — 이 때문에 "spotify" 소스 메타데이터를 AppleScript(데스크톱 앱 대상)에서 spotify_player 상태 폴링으로 교체하는 게 필수가 됨(Task 4)
4. **범위 분할**: "librespot을 캡처 파이프라인(PCM 직접 탭)까지 교체"할지 검토했으나, 검증된 Phase 1을 재설계하는 별도 대규모 작업으로 보고 범위 밖으로 명시 — ScreenCaptureKit 캡처는 무수정, spotify_player는 재생 제어·오디오 소스 역할만
5. **구현 순서**: 검색·플레이리스트·TUI 실시간뷰/라이브러리는 Phase 8로 이월하고, Phase 7은 핵심 재생 제어(재생/일시정지/다음곡/볼륨)+오케스트레이션+최소 TUI 셸까지만 — 리스크 큰 새 외부 의존성(spotify_player)을 먼저 실기기 검증하고 그 위에 화면을 얹는 순서
6. **모든 클라이언트(웹·TUI·macOS·iOS 앱) 기능 동등화 원칙**: 사용자가 "각 인터페이스는 독립되지만 기능은 동등해야 한다"고 명시 → TUI도 웹처럼 라이브러리·실시간뷰까지 갖춰야 하고(Phase 8), 오케스트레이션 로직은 `api/`에만 두어 모든 클라이언트가 재사용(TUI만 갖는 특수 역할은 로컬 api 서버 부트스트랩뿐)

### spotify_player 설치 절차 (신규 머신 재현용)

Homebrew 기본 배포판(`brew install spotify_player`)은 `daemon` cargo feature 없이 빌드되어 `-d`/`--daemon` 플래그가 없다. 헤드리스 구동을 위해 cargo로 재빌드해야 한다:

1. rust 버전 확인 — 이 머신은 Homebrew rust 1.86.0이었는데 여러 의존성(ratatui 0.30 등)이 1.87~1.90을 요구해 빌드 실패. `brew upgrade rust`로 1.97.1까지 올림
2. **`media-control` feature와 `daemon` 모드는 macOS에서 상호 배타적** — `cargo install spotify_player --locked --features daemon,image,notify`(default features 유지한 채)로 빌드하면 `-d` 실행 시 `"Running the application as a daemon on windows/macos with 'media-control' feature enabled is not supported!"`로 즉시 실패(exit 1). `default = ["rodio-backend", "media-control"]`이 원인이므로 **`--no-default-features`가 필수**: `cargo install spotify_player --locked --no-default-features --features daemon,image,notify,rodio-backend`
3. `~/.cargo/bin`이 PATH에 없으면(이 머신은 Homebrew rust만 쓰고 있어 rustup의 PATH 설정이 없었음) `.zshrc`에 `export PATH="$HOME/.cargo/bin:$PATH"` 추가. Homebrew판(daemon 없음)과 공존하면 `which spotify_player`가 어느 쪽을 잡을지 PATH 순서에 의존해 혼란스러우므로 **Homebrew판은 제거**(`brew uninstall spotify_player`) 권장
4. 인증(`spotify_player authenticate`)은 이 머신에서 이미 완료돼 있었고, 바이너리를 cargo판으로 교체해도 `~/.cache/spotify-player`의 토큰 캐시가 그대로 유효함을 확인(재인증 불필요)

### 발견 버그: `SpotifyPlayerDaemon`이 daemonize의 더블포크를 추적 못함 (`api/player.py`, 커밋 9cb4584)

- 증상: `POST /system/start`가 200을 반환하고 재생 제어·캡처는 전부 정상 작동하는데도 `GET /system/status`가 항상 `spotify_player_daemon: false`. `POST /system/stop` 후에도 `ps aux`에 spotify_player 데몬이 좀비로 계속 남음
- 원인: `spotify_player -d`는 `daemonize` crate로 유닉스 표준 더블포크를 한다 — `subprocess.Popen`으로 띄운 원래 자식 프로세스는 데몬화 완료 직후 스스로 종료하고, 실제 서비스는 부모와 연결이 끊긴 별도 PID(그랜드차일드)로 남는다. `is_running()`이 `self._proc.poll()`(원래 핸들)로 판정하고 있어서 실질적으로 항상 신뢰 불가했고, `stop()`도 이미 죽은 핸들에 신호를 보내는 no-op이 되어 실제 데몬을 못 건드림
- 재현: `spotify_player -d -o enable_media_control=false &`; `ps aux | grep spotify_player` → 두 개의 PID(원래 프로세스+데몬화된 서비스)가 잠깐 공존하다 원래 쪽만 사라짐
- 수정: `is_running()`을 `pgrep -f "spotify_player -d"`, `stop()`을 `pkill -f "spotify_player -d"`(타임아웃 시 `pkill -9`로 에스컬레이션) 기반으로 교체 — 프로세스 핸들이 아니라 실제 커맨드라인 매칭으로 판정. 실기기에서 `pkill -f`가 데몬화된 그랜드차일드까지 정확히 종료시킴을 직접 확인 후 반영
- 교훈: 서브프로세스 오케스트레이션에서 "우리가 Popen으로 띄운 핸들"과 "실제로 떠 있는 서비스"는 대상 프로그램이 자체적으로 데몬화(더블포크)하면 서로 다른 프로세스가 된다 — 합성 테스트(fake Popen)는 이 차이를 드러내지 못하고 실기기에서만 발견됨

### 마일스톤 검증 결과

- `POST /system/start` → `spotify_player_daemon: true`(수정 후), `session_capturing: true`. 실제 데몬 프로세스 `ps aux`로 확인
- `POST /player/play`/`pause`/`volume?percent=40`/`next` — 전부 실제 Spotify 재생에 반응(재생/일시정지 토글, 볼륨 변경, 곡 전환을 `/player/status` 재조회로 확인)
- 재생 중 캡처 WAV가 실시간으로 증가(3.2MB→6.4MB→7.9MB, 수 초 간격 확인), `next` 명령으로 곡이 넘어갈 때마다 정확히 새 트랙으로 분리 저장(`002 - Yoko Kanno - My Favorite Things`, `003 - Yoko Kanno - Beni` 각각 WAV+JSON 사이드카)
- `POST /system/stop` → 세션 프로세스에 SIGINT 전달, WAV가 정상 마무리 저장(파일 크기 고정, JSON 완성)되고 프로세스 완전 종료(좀비 없음), 데몬도 pkill로 완전 정리됨
- `musicna-tui`는 이 세션에 대화형 tty가 없어 Textual `App.run_test()`로 실제 api 서버(+실제 spotify_player 데몬)에 연결하는 무헤드 통합 스크립트로 검증: `PlayerPanel`이 실제 곡명·아티스트·볼륨을 표시, `SessionStatus`가 "데몬: 켜짐 | 캡처: 녹음 중"을 정확히 표시, `space`/`n` 키 입력이 실제로 재생 상태 토글·다음곡 전환을 일으킴(위젯 텍스트 갱신은 2~3초 폴링 주기만큼 지연되지만 백엔드 반응은 즉시 확인됨). 실제 터미널에서의 대화형 확인은 다음 세션 과제로 남김

### 최종 전체 브랜치 리뷰에서 발견·수정한 두 번째 버그: 오디오 캡처가 여전히 데스크톱 앱만 필터링

Task 13에서 "검증 통과"로 기록했던 재생↔캡처 연동은, 실은 그 시점에 Spotify 데스크톱 앱이 우연히 함께 실행 중이었기 때문에 통과한 것이었다 — 전체 구현(Task 1~13)이 끝난 뒤 진행한 **최종 전체 브랜치 리뷰**(opus 모델, 13개 커밋 전체 diff)가 이 문제를 지적했고, 컨트롤러가 Spotify.app을 완전히 종료(`osascript -e 'tell application "Spotify" to quit'`)한 상태로 직접 재현해 확정했다.

- **원인**: `api/session/cli.py`의 `_APP_BUNDLE_IDS = {"spotify": "com.spotify.client", ...}`가 여전히 살아있어, `SystemOrchestrator.start()`가 세션 캡처 서브프로세스를 스폰할 때 `--system-audio`를 안 줘서 기본값(`capture_app_only=True`)으로 캡처 헬퍼에 `--app com.spotify.client`가 전달됐다. `capture-macos/Sources/musicna-capture/Capture.swift:88-97`의 `SCContentFilter(display:including:[app]:exceptingWindows:)`는 정확히 그 번들ID(데스크톱 앱)만 캡처하고, 앱이 실행 중이 아니면 `exit(1)`로 즉시 종료한다. Task 4가 **메타데이터** 경로는 spotify_player로 정확히 교체했지만, Task 5가 스폰하는 세션의 **오디오 캡처 대상**은 옛 방식에 머물러 있었다 — task-scoped 리뷰들은 각자 자기 파일만 봤기 때문에 이 두 Task 사이의 불일치를 못 잡았고, 전체 diff를 보는 최종 리뷰에서만 드러났다
- **재현**: Spotify.app 완전 종료 → `POST /system/start` → 3~4초 후 세션 프로세스가 `ps aux`에서 사라짐, `/system/status`가 `session_capturing: false`로 전환
- **수정**: `SystemOrchestrator.start()`의 세션 스폰 커맨드에 `--system-audio` 추가(`api/system.py`) — `session/cli.py`의 기존 옵션을 그대로 활용, `cli.py`·`Capture.swift`는 무수정
- **수정 후 재검증**(컨트롤러 직접, Spotify.app 완전 종료 상태): 세션 프로세스가 살아남았으나(로그: `musicna-capture: capturing system audio`) 이번엔 새 WAV가 안 생기는 **별개의 환경 문제**를 만남 — 기본 오디오 출력이 볼륨 API 미지원 HDMI TV 장치(`output volume: missing value`)로 잡혀 있었다. `switchaudio-osx`(`brew install switchaudio-osx`)로 Mac mini 내장 스피커로 전환하니 즉시 캡처 성공(21MB WAV, JSON 사이드카 정상 생성, `/system/stop`으로 정상 마무리). 검증 후 출력 장치 원복
- **교훈 두 가지**: ① 서브에이전트별 task-scoped 리뷰는 각 Task의 diff만 보므로, 여러 Task에 걸친 "이름은 같은데 실제로는 다른 두 가지 일"(메타데이터의 "spotify"와 오디오 캡처의 "spotify"가 서로 다른 소스를 가리키게 된 것)을 못 잡는다 — **전체 브랜치를 한 번에 보는 최종 리뷰가 반드시 필요한 이유** ② 재생 제어·상태 조회가 전부 정상이어도 실제 캡처 성공 여부는 반드시 파일 시스템 산출물(WAV 크기 증가)로 직접 확인해야 한다 — API 응답만으로는 오디오 출력 하드웨어 문제 같은 하위 레이어 실패를 가릴 수 있다

## Phase 8.5 실기기 검증 상세 기록 — 2026-07-26 (macOS)

Phase 8.5(중앙 배포 인프라)는 [설계 스펙](superpowers/specs/2026-07-26-central-deployment-ios-player-design.md) → [구현 계획](superpowers/plans/2026-07-26-phase-8-5-central-deployment.md)(7개 Task)을 `superpowers:subagent-driven-development`로 실행했다. Task 1~4(순수 코드)는 서브에이전트 구현+리뷰(각 1회 fix round 발생, 상세는 구현 계획 파일 참조)로 진행했고, Task 5~7(launchd·Tailscale·마일스톤 검증)은 서브에이전트가 대신할 수 없는 실기기·계정 로그인 단계라 사용자가 직접 진행했다.

### Task 5 — launchd LaunchAgent

`deploy/macos/com.musicna.api.plist` + `deploy/macos/install.sh`를 서브에이전트가 작성(plist XML 검증 `plutil -lint` 통과, 스크립트 `bash -n` 통과, 리뷰 승인). 사용자가 직접 `./deploy/macos/install.sh` 실행 → 설치·헬스체크(`curl http://127.0.0.1:8000/health`) 확인 완료. 운영 매뉴얼은 [deploy/macos/README.md](../deploy/macos/README.md)에 별도 작성(설치/상태확인/재시작/중지/제거/트러블슈팅).

### Task 6 — Tailscale 설정

Mac mini(디바이스명 `js-m4-mini`)에 Tailscale 설치, `tailscale status`/`tailscale ip -4`로 tailnet IP 확인, MagicDNS 활성화 확인까지는 문제없이 진행됐다.

**발견한 문제**: iPhone(`iphone-15-pro-max`)을 tailnet에 가입시키고 로그인까지 마쳤는데도 `tailscale status`에 **137일째 offline**으로 표시되어 원격 접속(`/health`)이 DNS 오류로 실패했다. 컨트롤러가 `tailscale status`를 직접 조회해 원인을 좁혔다 — **iOS에서는 로그인만으로는 VPN이 연결되지 않는다.** 로그인 후 시스템이 띄우는 "VPN 구성 추가" 승인을 놓치거나 앱을 바로 닫으면, 로그인 상태와 무관하게 실제 VPN 터널은 꺼진 채로 남는다. 아이폰 Tailscale 앱에서 연결 토글을 직접 켜자 즉시 `tailscale status`에 `active; direct ...`로 전환되고 원격 접속이 성공했다. 이 교훈("로그인 = 연결이 아니다")은 [운영 매뉴얼의 Tailscale 절](../deploy/macos/README.md#원격-접근-tailscale)에 기록해 재발 시 빠르게 진단할 수 있도록 했다.

### Task 7 — 전체 마일스톤 검증 (부분 완료)

- ✅ **집 밖(모바일 데이터)에서 웹 UI 라이브러리 조회**: 확인 완료 — Tailscale 경유로 트랙 목록 정상 렌더
- ⏳ **TUI 원격 접속·재생 제어**(`MUSICNA_API_URL`을 Tailscale 주소로 지정해 `musicna-tui` 실행): 이번 세션에서 시간 관계상 미확인 — **백로그로 이월**
- ⏳ **재부팅 복구**(Mac mini 실제 재부팅 후 launchd 자동 복구 확인, 자동 로그인 설정 검증 겸함): 이번 세션에서 미확인 — **백로그로 이월**

남은 두 항목은 PROGRESS.md 상단 "다음 할 일 (macOS)"에 등록해 다음 세션에서 이어서 확인한다.

### 최종 전체 브랜치 리뷰 (2026-07-26, opus 모델, 16개 커밋 전체 diff)

Task 1~7 전체 구현이 끝난 뒤 subagent-driven-development의 최종 단계로 진행. `RemoteCaptureManager`의 WAV+JSON 산출물이 `api/batch.py`의 배치 분석 스캔 패턴과 정확히 일치함, broadcaster 싱글턴 이동이 깨끗함, 두 태스크의 fix round(비정렬 청크 트리밍·async def 전환)가 서로 충돌 없이 조합됨을 확인 — 판정은 "Ready to merge(fix 후)".

**fix wave(커밋 `0a68f27`)로 수정**: ① `upload_chunk`가 muscriptor 전사(청크당 ~1.8초)를 이벤트 루프에서 동기 실행해 다른 모든 요청을 블로킹하던 문제 → `run_in_threadpool` 오프로드 ② 원격 세션이 `captured_at`을 안 보내면 DB dedup 키 충돌로 두 번째 녹음이 조용히 스킵될 수 있던 문제 → 서버 수신 시각으로 자동 스탬핑.

**스코프된 재리뷰에서 새로 발견 → park**: `run_in_threadpool` 오프로드가 이전에 이벤트 루프 단일 스레드 덕에 암묵적으로 보장되던 "같은 세션 동시 처리 배제"를 없애, 같은 `session_id`에 대한 동시 `/chunk` 요청이 `RemoteCaptureSession`의 비동기화 상태에서 진짜로 경합할 수 있게 됨. **판단**: 실재하는 이슈이나 이 엔드포인트를 실제로 호출하는 클라이언트가 아직 없음(Phase 10 iOS 앱 미구현)이라 현재 영향 없음 — park하고 **Phase 10 착수 시 `session_id`별 lock 추가를 선행 조건으로 PLAN.md·이 문서 Phase 10 체크리스트에 기록**(스킬 규칙상 최종 리뷰의 fix wave는 1회로 제한되어 추가 수정 라운드 없이 여기서 마무리).

## 협업 메모 (세션 재개/서브에이전트용)

- 개발 환경이 Linux 원격 컨테이너일 수 있음 → **capture-macos와 muscriptor Metal 실행은 로컬 macOS에서만 검증 가능**. 그 외(core/api)는 어디서든 테스트 가능
- 무거운 ML 의존성(muscriptor, allin1, CLAP)은 core의 **optional extra**로 분리해 스캐폴딩 단계에서는 설치하지 않는다
- 커밋·푸시는 지정 브랜치(`claude/music-analysis-app-planning-rsfa6x`)로만
- **macOS 실행 요구사항** (상세는 위 검증 기록 참조): ① 터미널에 화면·시스템 오디오 기록 권한(TCC) ② HF 로그인 + muscriptor small/large 라이선스 동의 ③ arm64는 torch>=2.3 (transcribe extra가 강제함) ④ analyze extra는 natten 소스 빌드 순서 준수(위 Phase 3·4 기록의 3단계) ⑤ 캡처 시 재생 볼륨 확보 — 준무음 캡처는 전사·비트 검출이 빈 결과가 됨 ⑥ Phase 7~: spotify_player를 cargo로 `--no-default-features --features daemon,image,notify,rodio-backend`로 재빌드(Homebrew판은 daemon 미지원) + `~/.cargo/bin` PATH 등록 + `spotify_player authenticate`(위 Phase 7 검증 기록 참조) ⑦ **기본 오디오 출력 장치가 볼륨 API를 지원해야 함**(HDMI TV 등은 `missing value`를 반환하며 `--system-audio` 캡처가 조용히 무음이 됨) — `SwitchAudioSource -c -t output`(`brew install switchaudio-osx`)으로 확인
- `data/`(audio/midi)는 git 미추적 — 검증 산출물은 이 머신 로컬에만 존재. 다른 머신에서 Phase 3 검증 시 캡처부터 다시 수행

### 환경 이슈: `uv sync`(extras 없음)가 ML 스택을 조용히 제거함

Phase 7 Task 12(전체 워크스페이스 회귀 테스트) 도중 발견: 여러 서브에이전트가 각자 `uv run pytest api/tests/...`나 `uv sync --all-packages`(extras 플래그 없이)를 반복 호출하면서, 그 전에 `--extra transcribe --extra analyze --extra mood`로 깔아뒀던 ML 스택(torch, natten, setuptools, cmake, ninja)이 조용히 제거되어 있었다 — uv는 `sync`를 "현재 요청된 조합과 정확히 일치하게 venv를 맞추는" 명령이라, extras를 안 주면 이전에 깔린 optional 그룹을 제거한다.

- **증상**: `uv sync --all-packages --extra transcribe --extra analyze --extra mood`가 `ModuleNotFoundError: No module named 'setuptools'`(natten 소스 빌드 실패)로 에러
- **복구 절차** (PROGRESS.md Phase 3·4 기록의 natten 빌드 순서와 동일한 원리): ① `uv sync --all-packages --extra transcribe`(torch 먼저 확보) ② `uv pip install setuptools cmake ninja` ③ `uv sync --all-packages --extra transcribe --extra analyze --extra mood`(전체 함께)
- **검증**: `uv run python -c "from musicna_core.analyze import _patch_natten_torch_compat; _patch_natten_torch_compat(); import natten, allin1, laion_clap"`이 에러 없이 통과해야 함
- **교훈**: ML extras가 필요한 작업(Phase 3 analyze, Phase 7 이후 spotify_player 무관하지만 같은 venv 공유) 전에는 항상 위 3단계로 먼저 확인할 것 — 특히 서브에이전트에게 여러 Task를 순차 디스패치할 때 각 Task의 `uv run pytest`가 extras 없이 실행되면 다음 Task 때는 스택이 빠져 있을 수 있음

### 이 세션에서 이 머신(로컬)에 영구 적용된 환경 변경사항 (저장소 밖, 재현 시 참고)

다른 macOS 머신에서 Phase 7을 재현하려면 아래를 전부 새로 해야 한다 — 이 머신엔 이미 적용되어 있음:

- Homebrew `rust` 1.86.0 → 1.97.1 업그레이드(`brew upgrade rust`) — spotify_player의 의존성(ratatui 0.30 등)이 1.87+ 요구
- `spotify_player`를 cargo로 재설치(`~/.cargo/bin/spotify_player`, daemon feature 포함), 기존 Homebrew판은 제거(`brew uninstall spotify_player`)
- `~/.zshrc`에 `export PATH="$HOME/.cargo/bin:$PATH"` 추가(Hermes Agent PATH 라인 다음)
- `brew install switchaudio-osx` — 오디오 출력 장치 전환/확인용 CLI
- `spotify_player authenticate`는 이 머신에서 이전 세션에 이미 완료돼 있었음(재인증 불필요했음) — 신규 머신에서는 최초 1회 필요, OAuth 브라우저 흐름
