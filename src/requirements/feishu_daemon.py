# 定位: feishu_daemon.py AutoDev 专属需求分析师飞书机器人服务入口。
from __future__ import annotations

import glob
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
from requirements.context_detector import build_project_context_summary
from requirements.flow import build_req_prompt, is_finalize_request, normalize_user_input
from requirements.handoff import handoff_srs_to_pipeline
from requirements.llm_provider import load_model_registry, resolve_model_spec
from requirements.presentation import FeishuCardPresenter, extract_semantic_response
from requirements.responder import FeishuResponder
from requirements.session import ReqSessionStore
from requirements.validator import validate_requirement_spec

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


def _find_latest_req_file(cwd: str, last_archived: str) -> str | None:
    if last_archived and os.path.isfile(last_archived):
        return last_archived
    req_dir = os.path.join(cwd, "docs", "requirements")
    candidates = sorted(glob.glob(os.path.join(req_dir, "REQ-*.md")))
    return candidates[-1] if candidates else None


def main() -> None:
    setup_logging()
    config_path = os.environ.get("AUTODEV_REQ_CONFIG", "config.req.toml")
    if not os.path.exists(config_path):
        log.error("找不到需求配置文件: %s", config_path)
        sys.exit(1)

    cfg = load_req_config(config_path)
    responder = FeishuResponder(cfg.app_id, cfg.app_secret)
    session_file = os.environ.get("AUTODEV_REQ_SESSION", ".req_session.json")
    store = ReqSessionStore(
        session_file,
        cfg.default_cwd,
        cfg.default_agent,
        default_mode=cfg.default_mode,
    )
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

        if clean_text == "/model" or clean_text == "/models" or clean_text.startswith("/model "):
            sess = store.get(chat_id)
            registry = load_model_registry()
            parts = clean_text.split(maxsplit=1)
            if len(parts) == 1:
                lines = ["🧠 **需求阶段可用大模型列表**（源自 `config.yaml` 完整模型 ID）："]
                for name, spec in registry.items():
                    mark = "✅ 当前" if name == sess["agent"] else "◻️"
                    lines.append(
                        f"{mark} `{name}` → `{spec.full_model_id}` (厂商: `{spec.vendor}`, CLI: `{spec.cli}`)"
                    )
                lines.append("\n💡 发送 `/model <名称>`（如 `/model gpt` 或 `/model claude-opus`）即可随时切换模型，历史问答上下文会自动保留。")
                send_pool.submit(responder.send_text, chat_id, "\n".join(lines))
                return

            target_model = parts[1].strip()
            try:
                spec = resolve_model_spec(target_model, registry)
                store.set_agent(chat_id, spec.name)
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"🔄 **需求分析模型已切换**！\n"
                    f"• 逻辑名：`{spec.name}`\n"
                    f"• 完整模型 ID：`{spec.full_model_id}`\n"
                    f"• 模型厂商：`{spec.vendor}` (CLI: `{spec.cli}`)\n"
                    f"• 历史问答记忆：已保留（共 {len(sess.get('history') or [])} 轮），可直接继续对话。",
                )
            except Exception as e:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 切换模型失败：{e}")
            return

        if clean_text == "/mode" or clean_text.startswith("/mode "):
            sess = store.get(chat_id)
            parts = clean_text.split(maxsplit=1)
            if len(parts) == 1:
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"⚙️ **当前大模型调用方式**：`{sess.get('mode', 'cli_session')}`\n\n"
                    f"• `cli_session`（默认）：使用 CLI 原生 `--resume` 会话续接，结合本地历史兜底；\n"
                    f"• `cli_stateless`：每次独立无状态调用，由本地 `history` 自动注入前序问答摘要，适合频繁跨模型/跨厂商切换。\n\n"
                    f"💡 发送 `/mode cli_session` 或 `/mode cli_stateless` 即可切换。",
                )
                return

            target_mode = parts[1].strip()
            try:
                store.set_mode(chat_id, target_mode)
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"✅ 调用方式已切换为：`{target_mode}`",
                )
            except Exception as e:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 切换调用方式失败：{e}")
            return

        if (
            clean_text in ("/handoff", "启动设计", "移交设计", "进入下一阶段")
            or clean_text.startswith("/handoff ")
        ):
            sess = store.get(chat_id)
            parts = clean_text.split(maxsplit=1)
            explicit_arg = parts[1].strip() if clean_text.startswith("/handoff ") and len(parts) > 1 else ""
            if explicit_arg:
                req_path = explicit_arg if os.path.isabs(explicit_arg) else os.path.join(sess["cwd"], explicit_arg)
            else:
                req_path = _find_latest_req_file(sess["cwd"], sess.get("last_archived_req", ""))

            if not req_path or not os.path.isfile(req_path):
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    "⚠️ 未找到可移交的定稿需求文档（`REQ-*.md`）。请先在对话中回复 `定稿` 生成标准需求规格说明。",
                )
                return

            try:
                proj_name = os.path.basename(sess["cwd"].rstrip(os.sep)) or "toy"
                info = handoff_srs_to_pipeline(
                    srs_path=req_path,
                    root=sess["cwd"],
                    project=proj_name,
                )
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"🚀 **已将定稿需求直通移交至下一阶段（S2 架构设计）！**\n\n"
                    f"• **运行编号**：`{info['run_id']}`\n"
                    f"• **需求标题**：{info['title']}\n"
                    f"• **来源文档**：`{os.path.basename(info['source_srs'])}`\n"
                    f"• **当前阶段**：`{info['stage']} (第 {info['round']} 轮)` — 已自动生成 S1 基线并跳过重复分析\n"
                    f"• **架构设计（S2）**：`{info['designer_agent']}` (`{info['designer_model']}`)\n"
                    f"• **设计审查（S3）**：`{info['reviewer_agent']}` (`{info['reviewer_model']}`)\n"
                    f"• **运行目录**：`{info['run_dir']}`",
                )
            except Exception as e:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 移交 S2 架构设计失败：{e}")
            return

        if clean_text in ("/status", "/状态"):
            sess = store.get(chat_id)
            try:
                spec = resolve_model_spec(sess["agent"])
                model_desc = f"`{spec.name}` → `{spec.full_model_id}` (厂商: `{spec.vendor}`)"
            except Exception:
                model_desc = f"`{sess['agent']}`"
            has_session = "已建立 (" + sess["session_id"][:8] + "...)" if sess["session_id"] else "未建立 (发送任意需求即可开始)"
            last_req = os.path.basename(sess["last_archived_req"]) if sess.get("last_archived_req") else "暂无"
            status_msg = (
                f"🤖 **AutoDev 需求分析师状态**\n"
                f"• 当前目标项目：`{sess['cwd']}`\n"
                f"• 分析推理模型：{model_desc}\n"
                f"• 调用方式：`{sess.get('mode', 'cli_session')}`（已记录 {len(sess.get('history') or [])} 轮问答）\n"
                f"• 交互会话上下文：{has_session}\n"
                f"• 最近定稿文档：`{last_req}`\n"
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
                "• 发送 `/model` 或 `/model <名称>`：查看或切换底层大模型（支持 Claude / Codex / Gemini 完整模型 ID）；\n"
                "• 发送 `/mode`：查看或切换调用方式（`cli_session` / `cli_stateless`）；\n"
                "• 发送 `看原型` 或 `做个原型`：生成外部界面的低保真线框图示例；\n"
                "• 聊充分后回复 `定稿`：输出符合 9 章节标准的《软件需求规格说明（SRS）》；\n"
                "• 定稿后回复 `启动设计` 或 `/handoff`：跳过重复分析，直通移交下一阶段（`S2 架构设计`）；\n"
                "• 发送 `/status`：查看当前绑定的项目、完整模型 ID 与会话状态。"
            )
            send_pool.submit(responder.send_text, chat_id, help_msg)
            return

        sess = store.get(chat_id)
        current_session_id = sess["session_id"] or None
        current_mode = sess.get("mode", "cli_session")
        current_history = sess.get("history") or []
        is_new = (current_session_id is None) and (len(current_history) == 0)
        is_final = is_finalize_request(clean_text)

        normalized_input = normalize_user_input(clean_text)
        project_context = build_project_context_summary(sess["cwd"])
        agent_prompt = build_req_prompt(
            normalized_input,
            is_new=is_new,
            project_context_summary=project_context,
        )

        def run_task() -> None:
            log.info(
                "开始调用需求 Agent: agent=%s mode=%s cwd=%s resume=%s",
                sess["agent"],
                current_mode,
                sess["cwd"],
                bool(current_session_id),
            )
            result = run_agent_turn(
                sess["agent"],
                agent_prompt,
                sess["cwd"],
                session_id=current_session_id,
                timeout=cfg.task_timeout,
                mode=current_mode,
                history=current_history,
            )

            if result.ok:
                new_session_id = result.parsed.session_id
                if new_session_id and new_session_id != current_session_id and current_mode == "cli_session":
                    store.update_session_id(chat_id, new_session_id)

                reply_text = result.parsed.reply.strip() or "（已完成分析，但未捕获到文本回复）"
                store.append_history(chat_id, clean_text, reply_text)

                archived_path = None
                validated_ok = False
                if is_final and len(reply_text) > 100:
                    try:
                        v_res = validate_requirement_spec(reply_text)
                        validated_ok = v_res.is_valid
                        if v_res.is_valid:
                            log.info("需求定稿文件通过程序化校验 [VALIDATED]")
                        else:
                            log.warning("需求定稿文件程序化校验未通过项: %s", v_res.errors)

                        req_dir = os.path.join(sess["cwd"], "docs", "requirements")
                        os.makedirs(req_dir, exist_ok=True)
                        ts = time.strftime("%Y%m%d-%H%M%S")
                        file_name = f"REQ-{ts}.md"
                        full_path = os.path.join(req_dir, file_name)
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(reply_text + "\n")
                            if v_res.is_valid:
                                f.write("\n<!-- SPEC-VALIDATED: PASS -->\n")
                            else:
                                f.write(f"\n<!-- SPEC-VALIDATED: FAIL - {'; '.join(v_res.errors)} -->\n")
                        archived_path = full_path
                        store.set_last_archived_req(chat_id, full_path)
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
                        if validated_ok:
                            fallback_text += "\n🚀 回复 `启动设计` 或 `/handoff` 可直接移交至下一阶段（S2 架构设计）。"
                    responder.send_text(chat_id, fallback_text[:cfg.output_limit])
                else:
                    if archived_path:
                        responder.upload_text_file(chat_id, reply_text, filename=os.path.basename(archived_path))
                        if validated_ok:
                            responder.send_text(
                                chat_id,
                                f"✅ 需求规格已归档（`{os.path.basename(archived_path)}`）并通过 9 章节标准契约校验！\n"
                                f"👉 直接回复 **`启动设计`** 或 **`/handoff`**，即可跳过重复分析、直通下一阶段（**S2 架构设计**）。",
                            )
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
