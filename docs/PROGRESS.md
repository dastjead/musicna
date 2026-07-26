# musicna — 진행 상황 (PROGRESS)

> 작업 재개·서브에이전트 협업용 단일 진실 소스(single source of truth).
> **규칙**: 작업 단계를 시작/완료할 때마다 이 파일을 갱신하고 즉시 커밋·푸시한다.
> 계획 자체는 [PLAN.md](PLAN.md) 참조. 계획 변경은 PLAN.md에, 실행 기록은 여기에.

## 현재 상태

- **현재 Phase**: **Phase 0~7 전체 마일스톤 실기기 검증 통과**. Phase 7은 spotify_player 재생 엔진 통합(핵심 재생 제어)까지 완료, 검색·플레이리스트·TUI 실시간뷰/라이브러리는 Phase 8로 이월
- **작업 브랜치**: `claude/music-analysis-app-planning-rsfa6x`
- **분담**: `capture-macos/`·`api/session/`은 macOS 로컬 담당, 원격은 `core/`·문서 담당. 작업 전 반드시 pull
- **다음 할 일 (macOS)**: ① `uv run musicna-tui`를 실제 터미널에서 대화형으로 확인(이번 검증은 `run_test()` 기반 무헤드 통합 검증) ② 정상 레벨 곡 추가 캡처·축적. **주의**: 기본 오디오 출력 장치가 HDMI 등 볼륨 API 미지원 장치면 `--system-audio` 캡처가 조용히 실패한다 — 캡처 전 `SwitchAudioSource -c -t output`으로 확인, 필요시 내장 스피커로 전환(아래 Phase 7 기록 참조)
- **다음 할 일 (원격)**: Phase 8(TUI 기능 동등화 — 검색·플레이리스트·실시간뷰·라이브러리 브라우저) 착수, 또는 Alembic 마이그레이션 도입

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

### Phase 4 — DB 저장
- [x] 저장소 패턴: `save_analysis`/`list_latest_analyses`/`has_analysis` (`core/store/repository.py`) — AnalysisResult↔DB 왕복, 재분석 이력 누적, 트랙 재사용. 테스트 3건
- [x] api `/tracks`를 DB 조회로 교체 (env `MUSICNA_DB`, 기본 data/musicna.db) + TestClient 테스트 2건
- [x] 배치 오케스트레이터 `musicna-analyze` (`api/batch.py`): WAV+JSON 스캔 → (필요시 전사) → 분석 → DB. 중복 건너뜀/--force, muscriptor 미설치 시 MIDI 없이 진행. 테스트 2건
- [ ] Alembic 마이그레이션 (스키마 변경 발생 시 도입)
- [x] **(macOS)** 마일스톤: 재생→분석→DB 자동 축적 — 실캡처 2트랙 `uv run musicna-analyze` E2E 통과 (분석 2·실패 0, 재실행 시 중복 건너뜀, /tracks가 DB 결과 반환)

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
- [ ] 검색·플레이리스트(`/player/search`, `/player/playlists`)
- [ ] 실시간 분석 뷰(코드·피아노 롤)를 TUI에 추가 (`/ws/live` 재사용)
- [ ] 라이브러리 브라우저를 TUI에 추가 (`/tracks` 재사용)

### 이후 — Phase 9(macOS 앱)·Phase 10(iOS 뷰어 앱)
- [ ] Phase 9: `api/`만 호출하는 macOS 네이티브 앱
- [ ] Phase 10: SwiftUI + OpenAPI 생성 클라이언트, iOS 뷰어 겸 원격 제어

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

## 협업 메모 (세션 재개/서브에이전트용)

- 개발 환경이 Linux 원격 컨테이너일 수 있음 → **capture-macos와 muscriptor Metal 실행은 로컬 macOS에서만 검증 가능**. 그 외(core/api)는 어디서든 테스트 가능
- 무거운 ML 의존성(muscriptor, allin1, CLAP)은 core의 **optional extra**로 분리해 스캐폴딩 단계에서는 설치하지 않는다
- 커밋·푸시는 지정 브랜치(`claude/music-analysis-app-planning-rsfa6x`)로만
- **macOS 실행 요구사항** (상세는 위 검증 기록 참조): ① 터미널에 화면·시스템 오디오 기록 권한(TCC) ② HF 로그인 + muscriptor small/large 라이선스 동의 ③ arm64는 torch>=2.3 (transcribe extra가 강제함) ④ analyze extra는 natten 소스 빌드 순서 준수(위 Phase 3·4 기록의 3단계) ⑤ 캡처 시 재생 볼륨 확보 — 준무음 캡처는 전사·비트 검출이 빈 결과가 됨 ⑥ Phase 7~: spotify_player를 cargo로 `--no-default-features --features daemon,image,notify,rodio-backend`로 재빌드(Homebrew판은 daemon 미지원) + `~/.cargo/bin` PATH 등록 + `spotify_player authenticate`(위 Phase 7 검증 기록 참조)
- `data/`(audio/midi)는 git 미추적 — 검증 산출물은 이 머신 로컬에만 존재. 다른 머신에서 Phase 3 검증 시 캡처부터 다시 수행
