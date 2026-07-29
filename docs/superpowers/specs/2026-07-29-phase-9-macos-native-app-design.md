# Phase 9 — macOS 네이티브 앱 설계

> 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.
> 웹·TUI와 동일 원칙 — `api/`만 호출하는 독립 클라이언트, Phase 8.5의 상시 중앙 api에 접속.

## 배경·목적

웹 UI(브라우저)와 TUI(터미널)가 이미 재생 제어·검색·플레이리스트·라이브러리 열람·실시간 분석 뷰를 전부 제공한다. 그럼에도 macOS 네이티브 앱을 별도로 만드는 이유는 두 가지다:

1. **가벼운 메뉴바 상시 제어** — 브라우저 탭이나 터미널 창을 열지 않아도 메뉴바에서 재생/일시정지·현재 곡·캡처 상태를 바로 확인·제어
2. **Phase 10(iOS) 코드 공유 디딤돌** — 네트워킹·모델 계층을 SwiftUI/AppKit에 의존하지 않는 순수 Swift 패키지로 만들어, 이후 iOS 앱이 그대로 재사용

**범위 밖으로 명시적으로 제외한 동기**: "웹의 canvas 피아노 롤보다 더 나은 네이티브 그래픽 감성 UI"는 이번 Phase의 목표가 아니다 — 메뉴바 앱은 가볍게 유지한다.

## 핵심 결정 사항 (브레인스토밍에서 확정)

- **형태**: 메뉴바 아이콘(`MenuBarExtra`, Dock 아이콘 없음) + 별도 크기조절 가능한 라이브러리 창. 하나의 팝오버에 다 욱여넣지 않는다(Spotify 데스크톱 앱과 유사한 2단 구조)
- **1차 기능 범위**: 재생 제어(재생/일시정지/다음곡/볼륨) + 세션 상태(캡처 중 여부) + 실시간 분석 뷰(현재 코드+짧은 히스토리, 텍스트만) + 라이브러리 목록(표, TUI `LibraryBrowserWidget`과 동일 컬럼). **검색·플레이리스트 재생은 이번 Phase 범위 밖**(TUI Phase 8에 이미 있음, 필요시 후속 Phase로)
- **라이브러리 상세(구조 타임라인·코드 진행 레인·무드 바)는 네이티브로 만들지 않는다** — 목록만 네이티브, 더 깊은 열람은 웹 UI가 계속 담당
- **코드 구조**: 로컬 Swift 패키지 `MusicnaKit`(네트워킹·모델·상태 스토어, 플랫폼 무관)을 Xcode 앱 타겟과 분리 — `core`/`api`를 macOS 전용 코드에서 분리해온 이 프로젝트의 기존 원칙과 동일. Phase 10 iOS 앱이 이 패키지를 그대로 재사용하는 것이 목적
- **프로젝트 구성**: Xcode 프로젝트(`.xcodeproj`)로 시작 — SwiftUI App 라이프사이클·메뉴바 씬·시스템 권한·앱 아이콘·Info.plist 관리가 표준적이고, `capture-macos`(순수 SPM CLI)와는 성격이 다름
- **오케스트레이션 없음** — Phase 8.5 이후의 TUI와 동일하게, 이 앱은 로컬 api를 부트스트랩하지 않고 이미 떠 있는 중앙 api(Mac mini, launchd)에 접속만 한다

## 아키텍처

