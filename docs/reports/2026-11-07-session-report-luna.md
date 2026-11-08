# Luna 驾驶员复测报告：真实跑完 S1–S9 并与 Sonnet 对照

日期：2026-11-07 ｜ 驾驶员：本会话中的 Luna（运行平台没有提供可独立核对的完整模型 ID） ｜ 流水线运行：`R20261107-001`

这份报告把 A 层（驾驶员维护 AutoDev）和 B/C 层（流水线中的 Agent 与模型）分开记录，并对照 Sonnet 的会话报告 `2026-11-07-session-report-sonnet-5-5.md`。同一个运行号也出现在 Sonnet 报告提到的试跑里；两者位于不同 worktree 和中台数据目录，不能混为一条运行。

## 1. 结论

- Luna 驾驶的 AutoDev 在隔离演示项目 `todo` 中真实跑完 S1–S9，最终状态为 `done`。S3 第一轮 REWORK，设计返工后第二轮 PASS；S4–S8 通过；用户明确授权后 S9 在本地生成正式标签。
- 两次流水线产出的 `todo` 都覆盖了需求中的 add、list、done、JSON 存储、`TODO_FILE` 和原子写入。代码实现有差异，但本次检查没有发现会阻止需求使用的重大差别；单次运行不足以判断哪位 Agent 更好。
- Luna 运行多了 S7U 使用验证。它成功运行了命令，并在隔离 HOME 下生成 `.todo.json`；这补上了 Sonnet 的 R010 没有干净 S7U 证据的问题。
- 阶段报告存在有意义的差异：两次 S3 都抓到“没有可直接运行的 `todo` 入口”；Luna 的 S6 将“本轮不写代码”标为范围冲突，而 Sonnet 的 S6 将其解释为 S1/S2 阶段范围。用户本轮明确要求真实执行 S1–S9，因此本次继续编码和本地发布已获明确授权。
- 比较器目前不能支持严格的 token 或模型胜负结论：它没有指出 Sonnet R010 缺 S7U；Codex 的实际模型未从 Luna 日志验证；Claude 的实际模型标签有前缀差异；Luna 的 effort 记录与实际规则不符；两次 token 格式也未归一到可比口径。

## 2. 两次真实运行

| 项目 | Sonnet 基线 | Luna 复跑 |
|---|---|---|
| 驾驶员（A 层） | Claude Code，报告记为 Sonnet 5.5 | 当前会话中的 Luna；完整模型 ID 无独立运行日志 |
| 运行目录 | `~/code/autodev/workspace/runs/R20261106-010` | `~/code/autodev-rerun-luna/workspace/runs/R20261107-001` |
| 状态 | `done`，S9 | `done`，S9 |
| 需求原文 | `requests/demo-todo-cli.md` | 同一份文件，SHA-256 `9df8bf7d6e2ef78eeece1ae4af10d12a1450c378996313da3d640d4480f0fad1` |
| B/C 模型配置与强度 | Claude `ai-code-with/claude-opus-5-5`、Codex `gpt-6-sol`；Sonnet 报告记 real run 为 low | 请求相同的模型；Luna 命令和隔离中台 `rules.json` 证实有效强度为 low |
| 返工 | S3 第 1 轮 REWORK，S2 第 2 轮后 S3 PASS | 同样是 S3 第 1 轮 REWORK，S2 第 2 轮后 S3 PASS |
| S7U | R010 没有该阶段 | PASS；运行 `add/list/--all/done/错误编号`，并检查默认文件 |
| 发布 | 本地 `v0.1.0-rc.1`、`v0.1.0` | 本地 `v0.1.0-rc.1`、`v0.1.0` |

需求文件的原文最后写着“这一轮只要求产出需求分析、设计和开发计划，不写代码”。这次 S6 将它标为与后续编码冲突；用户后来明确要求真实跑完 S1–S9，故本次按明确指令继续。需求文件未被改写。两个运行号 `R20261107-001` 分别存在于不同仓库根目录和独立中台目录。

