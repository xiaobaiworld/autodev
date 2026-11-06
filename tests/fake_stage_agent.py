"""F2 用的假阶段 Agent：读事件对象指向的 input.md，按策略文件给的结论写产物和 done.json，不花额度。

用法（autoloop 的 command 插件）：python3 fake_stage_agent.py <策略文件> "<提示词>"
策略文件是 JSON：{"S3": ["REWORK", "REWORK"]} 表示 S3 前两次给 REWORK，之后用默认结论。
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS", "S4": "DONE", "S6": "PASS"}
OUTPUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"], "S4": ["exec-report.md"],
           "S6": ["review.md"]}

policy_path, prompt = Path(sys.argv[1]), sys.argv[2]
subject = re.search(r"runs/R\d{8}-\d{3}/\S+", prompt).group(0).rstrip("。，).,")
sd = Path.cwd() / subject
fm = (sd / "input.md").read_text(encoding="utf-8")
field = lambda k: re.search(rf"^{k}: (.+)$", fm, re.M).group(1).strip()
stage, rnd = field("stage"), int(field("round"))
if stage == "S4":  # 编码阶段：往输入里写明的代码目录里放文件，模拟真实编码
    m = re.search(r"^- 代码目录[^：\n]*：(\S+)$", fm, re.M)   # 只认“输入文件”清单里的那一行，不认任务说明里碰巧出现的字
    wd = Path(m.group(1))
    (wd / "tests").mkdir(exist_ok=True)
    (wd / "todo.py").write_text(f"VERSION = {rnd}\n", encoding="utf-8")   # 每一轮内容不同，才算“有改动”
    # 第 1 轮的测试故意失败（策略里 check_fail_first 为真），之后的轮次才通过：用来演练“检查失败 -> 退回编码 -> 修好”
    policy_now = json.loads(policy_path.read_text())
    broken = policy_now.get("check_fail_first") and rnd == 1
    (wd / "tests" / "test_todo.py").write_text(
        "import unittest\nfrom todo import VERSION\nclass T(unittest.TestCase):\n"
        f"    def test_v(self):\n        self.assertEqual(VERSION, {99 if broken else rnd})\n", encoding="utf-8")
policy = json.loads(policy_path.read_text())
hang = policy.get("hang", {})
if hang.get(stage, 0) > 0:  # F5：前 N 次在这一阶段卡住，用来触发超时
    hang[stage] -= 1
    policy["hang"] = hang
    policy_path.write_text(json.dumps(policy))
    import time
    time.sleep(3600)
queue = policy.get(stage, [])
verdict = queue.pop(0) if queue else DEFAULT[stage]
policy[stage] = queue
policy_path.write_text(json.dumps(policy))
for name in OUTPUTS[stage]:
    (sd / name).write_text(f"---\nverdict: {verdict}\n---\n假产物\n", encoding="utf-8")
(sd / "done.json").write_text(json.dumps({
    "id": field("id"), "stage": stage, "round": rnd, "role": field("role"),
    "outputs": OUTPUTS[stage], "verdict": verdict, "summary": f"假 {stage} 第 {rnd} 轮，结论 {verdict}",
    "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
print(f"没事可做：假 {stage} 第 {rnd} 轮 {verdict}")
