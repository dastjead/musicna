# musicna — 진행 상황 (PROGRESS)

> 작업 재개·서브에이전트 협업용 단일 진실 소스(single source of truth).
> **규칙**: 작업 단계를 시작/완료할 때마다 이 파일을 갱신하고 즉시 커밋·푸시한다.
> 계획 자체는 [PLAN.md](PLAN.md) 참조. 계획 변경은 PLAN.md에, 실행 기록은 여기에.

## 현재 상태

- **현재 Phase**: **Phase 2 완료** (WAV→MIDI 마일스톤 검증 통과) ∥ Phase 3 준비 (원격 Linux에서 병행)
- **작업 브랜치**: `claude/music-analysis-app-planning-rsfa6x`
- **분담**: `capture-macos/`·`api/session/`은 macOS 로컬 담당, 원격은 `core/`·문서 담당. 작업 전 반드시 pull
- **다음 할 일 (macOS)**: Phase 3 — `uv sync --extra analyze`로 allin1 실설치·구조/BPM 검증, CLAP 무드 스파이크
- **다음 할 일 (원격)**: 코드 진행 추출(MIDI 기반, chorder/music21), analyze 파이프라인 조립

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
- [ ] 코드 진행 추출: MIDI 기반(chorder/music21) → 오디오(chroma) 교차 검증
- [ ] allin1 구조/BPM (macOS 또는 GPU 환경에서 검증)
- [ ] 스파이크: CLAP 무드 태깅 품질 검증
- [ ] 마일스톤: 곡 1개 전체 분석 JSON

### Phase 4 — DB 저장
- [ ] 파이프라인 → SQLite 연결, Alembic 마이그레이션
- [ ] 마일스톤: 재생→분석→DB 자동 축적

### Phase 5 — 웹 UI
- [ ] 라이브러리 브라우저, 구조 타임라인, 코드 진행 뷰

### Phase 6 — 실시간 미리보기
- [ ] 5초 청크 스트리밍 + WebSocket 라이브 뷰

### 이후 — iOS 뷰어 앱
- [ ] SwiftUI + OpenAPI 생성 클라이언트

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

## 협업 메모 (세션 재개/서브에이전트용)

- 개발 환경이 Linux 원격 컨테이너일 수 있음 → **capture-macos와 muscriptor Metal 실행은 로컬 macOS에서만 검증 가능**. 그 외(core/api)는 어디서든 테스트 가능
- 무거운 ML 의존성(muscriptor, allin1, CLAP)은 core의 **optional extra**로 분리해 스캐폴딩 단계에서는 설치하지 않는다
- 커밋·푸시는 지정 브랜치(`claude/music-analysis-app-planning-rsfa6x`)로만
