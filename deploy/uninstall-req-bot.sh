#!/usr/bin/env bash
# 卸载指定的 AutoDev 需求分析师机器人 launchd 服务。
# 支持参数：./uninstall-req-bot.sh [instance_or_label]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR_NAME="$(basename "$REPO_DIR")"
PLIST_DIR="$HOME/Library/LaunchAgents"

INSTANCE="${1:-${AUTODEV_BOT_INSTANCE:-}}"
if [ -n "${AUTODEV_BOT_LABEL:-}" ]; then
  LABEL="$AUTODEV_BOT_LABEL"
elif [ -n "$INSTANCE" ]; then
  if [[ "$INSTANCE" == com.* ]]; then
    LABEL="$INSTANCE"
  else
    LABEL="com.autodev.req-bot.$INSTANCE"
  fi
elif [ "$DIR_NAME" != "autodev" ]; then
  LABEL="com.autodev.req-bot.$DIR_NAME"
else
  LABEL="com.autodev.req-bot"
fi

PLIST="$PLIST_DIR/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ 已卸载服务：$LABEL 并删除 $PLIST"
