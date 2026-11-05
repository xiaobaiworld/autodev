import json
import tempfile
import unittest
from pathlib import Path

from cockpit.status import _w
from dashboard.logview import fit, format_line, latest_log, tail_lines


def j(**kw):
    return json.dumps(kw, ensure_ascii=False)


class FormatTest(unittest.TestCase):
    def test_claude_tool_use_shows_name_and_target(self):
        line = j(type="assistant", message={"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/a/b/input.md"}}]})
        self.assertEqual(format_line(line), ["工具 Read /a/b/input.md"])

    def test_claude_bash_shows_command(self):
        line = j(type="assistant", message={"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]})
        self.assertEqual(format_line(line), ["工具 Bash ls -la"])

    def test_claude_text_first_lines(self):
        line = j(type="assistant", message={"content": [{"type": "text", "text": "结论 ACCEPT\n第二行"}]})
        self.assertEqual(format_line(line), ["说 结论 ACCEPT", "  第二行"])

    def test_claude_thinking_signature_is_dropped(self):
        line = j(type="assistant", message={"content": [{"type": "thinking", "signature": "x" * 500, "thinking": "想想"}]})
        self.assertEqual(format_line(line), ["想 想想"])

    def test_claude_noise_events_dropped(self):
        for t in ("system", "rate_limit_event"):
            self.assertEqual(format_line(j(type=t, subtype="hook_started")), [])

    def test_claude_tool_result_is_short_and_one_line(self):
        long = "行1\n" + "x" * 500
        line = j(type="user", message={"content": [{"type": "tool_result", "content": long}]})
        out = format_line(line)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("得 行1"))
        self.assertLess(len(out[0]), 100)

    def test_claude_result_shows_cost(self):
        line = j(type="result", total_cost_usd=0.1969, duration_ms=35000, is_error=False)
        self.assertEqual(format_line(line), ["完成 35s $0.197"])

    def test_claude_error_result(self):
        self.assertIn("出错", format_line(j(type="result", is_error=True, total_cost_usd=0, duration_ms=1000))[0])

    def test_codex_command_and_message(self):
        done = j(type="item.completed", item={"type": "command_execution", "command": "/bin/zsh -lc \"cat x\"", "exit_code": 0})
        self.assertEqual(format_line(done), ['命令 /bin/zsh -lc "cat x" → 0'])
        self.assertEqual(format_line(j(type="item.started", item={"type": "command_execution", "command": "ls"})), [])
        msg = j(type="item.completed", item={"type": "agent_message", "text": "我先读取"})
        self.assertEqual(format_line(msg), ["说 我先读取"])

    def test_codex_file_change(self):
        line = j(type="item.completed", item={"type": "file_change", "changes": [{"path": "/x/review.md", "kind": "add"}]})
        self.assertEqual(format_line(line), ["改文件 add /x/review.md"])

    def test_codex_turn_completed_tokens(self):
        line = j(type="turn.completed", usage={"input_tokens": 301211, "output_tokens": 1265})
        self.assertEqual(format_line(line), ["完成 输入 301211 输出 1265"])

    def test_plain_text_passes_through_trimmed(self):
        self.assertEqual(format_line("没事可做：假产物"), ["没事可做：假产物"])
        self.assertEqual(format_line("   "), [])

    def test_broken_json_does_not_raise(self):
        self.assertEqual(format_line('{"type": "assistant", '), ['{"type": "assistant",'])  # 半截 JSON 当文字显示


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def mk(self, name, text="x", turn=1):
        d = self.runs / name
        d.mkdir()
        (d / f"stdout-{turn}.log").write_text(text)
        return d / f"stdout-{turn}.log"

    def test_no_runs_dir(self):
        self.assertIsNone(latest_log(self.runs / "nope"))

    def test_picks_highest_run_number_not_mtime(self):
        a = self.mk("2-1")
        self.mk("10-1")
        b = self.mk("9-1")
        b.touch()
        self.assertEqual(latest_log(self.runs).parent.name, "10-1")

    def test_prefers_later_attempt_and_turn(self):
        self.mk("5-1")
        self.mk("5-2")
        self.assertEqual(latest_log(self.runs).parent.name, "5-2")

    def test_ignores_dirs_without_log(self):
        (self.runs / "7-1").mkdir()
        self.mk("3-1")
        self.assertEqual(latest_log(self.runs).parent.name, "3-1")

    def test_tail_lines_limits_and_formats(self):
        lines = [j(type="assistant", message={"content": [{"type": "text", "text": f"第{i}句"}]}) for i in range(50)]
        p = self.mk("1-1", "\n".join(lines))
        out = tail_lines(p, 5)
        self.assertEqual(len(out), 5)
        self.assertEqual(out[-1], "说 第49句")

    def test_tail_lines_empty_file(self):
        self.assertEqual(tail_lines(self.mk("1-1", ""), 5), [])

    def test_tail_lines_only_reads_the_end_of_a_large_file(self):
        big = "\n".join(j(type="assistant", message={"content": [{"type": "text", "text": "x" * 100}]}) for _ in range(20000))
        p = self.mk("1-1", big)
        self.assertEqual(len(tail_lines(p, 3, max_bytes=20000)), 3)


if __name__ == "__main__":
    unittest.main()


class PaneTest(unittest.TestCase):
    def test_frame_without_runs(self):
        from dashboard.logpane import frame
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("还没有", frame(tmp, None, 20, 80))

    def test_frame_with_log_and_dead_hub(self):
        from dashboard.logpane import frame
        from driver.hub import HubError

        class DeadHub:
            def state(self):
                raise HubError("连不上")

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "worker" / "runs" / "4-2"
            d.mkdir(parents=True)
            (d / "stdout-1.log").write_text(j(type="assistant", message={"content": [{"type": "text", "text": "你好"}]}) + "\n")
            out = frame(tmp, DeadHub(), 20, 80)
        self.assertIn("第 4 轮（尝试 2）", out)
        self.assertIn("说 你好", out)

    def test_frame_with_hub_adds_rule_and_agent(self):
        from dashboard.logpane import frame

        class Hub_:
            def state(self):
                return {"runs": [{"id": 4, "rule": "s2-designer", "agent": "claude-opus", "state": "claimed"}]}

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "worker" / "runs" / "4-1"
            d.mkdir(parents=True)
            (d / "stdout-1.log").write_text("纯文本一行\n")
            out = frame(tmp, Hub_(), 20, 80)
        self.assertIn("s2-designer / claude-opus  claimed", out)
        self.assertIn("纯文本一行", out)


class DeadHub:
    def state(self):
        from driver.hub import HubError
        raise HubError("连不上")


class FitTest(unittest.TestCase):
    def test_fit_by_display_width(self):
        self.assertEqual(fit("abc", 10), "abc")
        out = fit("中文很长很长的一行", 9)
        self.assertLessEqual(_w(out), 9)
        self.assertTrue(out.endswith("…"))

    def test_frame_never_exceeds_pane_width(self):
        from dashboard.logpane import frame
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "worker" / "runs" / "1-1"
            d.mkdir(parents=True)
            long = j(type="assistant", message={"content": [{"type": "text", "text": "很长的一句话" * 40}]})
            (d / "stdout-1.log").write_text(long + "\n")
            out = frame(tmp, DeadHub(), 30, 62)
        self.assertTrue(all(_w(l) <= 62 for l in out.splitlines()))
        self.assertLessEqual(len(out.splitlines()), 30)

    def test_tool_result_line_number_prefix_removed(self):
        line = j(type="user", message={"content": [{"type": "tool_result", "content": "1\t---\n2\tid: R1"}]})
        self.assertEqual(format_line(line), ["得 ---"])
