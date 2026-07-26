#!/bin/bash
# musicna api를 launchd LaunchAgent로 등록한다. 이 저장소 루트에서 실행할 것.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC="$REPO_ROOT/deploy/macos/com.musicna.api.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.musicna.api.plist"

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" -e "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"

echo "설치 완료: $PLIST_DST"
echo "확인: launchctl list | grep com.musicna.api"
echo "로그: tail -f $HOME/Library/Logs/musicna-api.log"
