# F2 报告：我们的流水线驱动跑在 autoloop 上（2026-11-05）

脚本：`tests/f2_pipeline.py`（真实 Agent）、`tests/f2_pipeline.py --fake-rework`（假 Agent）。流转、轮次、校验由我们的 `Controller` 决定；`src/driver/` 只负责发事件、读事实流、判断中台那一轮有没有结束。

## 结果

| 项 | 方式 | 结果 | 证据 |
| --- | --- | --- | --- |
| S1 到 S3 跑通 | 真实 Agent，玩具需求 `divide(a, b)` | 通过，约 157 秒 | S1 ACCEPT、S2 DONE、S3 PASS，状态 done |
| 实际模型 | 日志与 Codex 会话记录 | S1、S2 为 `claude-opus-5-5`，S3 为 `gpt-6-sol`，与配置一致 | 日志 `"model"` 字段；`~/.codex/sessions` 的 `turn_context` |
| 作者与审查者厂商不同 | 启动时 `check_vendors` | 配置里 anthropic 对 openai，放行；同厂商拒绝启动由单元测试覆盖 | `tests/test_controller.py` |
| REWORK 轮次上限 | 假 Agent，S3 一直 REWORK，真实中台 | 通过：S2、S3 各 3 轮后停在 needs-human，有 `limit.exceeded` | `S2-design/round-1..3` |
| 产物契约 | `validate_done` | done.json 的 id、阶段、轮次、角色、verdict、产物文件都核对 | 单元测试加两次端到端 |

## 没验证的

- 真实审查者给出 REWORK 并写出实质意见、设计者在下一轮据此修改：真实运行里 S3 一次 PASS，`findings` 为空，设计也很简单；REWORK 回路只用假 Agent 测过，没有测"回应意见"这一步。
- 中台把失败的轮次放回队列重试（`attempts`），以及驱动超过 `step_retries` 后取消那一轮：只有 `RunTracker` 和 `runner` 的单元测试，没在真实中台上触发过。
- 中台或驱动被强杀后的恢复：属于 F5。
- 驱动每次都从事实日志序号 0 重放（`runner.py` 有 `ponytail:` 标注），历史大了会慢。

## 设计上的取舍

- 事件 id 带尝试序号（`<需求>-<阶段>-r<轮>-a<次>`）：中台对同一 id 去重，重试若复用 id 拿不到新的一轮。
- 事件的 `subject` 放步骤目录（`runs/<需求>/<阶段>/round-N`），规则的 `cwd` 是 workspace，Agent 的提示词只说"读 subject 目录下的 input.md"。外部文字不进提示词的规则保持不变。
- 中台状态 `failed` 不是终点，会回到 `queued` 并带 `attempts`；连续失败 10 次后中台自己把那一轮标为 `cancelled`，驱动把它当步骤失败。
