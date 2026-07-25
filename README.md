# musicna

스트리밍 앱(Spotify, YouTube Music 등)의 재생 사운드를 캡처하여, [muscriptor](https://github.com/muscriptor/muscriptor)로 MIDI 변환을 거친 뒤 **무드 · 곡 구조 · 코드 진행 · 키/템포**를 분석해 개인 데이터베이스(SQLite)로 축적하는 macOS 우선 앱.

> 📋 마스터 플랜: [docs/PLAN.md](docs/PLAN.md) · 진행 상황: [docs/PROGRESS.md](docs/PROGRESS.md)
> Phase 0~6 구현 완료 — 캡처→전사→분석→DB→웹 UI→실시간 미리보기 전 구간 동작

## 아키텍처

```
[스트리밍 재생] → 캡처(Swift/ScreenCaptureKit) → 세션 매니저(트랙 분할)
    → muscriptor(오디오→MIDI) → 분석(구조·코드·키·무드) → SQLite → FastAPI → 웹/iOS UI
                └→ 실시간: 5초 청크 전사 → WebSocket → 라이브 뷰 (코드·피아노 롤)
```

## 저장소 구조 (코어 분리)

| 디렉터리 | 역할 |
|---|---|
| `core/` | 순수 Python 분석 엔진 (플랫폼 독립, 파일 in → Pydantic 결과 out) |
| `api/` | FastAPI — core의 유일한 외부 진입점, 웹/iOS 공용. 세션 매니저·배치·실시간 CLI 포함 |
| `capture-macos/` | Swift 캡처 헬퍼 (macOS 전용, ScreenCaptureKit → PCM stdout) |
| `web/` | 웹 UI (api만 호출) — 라이브러리·곡 상세·실시간 뷰 |
| `docs/` | PLAN.md(계획) · PROGRESS.md(진행 상황) |
| `data/` | 캡처 오디오/MIDI/DB (git 미추적) |

## 사용법 (macOS)

최초 1회: 화면 기록 권한 허용, HuggingFace 로그인 + muscriptor 가중치 라이선스 동의
(상세 절차는 [docs/PROGRESS.md](docs/PROGRESS.md)의 "실기기 검증 상세 기록" 참조)

```sh
uv sync --extra transcribe --extra analyze --extra mood   # ML 스택 포함 설치
cd capture-macos && swift build -c release && cd ..       # 캡처 헬퍼 빌드

# ① 수집: Spotify/Apple Music 재생 중 곡 단위 WAV+메타데이터 자동 저장
uv run musicna-session --source spotify

# ② 분석: 전사(MIDI) → 구조·코드·키·무드 → SQLite 축적
uv run musicna-analyze

# ③ 열람: 웹 UI (라이브러리, 구조 타임라인, 코드 진행, 무드)
uv run uvicorn musicna_api.main:app        # → http://127.0.0.1:8000/

# ④ 실시간 미리보기: 재생과 동시에 코드·피아노 롤 표시
./capture-macos/.build/release/musicna-capture | uv run musicna-live
#   → http://127.0.0.1:8000/live.html
```

## 개발 (모든 플랫폼)

core/api는 플랫폼 독립 — ML extra 없이도 전체 테스트가 Linux에서 통과한다:

```sh
uv sync            # 기본+dev 의존성 (무거운 ML extra 제외)
uv run pytest      # 전체 테스트
```

## 유의 사항

- muscriptor 모델 가중치는 **CC BY-NC 4.0 (비상업)** — 본 프로젝트는 개인 연구/취미 용도
- 캡처한 스트리밍 음원과 파생물(MIDI 등)은 **사적 이용 범위로 한정**하며 공유·배포·커밋하지 않는다
