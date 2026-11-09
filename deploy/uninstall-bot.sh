#!/usr/bin/env bash
# 统一卸载脚本（D023）：按清单里的标签卸载一个机器人的 launchd 服务，只动这一个。
# 用法：deploy/uninstall-bot.sh <机器人名>
set -euo pipefail

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "用法：$0 <机器人名>" >&2
  exit 2
fi
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_DIR/.venv/bin/python"
BOT_VARS="$(cd "$REPO_DIR" && PYTHONPATH="$REPO_DIR/src" "$PY" -m requirements.bots show "$NAME" --root "$REPO_DIR" --no-whitelist-check)" || exit 1
eval "$BOT_VARS"

LABEL="${AUTODEV_BOT_LABEL:-$BOT_LABEL}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ 已卸载服务：${LABEL}（机器人：${NAME}）并删除 ${PLIST}"