```
macos-app/                          (신규 최상위 디렉터리)
    Musicna.xcodeproj
    Musicna/                        App 타겟 (SwiftUI, macOS 전용 UI만)
        MusicnaApp.swift            MenuBarExtra + WindowGroup("library") 씬 선언
        MenuBarView.swift           재생 제어·세션 상태·실시간 코드 + "라이브러리 열기"·"웹 UI 열기" 버튼
        LibraryWindowView.swift     트랙 목록 Table
        PreferencesView.swift       api 접속 주소 설정(간단한 텍스트 필드 1개)
        Assets.xcassets, Info.plist, Musicna.entitlements
    MusicnaKit/                     로컬 Swift 패키지 — 플랫폼 무관 로직 (Phase 10과 공유)
        Package.swift
        Sources/MusicnaKit/
            APIClient.swift         REST 호출 (health/player/system/tracks) — URLSession만 사용
            LiveEventClient.swift   WebSocket(/ws/live) 구독, 재연결 루프
            Models.swift            Codable 모델 (LiveEvent 판별 유니언, PlayerStatus, AnalysisResult 등)
            PlayerStatusStore.swift ObservableObject — 재생·세션 상태 폴링
            LiveAnalysisStore.swift ObservableObject — 현재 코드·히스토리·연결 상태
            LibraryStore.swift      ObservableObject — /tracks 목록, 손상 항목 개별 skip
        Tests/MusicnaKitTests/
            APIClientTests.swift        URLProtocol 스텁으로 요청 형태·응답 파싱 검증
            LiveAnalysisStoreTests.swift 가짜 이벤트 스트림으로 상태 전이 검증
```

`core/`의 "macOS API import 금지" 원칙과 대응되는 이 Phase만의 원칙: **`MusicnaKit`은 `SwiftUI`/`AppKit`을 import하지 않는다** — `URLSession`·`Foundation`(크로스플랫폼 코어 라이브러리)만 사용해, App 타겟(메뉴바·창 UI)에서 완전히 분리한다.

## 컴포넌트별 상세

### `MusicnaKit/APIClient.swift`
- `health() async -> Bool`, `playerStatus() async throws -> PlayerStatus?`, `playerPlay/Pause/Next/Previous() async throws`, `playerVolume(_ percent: Int) async throws`, `systemStatus() async throws -> SystemStatus`, `tracks() async throws -> [AnalysisResult]`
- `baseURL: URL`을 생성자 인자로 받음(기본값 `http://127.0.0.1:8000`, `UserDefaults`에 저장, `PreferencesView`에서 편집) — TUI의 `MUSICNA_API_URL`과 동일한 역할, Tailscale 주소로 교체 가능

### `MusicnaKit/LiveEventClient.swift`
- `URLSessionWebSocketTask` 기반, `/ws/live` 구독. `AsyncStream<LiveEvent>` 또는 콜백으로 이벤트 방출
- **재연결 규칙(Phase 8 TUI에서 배운 교훈을 그대로 적용)**: 정상 종료든 에러든 재연결 전 항상 고정 딜레이를 거친다 — 그렇지 않으면 즉시 재연결을 반복하는 바쁜 루프가 될 수 있다는 걸 `LiveAnalysisWidget` 구현 중 실측으로 확인한 바 있음(Phase 8 작업 로그 참조). 여기서는 처음부터 이 함정을 피해 설계한다

### `MusicnaKit/PlayerStatusStore.swift` / `LiveAnalysisStore.swift` / `LibraryStore.swift`
- `ObservableObject`, `@Published` 상태(TUI 위젯의 `refresh_status()`/`_render_state()`와 대응)
- `PlayerStatusStore`: 2~3초 주기 `Timer`로 `/player/status`+`/system/status` 폴링(TUI `PlayerPanel`/`SessionStatus`와 동일 주기)
- `LiveAnalysisStore`: `LiveEventClient` 구독, 현재 코드·최근 히스토리(최대 8개)·연결 상태 유지 — `LiveAnalysisWidget._handle_event()`와 동일 상태 전이 로직
- `LibraryStore`: 라이브러리 창이 열릴 때 + 수동 새로고침 시 `/tracks` 조회. **손상된 응답 항목은 개별 skip**(Phase 8 최종 리뷰에서 고친 KeyError 방지 패턴을 처음부터 반영 — `Decodable` 배열 통짜 디코딩 대신 항목별 `try?` 디코딩으로 하나가 깨져도 나머지는 표시)

### `Musicna/MenuBarView.swift`
- 현재 곡(제목·아티스트)·재생/일시정지/다음곡·볼륨 슬라이더, 세션 캡처 상태(녹음 중 점 표시), 실시간 코드(대형 텍스트)+짧은 히스토리
- "라이브러리 열기"(`openWindow(id: "library")`), "웹 UI 열기"(`NSWorkspace.shared.open(baseURL)`), "설정..."(PreferencesView) 버튼

