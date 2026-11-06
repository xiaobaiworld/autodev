"""F5 用假命令：成功、挂起或返回错误，避免真实模型与额度。"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

mode, prompt = sys.argv[1], sys.argv[2]
subject = re.search(r"runs/R\d{8}-\d{3}/\S+", prompt).group(0).rstrip("。，).,")
folder = Path.cwd() / subject
fm = (folder / "input.md").read_text(encoding="utf-8")
stage = re.search(r"^stage: (\S+)", fm, re.M).group(1)
if mode == "crash":
    print("simulated process crash", file=sys.stderr)
    raise SystemExit(19)
if mode == "hang":
    time.sleep(30)
if mode == "slow" or (mode == "slow-first" and stage == "S1"):
    time.sleep(4)
field = lambda name: re.search(rf"^{name}: (.+)$", fm, re.M).group(1).strip()
stage, rnd = field("stage"), int(field("round"))
outputs = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"]}[stage]
verdict = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS"}[stage]
for name in outputs:
    body = "## 原文对照\n\n通过。\n" if stage == "S3" else "假阶段产物。\n"
    (folder / name).write_text(f"---\nverdict: {verdict}\n---\n{body}", encoding="utf-8")
done = {"schema_version": 1, "id": field("id"), "stage": stage, "round": rnd, "role": field("role"),
        "outputs": outputs, "verdict": verdict, "summary": "F5 假 Agent 完成",
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
(folder / "done.json").write_text(json.dumps(done), encoding="utf-8")
print(f"没事可做：{stage} {verdict}")
