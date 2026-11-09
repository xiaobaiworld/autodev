import json
import tempfile
import unittest
from pathlib import Path

from cockpit.agents import parse_agents, parse_limits, parse_roles
from cockpit.controller import Controller
from cockpit.pipeline import validate_done
from cockpit.store import Run
from requirements.handoff import HandoffVerificationError, extract_srs_metadata, handoff_srs_to_pipeline
from requirements.llm_provider import (
    ModelSpec,
    build_model_argv,
    inject_stateless_history,
    load_model_registry,
    resolve_model_spec,
)
from requirements.session import ReqSessionStore

VALID_SRS_SAMPLE = """# 需求规格说明书：飞书需求看板卡片推送

## 1. 需求标识与元数据
- **需求编号**：`REQ-20261107-175000`
- **需求名称**：飞书需求看板卡片推送
- **目标项目**：`/Users/bai/code/autodev`
- **当前状态**：`VALIDATED`

## 2. 需求规模分类与需求关联网络
- **需求规模类别**：`Sub-feature`（子功能/小需求）
- **功能层级归属**：属于 `src/requirements/` 飞书交互模块下的子功能。
- **需求关联网络**：
  - `Parent`: 飞书端全生命周期交互闭环
  - `Depends-on`: `REQ-20261107-120000.md`（飞书卡片渲染基础能力）

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：流水线卡在人工关口时，用户如果不打开桌面端就不知道需要拍板。
- **业务目标**：当流水线进入等待人工拍板状态时，30 秒内向飞书发送交互卡片提醒用户决策。

## 4. 业务用例与核心流程 (Scope)
- 监听或读取 `needs-human` 状态变更并组装通知摘要。
- 发送包含需求编号、当前阶段与阻塞原因的飞书卡片。

## 5. 明确非目标与边界 (Non-goals)
- ❌ 本期不在飞书端直接修改代码文件。
- ❌ 本期不支持多人会签审批流。

## 6. 外部界面原型草图 (UI Wireframe)
```text
+------------------------------------------+
| [!] 需求 R20261107-001 等待您的拍板       |
| 阶段: S3 设计审查 | 原因: 轮次达上限      |
| [1. 继续下一轮]  [2. 打回重做]            |
+------------------------------------------+
```

## 7. 业务约束与前置依赖
- 飞书接口网络超时时记录告警日志，不阻塞或弄崩主流水线。

## 8. 可量化验收标准清单 (Acceptance Criteria)
- **场景 1（正常推送）**：当需求状态变为 `needs-human` 时，30 秒内触发一次飞书卡片推送。
- **场景 2（信息完备）**：卡片内完整展示需求 ID、当前阶段与待决定事项。
- **场景 3（防骚扰去重）**：同一轮次的同一个阻塞事件不重复轰炸推送。

## 9. 下游架构设计关注点
- 关注状态轮询或事件钩子的幂等去重位置。

<!-- SPEC-VALIDATED: PASS -->
"""


