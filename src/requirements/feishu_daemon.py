# 定位: feishu_daemon.py AutoDev 专属需求分析师飞书机器人服务入口。
from __future__ import annotations

import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from requirements.agent_runner import run_agent_turn
from requirements.config import load_req_config
from requirements.flow import build_req_prompt, is_finalize_request, normalize_user_input
from requirements.presentation import FeishuCardPresenter, extract_semantic_response
from requirements.responder import FeishuResponder
from requirements.session import ReqSessionStore

log = logging.getLogger("autodev.req")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def extract_text_from_message(content_raw: str) -> str:
    try:
        data = json.loads(content_raw)
        return data.get("text", "").strip()
    except Exception:
        return content_raw.strip()


def strip_mentions(text: str, mentions) -> str:
    for m in mentions or []:
        if getattr(m, "key", None):
            text = text.replace(m.key, "")
    return text.strip()


def main() -> None:
    setup_logging()
    config_path = os.environ.get("AUTODEV_REQ_CONFIG", "config.req.toml")
    if not os.path.exists(config_path):
        log.error("找不到需求配置文件: %s", config_path)
        sys.exit(1)

    cfg = load_req_config(config_path)
    responder = FeishuResponder(cfg.app_id, cfg.app_secret)
    session_file = os.environ.get("AUTODEV_REQ_SESSION", ".req_session.json")
    store = ReqSessionStore(session_file, cfg.default_cwd, cfg.default_agent)
    work_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="req-worker")
    send_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="req-sender")

    log.info("AutoDev 需求分析师机器人启动中... app_id=%s, default_cwd=%s", cfg.app_id, cfg.default_cwd)

    def on_message(data: P2ImMessageReceiveV1) -> None:
        event = data.event
        msg = event.message
        sender = event.sender
        user_open_id = sender.sender_id.open_id if sender and sender.sender_id else ""
        chat_id = msg.chat_id

        if cfg.allow_users and user_open_id not in cfg.allow_users:
            log.warning("拦截未授权用户访问: %s", user_open_id)
            send_pool.submit(responder.send_text, chat_id, "🔒 抱歉，当前需求分析机器人仅对授权人员开放。")
            return

        raw_text = extract_text_from_message(msg.content or "")
        clean_text = strip_mentions(raw_text, getattr(msg, "mentions", None)).strip()

        if not clean_text:
            return

        log.info("收到需求消息: user=%s, text=%r", user_open_id, clean_text[:60])

        if clean_text in ("/new", "/重置", "/清空", "新需求", "/reset"):
            store.reset_session(chat_id)
            sess = store.get(chat_id)
            send_pool.submit(
                responder.send_text,
                chat_id,
                f"🌱 已为你开启新的需求会话！\n当前项目：`{sess['cwd']}`\n请直接发消息描述你想要实现的想法。",
            )
            return

        if clean_text.startswith("/project ") or clean_text.startswith("/cd "):
            target_path = clean_text.split(maxsplit=1)[1].strip()
            sess = store.get(chat_id)
            expanded = os.path.expanduser(target_path)
            resolved = os.path.realpath(expanded) if os.path.isabs(expanded) else os.path.realpath(os.path.join(sess["cwd"], expanded))
            allowed = any(resolved == d or resolved.startswith(d + os.sep) for d in cfg.allow_dirs)
            if not allowed:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 拒绝：目录不在白名单内 `{resolved}`")
                return
            store.set_cwd(chat_id, resolved)
            send_pool.submit(
                responder.send_text,
                chat_id,
                f"📁 目标项目已切换至：`{resolved}`\n已关联该项目上下文，可继续聊需求。",
            )
            return

        if clean_text in ("/status", "/状态"):
            sess = store.get(chat_id)
            has_session = "已建立 (" + sess["session_id"][:8] + "...)" if sess["session_id"] else "未建立 (发送任意需求即可开始)"
            status_msg = (
                f"🤖 **AutoDev 需求分析师状态**\n"
                f"• 当前目标项目：`{sess['cwd']}`\n"
                f"• 分析推理引擎：`{sess['agent']}`\n"
                f"• 交互会话上下文：{has_session}\n"
                f"• 安全模式：严格只读 (Read-Only)"
            )
            send_pool.submit(responder.send_text, chat_id, status_msg)
            return

        if clean_text in ("/help", "/帮助"):
            help_msg = (
                "🎯 **欢迎使用 AutoDev 需求分析师！**\n\n"
                "你不需要记忆任何复杂命令，直接在对话框中告诉我你想做什么需求即可。\n"
                "我会基于当前目标项目代码和架构，深入帮你理清目标、梳理非目标与验收标准。\n\n"
                "📌 **常用辅助指令**：\n"
                "• 发送 `/new` 或 `新需求`：开启一个全新的需求会话；\n"
                "• 发送 `/project <路径>`：切换到其他项目目录；\n"
                "• 聊充分后回复 `定稿`：我会为你输出标准的《软件需求规格说明》；\n"
                "• 发送 `/status`：查看当前绑定的项目与会话状态。"
            )
            send_pool.submit(responder.send_text, chat_id, help_msg)
            return

        sess = store.get(chat_id)
        current_session_id = sess["session_id"] or None
        is_new = current_session_id is None
        is_final = is_finalize_request(clean_text)

        normalized_input = normalize_user_input(clean_text)
        agent_prompt = build_req_prompt(normalized_input, is_new=is_new)

        def run_task() -> None:
            log.info("开始调用需求 Agent: agent=%s cwd=%s resume=%s", sess["agent"], sess["cwd"], bool(current_session_id))
            result = run_agent_turn(
                sess["agent"],
                agent_prompt,
                sess["cwd"],
                session_id=current_session_id,
                timeout=cfg.task_timeout,
            )

            if result.ok:
                new_session_id = result.parsed.session_id
                if new_session_id and new_session_id != current_session_id:
                    store.update_session_id(chat_id, new_session_id)

                reply_text = result.parsed.reply.strip() or "（已完成分析，但未捕获到文本回复）"

                archived_path = None
                if is_final and len(reply_text) > 100:
                    try:
                        req_dir = os.path.join(sess["cwd"], "docs", "requirements")
                        os.makedirs(req_dir, exist_ok=True)
                        ts = time.strftime("%Y%m%d-%H%M%S")
                        file_name = f"REQ-{ts}.md"
                        full_path = os.path.join(req_dir, file_name)
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(reply_text + "\n")
                        archived_path = full_path
                        log.info("需求定稿文件已落盘: %s", full_path)
                    except Exception as e:
                        log.warning("定稿文件写入失败: %s", e)

                semantic_resp = extract_semantic_response(reply_text, is_finalize=is_final)
                feishu_presenter = FeishuCardPresenter()
                card_data = feishu_presenter.render(semantic_resp)

                card_sent = responder.send_card(chat_id, card_data)
                if not card_sent:
                    log.warning("卡片发送失败，降级回退到普通文本回复")
                    fallback_text = reply_text
                    if archived_path:
                        fallback_text += f"\n\n---\n📄 **需求文档已自动归档至项目**：\n`{archived_path}`"
                    responder.send_text(chat_id, fallback_text[:cfg.output_limit])
                else:
                    if archived_path:
                        responder.upload_text_file(chat_id, reply_text, filename=os.path.basename(archived_path))
            else:
                err_msg = result.parsed.error
                log.warning("需求分析未成功: %s", err_msg)
                responder.send_text(chat_id, f"⚠️ 需求分析中断：{err_msg}")

        work_pool.submit(run_task)

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )

    client = lark.ws.Client(
        cfg.app_id,
        cfg.app_secret,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )

    log.info("AutoDev 需求分析师机器人已就绪，正在连接飞书长连接...")
    client.start()


if __name__ == "__main__":
    main()
