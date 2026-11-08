# 换一个 Agent 再跑一遍，并比较差别

读这份的时机：想用别的 Agent 或别的模型把流水线再走一遍，比较结果，分清差别来自 **Agent（命令行工具）** 还是 **大模型**。

## 0. 先分清"哪个 Agent"：有三层，别混

| 层 | 是什么 | 在哪里换 | 换了会影响什么 |
| --- | --- | --- | --- |
| A 驾驶员 | 开发和维护这套流水线的 Agent（本次是 Claude Code + Sonnet 5.5）：读代码、写代码、跑测试、提交 | 你打开哪个工具、选哪个模型 | 代码写得怎样、文档怎样、会不会犯错。**报告 `docs/reports/2026-11-07-session-report-sonnet-5-5.md` 记的就是这一层** |
| B 流水线里的 Agent | S1 到 S8 里被派活的 Claude、Codex（以及原定的 agy） | 当前 Agent 注册表及 config.yaml 角色引用覆盖 | 分析、设计、审查、编码、验收的质量 |
| C 同一个 CLI 下的模型 | 比如 Claude Code 可以跑 Opus 或 Sonnet；Codex 可以跑不同的 GPT | `config.yaml` 里 `model` 一项 | 同一个 CLI 的行为是否因模型而变 |

要回答"到底是 Agent 的区别还是大模型的区别"，**一次只变一层，别的都不动**（第 5 节）。

## 1. 再跑一遍之前要有的东西

1. 这个仓库的最新提交（`git pull`），`PYTHONPATH=src python3 -m unittest discover -s tests` 全部通过。本次结束时是 212 个。
2. agent-autoloop 检出在 `~/code/agent-autoloop`，锁定提交 `8f8e2ee`。Node 能用（联机脚本用 `node` 启动它）。
3. 流水线里要用到的命令行工具本机可用：`claude`、`codex`（`agy` 暂不支持，见第 4 节）。模型名用完整 ID，**不用别名**，本机经 magpie 网关，别名会被映射成别的模型（`docs/MODELS.md`）。
4. 一个跑着的中台和它的数据目录（本次用的是 `/tmp/autodev-demo/home`；`/tmp` 重启会没，重建方法在 `next.md` 的"换窗口接手时要知道"）。

## 2. 先不花额度：用假 Agent 验证你的环境

这些用假 Agent，不花额度，几十秒到一分钟，先跑通再跑真的。**任何一个不通过，先别跑真实的。**

```
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tests/f2_pipeline.py --build        # 假 Agent 跑完整 S1 到 S9（含真实 git 标签、S5 失败一次、S6 打回一次、S7U 抓住"没有可执行位"）
python3 tests/f2_pipeline.py --fake-rework
python3 tests/f5_crash.py hang
python3 tests/f5_crash.py crash
python3 tests/f5_crash.py ctrl-kill
python3 tests/f5_crash.py hub-kill
```

## 3. 跑真实的一遍

```
PYTHONPATH=src python3 -m driver.run \
  --home /tmp/autodev-demo/home --root ~/code/autodev \
  --request requests/demo-todo-cli.md --kind pipeline/build --effort low
```

- 花额度。`--effort low` 是把所有 Agent 的强度压到 low；要比较真实强度，去掉它，但费用会明显上升。
- 不加 `--kind` 默认只跑到设计审查（`pipeline/design`）。
- 跑到 S9 前会停下（退出码 2，状态 `needs-human`），**这是设计**：正式发布前要人批准。看板"待你决定"会写"要你批准才进 S9"。批准：

```
PYTHONPATH=src python3 -m driver.reply <需求号> continue --note "批准" --home /tmp/autodev-demo/home
```

  退回用 `rework --stage S4`，不发用 `reject`。
- 所有命令都要带 `PYTHONPATH=src`，否则找不到模块。
- `requests/demo-todo-cli.md` 是演示需求，不在 git 里（`requests/` 没有提交）。**比较用同一份需求**，一个字都别改。

## 4. 怎么换

### 4.1 换流水线里某个角色用的 Agent 或模型（B 层、C 层）

先用 `PYTHONPATH=src python3 -m cockpit.registry` 确认当前生效登记，再改相应条目：

- 默认 config/agents.toml 的 agents 登记执行器，models 登记厂商、完整 model_id、调用方式、强度和能力限制；本机覆盖规则见 docs/MODELS.md。
- defaults 将角色绑定到登记模型；config.yaml 的 roles 可保存项目覆盖引用。角色有 analyst、designer、design_reviewer、coder、code_reviewer、acceptor；所选模型需具有对应能力。

