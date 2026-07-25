"""spotify_player(Homebrew/cargo, librespot 기반) 서브프로세스 제어.

musicna은 spotify_player를 헤드리스 데몬(`-d`, cargo `daemon` feature 빌드 필요)으로 구동해
스스로 Spotify Connect 기기가 된다. 재생 제어는 이 바이너리의 CLI 서브커맨드를 그대로
서브프로세스로 호출해 이루어진다(자체 librespot 바인딩을 작성하지 않는다).

CLI 문법은 실측 확인(2026-07-26, spotify_player 0.24.1, macOS)에 기반한다:
  spotify_player get key playback   → 현재 재생 상태 JSON (rspotify CurrentPlaybackContext 형태)
  spotify_player get key devices    → 기기 목록 JSON
  spotify_player playback play|pause|play-pause|next|previous
  spotify_player playback volume <percent:-100..100> [--offset]
  spotify_player connect --id <id> | --name <name>
"""

import json

from pydantic import BaseModel


class PlayerStatus(BaseModel):
    is_playing: bool
    item_title: str | None = None
    item_artist: str | None = None
    item_album: str | None = None
    item_duration_s: float | None = None
    progress_s: float | None = None
    volume_percent: int | None = None
    device_name: str | None = None
    shuffle: bool = False
    repeat_state: str = "off"


class PlayerDevice(BaseModel):
    id: str
    name: str
    is_active: bool
    volume_percent: int | None = None


def parse_playback_json(raw: str) -> PlayerStatus | None:
    """`spotify_player get key playback` 출력을 파싱. 재생 중이 아니면(JSON null) None."""
    data = json.loads(raw)
    if not data:
        return None
    item = data.get("item") or {}
    device = data.get("device") or {}
    artists = item.get("artists") or []
    duration_ms = item.get("duration_ms")
    progress_ms = data.get("progress_ms")
    return PlayerStatus(
        is_playing=bool(data.get("is_playing", False)),
        item_title=item.get("name"),
        item_artist=artists[0]["name"] if artists else None,
        item_album=(item.get("album") or {}).get("name"),
        item_duration_s=(duration_ms / 1000) if duration_ms is not None else None,
        progress_s=(progress_ms / 1000) if progress_ms is not None else None,
        volume_percent=device.get("volume_percent"),
        device_name=device.get("name"),
        shuffle=bool(data.get("shuffle_state", False)),
        repeat_state=data.get("repeat_state", "off"),
    )


def parse_devices_json(raw: str) -> list[PlayerDevice]:
    """`spotify_player get key devices` 출력을 파싱."""
    data = json.loads(raw)
    return [
        PlayerDevice(
            id=d["id"], name=d["name"],
            is_active=d.get("is_active", False),
            volume_percent=d.get("volume_percent"),
        )
        for d in data
    ]
