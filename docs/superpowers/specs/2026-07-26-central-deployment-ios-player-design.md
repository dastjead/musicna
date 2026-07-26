# musicna 중앙 배포(api/DB) + iOS 자체 재생·캡처 확장 설계

> Phase 8(TUI 연결 방식 변경)·Phase 9 준비(배포 인프라)·Phase 10(iOS 앱 범위 확정)에 걸쳐 영향을 주는 설계 스펙.
> 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.
> Phase 7·8 설계는 [2026-07-26-tui-player-orchestration-design.md](2026-07-26-tui-player-orchestration-design.md) 참조 — 이 문서는 그 후속.

## 배경·목적

Phase 0~7까지는 "api가 유일한 코어 진입점"이라는 *논리적* 중앙화만 다뤘고, 그 api를 실제로 어디서 얼마나 상시 띄워둘지 — 즉 **운영상의 중앙화** — 는 미정이었다. PLAN.md에는 "Mac이 홈 네트워크에서 FastAPI 노출"이라는 한 줄만 있었을 뿐, 상주 방식·원격 접근 범위·클라이언트별 재생·캡처 소유 방식은 결정된 바가 없었다.

Phase 8 착수 직전, 사용자가 이 부분을 먼저 정교화하고 싶다고 하여 브레인스토밍을 진행했다. 이 문서는 그 논의 과정에서 나온 결정과, 결정에 이르기까지 검토·기각한 대안들을 함께 기록한다(나중에 "왜 이렇게 했는지" 헷갈리지 않도록).

## 핵심 결정 사항

- **원격 접근**: Tailscale(WireGuard 메시 VPN) 채택. 공인 인터넷 미노출
- **상시 구동**: Mac mini는 24/7 홈서버로 운용, 자동 로그인 설정, `api`는 launchd LaunchAgent로 상주
- **단일 api 프로세스 원칙**: api 프로세스는 정확히 하나만 상시 구동되며 DB·캡처 세션·spotify_player 데몬을 독점 소유한다. TUI의 "자체 로컬 api 부트스트랩"(Phase 7 설계)은 폐기하고, TUI도 웹처럼 상시 api에 접속만 하는 클라이언트가 된다
- **재생·캡처 소유 모델**: Mac mini(spotify_player+ScreenCaptureKit)는 기존 그대로 유지. **iOS 앱도 자체 재생·캡처 기기가 된다**(신규) — `librespot-golang` + gomobile 임베딩, **포그라운드 전용**(백그라운드 상시 대기는 iOS 정책상 불가로 판단)
- **분석 파이프라인은 무수정**: 오디오가 Mac 로컬 subprocess에서 오든 iOS 네트워크 스트림에서 오든, Phase 3~6 분석 로직(muscriptor/allin1/CLAP/코드 진행/실시간 미리보기)은 그대로. 신규 "원격 오디오 인제스트" 엔드포인트만 입력 경로로 추가
- iOS는 Phase 6에서 이미 만든 `/ws/live` 이벤트 계약(LiveEvent)을 그대로 구독해 네이티브 실시간 시각화를 갖는다 — 단순 리모컨이 아니라 "재생하며 분석을 보는" 뷰어로서의 차별점을 갖도록 함

## 논의 과정 (결정에 이른 배경)

### 1. 원격 접근 방식 — Tailscale vs 공개 인터넷 노출 vs 수동 WireGuard

세 가지를 비교했다:

- **Tailscale(채택)**: 포트포워딩·공유기 설정 불필요, NAT 자동 통과. 가장 큰 이유는 **현재 api에 인증 시스템이 전혀 없다**는 점 — Tailscale의 "터널 안에 있음 = 내 기기임"이라는 네트워크 레벨 신뢰만으로 충분해서, 로그인/토큰 시스템을 새로 구현할 필요가 없어진다. 캡처 음원의 "사적 이용 한정" 성격과도 부합
- **Cloudflare Tunnel 등 공개 인터넷 노출(기각)**: 도메인·TLS 관리가 생기고, 무엇보다 API가 공개되므로 인증 시스템을 직접 구현해야 한다 — 개인 프로젝트 규모에 비해 보안 부담이 큼
- **수동 WireGuard(기각)**: Tailscale과 원리는 같지만 키 관리·NAT 설정을 직접 해야 해서, 순이득 없이 운영 부담만 늘어남

