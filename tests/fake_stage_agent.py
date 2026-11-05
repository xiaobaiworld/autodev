"""F2 用的假阶段 Agent：读事件对象指向的 input.md，按策略文件给的结论写产物和 done.json，不花额度。

用法（autoloop 的 command 插件）：python3 fake_stage_agent.py <策略文件> "<提示词>"
策略文件是 JSON：{"S3": ["REWORK", "REWORK"]} 表示 S3 前两次给 REWORK，之后用默认结论。
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS"}
OUTPUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"]}

policy_path, prompt = Path(sys.argv[1]), sys.argv[2]
subject = re.search(r"runs/R\d{8}-\d{3}/\S+", prompt).group(0).rstrip("。，).,")
sd = Path.cwd() / subject
fm = (sd / "input.md").read_text(encoding="utf-8")
field = lambda k: re.search(rf"^{k}: (.+)$", fm, re.M).group(1).strip()
stage, rnd = field("stage"), int(field("round"))
policy = json.loads(policy_path.read_text())
queue = policy.get(stage, [])
verdict = queue.pop(0) if queue else DEFAULT[stage]
policy[stage] = queue
policy_path.write_text(json.dumps(policy))
for name in OUTPUTS[stage]:
    (sd / name).write_text(f"---\nverdict: {verdict}\n---\n假产物\n", encoding="utf-8")
(sd / "done.json").write_text(json.dumps({
    "id": field("id"), "stage": stage, "round": rnd, "role": field("role"),
    "outputs": OUTPUTS[stage], "verdict": verdict,
    "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
print(f"没事可做：假 {stage} 第 {rnd} 轮 {verdict}")
