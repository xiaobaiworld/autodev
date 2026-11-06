import os
import tempfile
import time
import unittest
from pathlib import Path

from cockpit.tools import run_check

PY = "python3"


class ReleaseToolTest(unittest.TestCase):
    """S7 发布候选 / S9 正式发布：只在本地 git 里打标签，不推送。"""

    def setUp(self):
        from cockpit.workdir import prepare
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wd, self.sd = self.root / "wd", self.root / "sd"
        prepare(self.wd, {"todo.py": "x = 1\n"})
        self.sd.mkdir()
        self.state = {"id": "R1"}

    def tearDown(self):
        self.tmp.cleanup()

    def rel(self, tag, version="0.1.0", **extra):
        from cockpit.tools import run_release
        return run_release(self.wd, self.sd, dict({"tag": tag, "version": version}, **extra), self.state)

    def tags(self):
        from cockpit.workdir import list_tags
        return sorted(list_tags(self.wd))

    def test_rc_numbers_count_up_and_do_not_touch_the_changelog(self):
        self.assertEqual(self.rel("rc")["verdict"], "PASS")
        self.assertEqual(self.rel("rc")["verdict"], "PASS")
        self.assertEqual(self.tags(), ["v0.1.0-rc.1", "v0.1.0-rc.2"])
        self.assertFalse((self.wd / "CHANGELOG.md").exists())
        self.assertIn("v0.1.0-rc.2", (self.sd / "release.log").read_text())

    def test_rc_numbering_is_per_version(self):
        self.rel("rc", "0.1.0")
        self.rel("rc", "0.2.0")
        self.assertEqual(self.tags(), ["v0.1.0-rc.1", "v0.2.0-rc.1"])

    def test_final_tags_and_writes_changelog_once(self):
        r = self.rel("final", note="命令行待办")
        self.assertEqual((r["verdict"], self.tags()), ("PASS", ["v0.1.0"]))
        text = (self.wd / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## v0.1.0", text)
        self.assertIn("R1：命令行待办", text)

    def test_final_never_overwrites_an_existing_tag(self):
        self.rel("final")
        before = (self.wd / "CHANGELOG.md").read_text(encoding="utf-8")
        r = self.rel("final")
        self.assertEqual(r["verdict"], "BLOCK")                          # 交给人，不覆盖
        self.assertEqual((self.wd / "CHANGELOG.md").read_text(encoding="utf-8"), before)
        self.assertEqual(self.tags(), ["v0.1.0"])

    def test_tag_points_at_a_commit_that_includes_the_final_changes(self):
        import subprocess
        (self.wd / "late.py").write_text("y = 2\n")                      # 标签之前还没提交的改动
        self.rel("rc")
        shown = subprocess.run(["git", "show", "--stat", "--format=", "v0.1.0-rc.1"], cwd=self.wd,
                               capture_output=True, text=True).stdout
        self.assertIn("late.py", shown)

    def test_bad_specs_are_refused_before_touching_git(self):
        for tag, version in (("beta", "0.1.0"), ("rc", "1.0"), ("final", ""), ("rc", "v0.1.0")):
            with self.subTest(tag=tag, version=version):
                with self.assertRaises(ValueError):
                    self.rel(tag, version)
        self.assertEqual(self.tags(), [])

    def test_template_without_tag_or_version_is_refused_at_load_time(self):
        import json
        from unittest import mock
        from cockpit import pipeline
        t = pipeline.load_template("pipeline/build")
        t["stages"]["S5"].update(runner="tool", tool="release")           # 借现成的阶段换成缺字段的 release
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "build.json").write_text(json.dumps({k: v for k, v in t.items() if k != "extends"}, ensure_ascii=False))
            (Path(d) / "design.json").write_text((pipeline.TEMPLATES / "design.json").read_text(encoding="utf-8"))
            with mock.patch.object(pipeline, "TEMPLATES", Path(d)):
                with self.assertRaisesRegex(ValueError, "release 工具需要 tag"):
                    pipeline.load_template("pipeline/build")


class RunCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wd, self.sd = self.root / "wd", self.root / "sd"
        (self.wd / "tests").mkdir(parents=True)
        self.sd.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_test(self, body):
        (self.wd / "tests" / "test_x.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n"
                                                    + "".join(f"        {l}\n" for l in body.splitlines()))

    def check(self, timeout=20, command=None):
        spec = {"command": command or [PY, "-m", "unittest", "discover", "-s", "tests"]}
        return run_check(self.wd, self.sd, spec, timeout)

    def test_passing_tests_pass_and_log_is_written(self):
        self.write_test("self.assertEqual(1, 1)")
        r = self.check()
        self.assertEqual(r["verdict"], "PASS")
        log = (self.sd / "check.log").read_text()
        self.assertIn("Ran 1 test", log)
        self.assertIn("退出码 0", log)

    def test_failing_tests_fail_with_the_reason_in_the_log(self):
        self.write_test("self.assertEqual(1, 2)")
        r = self.check()
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("AssertionError", (self.sd / "check.log").read_text())

    def test_zero_tests_is_not_a_pass(self):
        r = self.check()                                    # tests 目录里什么都没有：unittest 退出码 5，或 Ran 0 tests
        self.assertEqual(r["verdict"], "FAIL")

    def test_exit_zero_but_zero_tests_is_not_a_pass(self):
        r = self.check(command=[PY, "-c", "print('Ran 0 tests in 0.000s')"])    # 退出码 0，但没跑任何测试
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("一个测试都没有跑", r["summary"])

    def test_timeout_kills_the_whole_process_group(self):
        marker = self.root / "child_alive"
        script = ("import subprocess,sys,time\n"
                  f"subprocess.Popen([sys.executable,'-c',\"import time,pathlib;time.sleep(3);pathlib.Path(r'{marker}').write_text('x')\"])\n"
                  "time.sleep(60)\n")
        t0 = time.time()
        r = self.check(timeout=1, command=[PY, "-c", script])
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("超时", (self.sd / "check.log").read_text())
        self.assertLess(time.time() - t0, 10)
        time.sleep(4)
        self.assertFalse(marker.exists())                   # 子进程也被杀了，没有残留

    def test_environment_is_minimal_and_home_is_a_scratch_dir(self):
        os.environ["AUTODEV_SECRET_PROBE"] = "不该被带进去"
        try:
            code = ("import os,sys\n"
                    "print('SECRET' if 'AUTODEV_SECRET_PROBE' in os.environ else 'no-secret')\n"
                    "print('HOME=' + os.environ['HOME'])\n")
            self.check(command=[PY, "-c", code])
        finally:
            del os.environ["AUTODEV_SECRET_PROBE"]
        log = (self.sd / "check.log").read_text()
        self.assertIn("no-secret", log)
        self.assertNotIn("SECRET\n", log.replace("no-secret", ""))
        self.assertIn(f"HOME={self.sd / 'scratch'}", log)

    def test_command_runs_in_the_workdir_and_src_is_importable(self):
        (self.wd / "src").mkdir()
        (self.wd / "src" / "mod.py").write_text("VALUE = 7\n")
        self.write_test("from mod import VALUE\nself.assertEqual(VALUE, 7)")
        self.assertEqual(self.check()["verdict"], "PASS")

    def test_python_cache_is_not_written_into_the_workdir(self):
        (self.wd / "src").mkdir()
        (self.wd / "src" / "mod.py").write_text("VALUE = 1\n")
        self.write_test("import mod")
        self.check()
        self.assertEqual(list(self.wd.rglob("__pycache__")), [])

    def test_bad_command_specs_are_refused_before_running_anything(self):
        for bad in (None, [], "python3 -m unittest", ["ok", 3]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    run_check(self.wd, self.sd, {"command": bad}, 5)

    def test_missing_executable_is_a_tool_error_not_a_fail_verdict(self):
        with self.assertRaises(FileNotFoundError):          # 命令本身不存在是工具/配置问题，交给控制器按步骤失败处理
            self.check(command=["definitely-not-a-real-binary-xyz"])


if __name__ == "__main__":
    unittest.main()
