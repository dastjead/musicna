"""캡처 세션 CLI — 캡처 헬퍼를 띄우고 PCM을 트랙별 WAV로 저장한다.

실행: uv run musicna-session [--source spotify|apple_music|silence] [--out data/audio]

- spotify / apple_music: AppleScript 폴링으로 트랙 경계 감지
- silence: 메타데이터 없는 소스(브라우저 등)용 무음 감지 폴백
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import BinaryIO

from .metadata import NowPlaying, poll_now_playing
from .recorder import TrackRecorder
from .silence import SilenceSplitter

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK_FRAMES = 4800  # 0.1초
CHUNK_BYTES = CHUNK_FRAMES * CHANNELS * 4  # float32
POLL_INTERVAL_S = 1.0

# Spotify 클라이언트만 캡처하도록 헬퍼에 넘길 번들 ID
_APP_BUNDLE_IDS = {"spotify": "com.spotify.client", "apple_music": "com.apple.Music"}


def read_exact(stream: BinaryIO, n: int) -> bytes:
    """부분 읽기를 이어 붙여 정확히 n바이트를 반환한다. EOF면 남은 만큼만."""
    parts: list[bytes] = []
    remaining = n
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            break
        parts.append(chunk)
        remaining -= len(chunk)
    return b"".join(parts)


def fallback_now_playing(index: int) -> NowPlaying:
    """무음 폴백 모드에서 트랙 경계마다 만드는 가짜 메타데이터."""
    return NowPlaying(state="playing", title=f"Untitled {index:03d}", source="unknown")


def default_helper_path() -> Path:
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "capture-macos" / ".build" / "release" / "musicna-capture"


def _log(message: str) -> None:
    print(f"[musicna-session] {message}", file=sys.stderr, flush=True)


def run_session(
    source: str, out_dir: Path, helper: Path, capture_app_only: bool
) -> list:
    cmd = [str(helper)]
    bundle_id = _APP_BUNDLE_IDS.get(source)
    if capture_app_only and bundle_id:
        cmd += ["--app", bundle_id]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert proc.stdout is not None
    recorder = TrackRecorder(out_dir=out_dir, sample_rate=SAMPLE_RATE, channels=CHANNELS)
    splitter = SilenceSplitter(sample_rate=SAMPLE_RATE, channels=CHANNELS)
    fallback_index = 0
    last_poll = 0.0
    heard_any = False

    _log(f"capturing → {out_dir} (source={source}, helper={helper.name})")
    try:
        while True:
            chunk = read_exact(proc.stdout, CHUNK_BYTES)
            if not chunk:
                _log("capture helper stream ended")
                break

            if source == "silence":
                if splitter.feed(chunk):
                    fallback_index += 1
                    recorder.update_metadata(fallback_now_playing(fallback_index))
                elif not heard_any and splitter.heard_sound:
                    # 첫 소리 → 첫 트랙 시작
                    heard_any = True
                    fallback_index += 1
                    recorder.update_metadata(fallback_now_playing(fallback_index))
            else:
                now = time.monotonic()
                if now - last_poll >= POLL_INTERVAL_S:
                    last_poll = now
                    recorder.update_metadata(poll_now_playing(source))

            recorder.feed(chunk)
    except KeyboardInterrupt:
        _log("stopping (Ctrl-C)")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        finished = recorder.finalize()

    for track in finished:
        seconds = track.frames / SAMPLE_RATE
        _log(f"saved: {track.wav_path.name} ({seconds:.1f}s)")
    _log(f"done — {len(finished)} track(s)")
    return finished


def main() -> None:
    parser = argparse.ArgumentParser(prog="musicna-session", description=__doc__)
    parser.add_argument(
        "--source", choices=["spotify", "apple_music", "silence"], default="spotify"
    )
    parser.add_argument("--out", type=Path, default=Path("data/audio"))
    parser.add_argument("--helper", type=Path, default=None, help="캡처 헬퍼 실행 파일 경로")
    parser.add_argument(
        "--system-audio", action="store_true",
        help="앱 오디오만이 아니라 시스템 오디오 전체를 캡처",
    )
    args = parser.parse_args()

    helper = args.helper or default_helper_path()
    if not helper.exists() and shutil.which(str(helper)) is None:
        _log(f"capture helper not found: {helper}")
        _log("build it first: cd capture-macos && swift build -c release")
        sys.exit(1)

    run_session(
        source=args.source,
        out_dir=args.out,
        helper=helper,
        capture_app_only=not args.system_audio,
    )


if __name__ == "__main__":
    main()
