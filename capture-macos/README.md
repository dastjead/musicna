# capture-macos

macOS 시스템 오디오 캡처 헬퍼 (Swift CLI). **Phase 1에서 구현 — macOS 실기기 필요.**

## 역할

ScreenCaptureKit으로 시스템 오디오(또는 특정 앱 오디오)를 캡처하여 **48kHz PCM(float32, stereo)을 stdout으로 파이프**한다. 그 이상은 하지 않는다 — 트랙 분할, 저장, 메타데이터는 Python 세션 매니저(api 측) 담당.

```
musicna-capture [--app <bundle-id>] | python 세션 매니저
```

## 요구 사항

- macOS 13+ (ScreenCaptureKit 오디오 캡처), 화면 기록 권한 필요
- 폴백: [BlackHole](https://github.com/ExistentialAudio/BlackHole) 가상 오디오 장치 + Python `sounddevice`

## 메타데이터 (세션 매니저 측)

- Spotify / Apple Music: AppleScript로 곡명·아티스트·재생 위치 조회
- 브라우저(YouTube Music 등): 무음 감지 기반 트랙 경계 폴백
- 주의: macOS 15.4+에서 MediaRemote 사적 API가 제한되어 사용하지 않는다
