"""设计机器人飞书入口（第一版：只负责连通与身份核对，业务能力后续按契约接入）。"""
from __future__ import annotations

import logging
import os
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("autodev.design")

HELP = (
    "设计机器人已连通。目前只做连通与身份核对，设计讨论、状态查询等能力还在接入中。\n"
    "可用：/help 查看本说明。"
)


class DesignBotError(ValueError):
    """配置不合法；消息直接给人看。"""


@dataclass(frozen=True)
class DesignConfig:
    app_id: str
    app_secret: str
    allow_users: set[str]
    discover_mode: bool


def load_design_config(path) -> DesignConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    feishu = raw.get("feishu", {})
    allow = raw.get("allow", {})
    app_id = str(feishu.get("app_id", "")).strip()
    app_secret = str(feishu.get("app_secret", "")).strip()
    if not app_id or not app_secret:
        raise DesignBotError("缺少 [feishu] app_id / app_secret")
    users = {str(u) for u in allow.get("users", []) if str(u).strip()}
    discover = allow.get("discover") is True
    if not users and not discover:
        raise DesignBotError("白名单 [allow] users 为空：设计机器人不允许对所有人开放；首次取 open_id 请临时设置 discover = true")
    return DesignConfig(app_id, app_secret, users, discover)


def decide(cfg: DesignConfig, open_id: str, text: str) -> tuple[str, str]:
    """纯函数：返回 (动作, 内容)。动作为 ignore / record / reply，便于不连飞书就能测试。"""
    text = (text or "").strip()
    if not text:
        return ("ignore", "")
    if cfg.discover_mode:
        return ("record", open_id)
    if open_id not in cfg.allow_users:
        return ("reply", "🔒 抱歉，设计机器人仅对授权人员开放。")
    return ("reply", HELP)


def main() -> None:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

    from requirements.feishu_daemon import extract_text_from_message, setup_logging, strip_mentions
    from requirements.responder import FeishuResponder

    setup_logging()
    config_path = os.environ.get("AUTODEV_DESIGN_CONFIG", "config.design.toml")
    if not os.path.exists(config_path):
        log.error("找不到设计机器人配置文件: %s", config_path)
        sys.exit(1)
    try:
        cfg = load_design_config(config_path)
    except DesignBotError as e:
        log.error("配置错误: %s", e)
        sys.exit(1)

    responder = FeishuResponder(cfg.app_id, cfg.app_secret)
    send_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="design-sender")

    def on_message(data: P2ImMessageReceiveV1) -> None:
        msg = data.event.message
        sender = data.event.sender
        open_id = sender.sender_id.open_id if sender and sender.sender_id else ""
        clean = strip_mentions(extract_text_from_message(msg.content or ""), getattr(msg, "mentions", None))
        action, content = decide(cfg, open_id, clean)
        if action == "record":
            log.warning("发现模式：收到消息，发送者 open_id=%s（未回复）", open_id)
        elif action == "reply":
            send_pool.submit(responder.send_text, msg.chat_id, content)

    def on_read(data) -> None:
        """飞书的“消息已读”回执，无需处理；注册空处理函数避免日志刷 processor not found。"""

    builder = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message)
    handler = builder.register_p2_im_message_message_read_v1(on_read).build()
    client = lark.ws.Client(cfg.app_id, cfg.app_secret, event_handler=handler, log_level=lark.LogLevel.INFO)
    log.info("AutoDev 设计机器人已就绪（发现模式=%s），正在连接飞书长连接...", cfg.discover_mode)
    client.start()


if __name__ == "__main__":
    main()
