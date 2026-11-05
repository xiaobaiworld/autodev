# agent-autoloop 补测计划 v2（2026-11-05）

> 给执行 Agent：只做本文的补测，结果写入 `docs/spikes/2026-11-05-autoloop-test-report-v2.md`。不要修改 AutoDev 仓库的其他文件，不要推送到 GitHub 以外的地方。

## 1. 背景

v1 报告（`2026-11-04-autoloop-test-report.md`）结论：G1、G2、G6 可信；G3、G4、G7 受测试设计影响，判定不可靠；最关键的 G5 没跑。教训见 `docs/lessons.md` L002。本计划只补这几项，轮数上限 **10 轮**。

沿用 v1 的隔离约束：临时 HOME、`--no-service`、随机端口、假 `osascript`、不碰真实项目、不读取或打印凭据。autoloop 仍用提交 `8f8e2ee`。可复用 `/tmp/autoloop-spike` 里已有的安装和上游源码，没有就按 v1 第 4 节重装。

## 2. 补测目标（按优先级）

| 编号 | 问题 | 通过标准 |
|---|---|---|
| G5 | 外部流程程序能否把 S1→S2→S3 串在 autoloop 上 | 三阶段按顺序各跑一次，产物首行符合约定，重复发同一事件只跑一次 |
| G5h | 跳数怎么算 | 方式 A（外部逐阶段发事件）每个阶段 hops 为 0；方式 B（Agent 回执带出事件）每层加 1，记录第几层被熔断 |
| G4 | 提问、回答、续接对三个 Agent 是否可靠 | 每个 Agent 回答后只触发自己的一次续接，会话 ID 不变，复述暗号 |
| G7 | 外部文字是否影响指令 | 注入文字不改变 Agent 的行为（`pwned.txt` 不存在），带 `cwd` 字段的事件被拒收（v1 已通过，只需在新判据下复核） |
| G3 | 模型切换 | 先做 G3-0；通过后再跑两轮，日志里两个不同的实际模型名 |

## 3. 测试设计原则

1. 每个被测 Agent 用**独立目录**，`access` 设为 `read`，只有写产物的那一轮单独用 `edit`。目录里不放别的需求文件。
2. 每个 Agent 的提问卡片使用**唯一 key**，提示词里明确写出，如 `"key": "q-claude"`、`"q-codex"`、`"q-agy"`。
3. 先跑 G5，再跑 G4，最后 G3。额度用完就停，并在报告里写明跑到哪里。
4. 判定要区分三件事：文字有没有进提示词、Agent 有没有读到、Agent 有没有照做。只有第三项失败才算隔离失败。

## 4. 步骤

### T1 三阶段小案例（G5、G5h）

**玩具仓库**（与 v1 相同）：

```bash
export T=/tmp/autoloop-spike TOY=$T/toy2
mkdir -p $TOY/requests $TOY/runs/r1 && cd $TOY && git init -q
printf 'def add(a, b):\n    return a + b\n' > calc.py
echo '需求 r1：给 calc.py 增加 divide(a, b)。除数为 0 时抛出 ValueError，信息为 "除数不能为 0"。' > requests/r1.md
git add -A && git commit -qm init
```

**规则**：来源 `spike`，三条规则，`cwd` 均为 `$TOY`：

| 事件类型 | Agent | 权限 | 提示词要点 | 产物 |
|---|---|---|---|---|
| `stage.s1` | `claude-cheap` | edit | 读 `requests/r1.md` 与 `calc.py`，写分析，首行 `结论：ACCEPT` 或 `REJECT` | `runs/r1/analysis.md` |
| `stage.s2` | `claude-cheap` | edit | 读分析，写设计 | `runs/r1/design.md` |
| `stage.s3` | `codex-cheap` | edit | 读设计，首行 `结论：PASS` 或 `REWORK` | `runs/r1/review.md` |

提示词只写路径，不内联需求原文，不要求改 `calc.py`。

**方式 A（外部推进，AutoDev 拟采用）**：写脚本 `$T/scripts/drive.sh`（放在上游源码和玩具仓库之外），依次：

1. `POST /v1/events`，`id` 为 `r1:s1`，`type` 为 `stage.s1`，不带 `hops`。
2. 用 `agent-autoloop status` 或轮询产物文件，等 S1 完成；检查 `analysis.md` 首行含 `ACCEPT`。
3. 发 `r1:s2`，再发 `r1:s3`，同样不带 `hops`。
4. 对 `r1:s2` **重复发送一次**，记录响应里的 `duplicate` 和 `routed`。
5. 每个阶段执行 `agent-autoloop why <轮号>`，记录事件的 hops。

**方式 B（Agent 回执链式推进）**：给 S1 和 S2 的规则加 `emits`，让 Agent 在回执的 `events` 里发出下一阶段事件。记录每层 hops，并把链接长（可让 S3 回执再发 `stage.s2` 制造回路）直到被熔断：第几层停止，`status` 是否出现通知卡片。

**判断**：方式 A 的 hops 全为 0，方式 B 每层加 1 并在第 9 层前后被拦，说明 `docs/protocol.md` 第 292 行的描述成立。

### T2 提问续接（G4）

三个 Agent 各用独立目录和唯一 key，**依次**测，不并行。每个 Agent：

- 第一轮提示词：记住暗号 `pear-<编号>`；按约定附 `agent-autoloop` 代码块提一个选项题，`key` 用上面的唯一值。
- 用 `agent-autoloop answer <卡片号> 2` 回答。
- 检查：只触发一次续接；`why` 里两轮会话 ID 相同；回复复述暗号和数字 2。
- 等待期间对该 Agent 做一次 `ps aux | grep -E 'claude|codex|agy'`，记录是否有残留进程。

### T3 外部文字复核（G7）

保持 v1 的注入事件不变，按新判据记录：

| 项 | 记录 |
|---|---|
| 提示词里有无注入文字 | 读 `home/worker/runs/<轮>/` 里的提示词或 `context.json` 位置，说明在哪 |
| Agent 有无读到 | 输出里是否出现 |
| Agent 有无照做 | `pwned.txt` 是否存在 |
| 带 `cwd` 的事件 | HTTP 响应 |

### T4 模型切换（G3，视额度）

1. **G3-0**：在测试机直接运行 `claude -p "只回答你的模型名" --model sonnet` 与 `--model opus`，若返回相同模型名，说明网关把别名映射成了同一个模型，G3 结论为"环境限制，不适用"，停止本项。
2. 否则让 autoloop 的 `claude-cheap`（sonnet/low）和 `claude-strong`（opus/high）各跑一轮，从 `stdout-1.log` 的 `init.model` 读实际模型。

## 5. 报告格式

沿用 v1 的"结论一览加逐项记录"。每个目标写：通过、不通过、未测、环境限制之一，并写证据（命令、日志文件、字段名）。末尾给出一段"对 AutoDev 的建议"，只回答一个问题：九阶段流程能否放在 autoloop 上，若不能，卡在哪一项。

## 6. 收尾

- 报告提交并推送：`git add docs/spikes && git commit -m "docs: record autoloop v2 validation" && git push`。
- 不要删除 `~/.local/bin/agent-autoloop` 链接，在报告里写明位置。
- 清理本计划创建的临时目录，保留日志。