**旧实现限制（尚未适配 D019）**：程序仍校验以下作者/审查者的 `vendor` 不同：（`designer`, `design_reviewer`）、（`coder`, `code_reviewer`）、（`coder`, `acceptor`）；同厂商会报 `违反 D008`。当前规则已由 [D019](../DECISIONS.md#d019-设计审查分级优先独立审核允许降级与简单复用免审) 允许同厂商、单模型降级和简单复用免审，无须再次为原则请求例外批准。代码迁移前本指南的现有运行路径仍受该限制，不能手工伪造审核通过来绕开。

**当前流水线内置适配器只支持 `claude` 和 `codex`**。需求文本调用另支持 agy/Ollama，但不代表能承担流水线文件产物协议。`src/driver/setup.py` 的 USE 表只包含前两者，绑 agy 会报“暂不支持”。要支持新的流水线执行器：

1. 在 `USE` 里加一项，并确认 autoloop 有对应的插件（`use` 的取值）；没有的话要走它的 `command` 插件，需要自己写命令模板。
2. 把实际模型、用量从日志里取出来的解析加到 `src/driver/record.py` 的 `parse_log`（现在只认 Claude 的 `-p` 输出和 Codex 的 `exec --json`）。**不加这个，每步记录里没有实际模型和 token，比较就无从谈起。**
3. 先单独跑一轮"写一个文件"的最小任务验证（参考 `docs/spikes/2026-11-05-f1-agents-report.md` 的五条标准），确认：能无界面运行、权限不弹窗卡住、日志里的实际模型和配置一致。

模型名只写完整 ID，怎么查见 `docs/MODELS.md` 第 3 节。

### 4.2 换驾驶员（A 层）

不用改仓库里任何东西，只要换你打开的工具和模型，然后让它读这几份（顺序）：

1. `AGENTS.md`（项目目的、原则、第一步先查 `docs/TOOLS.md`）
2. `next.md`（当前状态、待你定、已知的坑、命令）
3. `docs/OPTIMIZATIONS.md`（每次流程优化和它的结果）
4. `docs/lessons.md`

然后给它的指令要具体，例如："按 `docs/guides/rerun-with-another-agent.md` 第 2、3 节把流水线跑一遍，把过程写成和 `docs/reports/2026-11-07-session-report-sonnet-5-5.md` 同样结构的报告"。

要注意的环境事实（驾驶员会遇到，我遇到过）：
- 有些工具的命令执行要过安全分类器，它依赖的模型时好时坏，会拦掉无害命令。`.claude/settings.local.json` 里有一份白名单（不在 git 里）；复合命令（`&&`、管道）不命中，要拆成单条。
- 在 Herdr 里的 `pro1` 是你自己的空间，不要动。
- 它做的每次流程改动，要求写进 `docs/OPTIMIZATIONS.md`（改了什么、为什么、怎么回退、怎么量、实际量到什么；没量过写"未测"）。

## 5. 怎么比较，才分得清是 Agent 还是模型

**核心原则：一次只变一个量，其它都固定。** 固定需求原文、config.yaml、当前 Agent 注册表（除了要比较的项）、模板哈希、代码版本和 --effort，记录本机覆盖配置来源。

| 想回答 | 做法 | 其它都不变 |
| --- | --- | --- |
| 同一个 CLI 下，换模型有没有区别 | C 层：只改有效注册表的模型条目或默认引用 | CLI、需求、模板 |
| 同一个模型，换 CLI 有没有区别 | 要求两个 CLI 真的在跑同一个模型。**这一条我没有验证过**：`docs/MODELS.md` 只说两个 CLI 的模型 ID 来源不同（Claude 看 `~/.claude/settings.json`，Codex 看 `~/.codex/magpie-desktop-models.json`），Codex 的同类模型还有 `ai-code-with/` 与 `codex/` 两组前缀。先各自启动一次，看日志里的实际模型名（`record-a1.json` 的 `actual_model`）是不是同一个，确认了才能下这个结论 | 模型、需求、模板 |
| 驾驶员换了，维护出来的代码和文档有没有区别 | A 层：换工具和模型，给同样的指令，比较第 6 节的指标 | 同一份起点提交、同一份指令 |

**一次样本不能下结论。** 同一个需求，设计审查的返工轮数在 1 到 3 轮之间波动，总 token 随之差一倍。至少每种配置跑 3 次，看分布，不看单次。

**用工具比，不要靠印象**：

```
PYTHONPATH=src python3 -m driver.record workspace/runs/<需求号>             # 一个需求的 token，按阶段、按 Agent 拆
PYTHONPATH=src python3 -m driver.compare diff workspace/runs/<基线> workspace/runs/<对照>
```

`driver.compare` 先报"可比性"：需求文本不同、步骤输入不同（比如有没有"范围"说明）、实际模型不同、有的步骤没有用量，都会列出来。**可比性有问题的差异，不要当结论。** 它读每步的 `record-a<次>.json`，所以用到的 CLI 必须能在记录里写出实际模型和 token（见 4.1 第 2 点）。

## 6. 比较什么（建议的指标）

流水线里的 Agent（B、C 层）：

| 指标 | 来源 |
| --- | --- |
| 到哪一步、有没有走到 S9 | `state.json` 的 `status`、`stage` |
| 每个关口返工几轮 | `driver.compare` 的结论序列；`counters` |
| 总 token、按阶段按 Agent | `driver.record` |
| 是否因为 BLOCK 或失败转人工，原因是什么 | `events.jsonl`、看板"待你决定" |
| 审查是否抓到了真实问题 | 读 `review.md` 的"原文对照"，对着需求原文自己判断；这一项自动化不了 |
| 做出来的东西能不能用 | S5 的 `check.log`、S7U 的 `usage.log`；以及你自己用一遍 |

驾驶员（A 层）：

| 指标 | 怎么看 |
| --- | --- |
| 单元测试从多少变到多少，最后是否全过 | `python3 -m unittest discover -s tests` |
| 联机场景是否全过 | 第 2 节的几条命令 |
| 犯了哪些错，怎么发现的 | 参考报告第 6 节的格式 |
| 没验证的事有没有如实写"未验证" | 读它的报告 |
| 有没有替你做了不该替你做的决定（比如批准发布） | 读它的报告第 7 节 |

## 7. 已知的坑（别重踩）

- 模型别名会被映射成别的模型。只写完整 ID。
- 用 `| tail` 的命令，退出码是 `tail` 的，不是脚本的。别靠退出码判断成败，看输出的最后一行"通过/未通过"。
- 测试和修改测试的编辑一起发出去，会读到旧文件，得到假通过。编辑落盘后单独再跑一次。
- 临时的 `python3 -c` 和 `cp`、`mkdir` 不在白名单里，在会拦命令的环境里会被拦。
- 写大文件时内容可能被截断，写完要读一遍确认。
- 联机脚本里 `workspace/projects/` 下的演示代码和本地 git 标签不进 AutoDev 的提交（已在 `.gitignore`）。
- S7、S9 只在演示项目的**本地** git 里打标签，没有推送、没有部署。接真实项目前必须先问人。

## 7.1 使用脚本是人写的，写错了会冤枉 Agent（S7U）

S7U 的使用脚本（`templates/pipeline/build.json` 的 S7U）现在是演示项目 `todo` 的。这次会话里我写错过一次：把数据文件指向一个不存在的子目录，而需求并没有要求程序自己建目录，结果真实 Codex 写的、并不违反需求的代码被判 FAIL，白白多跑一轮。假 Agent 的代码恰好会建目录，所以单元测试和联机验证都没发现。

换项目、或换 Agent 重跑时：
- **使用脚本只测需求原文明确要求的行为**，不要加需求没写的前提（建目录、特定输出格式）。
- 换了 Agent 之后，先看 `usage.log` 里的第一个 FAIL：是代码不符合需求，还是脚本多要求了。判断不了就别当成 Agent 的缺陷。
- 改了使用脚本，之前的运行结果就不再和之后的可比（`driver.compare` 会因模板哈希不同报出来）。

## 8. 如果想让别的 Agent 当"流水线里的验收者"（原设计是 agy）

现在 `acceptor` 绑的是 Claude（`docs/DECISIONS.md` D015）。换回 agy 之前要先做三件事：

1. 验证 agy 的实际模型和用量能不能从它的输出里取到（`record.py` 的解析）。
2. `setup.py` 支持它（`USE` 表加 `agy`，或者走 autoloop 的 `command` 插件）。
3. 确认它能在只读、无界面的方式下完成"读 `usage.log`、写 `acceptance.md`"，并且遵守不改代码。

然后只改 `config.yaml` 里 `acceptor` 一行，并在 `docs/OPTIMIZATIONS.md` 登记一条，和 R010 那次（Claude 验收）比。
