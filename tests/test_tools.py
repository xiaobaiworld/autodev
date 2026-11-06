import os
import tempfile
import time
import unittest
from pathlib import Path

from cockpit.tools import run_check

PY = "python3"


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