class TestRequirementsLlmAndHandoff(unittest.TestCase):
    def test_load_model_registry_and_forbid_short_alias(self):
        registry = load_model_registry()
        self.assertIn("claude-sonnet", registry)
        self.assertIn("claude-opus", registry)
        self.assertIn("codex", registry)
        self.assertIn("agy", registry)

        spec = resolve_model_spec("cc", registry)
        self.assertEqual(spec.name, "claude-sonnet")
        self.assertEqual(spec.full_model_id, "ai-code-with/claude-sonnet-5-5")
        self.assertEqual(spec.vendor, "anthropic")

        bad_spec = ModelSpec(name="bad", cli="claude", vendor="anthropic", model="sonnet")
        with self.assertRaises(ValueError):
            bad_spec.validate()

    def test_build_model_argv_session_vs_stateless(self):
        registry = load_model_registry()
        claude_spec = registry["claude-sonnet"]
        argv_sess = build_model_argv(claude_spec, "你好", cwd="/tmp", session_id="sid-123", mode="cli_session")
        self.assertIn("--model", argv_sess)
        self.assertIn("ai-code-with/claude-sonnet-5-5", argv_sess)
        self.assertIn("--resume", argv_sess)
        self.assertIn("sid-123", argv_sess)

        argv_stateless = build_model_argv(claude_spec, "你好", cwd="/tmp", session_id="sid-123", mode="cli_stateless")
        self.assertNotIn("--resume", argv_stateless)

        codex_spec = registry["codex"]
        argv_codex = build_model_argv(codex_spec, "分析需求", cwd="/tmp", session_id="thread-9", mode="cli_session")
        self.assertEqual(argv_codex[:3], ["codex", "exec", "resume"])
        self.assertIn("gpt-6-sol", argv_codex)
        self.assertIn("model_reasoning_effort=low", argv_codex)

    def test_inject_stateless_history_and_session_store(self):
        history = [
            {"user": "我想做个导出功能", "assistant": "请问是导出 CSV 还是 Excel？"},
            {"user": "1", "assistant": "好的，已确认 CSV。"},
        ]
        merged = inject_stateless_history("定稿", history)
        self.assertIn("前序多轮对话上下文", merged)
        self.assertIn("我想做个导出功能", merged)
        self.assertIn("定稿", merged)

        with tempfile.TemporaryDirectory() as tmp:
            store_path = str(Path(tmp) / "sess.json")
            store = ReqSessionStore(store_path, default_cwd=tmp, default_agent="cc")
            s0 = store.get("chat-1")
            self.assertEqual(s0["agent"], "claude-sonnet")
            self.assertEqual(s0["mode"], "cli_session")

            store.update_session_id("chat-1", "sid-abc")
            store.append_history("chat-1", "你好", "收到")
            store.set_agent("chat-1", "codex")

            s1 = store.get("chat-1")
            self.assertEqual(s1["agent"], "codex")
            self.assertEqual(s1["session_id"], "")
            self.assertEqual(len(s1["history"]), 1)

    def test_claude_markdown_prompt_cannot_be_parsed_as_options(self):
        spec = load_model_registry()["claude-opus"]
        for prompt in ("---\nproject: demo\n---\nDesign this", "--help"):
            for mode in ("cli_session", "cli_stateless"):
                with self.subTest(prompt=prompt, mode=mode):
                    argv = build_model_argv(spec, prompt, "/tmp", "sid-123", mode=mode)
                    self.assertEqual(argv[-2:], ["--", prompt])
                    self.assertIn("--permission-mode", argv[:-2])
                    self.assertEqual("--resume" in argv[:-2], mode == "cli_session")

    def test_handoff_rejects_invalid_srs(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_srs = Path(tmp) / "REQ-bad.md"
            bad_srs.write_text("# 随便写写\n内容太短且缺章节\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                handoff_srs_to_pipeline(bad_srs, root=tmp)
            self.assertIn("未通过 SRS v1.0 程序化契约校验", str(ctx.exception))

    def test_handoff_srs_directly_to_s2_and_advance_pipeline(self):
        meta = extract_srs_metadata(VALID_SRS_SAMPLE)
        self.assertEqual(meta["title"], "飞书需求看板卡片推送")
        self.assertEqual(len(meta["acceptance_criteria"]), 3)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            srs_file = root / "REQ-20261107-175000.md"
            srs_file.write_text(VALID_SRS_SAMPLE, encoding="utf-8")

            info = handoff_srs_to_pipeline(srs_file, root=root, project="autodev")
            self.assertEqual(info["stage"], "S2")
            self.assertEqual(info["round"], 1)
            self.assertEqual(info["designer_agent"], "claude-opus")
            self.assertEqual(info["reviewer_agent"], "codex")

            run_dir = Path(info["run_dir"])
            run = Run(run_dir)
            state = run.load()
            self.assertEqual(state["stage"], "S2")
            self.assertEqual(state["step"]["role"], "designer")
            self.assertEqual(state["step"]["state"], "pending")

            # 验证生成的 S1 基线完全符合流水线 S1 validate_done 契约
            s1_dummy_state = dict(
                state,
                stage="S1",
                round=1,
                step={"dir": "S1-analysis/round-1", "role": "analyst"},
            )
            self.assertIsNone(validate_done(run_dir, s1_dummy_state))

            # 用 Controller 从 S2 直接推进到 S3 再到 done，验证与主流水线 100% 兼容
            cfg_text = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8")
            agents, roles, limits = parse_agents(cfg_text), parse_roles(cfg_text), parse_limits(cfg_text)

            def fake_invoke(sd, timeout_s=60):
                inp = (sd / "input.md").read_text(encoding="utf-8")
                if "stage: S2" in inp:
                    assert "requests/active/" in inp
                    assert "S1-analysis/round-1/analysis.md" in inp
                    (sd / "design.md").write_text("---\nverdict: DONE\nsummary: ok\n---\n# 设计\n", encoding="utf-8")
                    (sd / "dev-plan.md").write_text("---\nverdict: DONE\nsummary: ok\ntasks: [t1]\n---\n# 计划\n", encoding="utf-8")
                    (sd / "prototype.md").write_text("# 原型\n不适用：无 GUI\n", encoding="utf-8")
                    (sd / "done.json").write_text(
                        json.dumps({
                            "id": state["id"],
                            "stage": "S2",
                            "round": 1,
                            "role": "designer",
                            "outputs": ["design.md", "dev-plan.md", "prototype.md"],
                            "verdict": "DONE",
                            "summary": "完成 S2 架构设计",
                            "finished_at": "2026-11-07T18:00:00+08:00",
                        }),
                        encoding="utf-8",
                    )
                elif "stage: S3" in inp:
                    (sd / "review.md").write_text(
                        "---\nverdict: PASS\nfindings: []\n---\n## 原文对照\n全部符合。\n",
                        encoding="utf-8",
                    )
                    (sd / "done.json").write_text(
                        json.dumps({
                            "id": state["id"],
                            "stage": "S3",
                            "round": 1,
                            "role": "design_reviewer",
                            "outputs": ["review.md"],
                            "verdict": "PASS",
                            "summary": "设计审查通过",
                            "finished_at": "2026-11-07T18:01:00+08:00",
                        }),
                        encoding="utf-8",
                    )
                return {"ok": True}

            ctrl = Controller(root, agents, roles, limits, invoke_fn=fake_invoke)
            ctrl.run_all(run_dir, log=lambda _: None)

            final_state = run.load()
            self.assertEqual(final_state["status"], "done")
            self.assertEqual(final_state["stage"], "S3")

    def test_handoff_rejects_project_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            srs_file = root / "REQ-test.md"
            srs_file.write_text(VALID_SRS_SAMPLE, encoding="utf-8")
            with self.assertRaises(HandoffVerificationError) as ctx:
                handoff_srs_to_pipeline(srs_file, root=root, project="personagent")
            self.assertIn("不一致，拒绝移交", str(ctx.exception))

    def test_session_project_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            sfile = Path(tmp) / "session.json"
            store = ReqSessionStore(str(sfile), default_cwd="/tmp/autodev", default_agent="claude-sonnet")
            store.set_project("chat-1", "autodev")
            store.update_session_id("chat-1", "sess-123")
            store.append_history("chat-1", "开发需求A", "好的")
            store.set_active_req_id("chat-1", "REQ-001")

            s0 = store.get("chat-1")
            self.assertEqual(s0["project"], "autodev")
            self.assertEqual(s0["session_id"], "sess-123")
            self.assertEqual(len(s0["history"]), 1)
            self.assertEqual(s0["active_req_id"], "REQ-001")

            # 切换项目：强制隔离清空历史上下文（D016 不变量）
            store.set_project("chat-1", "personagent")
            s1 = store.get("chat-1")
            self.assertEqual(s1["project"], "personagent")
            self.assertEqual(s1["session_id"], "")
            self.assertEqual(len(s1["history"]), 0)
            self.assertEqual(s1["active_req_id"], "")


if __name__ == "__main__":
    unittest.main()
