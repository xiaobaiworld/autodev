#!/usr/bin/env bash
# 卸载 AutoDev 设计机器人 launchd 服务（只动设计机器人，不碰需求机器人）。
set -euo pipefail

LABEL="${AUTODEV_DESIGN_LABEL:-com.autodev.design-bot}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ 已卸载服务：$LABEL 并删除 $PLIST"
