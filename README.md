# musicna

스트리밍 앱(Spotify, YouTube Music 등)의 재생 사운드를 캡처하여, [muscriptor](https://github.com/muscriptor/muscriptor)로 MIDI 변환을 거친 뒤 **무드 · 곡 구조 · 코드 진행 · 키/템포**를 분석해 개인 데이터베이스(SQLite)로 축적하는 macOS 우선 앱.

> 📋 마스터 플랜: [docs/PLAN.md](docs/PLAN.md) · 진행 상황: [docs/PROGRESS.md](docs/PROGRESS.md)

## 아키텍처

```
[스트리밍 재생] → 캡처(Swift/ScreenCaptureKit) → 세션 매니저(트랙 분할)
    → muscriptor(오디오→MIDI) → 분석(구조·코드·키·무드) → SQLite → FastAPI → 웹/iOS UI
```

## 저장소 구조 (코어 분리)

| 디렉터리 | 역할 |
|---|---|
| `core/` | 순수 Python 분석 엔진 (플랫폼 독립, 파일 in → Pydantic 결과 out) |
| `api/` | FastAPI — core의 유일한 외부 진입점, 웹/iOS 공용 |
| `capture-macos/` | Swift 캡처 헬퍼 (macOS 전용) |
| `web/` | 웹 UI (api만 호출) |
| `docs/` | PLAN.md(계획) · PROGRESS.md(진행 상황) |
| `data/` | 캡처 오디오/MIDI/DB (git 미추적) |

## 개발

```bash
uv sync                      # 기본 의존성 (무거운 ML extra 제외)
uv run pytest                # 스모크 테스트
uv run uvicorn musicna_api.main:app --reload   # API 서버
```

ML 의존성은 Phase별 optional extra로 설치: `uv sync --extra transcribe --extra analyze --extra mood`

## 유의 사항

- muscriptor 모델 가중치는 **CC BY-NC 4.0 (비상업)** — 본 프로젝트는 개인 연구/취미 용도
- 캡처한 스트리밍 음원은 **사적 이용 범위로 한정**하며 공유·배포·커밋하지 않는다
