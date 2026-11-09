"""机器人清单（D023）：读取 config/bots.toml，校验运行环境与白名单，供安装脚本和机器人启动共用。"""
from __future__ import annotations

import argparse
import os
import shlex
import sys
import tomllib
from pathlib import Path

DEFAULT_ENV = "home-mac"
REQUIRED = ("description", "module", "config_file", "config_env", "label", "stages", "runs_on")
MANIFEST = Path(__file__).resolve().parents[2] / "config" / "bots.toml"


class BotError(ValueError):
    """清单或本机配置不合法；消息直接给人看。"""


def load_manifest(path=MANIFEST) -> dict:
    bots = tomllib.loads(Path(path).read_text(encoding="utf-8")).get("bots", {})
    if not bots:
        raise BotError(f"清单里没有任何机器人: {path}")
    labels = {}
    for name, b in bots.items():
        missing = [k for k in REQUIRED if k not in b]
        if missing:
            raise BotError(f"机器人 {name} 缺少字段: {missing}")
        if b["label"] in labels:
            raise BotError(f"标签重复: {b['label']}（{labels[b['label']]} 与 {name}）")
        labels[b["label"]] = name
    return bots


def select(bots: dict, name: str, env: str | None = None) -> dict:
    """取出一个机器人；它声明的运行环境和当前环境不一致时拒绝（同一飞书应用只能有一个长连接）。"""
    env = env or os.environ.get("AUTODEV_ENV", DEFAULT_ENV)
    if name not in bots:
        raise BotError(f"清单里没有机器人 {name}，可用: {sorted(bots)}")
    if bots[name]["runs_on"] != env:
        raise BotError(f"机器人 {name} 声明运行在 {bots[name]['runs_on']}，当前环境是 {env}，拒绝安装")
    return bots[name]


def require_whitelist(config_path) -> None:
    """白名单为空一律拒绝；只有明确写了 discover = true（首次取 open_id）才允许为空。"""
    p = Path(config_path)
    if not p.is_file():
        raise BotError(f"找不到本机配置文件 {p}（含飞书凭证与 [allow] users 白名单）")
    allow = tomllib.loads(p.read_text(encoding="utf-8")).get("allow", {})
    users = [u for u in allow.get("users", []) if str(u).strip()]
    if not users and allow.get("discover") is not True:
        raise BotError(f"{p.name} 的 [allow] users 为空：不允许对所有人开放（首次取 open_id 可临时设 discover = true）")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="机器人清单工具（供 deploy/install-bot.sh 使用）")
    ap.add_argument("action", choices=["show", "list"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--root", default=str(MANIFEST.parents[1]), help="部署目录，用来定位本机配置文件")
    ap.add_argument("--no-whitelist-check", action="store_true", help="卸载等场景不检查白名单")
    a = ap.parse_args(argv)
    try:
        bots = load_manifest()
        if a.action == "list":
            for n, b in bots.items():
                print(n, b["label"], b["runs_on"], b["description"])
            return 0
        if not a.name:
            raise BotError("需要机器人名称")
        b = select(bots, a.name)
        if not a.no_whitelist_check:
            require_whitelist(Path(a.root) / os.environ.get(b["config_env"], b["config_file"]))
    except (BotError, OSError, tomllib.TOMLDecodeError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    for key, var in (("module", "BOT_MODULE"), ("config_file", "BOT_CONFIG"), ("config_env", "BOT_CONFIG_ENV"), ("label", "BOT_LABEL")):
        print(f"{var}={shlex.quote(b[key])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
