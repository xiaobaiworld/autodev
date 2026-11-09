# 定位: feishu_daemon.py AutoDev 专属需求分析师飞书机器人服务入口（委托给 requirements.service 统一编排与审计）。
from __future__ import annotations

import glob
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from requirements.config import load_req_config
from cockpit.projects import RegistryError, register_project
from requirements.handoff import HandoffVerificationError, handoff_srs_to_pipeline
from requirements.llm_provider import load_model_registry, resolve_model_spec
from requirements.presentation import FeishuCardPresenter
from requirements.responder import FeishuResponder
from requirements.service import execute_clarification_turn
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
    if not cfg.allow_users:
        log.error("%s 的 [allow] users 为空：需求机器人不允许对所有人开放（D023），请先填写白名单", config_path)
        sys.exit(1)
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
    pending_project_init = {}

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

        if clean_text in ("/project", "/项目") or clean_text.startswith("/project ") or clean_text.startswith("/cd "):
            sess = store.get(chat_id)
            parts = clean_text.split(maxsplit=1)
            if clean_text == "/project init yes":
                pending = pending_project_init.pop(chat_id, None)
                if not pending:
                    send_pool.submit(responder.send_text, chat_id, "没有待确认的项目登记请求，请重新发送 `/project add <名称> <路径>`。")
                    return
                try:
                    result = register_project(Path(__file__).resolve().parents[2], pending["name"], pending["path"], init_git=True)
                    updated = store.set_project(chat_id, pending["name"], cwd=pending["path"])
                    send_pool.submit(responder.send_text, chat_id, f"✅ 项目已登记并切换：`{updated['project']}`\n目录：`{updated['cwd']}`")
                except RegistryError as e:
                    send_pool.submit(responder.send_text, chat_id, f"⚠️ 项目登记失败：{e}")
                return
            if clean_text.startswith("/project add "):
                add = clean_text.split(maxsplit=3)
                if len(add) != 4:
                    send_pool.submit(responder.send_text, chat_id, "用法：`/project add <名称> <路径>`")
                    return
                name, raw_path = add[2], add[3]
                resolved = str(Path(raw_path).expanduser().resolve())
                allowed_dirs = [Path(d).expanduser().resolve() for d in cfg.allow_dirs]
                if not any(Path(resolved) == d or d in Path(resolved).parents for d in allowed_dirs):
                    send_pool.submit(responder.send_text, chat_id, f"⚠️ 拒绝：目录不在白名单内 `{resolved}`")
                    return
                try:
                    result = register_project(Path(__file__).resolve().parents[2], name, resolved)
                    if result["status"] == "needs_init":
                        pending_project_init[chat_id] = {"name": name, "path": resolved}
                        send_pool.submit(responder.send_text, chat_id, ("该目录不存在，是否在本地新建并执行 git init？请回复 `/project init yes`。" if result.get("missing") else "该目录不是 Git 仓库，是否执行 git init？请回复 `/project init yes`。"))
                        return
                    updated = store.set_project(chat_id, name, cwd=resolved)
                    send_pool.submit(responder.send_text, chat_id, f"✅ 项目已登记并切换：`{updated['project']}`\n目录：`{updated['cwd']}`")
                except RegistryError as e:
                    send_pool.submit(responder.send_text, chat_id, f"⚠️ 项目登记失败：{e}")
                return
            if len(parts) == 1:
                cur_proj = sess.get("project") or os.path.basename(sess["cwd"].rstrip(os.sep))
                cur_req = sess.get("active_req_id") or "待定稿"
                history_count = len(sess.get("history") or [])
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"📁 **当前项目身份与需求绑定状态**（D016）：\n\n"
                    f"• **目标项目身份**：`{cur_proj}`\n"
                    f"• **关联工程路径**：`{sess['cwd']}`\n"
                    f"• **当前活跃需求**：`{cur_req}`\n"
                    f"• **会话历史深度**：{history_count} 轮对话\n\n"
                    f"💡 发送 `/project <项目路径或名称>` 可切换；发送 `/project add <名称> <路径>` 可登记项目。切换时系统将隔离历史记忆。",
                )
                return

            target_path = parts[1].strip()
            expanded = os.path.expanduser(target_path)
            resolved = os.path.realpath(expanded) if os.path.isabs(expanded) else os.path.realpath(os.path.join(sess["cwd"], expanded))
            allowed = any(resolved == d or resolved.startswith(d + os.sep) for d in cfg.allow_dirs)
            if not allowed and os.path.exists(resolved):
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 拒绝：目录不在白名单内 `{resolved}`")
                return

            target_proj_name = os.path.basename(resolved.rstrip(os.sep)) if os.path.exists(resolved) else target_path
            target_cwd = resolved if os.path.exists(resolved) else sess["cwd"]
            updated = store.set_project(chat_id, target_proj_name, cwd=target_cwd)
            send_pool.submit(
                responder.send_text,
                chat_id,
                f"📁 **目标项目身份已切换至：`{updated['project']}`**\n"
                f"• 关联目录：`{updated['cwd']}`\n"
                f"• 上下文隔离状态：已隔离清空历史上下文（D016），新需求会话已就绪，请直接描述你的想法。",
            )
            return

        if clean_text == "/model" or clean_text == "/models" or clean_text.startswith("/model "):
            sess = store.get(chat_id)
            registry = load_model_registry()
            parts = clean_text.split(maxsplit=1)
            if len(parts) == 1:
                lines = ["🧠 **已登记大模型**（源自本机 Agent/模型注册表）："]
                for name, spec in registry.items():
                    mark = "✅ 当前" if name == sess["agent"] else "◻️"
                    lines.append(
                        f"{mark} `{name}` → `{spec.full_model_id}` (厂商: `{spec.vendor}`, CLI: `{spec.cli}`)"
                    )
                    if spec.supported_tasks:
                        lines.append('适用任务：' + '、'.join(spec.supported_tasks))
                    if spec.unsupported_tasks:
                        lines.append('不适用：' + '、'.join(spec.unsupported_tasks))
                lines.append("\n💡 发送 `/model <名称>`（如 `/model codex` 或 `/model claude-opus`）即可随时切换模型，历史问答上下文会自动保留。")
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

        if clean_text == "/type" or clean_text.startswith("/type "):
            sess = store.get(chat_id)
            parts = clean_text.split(maxsplit=1)
            if len(parts) == 1:
                src_label = "👤 人工指定" if sess.get("req_type_source") == "manual" else "🤖 Agent 自动寻找与分类"
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"🧭 **当前需求类型分类状态**\n\n"
                    f"• 当前类型：`{sess.get('req_type', 'AUTO')}`\n"
                    f"• 分类方式：{src_label}（{sess.get('req_type_reason', '')}）\n\n"
                    f"**支持双轨分类（Agent 自动识别 + 人工指定）**：\n"
                    f"• `/type auto`：交由 Agent 结合项目代码与 `deploy/` 目录自动判断（默认）；\n"
                    f"• `/type software`：锁定为 **💻 偏软件功能开发**（聚焦业务用例与 UI 线框图）；\n"
                    f"• `/type deployment`：锁定为 **🚀 偏环境部署工程**（聚焦部署脚本清单、拓扑草图与幂等验收）；\n"
                    f"• `/type hardware`：锁定为 **🔧 偏硬件与设备接入工程**（聚焦外设协议、物理接线拓扑与断连自愈）；\n"
                    f"• `/type hybrid`：锁定为 **🔗 跨类复合（软件/部署/硬件协同）**。",
                )
                return

            target_type = parts[1].strip()
            try:
                updated_sess = store.set_req_type(chat_id, target_type, source="manual")
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"✅ **需求类型已更新**：`{updated_sess['req_type']}`（{updated_sess['req_type_reason']}）",
                )
            except Exception as e:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 切换需求类型失败：{e}")
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
                proj_name = sess.get("project") or os.path.basename(sess["cwd"].rstrip(os.sep))
                autodev_root = getattr(cfg, "autodev_root", "") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                info = handoff_srs_to_pipeline(
                    srs_path=req_path,
                    root=autodev_root,
                    project=proj_name,
                )
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"🚀 **已将定稿需求直通移交至下一阶段（S2 架构设计）！**\n\n"
                    f"• **运行编号**：`{info['run_id']}`\n"
                    f"• **目标项目**：`{info['project']}`\n"
                    f"• **需求标题**：{info['title']}\n"
                    f"• **来源文档**：`{os.path.basename(info['source_srs'])}`\n"
                    f"• **当前阶段**：`{info['stage']} (第 {info['round']} 轮)` — 已自动生成 S1 基线并跳过重复分析\n"
                    f"• **架构设计（S2）**：`{info['designer_agent']}` (`{info['designer_model']}`)\n"
                    f"• **设计审查（S3）**：`{info['reviewer_agent']}` (`{info['reviewer_model']}`)\n"
                    f"• **运行目录**：`{info['run_dir']}`",
                )
            except HandoffVerificationError as e:
                send_pool.submit(
                    responder.send_text,
                    chat_id,
                    f"🛑 **移交被程序拦截（拒绝交接 S2，D016）**：\n\n"
                    f"原因：{e}\n\n"
                    f"💡 **排查指引**：\n"
                    f"1. 检查定稿文档第 1 节中的【归属项目】与【需求编号】是否完整有效；\n"
                    f"2. 当前会话绑定的项目身份为 `{sess.get('project')}`，若不符请发送 `/project <项目>` 切换后重新定稿；\n"
                    f"3. 无法核实的项目将被坚决拒绝，严禁带病移交下游。",
                )
            except Exception as e:
                send_pool.submit(responder.send_text, chat_id, f"⚠️ 移交 S2 架构设计异常：{e}")
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
            cur_req = sess.get("active_req_id") or "待定稿"
            cur_proj = sess.get("project") or os.path.basename(sess["cwd"].rstrip(os.sep))
            src_label = "👤 人工指定" if sess.get("req_type_source") == "manual" else "🤖 Agent自动分类"
            status_msg = (
                f"🤖 **AutoDev 需求分析师状态**（D016 双身份绑定）\n"
                f"• 当前目标项目：`{cur_proj}` (`{sess['cwd']}`)\n"
                f"• 当前活跃需求：`{cur_req}`\n"
                f"• 需求类型分类：`{sess.get('req_type', 'AUTO')}` ({src_label})\n"
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
                "我会基于你输入的内容以及当前项目代码，自动帮你分辨属于 **偏软件开发 (`SOFTWARE`)**、**偏环境部署 (`DEPLOYMENT`)**、**偏硬件接入 (`HARDWARE`)** 还是 **跨类复合 (`HYBRID`)**，并自动套用对应的分类模板完成需求梳理。\n\n"
                "📌 **常用辅助指令**：\n"
                "• 发送 `/new` 或 `新需求`：开启一个全新的需求会话；\n"
                "• 发送 `/type` 或 `/type auto|software|deployment|hardware|hybrid`：查看或切换需求类型（默认由 Agent 自动寻找分类，也可人工指定）；\n"
                "• 发送 `/project <路径>`：切换到其他项目目录；\n"
                "• 发送 `/model` 或 `/model <名称>`：查看或切换底层大模型（支持 Claude / Codex / Gemini 完整模型 ID）；\n"
                "• 发送 `/mode`：查看或切换调用方式（`cli_session` / `cli_stateless`）；\n"
                "• 发送 `看原型` 或 `看拓扑`：生成外部界面的低保真线框图或环境部署拓扑草图；\n"
                "• 聊充分后回复 `定稿`：按需求类型输出符合 9 章节标准的《软件/部署需求规格说明（SRS）》；\n"
                "• 定稿后回复 `启动设计` 或 `/handoff`：跳过重复分析，直通移交下一阶段（`S2 架构设计`）；\n"
                "• 发送 `/status`：查看当前绑定的项目、需求分类、完整模型 ID 与会话状态。"
            )
            send_pool.submit(responder.send_text, chat_id, help_msg)
            return

        def run_task() -> None:
            outcome = execute_clarification_turn(
                store=store,
                chat_id=chat_id,
                user_text=clean_text,
                timeout=cfg.task_timeout,
                channel="feishu",
            )
            if outcome.ok:
                feishu_presenter = FeishuCardPresenter()
                card_data = feishu_presenter.render(outcome.semantic)
                validated_ok = bool(outcome.validation and outcome.validation.is_valid)

                card_sent = responder.send_card(chat_id, card_data)
                if not card_sent:
                    log.warning("卡片发送失败，降级回退到普通文本回复")
                    fallback_text = outcome.reply_text
                    if outcome.archived_path:
                        fallback_text += f"\n\n---\n📄 **需求文档已自动归档至项目**：\n`{outcome.archived_path}`"
                        if validated_ok:
                            fallback_text += "\n🚀 回复 `启动设计` 或 `/handoff` 可直接移交至下一阶段（S2 架构设计）。"
                    responder.send_text(chat_id, fallback_text[:cfg.output_limit])
                else:
                    if outcome.archived_path:
                        responder.upload_text_file(chat_id, outcome.reply_text, filename=outcome.archived_filename)
                        if validated_ok:
                            responder.send_text(
                                chat_id,
                                f"✅ 需求规格已归档（`{outcome.archived_filename}`）并通过 9 章节标准契约校验！\n"
                                f"👉 直接回复 **`启动设计`** 或 **`/handoff`**，即可跳过重复分析、直通下一阶段（**S2 架构设计**）。",
                            )
            else:
                log.warning("需求分析未成功: %s", outcome.error)
                responder.send_text(chat_id, outcome.reply_text)

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
