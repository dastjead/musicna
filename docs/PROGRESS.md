# musicna — 진행 상황 (PROGRESS)

> 작업 재개·서브에이전트 협업용 단일 진실 소스(single source of truth).
> **규칙**: 작업 단계를 시작/완료할 때마다 이 파일을 갱신하고 즉시 커밋·푸시한다.
> 계획 자체는 [PLAN.md](PLAN.md) 참조. 계획 변경은 PLAN.md에, 실행 기록은 여기에.

## 현재 상태

- **현재 Phase**: **Phase 3·4 마일스톤 검증 통과** (chroma 교차 검증만 잔여) ∥ Phase 5 준비
- **작업 브랜치**: `claude/music-analysis-app-planning-rsfa6x`
- **분담**: `capture-macos/`·`api/session/`은 macOS 로컬 담당, 원격은 `core/`·문서 담당. 작업 전 반드시 pull
- **다음 할 일 (macOS)**: ① 캡처 레벨 정상 곡으로 트랙 추가 축적(002는 준무음 캡처였음) ② Phase 6 준비 — 스트리밍 전사 미리보기
- **다음 할 일 (원격)**: Phase 5 — 웹 UI (라이브러리 브라우저, 구조 타임라인, 코드 진행 뷰; /tracks API 사용). 코드 진행 chroma 교차 검증도 원격 구현 가능(librosa)

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
- [ ] 코드 진행 오디오(chroma) 교차 검증 — librosa/madmom 통합 시 (source=AUDIO/MERGED)
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
| 2026-07-25 | 원격: Phase 3 코드 진행 추출(MIDI 기반) + `analyze_track` 파이프라인 조립 | 30 tests passed. chorder 대신 music21 harmony 라벨링으로 base 의존성만으로 구현(합성 MIDI에서 C/F/G/C·Am7 정확). allin1/CLAP 미설치 시 자동 건너뜀 — macOS에서 extra 설치 후 실캡처 곡 검증 필요 |
| 2026-07-25 | 원격: Phase 4 구현 — 저장소 패턴, /tracks DB 조회, `musicna-analyze` 배치 CLI | 37 tests passed. E2E 마일스톤(실캡처→DB)은 macOS에서 `uv run musicna-analyze`로 검증 필요 |
| 2026-07-25 | **Phase 4 E2E 마일스톤 검증 통과**(macOS): `musicna-analyze` 실캡처 2트랙 → SQLite 축적·중복 건너뜀·/tracks 조회 확인. 견고성 수정 2건: 노트 없는 MIDI 키 추정 크래시, allin1 bpm=None 크래시 | 002 트랙은 캡처 레벨이 준무음(-51dB RMS)이라 large 전사가 0노트 — 파이프라인은 크래시 없이 강등 처리하도록 수정. 캡처 볼륨 주의 |
| 2026-07-25 | **Phase 3 allin1·CLAP 검증 완료**(macOS): allin1 설치 확립(madmom git 핀 + natten 0.15.1 소스 빌드 + torch 호환 셈), BPM/구간 검출 확인. CLAP 무드 스파이크 → `core/analyze/moods.py` 구현 | 43 tests passed. allin1 `multiprocess=False` 필수(스폰 교착), 부산물은 임시 디렉터리로. 상세는 아래 검증 기록 |

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

## 협업 메모 (세션 재개/서브에이전트용)

- 개발 환경이 Linux 원격 컨테이너일 수 있음 → **capture-macos와 muscriptor Metal 실행은 로컬 macOS에서만 검증 가능**. 그 외(core/api)는 어디서든 테스트 가능
- 무거운 ML 의존성(muscriptor, allin1, CLAP)은 core의 **optional extra**로 분리해 스캐폴딩 단계에서는 설치하지 않는다
- 커밋·푸시는 지정 브랜치(`claude/music-analysis-app-planning-rsfa6x`)로만
- **macOS 실행 요구사항** (상세는 위 검증 기록 참조): ① 터미널에 화면·시스템 오디오 기록 권한(TCC) ② HF 로그인 + muscriptor small/large 라이선스 동의 ③ arm64는 torch>=2.3 (transcribe extra가 강제함) ④ analyze extra는 natten 소스 빌드 순서 준수(위 Phase 3·4 기록의 3단계) ⑤ 캡처 시 재생 볼륨 확보 — 준무음 캡처는 전사·비트 검출이 빈 결과가 됨
- `data/`(audio/midi)는 git 미추적 — 검증 산출물은 이 머신 로컬에만 존재. 다른 머신에서 Phase 3 검증 시 캡처부터 다시 수행