### 2. 상시 구동 여부

Mac mini(캡처·분석·재생 서버 역할)를 상시 켜둘 수 있는지가 원격 접근의 전제 조건이었다. 사용자가 "상시 켜둘 수 있음"을 확인 → launchd 상주 서비스 설계로 이어짐. 자동 로그인도 필요한데, ScreenCaptureKit이 로그인된 유저 세션을 요구하기 때문에(TCC 권한이 세션에 묶임) LaunchDaemon(root, 로그인 전 실행)이 아니라 **LaunchAgent**(유저 세션에 종속)가 맞고, 정전·재부팅 후 자동 복구를 위해 자동 로그인도 함께 설정하기로 함.

### 3. 단일 api 프로세스 vs 클라이언트별 자체 부팅

상시 중앙 api가 생기면 Phase 7에서 만든 TUI의 "자체 로컬 api 부트스트랩" 특례가 두 가지 문제를 만든다는 걸 확인했다: ① 웹과 다른 특수 취급이 불필요해짐 ② TUI가 별도 api 프로세스를 띄우면 같은 SQLite 파일에 동시 접근하는 프로세스가 두 개 생겨 동시성 리스크가 생긴다. → **TUI도 상시 api에 접속하도록 변경**하기로 결정, 자체 부팅 코드는 제거 대상.

### 4. 재생·캡처 소유 모델 — "DB만 중앙, 나머지는 앱마다?"

사용자가 처음 제안한 방향은 "DB만 중앙/단일로 두고 spotify_player·캡처는 앱마다 따로 두면 어떤가"였다. 이를 검토하며 다음을 확인했다:

- **iOS는 애초에 시스템 오디오 캡처가 불가능**하다(하기 어려운 게 아니라 API 자체가 없음) — Apple 샌드박스 모델상 다른 앱의 오디오 출력을 가로챌 방법이 없다. macOS의 ScreenCaptureKit에 대응하는 기능이 iOS엔 없음(PLAN.md에도 이미 이 제약이 "iOS는 뷰어 앱으로 접근"의 근거로 명시돼 있었음)
- **macOS는 원리상 다기기 분산이 가능**하다(Mac mini 외의 맥북 등에서도 캡처+spotify_player를 각각 띄우고 중앙 api로 오디오를 보내는 구조는 짤 수 있음) — 다만 그러면 무거운 ML 스택(muscriptor/allin1/CLAP, Phase 2·3에서 겪은 natten 빌드 이슈 등)을 기기마다 설치해야 하는 부담이 생긴다. 사용자에게 확인한 결과 **실제로는 Mac mini 하나로 충분**하다고 하여, 이 다기기 macOS 분산 시나리오는 설계에서 제외

### 5. iOS 자체 재생 — "다른 앱을 가로채는 게 아니라, 우리 앱 자체가 재생 기기면?"

여기서 사용자가 핵심 통찰을 제시했다: Phase 7에서 이미 "데스크톱 앱 원격제어"가 아니라 "musicna 자신이 spotify_player로 Spotify Connect 기기가 된다"는 자체 스트리밍 모델을 선택했는데, **같은 원리를 iOS에도 적용하면 시스템 캡처 권한 문제 자체가 사라진다** — 디코딩된 PCM이 애초에 우리 앱 프로세스 안에서 만들어지므로, 재생 직전 버퍼를 그냥 같이 흘려보내면 되고 "다른 앱 가로채기"가 아니다.

이 통찰의 타당성을 웹 조사로 검증했다(2026-07 기준):

