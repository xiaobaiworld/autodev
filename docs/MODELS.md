# 模型名规则（2026-11-05）

读这份文件的时机：改 `config.yaml` 的 `agents`、写启动命令、写模型校验、换机器、换网关、审查者与作者的厂商判断（D008）。

审查强度与优先级按 D019：争取不同模型/跨厂商，允许单模型降级和简单复用免审；不再把跨厂商或双模型作为所有任务的硬门槛。完整模型 ID、真实模型证据和不能伪称双模型的规则继续有效。现有代码中的旧厂商硬校验尚未调整。

## 1. 规则

1. `config.yaml` 的 `model` 一律写完整 ID，禁止用别名（opus、sonnet、haiku 等）。
2. 模型只通过启动参数指定，不用 `magpie <agent> <model>`。后者改的是用户的全局默认，会影响日常使用。
3. `config.yaml` 里的 ID 是本机相关的。换机器或换网关，要重新核对。
4. 启动 Agent 后以横幅显示的模型名为准，不以配置为准。配置与横幅不符，按失败处理。

## 2. 为什么

本机所有 Agent 经 magpie 网关（`127.0.0.1:3425`），模型名会被映射，和标准名不一致。

- `~/.claude/settings.json` 里 `ANTHROPIC_DEFAULT_SONNET_MODEL` 指向 `ai-code-with/claude-opus-5-5`。所以 `claude --model sonnet` 实际跑的是 Opus。别名 opus 也指向同一个模型。
- autoloop v1 的 G3（同一 CLI 切换模型）因此不通过：sonnet 与 opus 两轮的实际模型相同（见 `docs/spikes/2026-11-04-autoloop-test-report.md`）。这不是 autoloop 的问题。
- 驾驶舱 P0 实验里 `--model sonnet` 的横幅显示 Opus，发现了同一个原因（`docs/lessons.md` L004、L005）。

后果：按别名配置的"便宜模型"和"强模型"可能是同一个模型，成本和独立性（D008）的假设都会落空，而且不会报错。

## 3. 各 Agent 的指定方式

| Agent | 模型参数 | 强度参数 | 可用 ID 的来源 | 验证 |
| --- | --- | --- | --- | --- |
| Claude Code | `--model <完整 ID>` | 未测启动参数，会话内有 `/effort` | `~/.claude/settings.json` 的 `CLAUDE_CODE_MODEL_CAPABILITIES` | `--model ai-code-with/claude-sonnet-5-5`，横幅显示 Sonnet 5.5 |
| Codex | `-m <ID>` | `-c model_reasoning_effort=<档位>` | `~/.codex/magpie-desktop-models.json`（含各模型支持的档位） | `-m gpt-6-sol -c model_reasoning_effort=low`，横幅显示 `GPT-6-Sol low` |
| agy | `--model <ID>` | ID 末尾带档位，如 `claude-sonnet-5-5-low`；另有 `--effort` 未测 | `agy models` | `--model claude-sonnet-5-5-low -p '…' --dangerously-skip-permissions`，退出码 0 |

注意：
- Claude 的 ID 带 `ai-code-with/` 前缀，Codex 的同类模型也有 `ai-code-with/` 与 `codex/` 两组前缀，不要混用。
- 各模型支持的强度档位不同（例如 `glm-5.3` 只有 low、high、max），启动前要查表，不能照抄。
- agy 的默认模型在本机曾报 `User location is not supported`（L004），指定模型后可用。

## 4. 同步到哪里

| 内容 | 位置 |
| --- | --- |
| 每个 Agent 实际用的完整 ID 与强度 | `config.yaml`（唯一真源） |
| 规则、原因、各 CLI 的指定方式 | 本文 |
| 一次性的踩坑过程 | `docs/lessons.md` L004、L005 |
| 设计文档里的示例 | 只示意结构，不写具体 ID |

不要在别处再抄一份具体 ID。要查就读 `config.yaml`。

## 5. 程序要做的事（P1 起实现，现在没有代码）

主控启动时：
1. 拒绝别名：`model` 不在对应来源的可用列表里，就不启动，并打印原因和来源文件。
2. 校验强度档位在该模型支持的范围内。
3. 按实际所选模型判断 `vendor`，用于 D019 的独立性优选与如实记录；不把同厂商一律判失败。agy 能跑 Claude 模型，不能只看 CLI 名。现有 D008 硬校验的适配另行实施。
4. 每次调用后读横幅或日志里的实际模型名，与配置不符就记 `failed`。读法未验证，P3 实现时先测。

## 6. 还没验证的

- Claude 启动参数里指定强度的方式。
- agy 的 `--effort` 与 ID 末尾档位同时给出时谁生效。
- 横幅里的模型名能否稳定解析，还是改读日志。
- 换机器时 ID 是否仍然有效（homemac 未测）。