### `Musicna/LibraryWindowView.swift`
- `Table`(제목·아티스트·BPM·키/모드·대표 무드) — TUI `LibraryBrowserWidget` 컬럼과 동일
- 행 선택 시 별도 상세 뷰는 만들지 않는다(범위 밖 — 아래 "범위 밖" 절 참조). 목록 열람만 제공하고 더 깊은 정보(구조 타임라인 등)는 웹 UI로 안내하지 않는다 — v1은 순수 목록 뷰

## 데이터 흐름·생명주기

1. **앱 기동**: Dock 아이콘 없이 메뉴바 아이콘만 표시. 저장된(또는 기본) api 주소로 `PlayerStatusStore`가 즉시 1회 조회 후 폴링 시작
2. **재생 명령**: 메뉴바 버튼 → `APIClient.playerPlay()` 등 → 성공 시 다음 폴링 사이클에 상태 반영(TUI와 동일하게 즉시 낙관적 갱신은 하지 않음 — 단순함 우선)
3. **실시간 뷰**: 메뉴바가 보이는 동안 `LiveEventClient`가 WebSocket 연결을 유지. 메뉴바 팝오버가 닫혀 있어도 앱 프로세스는 살아있으므로 구독은 계속 유지(다음에 열었을 때 최신 상태 즉시 표시)
4. **라이브러리 창**: 사용자가 "라이브러리 열기"를 누를 때만 `LibraryStore`가 fetch — 안 열려 있으면 불필요한 폴링 없음(TUI는 앱 실행 내내 위젯이 마운트돼 있어 5초 폴링하지만, 네이티브 창은 열려 있을 때만 폴링해 리소스 절약)

## 오류 처리

- api 연결 실패(어느 엔드포인트든) → 해당 스토어가 "연결 안 됨" 상태로 전환, 메뉴바에 인라인 표시(크래시 없음) — 웹/TUI와 동일 원칙
- `LibraryStore`의 개별 항목 디코딩 실패는 그 항목만 건너뛰고 나머지는 표시(위 컴포넌트 절 참조)
- WebSocket 끊김은 고정 딜레이 후 항상 재연결 시도(무한 재시도, busy loop 방지)

## 테스트

- `MusicnaKitTests`: `APIClient`는 `URLProtocol` 스텁으로 요청 경로·파라미터·응답 파싱 검증(TUI `httpx.MockTransport` 패턴과 동일 정신), `LiveAnalysisStore`는 가짜 이벤트 스트림 주입으로 상태 전이 검증. `MusicnaKit`이 `Foundation`만 쓰므로 `swift test`로 Xcode 없이도(이 프로젝트가 지금 원격 환경에서 진행 중이더라도) 통과 여부를 시도해볼 수 있다 — 단, 최종 확정은 macOS에서
- App 타겟(SwiftUI 뷰 렌더링, 메뉴바 동작, 실제 api·WebSocket 연동)은 기존 Phase들과 동일하게 **macOS 실기기 수동 검증**이 필요한 영역
- 마일스톤: 메뉴바에서 재생/일시정지·다음곡·볼륨 조작 시 실제 Spotify 재생이 반응하고, 캡처 상태·실시간 코드가 실제 재생과 함께 갱신되며, 라이브러리 창이 실제 캡처된 트랙을 표시

## 범위 밖 (이번 Phase에서 다루지 않음)

- 검색·플레이리스트 재생(TUI Phase 8에 이미 있음 — 필요해지면 후속 작업)
- 그래픽 피아노 롤(웹의 canvas 피아노 롤에 준하는 네이티브 렌더링) — 실시간 뷰는 텍스트(현재 코드+히스토리)만
- 트랙 상세 뷰(구조 타임라인·코드 진행 레인·무드 바) — 웹 UI가 계속 담당
- 앱 아이콘·브랜딩 폴리싱, 자동 업데이트(Sparkle 등), 코드 서명·배포(로컬 개발 빌드 전제)
- 여러 api 프로필 저장/전환 UI(설정은 단일 텍스트 필드로 충분, Tailscale 주소 수동 입력)