R010 执行时尚无 S7U。Sonnet 报告写作期间曾有另一条 `R20261107-001` 试跑，后来修正了 S7U 的数据文件路径；它不是这里的 Luna 运行。

## 3. 生成的 todo 代码对照

两次 S4 均运行了 4 个单元测试并通过。主要差别是实现选择和错误提示：

| 项目 | Sonnet R010 | Luna R20261107-001 |
|---|---|---|
| CLI 入口 | `bin/todo`，通过 `realpath` 找到 `src` | `bin/todo`，通过入口目录的 `../src` 找到 `src`；软链场景由测试覆盖 |
| 存储 | `data_path()` 单独封装；`mkstemp` 后写、`fsync`、`os.replace` | 路径直接在 `main()` 取；`NamedTemporaryFile`、`fsync`、`os.replace`，并清理临时文件 |
| 输出文字 | “已添加”“已完成”等 | “添加”“完成”等 |
| 非数字编号 | 程序返回非零并显示自定义错误 | `argparse type=int` 拒绝并返回 2；满足原文“非零” |
| 测试重点 | 命令、损坏数据、替换失败、外目录与软链调用 | 命令、损坏/非法数据、替换失败、PATH 与软链调用 |
| 文档 | R010 文件清单没有 README | 新增 README，说明 PATH 和软链用法 |

这些差异没有改变需求要求的主要行为。两边都通过了自己的 4 项测试。Luna 的 S7U 还实际调用了入口；S7U 记录和隔离文件见运行目录。Sonnet R010 没有相同阶段，因此这里不能比较两边的使用验证质量。

## 4. 阶段报告对照

- **S1/S2/S3**：两边的第一版设计都没有提供用户可直接调用的 `todo` 命令。两边 S3 第一轮都指出入口和验收缺失，返工后的 S3 第二轮都通过。这是本次最清楚的一致结果，但仍只是各一次样本。
- **S6 范围判断**：Sonnet 把需求末尾“不写代码”理解为分析/设计阶段的范围说明；Luna 按整份需求原文指出后续交付代码超出原文。两种阅读在文本上存在分歧。用户本轮已明确把目标定为 S1–S9，所以本次执行范围清楚。
- **S6 测试缺口**：Sonnet 指出默认路径未测、重复 ID 未校验；Luna 指出默认路径、临时文件写入中途失败、非数字编号后未再次比对文件字节三个低级问题。Luna S6 记录默认路径未测，但 S7U 的 `.todo.json` 产物实际存在，见下条。
- **S7U/S8**：Luna 的 `usage.log` 显示 7 个命令成功或按预期失败；`scratch/.todo.json` 内容为 `{"items": [{"id": 1, "text": "用默认路径", "done": false}]}`，模板还声明了 `expect_file`。外部复核可确认默认路径文件确实生成。但 S8 的 `input.md` 只提供 `usage.log`，没有传入该文件或 `expect_file` 断言结果，因此 S8 的 A2 是真实的证据传递缺口，不是验收 Agent 漏看了文件。若要让 S8 使用这项验证，S7U 应把文件断言结果写进 `usage.log`。
- **Sonnet S8**：R010 的验收 Agent 没有亲自执行命令；其结论依据代码和 S5 检查日志。Luna 的 S8 收到了 S7U 原始使用记录，因此“能否实际调用”证据更强。

## 5. A 层工作与 Sonnet 报告对照

Sonnet 报告记录了 22 个提交、212 项单元测试，并总结了 O001–O009。Luna 这条分支从 F4 基线继续完成 F5/F6、S4–S9、本地复跑和报告；本次单元测试为 130 项通过。AutoDev 源码的结构差异较明显：Luna 删除了旧 Herdr 窗格调度模块 `claim/config/invoke/main/status` 和对应测试，重写并收拢了 `pipeline/controller`，新增模板驱动程序步骤、隔离代码工作区、记录/比较与人工回复模块。212 与 130 不是同一套测试集合；数量差不能单独说明质量，需做覆盖对应表才能确认删减是否恰当。

