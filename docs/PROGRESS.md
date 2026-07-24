# musicna — 진행 상황 (PROGRESS)

> 작업 재개·서브에이전트 협업용 단일 진실 소스(single source of truth).
> **규칙**: 작업 단계를 시작/완료할 때마다 이 파일을 갱신하고 즉시 커밋·푸시한다.
> 계획 자체는 [PLAN.md](PLAN.md) 참조. 계획 변경은 PLAN.md에, 실행 기록은 여기에.

## 현재 상태

- **현재 Phase**: Phase 0 완료 → Phase 1 (macOS 캡처 + 트랙 분할) 대기
- **작업 브랜치**: `claude/music-analysis-app-planning-rsfa6x`
- **다음 할 일**: Phase 1은 macOS 실기기 필요 (Swift 캡처 헬퍼). Linux 환경에서는 Phase 2~3 준비(muscriptor/allin1 패키지명·설치 검증, WAV 파일 입력 파이프라인)를 먼저 진행 가능

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
- [ ] Swift 캡처 헬퍼 (ScreenCaptureKit → PCM stdout)
- [ ] Python 세션 매니저: PCM 수신 → 트랙별 WAV 저장
- [ ] AppleScript 메타데이터 (Spotify/Apple Music) + 무음 감지 폴백
- [ ] 마일스톤: Spotify 재생 시 곡 단위 WAV 자동 저장

### Phase 2 — MIDI 변환
- [ ] muscriptor 통합 (core/transcribe), WAV → .mid
- [ ] 마일스톤: 피아노롤로 MIDI 확인

### Phase 3 — 배치 분석
- [ ] 스파이크: CLAP 무드 태깅 품질 검증
- [ ] allin1 구조/BPM, 코드 진행(MIDI+오디오 교차), 키 추정
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
| 2026-07-24 | Phase 0 완료: uv 워크스페이스, core(모델·DB·스텁), api(FastAPI), 문서·테스트 | ML 의존성은 optional extra로만 선언 — **패키지명 미검증**, Phase 2/3 착수 시 확인 필요 |

## 협업 메모 (세션 재개/서브에이전트용)

- 개발 환경이 Linux 원격 컨테이너일 수 있음 → **capture-macos와 muscriptor Metal 실행은 로컬 macOS에서만 검증 가능**. 그 외(core/api)는 어디서든 테스트 가능
- 무거운 ML 의존성(muscriptor, allin1, CLAP)은 core의 **optional extra**로 분리해 스캐폴딩 단계에서는 설치하지 않는다
- 커밋·푸시는 지정 브랜치(`claude/music-analysis-app-planning-rsfa6x`)로만