- **오디오 출력**: `cpal`(librespot 재생 백엔드가 의존하는 Rust 오디오 I/O 크레이트)이 실제 iOS 지원을 갖고 있음 — CoreAudio 호스트에 iOS 지원을 추가한 PR([RustAudio/cpal#485](https://github.com/RustAudio/cpal/pull/485))이 머지돼 있고 `ios-feedback` 예제 프로젝트까지 존재. AVAudioSession 연동도 검증된 패턴 → 오디오 재생 자체는 막힘 없음
- **Spotify Connect 클라이언트 임베딩**: Rust `librespot` 직접 iOS 포팅은 메인테이너가 지원 대상으로 문서화하지 않은 비공식 영역. 그러나 **Go 포트 `librespot-golang`은 정확히 이 용도의 `librespotmobile` 패키지를 이미 제공**한다 — Gomobile로 iOS/Android 바인딩을 만드는 `micro-controller`(Connect 기기로 보이기)·`micro-client`(실제 재생) 예제가 이미 존재. 즉 "아무도 안 해본 일"이 아니라 참고 가능한 실제 레퍼런스가 있음 — Rust 직접 포팅보다 훨씬 리스크가 낮은 경로
- **진짜 걸림돌 — iOS 백그라운드 정책**: Spotify Connect 기기로 "재생 중이 아닐 때도 계속 검색 가능한 상태로 대기"하는 건 iOS의 정식 백그라운드 실행 사유(오디오 재생 중·VoIP·위치 등)에 해당하지 않는다. 실제로 **공식 Spotify 앱조차** 백그라운드에서 Connect 연결이 끊기거나 재생이 멈춘다는 커뮤니티 불만이 다수 검색됨(iOS 앱 자체의 백그라운드 안정성 문제가 잘 알려진 이슈). 이 때문에 이 기능은 **앱이 포그라운드로 열려 있는 동안에만** 안정적으로 동작할 가능성이 높다고 판단

사용자가 이 조건(포그라운드 전용)을 감안하고도 Phase 10을 "iOS 자체 재생+캡처"로 확정하기로 결정. 추가로 "포그라운드 전용이라는 제약을 오히려 장점으로 살려서, 재생 중 실시간 분석·시각화를 더해 흥미로운 음악 데이터 뷰어로 만들자"는 방향을 제시 — 이는 Phase 6에서 이미 구축한 `/ws/live` 실시간 이벤트 인프라를 그대로 재사용하면 되므로 신규 분석 로직 없이 달성 가능하다고 판단.

## 아키텍처

```
[Mac mini, 자동 로그인, 상시 전원]
  ├─ launchd LaunchAgent
  │    └─ uvicorn (musicna_api.main:app)  ← 유일한 상시 프로세스, DB·캡처·세션 오케스트레이션 독점 소유
  ├─ Tailscale (WireGuard 메시)
  │    └─ MagicDNS 호스트네임 (예: mac-mini.tailXXXX.ts.net)
  ├─ 기존 캡처 경로 (무수정): musicna-session | capture-macos → WAV → data/audio/
  └─ data/musicna.db (SQLite, 이 프로세스만 접근)

[집 안/밖, Tailscale 가입 기기]
  ├─ 웹 브라우저 → http://mac-mini.tailXXXX.ts.net:8000/
  ├─ TUI → 같은 주소로 접속 (더 이상 자체 부팅 안 함)
  ├─ macOS 앱(Phase 9) → 같은 주소, 뷰어+원격제어
  └─ iOS 앱(Phase 10, 신규) → 같은 주소
       ├─ librespot-golang(gomobile) 임베딩 → 자체 Spotify Connect 기기 (포그라운드 전용)
       ├─ 디코딩 PCM을 재생과 동시에 신규 "원격 오디오 인제스트" 엔드포인트로 스트리밍
       ├─ librespot 세션의 트랙 전환 이벤트를 직접 API에 통지 (트랙 경계 신호)
       └─ /ws/live 구독 → 네이티브 SwiftUI 실시간 코드·피아노 롤 렌더
```

## 컴포넌트별 상세

### 배포 인프라 (신규)

- Tailscale 설치(Mac mini + 각 클라이언트 기기), MagicDNS로 안정적 호스트네임 확보
- `launchd` LaunchAgent plist: `uvicorn musicna_api.main:app` 기동, `KeepAlive`로 크래시 시 재시작, 로그인 시 자동 시작
- 자동 로그인 설정(시스템 환경설정) — 정전·재부팅 복구용
- 인증 계층은 이번 단계에서 추가하지 않음(Tailscale의 네트워크 레벨 신뢰로 충분하다고 판단) — 추후 필요 시 API 키 레이어를 얹을 여지만 남겨둠

### TUI 연결 방식 변경 (`tui/src/musicna_tui/app.py`)

- 기존: `GET /health` 실패 시 로컬 `uvicorn` 서브프로세스 부트스트랩 → 이 로직 제거
- 변경: 설정된 API 베이스 URL(기본값 `localhost`, Tailscale 호스트네임으로 override 가능)에 접속만 함 — 웹과 동일한 "순수 클라이언트" 위치로 격하

### 원격 오디오 인제스트 (신규 API)

- Mac 로컬 캡처는 subprocess가 stdout을 파이프하지만, iOS는 네트워크 너머에 있으므로 청크 업로드용 엔드포인트가 필요
- 수신한 PCM 청크를 ① 기존 `musicna-live` 파이프라인(muscriptor-small → `LiveChordTracker` → `LiveBroadcaster`)에 그대로 흘려 실시간 미리보기 제공 ② 트랙 종료 시 청크를 이어붙여 서버 쪽에서 WAV로 완성 저장 → 기존 배치 분석(`musicna-analyze`)이 그대로 집어감
- **Phase 3~6 분석 로직은 무수정** — 입력 소스가 "로컬 subprocess pipe" 외에 "네트워크 청크 스트림"으로 하나 늘어나는 것뿐
- 트랙 경계: iOS는 librespot 세션이 트랙 전환을 직접 알기 때문에, Mac의 AppleScript 폴링/무음감지 추론보다 **더 정확한 track_started/track_ended 신호**를 API에 바로 통지할 수 있음(부수적 이점)

### iOS 앱 (Phase 10 범위 확정)

- `librespot-golang` + gomobile 바인딩 임베딩 → 앱이 열려 있는 동안 자체 Spotify Connect 기기로 동작(**포그라운드 전용**, 백그라운드 상주는 지원하지 않음 — 앱 설명에 명시)
- 재생과 동시에 디코딩 PCM을 원격 인제스트 엔드포인트로 스트리밍
- `/ws/live` 구독 → SwiftUI 네이티브 실시간 코드·피아노 롤(웹 `live.html`과 동일 이벤트 계약, `core/models.py`의 `LiveEvent`를 그대로 재사용 — 신규 정의 불필요)
- 기존 라이브러리 브라우저·원격 재생제어 기능(뷰어 역할)도 그대로 유지

## 리스크·미검증 영역

- **가장 큰 미검증 영역**: `librespot-golang`을 실제 iOS 앱에 임베딩해서 진짜 Spotify Connect 기기로 인식되는지 자체가 이 프로젝트에서 아직 아무도 해본 적 없는 스파이크 — Phase 10 착수 시 "곡 재생 + Connect 기기로 인식" 여부부터 최소 스파이크로 검증 필요
- **신규 툴체인**: Go + gomobile 추가(기존 Swift+Python+외부 Rust 바이너리 구성에 하나 더) — 이 프로젝트에 처음 등장하는 언어
- **포그라운드 전용 제약**: 사용자에게 명확히 안내 필요("앱을 열어둔 동안만 재생·캡처됨")
- **동시성**: 단일 api 프로세스 원칙으로 SQLite 동시 접근 리스크는 해소되지만, 원격 오디오 인제스트가 실시간 미리보기(muscriptor-small)와 배치 분석(large) 두 파이프라인을 동시에 태우게 되므로 Mac 로컬 캡처와 iOS 캡처가 겹치는 경우(동시에 두 트랙이 들어오는 경우)의 처리는 Phase 10 계획 단계에서 별도 검토 필요
- Tailscale 원격 인제스트 엔드포인트는 공인 인터넷에 노출하지 않음(터널 안에서만 접근 가능)을 유지

## 범위 밖 / 향후 과제

- iOS 백그라운드 상주(항상 선택 가능한 Connect 기기)는 이번 설계에서 명시적으로 배제 — iOS 정책상 신뢰할 수 없다고 판단했기 때문. 필요해지면 별도 스파이크로 재검토
- macOS 다기기 분산 캡처(Mac mini 외 맥북 등)는 현재 불필요하다고 확인되어 설계에서 제외 — 필요해지면 "원격 오디오 인제스트"를 macOS 클라이언트에도 재사용하는 방식으로 확장 가능(같은 엔드포인트를 iOS·타 macOS가 공유)
- API 인증 레이어(Tailscale 신뢰 대신/추가로 API 키 등)는 이번 단계 범위 밖, 추후 필요시 도입
