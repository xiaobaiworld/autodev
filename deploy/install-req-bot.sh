#!/usr/bin/env bash
# 把 AutoDev 需求分析师机器人安装为 launchd 服务：登录自启 + 崩溃自动拉起。
# 支持多项目/多检出实例共存：可通过参数 $1、环境变量 AUTODEV_BOT_INSTANCE 或 AUTODEV_BOT_LABEL 指定实例。
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
  # 若检出目录非标准 autodev（如多检出、多分支目录），自动以目录名区分标签，防止覆盖主实例
  LABEL="com.autodev.req-bot.$DIR_NAME"
else
  LABEL="com.autodev.req-bot"
fi

PLIST="$PLIST_DIR/$LABEL.plist"
PY="$REPO_DIR/.venv/bin/python"
CONFIG_FILE="${AUTODEV_REQ_CONFIG:-config.req.toml}"

if [ ! -x "$PY" ]; then
  echo "❌ 找不到虚拟环境 python：$PY"
  echo "   请先在 autodev 目录执行：python3.11 -m venv .venv && .venv/bin/pip install lark_oapi pytest"
  exit 1
fi
if [ ! -f "$REPO_DIR/$CONFIG_FILE" ]; then
  echo "❌ 找不到 $REPO_DIR/$CONFIG_FILE，请先配置。"
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
        <string>$CONFIG_FILE</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$REPO_DIR/logs/${LABEL}.out</string>
    <key>StandardErrorPath</key>
    <string>$REPO_DIR/logs/${LABEL}.err</string>
</dict>
</plist>
EOF

echo "✅ 已写入 $PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✅ 已加载并启动服务：$LABEL"
echo "   状态：launchctl list | grep $LABEL"
echo "   日志：tail -f \"$REPO_DIR/logs/${LABEL}.out\""
echo "   💡 多项目共存提示：可通过 ./deploy/install-req-bot.sh <实例名> 启动不同项目的独立守护进程"
