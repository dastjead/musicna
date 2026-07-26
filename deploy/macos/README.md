# musicna api — launchd 운영 매뉴얼

`musicna_api.main:app`(uvicorn)을 Mac mini에서 launchd `LaunchAgent`로 상시 구동시키기 위한 설치·운영 가이드. Phase 8.5(중앙 배포 인프라) 설계 문서는 [docs/superpowers/specs/2026-07-26-central-deployment-ios-player-design.md](../../docs/superpowers/specs/2026-07-26-central-deployment-ios-player-design.md) 참조.

이 디렉터리의 두 파일:
- `com.musicna.api.plist` — launchd에 등록할 서비스 정의(템플릿, `__REPO_ROOT__`/`__HOME__` 플레이스홀더 포함)
- `install.sh` — 위 템플릿을 실제 경로로 치환해 `~/Library/LaunchAgents/`에 설치하고 등록

## 사전 조건

- 저장소가 클론돼 있고 `uv sync --all-packages --extra transcribe --extra analyze --extra mood`가 최소 1회 완료된 상태(ML 스택 포함)
- Mac mini 자동 로그인 설정 권장(재부팅 후에도 서비스가 자동 복구되려면 로그인된 유저 세션이 필요 — ScreenCaptureKit·spotify_player 모두 로그인 세션 종속)
- 포트 8000이 다른 프로세스에 점유돼 있지 않을 것

## 설치

```bash
cd /path/to/musicna   # 저장소 루트
./deploy/macos/install.sh
```

내부 동작:
1. `com.musicna.api.plist`의 `__REPO_ROOT__`/`__HOME__`을 실제 경로로 치환해 `~/Library/LaunchAgents/com.musicna.api.plist`에 복사
2. `launchctl unload`(이미 등록돼 있으면 정리) → `launchctl load -w`(등록 + 부팅/로그인 시 자동 시작 플래그)

성공 시 `설치 완료: ~/Library/LaunchAgents/com.musicna.api.plist` 출력.

재설치(코드 변경 후 plist 자체를 다시 반영하고 싶을 때)도 그냥 같은 명령을 다시 실행하면 된다 — `unload || true` 덕분에 멱등.

## 상태 확인

```bash
# 등록 여부·PID·마지막 종료 코드
launchctl list | grep com.musicna.api
# 예: PID   상태코드   com.musicna.api  (상태코드가 0이 아니면 비정상 종료 — 아래 로그 확인)

# 더 상세한 정보(최근 실행 시각, 스케줄 등)
launchctl print gui/$(id -u)/com.musicna.api

# 실제 응답 확인
curl http://127.0.0.1:8000/health
# {"status":"ok"} 기대
```

`launchctl list`의 상태코드가 음수(예: `-9`, `-15`)면 크래시 후 `KeepAlive`로 재시작을 시도 중이라는 뜻 — 로그를 확인한다.

## 로그

```bash
tail -f ~/Library/Logs/musicna-api.log        # stdout(uvicorn 접근 로그 등)
tail -f ~/Library/Logs/musicna-api.error.log  # stderr(트레이스백 등 에러)
```

## 재시작

```bash
launchctl kickstart -k gui/$(id -u)/com.musicna.api
```

(`-k`는 이미 떠 있으면 강제로 죽이고 재시작. plist 자체를 수정했다면 `kickstart`가 아니라 위 "설치" 절차를 다시 실행해야 변경사항이 반영된다 — `kickstart`는 이미 로드된 정의를 재시작할 뿐, 파일을 다시 읽지 않는다.)

## 중지

일시적으로만 멈추고 싶을 때(재부팅하면 다시 자동 시작됨):

```bash
launchctl unload ~/Library/LaunchAgents/com.musicna.api.plist
```

다시 켜려면:

```bash
launchctl load -w ~/Library/LaunchAgents/com.musicna.api.plist
```

## 완전 제거(자동 시작까지 해제)

```bash
launchctl unload ~/Library/LaunchAgents/com.musicna.api.plist
rm ~/Library/LaunchAgents/com.musicna.api.plist
```

이후 `./deploy/macos/install.sh`를 다시 실행하면 재설치된다.

## 트러블슈팅

- **`launchctl list`에 안 보임 / 상태코드가 계속 음수**: `~/Library/Logs/musicna-api.error.log` 확인. 흔한 원인:
  - `uv: command not found` — plist는 `/bin/zsh -lc "cd __REPO_ROOT__ && uv run ..."`로 실행되는데, `-l`(로그인 셸)이라 `~/.zshrc`까지 읽으므로 대화형 터미널에서 되던 PATH 설정(`export PATH="$HOME/.cargo/bin:$PATH"` 등, PROGRESS.md의 spotify_player 설치 절차 참조)은 보통 그대로 적용된다. 그래도 안 되면 `.zshrc`에 해당 PATH가 실제로 있는지, 혹은 `.zprofile`에만 있고 `.zshrc`엔 없는 건 아닌지 확인
  - `ModuleNotFoundError` 계열 — `uv sync`가 ML extras 없이 실행돼 스택이 빠져있는 경우(PROGRESS.md "환경 이슈" 절 참조). `uv sync --all-packages --extra transcribe --extra analyze --extra mood`로 복구 후 `launchctl kickstart -k gui/$(id -u)/com.musicna.api`
  - 포트 8000 점유 — `lsof -i :8000`으로 점유 프로세스 확인 후 종료
