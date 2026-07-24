# musicna — 에이전트 작업 지침

스트리밍 재생 사운드를 캡처해 muscriptor로 MIDI 변환 후 무드·구조·코드 진행을 분석하여 SQLite에 축적하는 macOS 우선 앱.

## 필수 워크플로

1. **작업 시작 전** `docs/PLAN.md`(마스터 플랜)와 `docs/PROGRESS.md`(진행 상황)를 읽는다.
2. 작업 단계를 시작/완료할 때마다 `docs/PROGRESS.md`의 체크리스트·작업 로그를 갱신한다. 계획이 바뀌면 `docs/PLAN.md`를 갱신한다.
3. 의미 있는 단위마다 커밋하고 원격에 푸시하여 협업 상태를 최신으로 유지한다.

## 구조 (코어 분리 원칙)

- `core/` — 순수 Python 분석 엔진. **macOS API import 금지**, 파일 in → Pydantic 결과 out. Linux에서도 테스트 가능해야 함
- `api/` — FastAPI. core의 유일한 외부 진입점 (웹/iOS 클라이언트 공용)
- `capture-macos/` — Swift 캡처 헬퍼 (macOS 전용 코드는 여기와 api 측 세션 매니저에만)
- `web/` — 웹 UI (api만 호출)
- `data/` — 캡처 오디오/MIDI/SQLite (git 미추적)

## 규칙

- Python은 uv 워크스페이스 (Python 3.11+). 무거운 ML 의존성은 optional extra로 분리
- muscriptor 가중치는 CC BY-NC — 비상업 용도 유지. 캡처 음원은 사적 이용 한정, 저장소에 커밋 금지
- 푸시는 현재 지정된 작업 브랜치로만
