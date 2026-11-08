#!/usr/bin/env bash
set -euo pipefail

LABEL="com.autodev.req-bot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "✅ 已卸载 $LABEL 并删除 plist"
