# capture-macos

macOS 시스템 오디오 캡처 헬퍼 (Swift CLI). **Phase 1에서 구현 — macOS 실기기 필요.**

## 역할

ScreenCaptureKit으로 시스템 오디오(또는 특정 앱 오디오)를 캡처하여 **48kHz PCM(float32, stereo)을 stdout으로 파이프**한다. 그 이상은 하지 않는다 — 트랙 분할, 저장, 메타데이터는 Python 세션 매니저(api 측) 담당.

```
musicna-capture [--app <bundle-id>] | python 세션 매니저
```

## 빌드·실행

```sh
cd capture-macos
swift build -c release          # → .build/release/musicna-capture
./.build/release/musicna-capture --app com.spotify.client > out.raw   # 특정 앱만
./.build/release/musicna-capture > out.raw                            # 시스템 오디오 전체
```

보통은 직접 실행하지 않고 세션 매니저가 subprocess로 띄운다:

```sh
uv run musicna-session --source spotify --out data/audio
```

## 요구 사항

- macOS 13+ (ScreenCaptureKit 오디오 캡처), 화면 기록 권한 필요
  - **최초 실행 전**: 시스템 설정 → 개인정보 보호 및 보안 → 화면·시스템 오디오 기록에서
    실행하는 터미널 앱을 허용해야 한다 (거부 시 "TCC를 거절함" 오류 후 즉시 종료)
- 폴백: [BlackHole](https://github.com/ExistentialAudio/BlackHole) 가상 오디오 장치 + Python `sounddevice`

## 메타데이터 (세션 매니저 측)

- Spotify / Apple Music: AppleScript로 곡명·아티스트·재생 위치 조회
- 브라우저(YouTube Music 등): 무음 감지 기반 트랙 경계 폴백
- 주의: macOS 15.4+에서 MediaRemote 사적 API가 제한되어 사용하지 않는다
