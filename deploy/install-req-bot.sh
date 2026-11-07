#!/usr/bin/env bash
# 把 AutoDev 需求分析师机器人安装为 launchd 服务：登录自启 + 崩溃自动拉起。
set -euo pipefail

LABEL="com.autodev.req-bot"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_DIR/.venv/bin/python"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"

if [ ! -x "$PY" ]; then
  echo "❌ 找不到虚拟环境 python：$PY"
  echo "   请先在 autodev 目录执行：python3.11 -m venv .venv && .venv/bin/pip install lark_oapi pytest"
  exit 1
fi
if [ ! -f "$REPO_DIR/config.req.toml" ]; then
  echo "❌ 找不到 $REPO_DIR/config.req.toml，请先配置。"
  exit 1
fi

codex_path="$(command -v codex || true)"
claude_path="$(command -v claude || true)"
codex_dir="$([ -n "$codex_path" ] && dirname "$codex_path" || true)"
claude_dir="$([ -n "$claude_path" ] && dirname "$claude_path" || true)"

RUN_PATH="${codex_dir:+$codex_dir:}${claude_dir:+$claude_dir:}$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$PLIST_DIR" "$REPO_DIR/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>-m</string>
        <string>requirements.feishu_daemon</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$REPO_DIR/src</string>
        <key>PATH</key>
        <string>$RUN_PATH</string>
        <key>AUTODEV_REQ_CONFIG</key>
        <string>config.req.toml</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$REPO_DIR/logs/req_daemon.out</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/logs/req_daemon.err</string>
</dict>
</plist>
EOF

echo "✅ 已写入 $PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✅ 已加载并启动 $LABEL"
echo "   状态：launchctl list | grep autodev"
echo "   日志：tail -f \"$REPO_DIR/logs/req_daemon.out\""
