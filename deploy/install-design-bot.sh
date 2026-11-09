#!/usr/bin/env bash
# 把 AutoDev 设计机器人安装为 launchd 服务：登录自启 + 崩溃自动拉起。
# 与需求机器人独立：标签固定为 com.autodev.design-bot（可用 AUTODEV_DESIGN_LABEL 覆盖），不会改动需求机器人的服务。
# 注意：服务会固定指向本脚本所在的检出目录，请在长期保留的目录里执行，不要在临时工作区里安装。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${AUTODEV_DESIGN_LABEL:-com.autodev.design-bot}"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
PY="$REPO_DIR/.venv/bin/python"
CONFIG_FILE="${AUTODEV_DESIGN_CONFIG:-config.design.toml}"

if [ ! -x "$PY" ]; then
  echo "❌ 找不到虚拟环境 python：$PY"
  echo "   请先执行：python3.11 -m venv .venv && .venv/bin/pip install lark_oapi"
  exit 1
fi
if [ ! -f "$REPO_DIR/$CONFIG_FILE" ]; then
  echo "❌ 找不到 $REPO_DIR/$CONFIG_FILE，请先配置（含 [feishu] 凭证和 [allow] users 白名单）。"
  exit 1
fi
# 白名单为空且未开发现模式时，机器人自己会拒绝启动；这里提前拦住，避免 launchd 反复拉起。
if ! grep -Eq '^[[:space:]]*users[[:space:]]*=[[:space:]]*\[[^]]*"[^"]+"' "$REPO_DIR/$CONFIG_FILE" \
   && ! grep -Eq '^[[:space:]]*discover[[:space:]]*=[[:space:]]*true' "$REPO_DIR/$CONFIG_FILE"; then
  echo "❌ $CONFIG_FILE 里没有白名单 users，也没有开启 discover，机器人会拒绝启动。"
  exit 1
fi

mkdir -p "$PLIST_DIR" "$REPO_DIR/logs"

cat > "$PLIST" <<PLISTEOF
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
        <string>requirements.design_bot</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$REPO_DIR/src</string>
        <key>AUTODEV_DESIGN_CONFIG</key>
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
PLISTEOF

chmod 600 "$PLIST"
echo "✅ 已写入 $PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✅ 已加载并启动服务：$LABEL（目录：$REPO_DIR）"
echo "   状态：launchctl list | grep $LABEL"
echo "   日志：tail -f \"$REPO_DIR/logs/${LABEL}.err\""