- **`curl http://127.0.0.1:8000/health`는 되는데 Tailscale/LAN에서 접속 안 됨**: plist의 uvicorn 커맨드에 `--host 0.0.0.0`이 있는지 확인(기본값 127.0.0.1로는 외부 인터페이스에서 응답 안 함). 그래도 안 되면 홈 라우터가 8000번을 외부로 포트포워딩하고 있진 않은지(있으면 안 됨 — 보안 문제) 확인하고, macOS 방화벽(시스템 설정 → 네트워크 → 방화벽)이 `uv`/Python 프로세스의 수신 연결을 막고 있지 않은지 확인
- **재부팅 후 서비스가 안 살아남음**: 자동 로그인이 설정돼 있는지 확인(로그인 전에는 유저 LaunchAgent가 실행되지 않는다 — 시스템 전체에 적용되는 LaunchDaemon이 아니라 이 유저 계정에 종속된 LaunchAgent이기 때문). 자동 로그인 후에도 안 되면 `launchctl list | grep com.musicna.api`로 애초에 등록이 살아있는지부터 확인(수동으로 `rm`한 적 없는지)
- **캡처(`/system/start`)가 실패함**: 이건 launchd 자체의 문제가 아니라 화면 기록 권한(TCC)·spotify_player 데몬·오디오 출력 장치 문제일 수 있음 — [docs/PROGRESS.md](../../docs/PROGRESS.md)의 Phase 7 검증 기록·"주의" 절 참조(HDMI 등 볼륨 API 미지원 출력 장치는 캡처가 조용히 무음이 됨)

## 원격 접근 (Tailscale)

집 밖에서도 이 api에 접속하려면 Mac mini와 클라이언트 기기(iPhone 등)가 같은 Tailscale 계정의 tailnet에 가입돼 있어야 한다. 공인 인터넷에는 아무것도 노출하지 않는다 — Tailscale 터널 안에서만 접근 가능.

### 설치·확인 (Mac mini)

```bash
brew install --cask tailscale
```

Tailscale.app 실행 → 계정 로그인 → 상태 확인:

```bash
# CLI가 PATH에 없으면 앱 번들 안의 바이너리를 직접 호출한다
/Applications/Tailscale.app/Contents/MacOS/tailscale status
/Applications/Tailscale.app/Contents/MacOS/tailscale ip -4
```

`tailscale status`에 Mac mini 자신의 디바이스명(예: `js-m4-mini`)과 tailnet IP(`100.x.x.x`)가 나오면 정상. 이 IP 또는 `<디바이스명>.<tailnet>.ts.net` 호스트네임이 원격 클라이언트의 접속 주소가 된다.

MagicDNS(호스트네임 해석)는 https://login.tailscale.com/admin/dns 에서 켜져 있는지 확인(기본 활성화).

### 클라이언트 기기 가입 (iPhone 등)

1. 해당 기기에 Tailscale 앱 설치, 같은 계정으로 로그인
2. **로그인만으로는 부족하다** — iOS는 로그인 후 시스템이 "VPN 구성 추가" 승인을 요청하는데, 이걸 놓치거나 앱을 바로 닫으면 로그인은 됐지만 실제 VPN 연결은 꺼진 채로 남는다(겉으로는 문제없어 보이지만 tailnet 트래픽이 전혀 안 감)
3. 기기의 Tailscale 앱에서 상단 토글이 켜져 있고 "Connected"로 표시되는지 반드시 확인. iOS 설정 → VPN 및 기기 관리에서도 Tailscale 프로필이 활성 상태인지 확인 가능
4. Mac mini에서 `tailscale status`를 다시 실행해 해당 기기가 `offline`이 아니라 `active`로 뜨는지로 최종 확인

**실기기에서 실제로 겪은 문제**: iPhone을 tailnet에 가입시켰다고 생각했지만 `tailscale status`에 137일째 `offline`으로 표시됨 — 원인은 로그인만 하고 VPN 토글이 꺼져 있었던 것. 토글을 켜자 즉시 `active`로 전환되고 원격 접속이 성공했다. **"로그인 = 연결"이 아니다**를 기억할 것.

### 원격 접속 확인

클라이언트 기기(가능하면 집 wifi가 아닌 모바일 데이터로 전환)에서:

```
http://<mac-mini-hostname>.<tailnet>.ts.net:8000/health
```

`{"status":"ok"}`가 나오면 성공. 안 되면 먼저 호스트명 대신 `tailscale ip -4`로 얻은 IP로 직접 시도해 DNS 문제인지 네트워크 문제인지 분리한다.

## 참고

- 전체 아키텍처·설계 배경은 [docs/superpowers/specs/2026-07-26-central-deployment-ios-player-design.md](../../docs/superpowers/specs/2026-07-26-central-deployment-ios-player-design.md), 구현 계획은 [docs/superpowers/plans/2026-07-26-phase-8-5-central-deployment.md](../../docs/superpowers/plans/2026-07-26-phase-8-5-central-deployment.md) 참조