Sonnet 的报告重点是第一次把整条流程接到 S9，并记录驾驶员开发过程中的失误；本报告重点是同一演示需求复跑、代码/阶段报告差异，以及复跑工具暴露的证据问题。报告结论方向一致：S1–S9 在本地演示项目可跑通；均不能据此证明对真实项目安全、发布或部署可用。

## 6. 比较工具的限制

本次运行 `driver.compare diff` 得到 `comparable: false`，但结果本身不能作为比较结论：

1. 它把 Claude 的 `ai-code-with/claude-opus-5-5` 与 `claude-opus-5-5` 的日志标签视为不同模型；两次配置请求的是同一完整 ID，但日志标签是否表示完全相同后端没有独立验证。
2. 它没有把 R010 缺少 S7U 列为可比性限制，也没有报告同阶段输入哈希的差异。两次 `steps` 长度不同，但工具没有给出阶段集合不同的说明。
3. `digest()` 读取当前仓库中的模板哈希，不是运行当时的快照。当前两份工作树哈希相同，不能证明 R010 运行时已有 S7U。
4. Luna 的 `record-a*.json` 把 Claude effort 记为 `high`，实际隔离中台 `rules.json` 以及命令行 `--effort low` 证明本轮有效强度为 `low`。记录使用了未覆盖 CLI 参数的原始配置。
5. Codex 的运行记录没有从日志解析出实际模型；启动命令有 `-m gpt-6-sol`，只能证明请求参数，不能独立证明实际响应模型。
6. 当前 Luna 解析器把 `total_tokens` 算为 `input_tokens + output_tokens`，没有把 Claude 单独记录的缓存输入计入总量；Sonnet 的历史记录又保留了原始 usage 字段，`driver.compare` 汇总出的 Sonnet `total_tokens` 为 0。两边总 token 不能据此对比。

因此，本报告按需求产物、阶段结果和实际文件做定性比较，不据 token 数判谁更省，也不据一次运行判谁更强。比较器及记录器应另开一项修复：保存运行时配置/模板快照、检测阶段与输入差异、记录有效 effort，并按来源统一 token 口径。

## 7. 能证明与不能证明的

**能证明：**

- 这次 Luna 运行从 S1 到 S9 达到 `done`；用户确认后的正式发布只在隔离演示仓库的本地 git 中完成。
- 两边 S3 都抓到了命令入口缺失并要求返工。
- Luna 的 S5 测试、S7U 使用脚本、S8 验收和 S9 本地发布均有运行产物。
- 本次使用脚本按预期创建了隔离默认路径 `.todo.json`。

**不能证明：**

- 不能证明 Luna 与 Sonnet 哪个整体更好；每种驾驶员/流水线组合只有一条基准运行。
- 不能比较两边 token 成本，不能确认 Codex 实际模型，也不能从模型日志前缀差异推断后端不同。
- 不能证明 S5/S7U 对任意恶意代码有安全隔离；它们只在受控演示项目上运行。
- 不能证明 S7/S9 对真实项目、远端仓库或部署环境安全；本次没有推送或部署。

## 8. 证据位置

- Luna 完整运行：`workspace/runs/R20261107-001/`
- Luna 生成项目：`workspace/projects/toy/R20261107-001/`
- Sonnet 基线运行：`~/code/autodev/workspace/runs/R20261106-010/`
- Sonnet 生成项目：`~/code/autodev/workspace/projects/toy/R20261106-010/`
- Sonnet 驾驶员报告：`docs/reports/2026-11-07-session-report-sonnet-5-5.md`
- 当前任务说明：`docs/guides/rerun-with-another-agent.md`

本次没有推送仓库或部署演示项目。生成的两个版本与对应阶段报告都保留在各自的本地运行目录。
