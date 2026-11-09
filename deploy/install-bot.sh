#!/usr/bin/env bash
# 统一安装脚本（D023）：把清单 config/bots.toml 里的一个机器人安装为 launchd 服务。
# 用法：deploy/install-bot.sh <机器人名>     名称见 `PYTHONPATH=src python3 -m requirements.bots list`
# 规则：只安装声明运行在本环境（AUTODEV_ENV，默认 home-mac）的机器人；白名单为空一律拒绝；
#       服务固定指向本脚本所在的检出目录，请在长期保留的部署目录里执行。
set -euo pipefail

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "用法：$0 <机器人名>（可用：req、design 等，见 config/bots.toml）" >&2
  exit 2
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO_DIR/.venv/bin/python"
PLIST_DIR="$HOME/Library/LaunchAgents"

if [ ! -x "$PY" ]; then
  echo "❌ 找不到虚拟环境 python：${PY}" >&2
  echo "   请先执行：python3.11 -m venv .venv && .venv/bin/pip install lark_oapi" >&2
  exit 1
fi

# 从清单取出该机器人的定义，同时检查运行环境与白名单；失败时清单工具已打印原因
BOT_VARS="$(cd "$REPO_DIR" && PYTHONPATH="$REPO_DIR/src" "$PY" -m requirements.bots show "$NAME" --root "$REPO_DIR")" || exit 1
eval "$BOT_VARS"

LABEL="${AUTODEV_BOT_LABEL:-$BOT_LABEL}"
CONFIG_FILE="${!BOT_CONFIG_ENV:-$BOT_CONFIG}"
PLIST="$PLIST_DIR/$LABEL.plist"

codex_path="$(command -v codex || true)"
claude_path="$(command -v claude || true)"
codex_dir="$([ -n "$codex_path" ] && dirname "$codex_path" || true)"
claude_dir="$([ -n "$claude_path" ] && dirname "$claude_path" || true)"
RUN_PATH="${codex_dir:+$codex_dir:}${claude_dir:+$claude_dir:}$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

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
        <string>$BOT_MODULE</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$REPO_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>$REPO_DIR/src</string>
        <key>PATH</key>
        <string>$RUN_PATH</string>
        <key>$BOT_CONFIG_ENV</key>
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
echo "✅ 已写入 ${PLIST}"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✅ 已加载并启动服务：${LABEL}（机器人：${NAME}，目录：${REPO_DIR}）"
echo "   状态：launchctl list | grep ${LABEL}"
echo "   日志：tail -f \"${REPO_DIR}/logs/${LABEL}.err\""
