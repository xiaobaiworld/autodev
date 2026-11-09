# S4 编码阶段设计（2026-11-06）

状态：**历史设计稿，不再作为当前待实现清单。** 2026-11-09 复核：模板驱动转移、`pipeline/build`、程序步骤、S4 工作目录及差异记录已在现有代码中实现；当前契约见 [S4 阶段入口](../stages/S4-code/README.md)。下文保留 2026-11-06 的原始观察和建议，未逐项复跑当时实验，不将所有旧“未验证”一概改为通过。 依据是读了 `src/cockpit/pipeline.py`、`controller.py`、`src/driver/setup.py`、`config.yaml`、`docs/DATA_SPEC.md` 7.3 和 `docs/design/2026-11-02-autodev-design.md` 第 5 到 8 节。写这份时 Bash 不可用，所以没有跑过任何东西。

## 1. 现状里 S4 接不上的地方（已读代码确认）

- `next_move` 把 S1 到 S3 写死：S3 `PASS` 直接 `done`。要接 S4，不能只加一个阶段，转移规则本身要改。
- `STAGES`、`ORDER`、`SCOPE` 在 `pipeline.py` 里启动时只加载 `pipeline/design` 一个模板；`validate_done`、`step_dir`、`write_input`、`_new_step` 都读这个全局，不看 `state["kind"]`。
- `driver/setup.py` 的规则也只按这三个阶段生成。
- 所有步骤都当 Agent 步骤处理，没有“由程序执行的步骤”这个概念。而设计里的 S5（检查）、S7（发布候选）、S9（发布）都是程序，不是 Agent。

## 2. 提议的做法

**2.1 新类型 `pipeline/build`，不改 `pipeline/design`。** `pipeline/design` 保持“只做到设计审查”，仍然有用（只想要设计的需求）。`pipeline/build` 的模板 `templates/pipeline/build.json` 阶段顺序是 S1、S2、S3、S4，S5 之后再加。

**2.2 转移规则写进模板，程序按模板走。** 每个阶段在模板里写“结论 → 去哪”，`next_move` 变成通用函数，不再写死阶段名：

```json
"S3": {"on": {"PASS": "next", "REWORK": {"goto": "S2", "counter": "design_review_rounds"}}}
```

- `next` 表示顺序里的下一个阶段，没有下一个就是完成。
- `BLOCK` 一律转人工；S1 的 `CLARIFY` 转人工、`REJECT` 结束，这两条保留。
- 带 `counter` 的回退受 `config.yaml` 里 `limits` 同名上限约束，超限转人工。计数器名也来自模板，`start_run` 按模板初始化。
- 这样改转移只改模板，不改代码，符合 F4 的方向（一处生成）。

**2.3 阶段区分 Agent 步骤和程序步骤。** 模板里阶段写 `"runner": "agent"` 或 `"runner": "tool"`，`tool` 步骤指向一个注册的函数。S4 是 `agent`。S5 是第一个 `tool`：在 worktree 里跑检查命令，退出码决定结论，写 `check.log`。这正对应你说的“每一步都是调用一个工具”。S4 这一步先不做 `tool`，但接口要留，所以 2.2 的改动要为它预留。

**2.4 S4 的产物与结论**（取自 DATA_SPEC 7.3，不是我新定的）：角色 `coder`，产物 `exec-report.md`，结论 `DONE` / `BLOCK`，产物 frontmatter 含 `verdict`、`summary`、`files_changed[]`、`tests_added[]`。`diff.patch` 由程序生成，不让 Agent 写。

**2.5 代码写在哪：放进 `workspace/` 里。** 现在规则的 `cwd` 是 `workspace`，Agent 能写的范围就是这里。如果 worktree 放在 `workspace` 之外，Codex 的沙箱会挡住写入。所以：

- 演示项目的仓库放 `workspace/projects/todo-demo/`，每个需求一个 worktree：`workspace/projects/todo-demo/<需求号>/`。`workspace/` 已在 `.gitignore` 里，不会进 AutoDev 自己的提交。
- `input.md` 明确写“只改这个目录里的文件”。
- **git 操作全部由程序做**（建 worktree、记起点提交、生成 `diff.patch`），Agent 只改文件，不提交。这样即使沙箱不让 Agent 动 `.git`，也不影响流程。设计 5.4 要求“重做编码步骤前先回到记录的提交”，也靠程序做：起点提交写进 `state.json`。

**2.6 目标项目用演示需求 `todo`，不碰 personagent。** personagent 没有可运行代码，`checks` 也没定。`config.yaml` 加一个 `todo-demo` 项目，`checks` 先写 `python3 -m unittest discover -s tests`。

**2.7 厂商约束（历史实现说明）。** 当时 `coder` 绑 `codex`，`code_reviewer` 绑 `claude-opus`，满足当时 D008 的厂商约束；S4 本身不审查，S6 才审查。2026-11-08 起审查原则以 D019 为准，不能再把“每对都必须跨厂商”作为新的设计要求；现有校验尚未适配分级策略。

## 3. 实现顺序（每步先写测试）

1. `pipeline.py` 改成按模板取阶段和转移：`load_template` 返回对象，函数都接收它；`pipeline/design` 的行为必须不变（现有 123 个测试是回归依据）。
2. 新增 `templates/pipeline/build.json`，`kinds.py` 登记 `pipeline/build`，`start_run` 按模板初始化计数器。
3. `driver/setup.py` 的规则按模板生成，S4 的规则 `to` 绑 `coder`。
4. 程序侧：建 worktree、记起点提交、生成 `diff.patch`（新模块，单独测试，在临时 git 仓库里）。
5. 假 Agent 跑通 S1 到 S4（`tests/fake_stage_agent.py` 加 S4）。
6. 真实 Agent 跑演示需求 `todo` 到 S4，核对 `files_changed` 与 `diff.patch` 一致，且改动没有出 worktree。

## 4. 没验证、会影响做法的点

- Codex 在 `workspace-write` 沙箱里能否在嵌套目录读写、能否运行 `python3 -m unittest`：没试过。
- Claude 当 `coder` 时是否同样能在 `workspace` 子目录里写：没试过（配置里 `coder` 是 Codex，但换角色时要用）。
- 起点提交与“回到起点”的重做，在真实 Agent 中途失败时是否可靠：没试过，这是 F5 类型的验证，S4 跑通后要补。
- `limits.check_rounds` 已在 `config.yaml`，但 `parse_limits` 读哪些键、缺键时怎样，我没核对。

## 5. 范围

只做 S4（编码）。S5 检查、S6 代码审查、S7 到 S9 另做，但 2.2 和 2.3 的模板结构要为它们留位置，避免之后再改一遍。
