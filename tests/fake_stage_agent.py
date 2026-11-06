"""假 Agent：按事件目录生成 S1-S4、S6、S8 产物；仅用于零额度联机验证。"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT = {"S1": "ACCEPT", "S2": "DONE", "S3": "PASS", "S4": "DONE", "S6": "PASS", "S8": "PASS"}
OUTPUTS = {"S1": ["analysis.md"], "S2": ["design.md", "dev-plan.md"], "S3": ["review.md"],
           "S4": ["exec-report.md"], "S6": ["review.md"], "S8": ["acceptance.md"]}


def todo_source():
    return '''#!/usr/bin/env python3
import json, os, sys, tempfile
from pathlib import Path

path = Path(os.environ.get("TODO_FILE", Path.home() / ".todo.json"))
def read():
    try: return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError: return []
def write(items):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(items, f, ensure_ascii=False)
        f.flush(); os.fsync(f.fileno()); tmp = f.name
    os.replace(tmp, path)
args = sys.argv[1:]
items = read()
if args and args[0] == "add" and len(args) == 2:
    item = {"id": max((x["id"] for x in items), default=0) + 1, "text": args[1], "done": False}
    items.append(item); write(items); print(item["id"])
elif args and args[0] == "list":
    for x in items:
        if not x["done"] or "--all" in args: print(f"{x['id']} {x['text']}" + (" [done]" if x["done"] else ""))
elif len(args) == 2 and args[0] == "done":
    try: number = int(args[1])
    except ValueError: print("编号无效", file=sys.stderr); sys.exit(1)
    item = next((x for x in items if x["id"] == number), None)
    if item is None: print("编号不存在", file=sys.stderr); sys.exit(1)
    item["done"] = True; write(items)
else:
    print("用法：todo add|list|done", file=sys.stderr); sys.exit(2)
'''


policy_path, prompt = Path(sys.argv[1]), sys.argv[2]
subject = re.search(r"runs/R\d{8}-\d{3}/\S+", prompt).group(0).rstrip("。，).,")
folder = Path.cwd() / subject
fm = (folder / "input.md").read_text(encoding="utf-8")
field = lambda name: re.search(rf"^{name}: (.+)$", fm, re.M).group(1).strip()
stage, rnd = field("stage"), int(field("round"))
policy = json.loads(policy_path.read_text(encoding="utf-8"))
queue = policy.get(stage, [])
verdict = queue.pop(0) if queue else DEFAULT[stage]
policy[stage] = queue
policy_path.write_text(json.dumps(policy))

if stage == "S4":
    # The S4 directory receives the code through the controller's workdir link.
    code = Path(re.search(r"- workdir：([^\n]+)", fm).group(1))
    (code / "bin").mkdir(parents=True, exist_ok=True)
    entry = code / "bin/todo"
    entry.write_text(todo_source(), encoding="utf-8")
    entry.chmod(0o755 if rnd >= 4 else 0o644)
    tests = code / "tests"
    tests.mkdir(exist_ok=True)
    if rnd == 1:
        body = "import unittest\nclass TodoTest(unittest.TestCase):\n def test_placeholder(self): self.assertEqual(1 + 1, 3)\n"
    else:
        body = '''import os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class TodoTest(unittest.TestCase):
 def test_add_list_done_and_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   env = dict(os.environ, TODO_FILE=str(Path(d) / "todo.json"))
   def call(*args): return subprocess.run([sys.executable, str(ROOT / "bin/todo"), *args], env=env, text=True, capture_output=True)
   self.assertEqual(call("add", "milk").stdout.strip(), "1")
   self.assertEqual(call("add", "report").stdout.strip(), "2")
   self.assertEqual(call("done", "1").returncode, 0)
   self.assertIn("report", call("list").stdout)
   self.assertNotIn("milk", call("list").stdout)
   self.assertIn("milk", call("list", "--all").stdout)
   self.assertNotEqual(call("done", "999").returncode, 0)
'''
    (tests / "test_todo.py").write_text(body, encoding="utf-8")

outputs = OUTPUTS[stage]
for name in outputs:
    if stage == "S3":
        body = "## 原文对照\n\n每项需求都有对应设计和计划。\n"
    elif stage == "S6":
        body = "## 原文对照\n\nPASS：逐项核对。\n"
    elif stage == "S8":
        body = "## 原文对照\n\nPASS：使用验证已通过。\n"
    else:
        body = "假产物\n"
    (folder / name).write_text(f"---\nverdict: {verdict}\nsummary: 假 {stage}\n---\n{body}", encoding="utf-8")
data = {"schema_version": 1, "id": field("id"), "stage": stage, "round": rnd, "role": field("role"),
        "outputs": outputs, "verdict": verdict, "summary": f"假 {stage} 第 {rnd} 轮 {verdict}",
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
(folder / "done.json").write_text(json.dumps(data), encoding="utf-8")
print(f"没事可做：假 {stage} 第 {rnd} 轮 {verdict}")
