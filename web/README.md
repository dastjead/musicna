# web

musicna 웹 UI — api(FastAPI)만 호출하는 순수 클라이언트(바닐라 HTML/CSS/JS, 빌드 도구 없음). 추후 iOS 앱과 동일한 API 계약(OpenAPI)을 공유한다.

## 실행

api 서버가 저장소 루트에서 실행되면 자동으로 함께 서빙된다:

```sh
uv run uvicorn musicna_api.main:app --reload   # → http://127.0.0.1:8000/
```

다른 경로에서 실행 시 `MUSICNA_WEB` 환경변수로 이 디렉터리를 지정한다.

## 화면

- **라이브러리**: 트랙 목록 (키·BPM·대표 무드 배지), 캡처 시각 역순
- **곡 상세**: 스탯 타일(BPM/키/길이/코드 수), **곡 구조 타임라인**(구간 직접 라벨+범례), **코드 진행 레인**(호버 시 구간·신뢰도 툴팁) + 텍스트 진행 스트립, **무드 점수 바**
- 접근성: 구간/코드의 표 뷰(접이식), 라이트/다크 자동(`prefers-color-scheme`)
- 색상은 dataviz 검증 팔레트 사용 — 구간 라벨은 고정 색 매핑(verse=파랑, chorus=주황 등, 순환 없음)

## 실시간 뷰 (`live.html`)

`/ws/live` WebSocket을 구독해 현재 재생 중인 곡의 전사 이벤트를 라이브 표시한다:

- **현재 코드** 대형 표시 + 최근 코드 히스토리
- **피아노 롤** — 최근 30초 스크롤 canvas (울리는 중인 노트는 현재 시각까지 연장)
- 자동 재접속, 트랙 시작 시 초기화

이벤트 공급 (macOS):

```sh
uv run uvicorn musicna_api.main:app          # 터미널 1: api 서버
./capture-macos/.build/release/musicna-capture | uv run musicna-live   # 터미널 2
```
