# musicna — 음악 구조 분석·데이터베이스화 앱 계획

> 이 문서는 프로젝트의 마스터 플랜입니다. 진행 상황은 [PROGRESS.md](PROGRESS.md)에서 추적합니다.
> 방향이 바뀌면 이 문서를 갱신하고, 완료/진행 체크는 PROGRESS.md에만 기록합니다.
>
> **현황(2026-07-25)**: Phase 0~6 구현 완료. Phase 1~4는 macOS 실기기 마일스톤 검증 통과,
> Phase 5~6은 원격 구현·E2E 시뮬레이션 검증 완료(실기기 확인 대기). 남은 로드맵: iOS 뷰어 앱.

## Context

스트리밍 앱(Spotify, YouTube Music 등)의 재생 사운드를 시스템 오디오 스트림으로 캡처하여, 재생과 동시에 음악을 분석하고 그 결과(무드, 곡 구조, 코드 진행, 키/템포 등)를 개인 데이터베이스로 축적하는 앱을 만든다. 중간 단계로 [muscriptor](https://github.com/muscriptor/muscriptor)(Kyutai/Mirelo의 다중 악기 전사 모델, Python/PyTorch, Apple Metal 지원)를 사용해 오디오를 MIDI로 변환·저장하고, 이를 분석 정확도의 기반으로 삼는다.

**확정 사항**

- 플랫폼: **macOS 우선**, 이후 iOS (iOS는 타 앱 오디오 캡처가 불가하므로 "DB 뷰어/브라우저 앱"으로 접근)
- 분석 방식: **하이브리드** — 재생 중 실시간 미리보기(준실시간 MIDI/코드) + 곡 종료 후 전체 배치 재분석으로 DB 확정 저장
- DB: **로컬 SQLite**
- 용도: **개인 연구/취미** (muscriptor 가중치 CC BY-NC 제약 문제 없음)

**핵심 기술 판단 (사전 조사 결과)**

- MIDI만으로는 무드·구조 분석이 부족 → **오디오 + MIDI 하이브리드 분석**
- 구조 분석: [`allin1`](https://github.com/mir-aidj/all-in-one) — BPM/비트/다운비트/구간(intro·verse·chorus·bridge·outro) 추출, PyTorch, macOS 지원 명시, madmom 의존
- 무드 분석: Essentia-tensorflow는 macOS arm64 pip 휠 결함(MTG/essentia#1486) → **LAION CLAP zero-shot 태깅**(PyTorch)을 1차로, 검증 스파이크로 확정
- 코드 진행: MIDI 기반(`music21`/`chorder` 템플릿 매칭) + 오디오 기반(madmom `DeepChromaChordRecognitionProcessor`) 교차 검증 — madmom은 allin1 의존성으로 이미 설치됨

## 아키텍처

```
[Spotify / YT Music 재생]
        │  시스템 오디오
        ▼
① 캡처 계층 (Swift CLI helper, ScreenCaptureKit)
        │  PCM 48kHz → stdout 파이프
        ▼
② 세션 매니저 (Python)
   - 트랙 경계 감지: AppleScript 메타데이터(Spotify/Music) + 무음 감지 폴백
   - 트랙별 WAV 저장 (data/audio/)
        │
        ├──► ③a 실시간 파이프라인: 5초 청크 → muscriptor 스트리밍 → MIDI 이벤트/코드 미리보기 (WebSocket)
        │
        ▼ (곡 종료 시)
③b 배치 분석 파이프라인
   - muscriptor 전체 전사 → .mid 저장 (data/midi/)
   - allin1: BPM/비트/구간 구조
   - 코드 진행: MIDI + chroma 교차 검증
   - 키 추정: librosa/music21
   - 무드: CLAP zero-shot 태그 + energy/valence 특성
        ▼
④ SQLite (SQLAlchemy) ── ⑤ FastAPI + 웹 UI (라이브러리 브라우저, 실시간 뷰)
```

## 기술 스택

| 계층 | 선택 | 근거 |
|---|---|---|
| 캡처 | Swift CLI + ScreenCaptureKit | 드라이버 설치 불필요(화면 기록 권한만), PCM을 stdout으로 파이프. 폴백: BlackHole + sounddevice |
| 트랙 메타데이터 | AppleScript (Spotify/Apple Music) | 곡명·아티스트·재생 위치 제공. 브라우저 재생은 무음 감지 폴백 |
| 전사 | muscriptor (Python lib, Metal) | 5초 청크 스트리밍 → 실시간 미리보기 겸용 |
| 구조/비트 | allin1 (+ madmom) | 검증된 구간 라벨링, macOS 지원 |
| 코드 | music21 + chorder (MIDI) / madmom (오디오) | 교차 검증으로 정확도 확보 |
| 무드 | LAION CLAP zero-shot (1차 스파이크로 검증) | PyTorch라 Apple Silicon 문제 없음 |
| DB | SQLite + SQLAlchemy + Alembic | 개인용, 파일 하나, 추후 서버 이전 용이 |
| API/UI | FastAPI + WebSocket + 경량 웹 프론트(피아노롤/타임라인) | muscriptor 자체 웹 UI와 같은 패턴, iOS 앱이 추후 같은 API 사용 |
| 패키징 | uv (Python 3.11+), 모노레포 | 아래 "코어 분리" 구조 참조 |

## 코어 분리 및 iOS 확장 전략

muscriptor(PyTorch, 최대 1.4B)와 allin1은 iOS 기기에서 직접 실행이 비현실적이므로, iOS 확장은 "코어 이식"이 아닌 **"코어를 API 뒤로 격리 + iOS는 클라이언트"** 구조로 설계한다. 이를 위해 처음부터 다음 레이어로 분리한다:

```
musicna/
├── capture-macos/     # Swift CLI — macOS 전용, PCM 파이프 출력만 담당 (교체 가능)
├── core/              # 순수 Python 분석 엔진 — 플랫폼 독립
│   │                  #   입력: 오디오 파일 경로 / 출력: 분석 결과 (Pydantic 모델)
│   ├── transcribe/    #   muscriptor 래퍼 (WAV → MIDI)
│   ├── analyze/       #   구조·코드·키·무드 (WAV+MIDI → AnalysisResult)
│   └── store/         #   SQLAlchemy 모델 + 저장소 패턴
├── api/               # FastAPI — core를 REST/WebSocket으로 노출 (유일한 코어 진입점)
│   │                  #   Phase 7~: player.py(spotify_player 데몬 제어)·system.py(오케스트레이션)도 여기 위치
├── web/               # 웹 UI — api만 호출 (macOS 지식 없음)
├── tui/ (Phase 7~)    # 터미널 UI(Textual) — api만 호출
└── ios/, macos/ (추후)  # SwiftUI 앱 — api만 호출
```

`spotify_player`(Homebrew, librespot 기반)는 이 트리에 속하지 않는 외부 바이너리 의존성이다 — api가 서브프로세스로 구동·제어할 뿐, 저장소에 코드로 포함되지 않는다.

분리 원칙:

- **core는 macOS API를 일절 import하지 않는다** — 캡처·AppleScript·spotify_player 오케스트레이션은 capture-macos와 api(세션 매니저·player.py)에만 존재. core는 "오디오 파일 in → 구조화된 결과 out"의 순수 함수적 파이프라인이라 Linux CI에서도 그대로 테스트 가능
- **API 계약이 곧 클라이언트 경계** — 모든 응답 스키마를 Pydantic으로 정의하고 FastAPI의 OpenAPI 스펙 자동 생성 → 추후 iOS/macOS에서 Swift 클라이언트 코드 생성(swift-openapi-generator) 가능. 웹·TUI가 쓰는 API를 모든 클라이언트가 그대로 재사용
- **실시간 스트림도 동일 경계** — 실시간 MIDI/코드 미리보기는 WebSocket 이벤트 스키마(JSON)로 정의하므로 웹/TUI/iOS/macOS 어느 클라이언트든 구독 가능
- **오케스트레이션도 API 뒤로 격리** — 백그라운드 프로세스(spotify_player 데몬, 캡처 세션) 기동/종료는 `api/system.py`가 소유. 클라이언트별 특수 역할은 로컬 실행 시의 부트스트랩(예: TUI가 api 서버 자체를 띄우는 것)뿐, 오케스트레이션 로직 자체는 중복 구현하지 않는다
- **iOS·macOS에서의 역할**: Mac이 캡처·분석·재생 서버(홈 네트워크에서 FastAPI 노출), iOS/macOS 앱은 라이브러리 탐색·실시간 뷰어·재생 원격 제어. 장기적으로 iOS 단독 경량 분석이 필요해지면 basic-pitch 계열의 CoreML 변환을 검토(별도 프로젝트 수준, 본 계획 범위 외)

## DB 스키마 (초안)

- `tracks`: id, title, artist, album, source(spotify/ytmusic/…), duration, captured_at, audio_path, midi_path
- `analyses`: track_id, engine 버전, bpm, key, mode, time_signature, analyzed_at
- `sections`: analysis_id, label(verse/chorus/…), start_s, end_s
- `chords`: analysis_id, chord(예: Am7), start_s, end_s, source(midi/audio/merged), confidence
- `moods`: analysis_id, tag, score
- `midi_notes`(선택): 검색용 노트 이벤트 요약 (원본은 .mid 파일)

## 단계별 마일스톤

- **Phase 0 — 프로젝트 스캐폴딩**: 코어 분리 구조대로 모노레포 구성(`capture-macos/`, `core/`, `api/`, `web/`), uv 프로젝트, README에 아키텍처 문서화
- **Phase 1 — 캡처 + 트랙 분할**: Swift 캡처 헬퍼 → Python 세션 매니저가 트랙별 WAV + 메타데이터 JSON 저장. *마일스톤: Spotify 재생 시 곡 단위 WAV가 자동 저장됨*
- **Phase 2 — MIDI 변환**: muscriptor 통합(Metal), WAV → .mid 저장. *마일스톤: 캡처된 곡의 MIDI가 생성되고 피아노롤로 확인 가능*
- **Phase 3 — 배치 분석**: allin1 구조/BPM, 코드 진행(교차 검증), 키, CLAP 무드. 각 라이브러리 검증 스파이크 포함. *마일스톤: 곡 1개에 대한 전체 분석 JSON 출력*
- **Phase 4 — DB 저장**: SQLAlchemy 모델 + 파이프라인 연결. *마일스톤: 재생→분석→DB 자동 축적*
- **Phase 5 — 웹 UI**: 라이브러리 브라우저(곡 목록, 구조 타임라인, 코드 진행 뷰), 통계(무드 분포 등)
- **Phase 6 — 실시간 미리보기**: 5초 청크 muscriptor 스트리밍 + WebSocket으로 현재 재생곡의 MIDI/코드 라이브 표시 (하이브리드 완성)
- **Phase 7 — 재생 엔진·오케스트레이션** ✅ **완료(2026-07-26, 실기기 검증 통과)**: `spotify_player`(librespot 기반, daemon feature는 cargo 빌드 필요 — Homebrew 기본 배포판엔 없음) 데몬을 api가 서브프로세스로 구동·제어(`/player/*`), 오케스트레이션 엔드포인트(`/system/*`)로 데몬·세션 기동을 API화. "spotify" 소스 메타데이터 폴링을 AppleScript에서 spotify_player 상태 조회로 교체(Apple Music 소스는 무수정). 최소 TUI 셸(플레이어 패널·세션 상태). 설계: [docs/superpowers/specs/2026-07-26-tui-player-orchestration-design.md](superpowers/specs/2026-07-26-tui-player-orchestration-design.md), 구현 계획: [docs/superpowers/plans/2026-07-26-tui-player-orchestration.md](superpowers/plans/2026-07-26-tui-player-orchestration.md). *마일스톤: TUI에서 재생/일시정지/다음곡/볼륨 조작 시 실제 Spotify 재생이 반응하고, 기존 캡처·트랙 분할에 그대로 반영됨* — 상세는 [PROGRESS.md](PROGRESS.md) 참조
- **Phase 8 — TUI 기능 동등화**: 검색·플레이리스트(`/player/search`, `/player/playlists`) 추가, 기존 `/ws/live`·`/tracks`를 재사용해 실시간 분석 뷰(코드·피아노 롤)와 라이브러리 브라우저를 TUI에 추가. *마일스톤: 웹 UI로 할 수 있는 모든 열람 작업을 TUI에서도 수행 가능*
- **Phase 9 — macOS 네이티브 앱**: 웹·TUI와 동일하게 `api/`만 호출하는 독립 클라이언트. 같은 패턴(기능 동등화, 단계별 실기기 검증)을 따름
- **Phase 10 — iOS 앱**: `api/`만 호출하는 뷰어 겸 원격 제어 앱(SwiftUI). Mac이 캡처·분석·재생 서버 역할(iOS 샌드박스상 타 앱 오디오 캡처 불가하므로 캡처는 계속 Mac 담당). 웹·TUI·macOS 앱과 동일한 API 계약을 재사용하는 같은 패턴을 따름

모든 클라이언트(웹·TUI·macOS·iOS 앱)는 독립된 인터페이스이되 `api/`가 제공하는 기능은 동등하게 갖춘다 — 어느 하나에만 있는 기능을 만들지 않는다.

## 리스크 및 유의점

- **muscriptor 가중치 CC BY-NC** — 개인용이므로 OK, 단 상업 전환 시 대체 모델(basic-pitch 등) 필요
- **스트리밍 음원 캡처** — 사적 이용 범위로 한정, 공유·배포 금지 (README에 명시)
- **macOS 권한** — ScreenCaptureKit은 화면 기록 권한 필요; macOS 15.4+에서 MediaRemote 사적 API 제한 → 메타데이터는 AppleScript로 우회
- **Essentia arm64 휠 결함** — CLAP로 대체; Phase 3 시작 시 무드 태깅 품질 스파이크로 검증
- **1.4B 모델 + 실시간** — 실시간 미리보기는 small(103M) 모델, 배치 확정 분석은 large 모델로 이원화

## 검증 방법

1. **Phase별 스모크 테스트**: 짧은 저작권-프리 샘플 오디오(bundled fixture)로 캡처→MIDI→분석→DB 전 구간 pytest 통합 테스트
2. **수동 E2E**: Spotify에서 코드 진행이 알려진 곡(예: 캐논 변주) 재생 → DB의 코드/구조/키가 실제와 일치하는지 확인
3. **UI 확인**: 웹 UI에서 타임라인·피아노롤 렌더링 확인
4. 개발 환경이 Linux(원격)일 경우 캡처 계층은 macOS 실기기 테스트 필요 — 캡처 이외 파이프라인은 WAV 파일 입력으로 CI 테스트 가능
