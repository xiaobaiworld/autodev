# 第一版程序协议（早期草案，已被 `SPEC-REQ-STANDARD-v1.0` 取代）

> 2026-11-09 归档：本文件原位于 `docs/modules/requirements/protocol.md`，已被正式的九章节标准契约取代，移入归档；原文未改，仅修正了相对链接。

> 适用范围更新（2026-11-08）：本页是 v0.9 旧实现的协议说明。审查要求如与 [D019](../DECISIONS.md#d019-设计审查分级优先独立审核允许降级与简单复用免审) 冲突以新原则为准，但现有操作仍执行原厂商校验和审核记录约束；降级/免审的结果协议及兼容迁移尚未实现，不能伪造 PASS 替代。固定版本与确认权限保持原有可追溯性。

> 2026-11-08：main 的现行 SRS 契约优先；旧分支已实现的版本化工作台作为兼容入口保留，不用本早期草案覆盖现行默认流程。实际兼容契约见 [使用指南](../modules/requirements/usage.md)、固定基线及测试；整合方案见 [整合设计](../design/2026-11-08-requirements-merge.md)。

> **状态说明（2026-11-07 更新，C1 收敛）**：本文件中的 6 项 `checklist.json` 与 `requirements.json` 草案协议已被正式的九大章节标准契约 [`docs/specs/REQUIREMENT_SPEC_STANDARD.md`](../specs/REQUIREMENT_SPEC_STANDARD.md)（`SPEC-REQ-STANDARD-v1.0`，配套检查器 [`src/requirements/validator.py`](../../src/requirements/validator.py) 与 S2 交接器 [`src/requirements/handoff.py`](../../src/requirements/handoff.py)）取代；第 4 节关于每次调用记录开始/结束时间、耗时与原始输入输出的要求已落地于 [`src/requirements/service.py`](../../src/requirements/service.py)（`workspace/requirements/audit.jsonl`）。本文件仅作早期方案追溯保留。

## 1. 模块结构和调用方式

```text
src/requirements/
  __init__.py      # 暴露会话操作
  session.py       # 状态循环、消息和版本提交、确认及导出
  document.py      # 清单/草稿校验、生成 Markdown、计算哈希
  agent.py         # 向现有中台派发一轮，取得回复；测试注入假实现
  __main__.py      # 参数解析和展示，调用同一组 Python 操作
```

第一版使用标准库，不新增 Web 框架或数据库。文件和模块按实际实现可合并，不为每个操作创建一层服务。Python 调用构造 `SessionStore(root, invoke, wall_clock, monotonic)`，测试注入假 Agent 和时钟；API 名称沿用 design.md 第 5 节。

CLI 拟为 `PYTHONPATH=src python3 -m requirements`，支持：

| 子命令 | 行为 |
| --- | --- |
| `create --project ID --request FILE` | 保存初始文本，返回会话 ID；默认通用清单，不自动联网 |
| `reply ID --file FILE --message-id KEY` | 追加回答并置 ready，不启动模型 |
| `step ID --home DIR --config FILE` | 推进至本轮结束或出错，显示模型回复、文档路径及缺项；若已在等人则不调用 |
| `show ID` | 显示状态、最新回复、待确认项、文档版本/哈希和每次调用时段/耗时 |
| `confirm ID --version N --hash HASH` | 本地校验并确认，成功后 completed；重复同一确认返回原结果 |
| `export ID --version N` | 输出已确认版本的文件引用与归属信息 |
| `retry ID` | error 时创建新的 attempt，仍需 step 执行，不自动花额度 |
| `reopen ID` | completed 转 waiting-human，保留旧基线，下一条回答开启修订 |

`--root` 指向 AutoDev 数据根目录。会话 ID 由程序生成并校验；回复仅在 waiting-human 接受，ready/working 不接受第二条未处理消息。重复 message-id 且内容相同返回原结果，内容不同报冲突。retry 和 confirm 不接受模型输出代替人工命令。

## 2. 最小经验清单与文档结构

| 清单 ID | 问题 | 必需 | 允许不适用 |
| --- | --- | --- | --- |
| goal | 解决什么问题，本期想达到什么结果？ | 是 | 否 |
| audience | 谁会使用，在什么场景下使用？ | 是 | 否 |
| functions | 主要功能和业务规则是什么？ | 是 | 否 |
| scope | 本期做什么、不做什么？ | 是 | 否 |
| constraints | 有哪些技术、数据、时间或其他特别约束？ | 是 | 是，需说明 |
| acceptance | 怎样判断交付符合需求？ | 是 | 否 |

这只是起始清单，不代表通用软件需求完整性的权威标准。Agent 可以扩展问题，人可以纠正。待定问题列表可以为空，不能把空列表当成缺少正文。

`requirements.json` 最小结构：

```json
{
  "schema_version": 1,
  "sections": {
    "goal": "背景与目标",
    "audience": "使用者与主要场景",
    "scope": "本期范围及不做事项",
    "constraints": "特别约束或暂无已知约束的说明"
  },
  "functions": [{"id": "F1", "text": "功能和业务规则", "sources": ["message:1"]}],
  "acceptance": [{"id": "A1", "text": "可检查的验收标准", "sources": ["message:1"]}],
  "checklist": [{"id": "goal", "status": "answered", "answer": "说明", "sources": ["message:1"]}],
  "suggestions": [],
  "open_questions": []
}
```

实际清单必须覆盖当前快照里的所有项，不以示例一项为完整结果。open_questions 每项包含 id、text、blocking；suggestions 每项包含 id、text、status（proposed/accepted/rejected）。提议保留在建议区，不能未经采纳进入确定的需求正文；整版人工确认表示接受已明示的正文和清单处理状态，不能证明程序已辨别所有模型臆测。

草稿允许空字段/空列表，检查返回具体位置，例如 functions、checklist.acceptance。完成时至少一条功能和一条验收标准；约束可明确写暂无已知约束。必需项 open、不允许的不适用、缺少不适用理由、blocking=true 的问题阻止确认；非阻碍问题和未采纳建议可留在独立列表，不阻碍确认。已知占位内容按完整字段值（空白、待补充、TODO）检查，不能只因为句中出现这些字样就拒绝。

## 3. 每轮输入输出协议

传给 Agent 的 input.json 包含：本轮外部输入、此前交流、最新草稿、清单快照、本地检查缺项和输出格式说明。模型接收的资料都是数据，无权改程序状态或替人确认。第一版保留完整交流，不开发自动摘要或截断；超过配置的调用能力时返回明确错误，保留原文供人处理。

模型返回一个 JSON 对象：`reply`（对人展示的问题/说明）和 `draft`（上述结构）。raw-output.txt 原样保存模型可取得的回复文本，不记录底层 CLI 工具事件；解析失败仍保留输出，并显示 error，不损坏上一版。合法回复和草稿落盘后转 waiting-human，不因缺项自动再问模型。

中台适配复用 Hub.emit、Hub.facts、RunTracker 和现有配置；新增独立的 requirements.clarify 事件规则，subject 指向受控轮次目录；不复用读取流水线 state 的 make_invoke。Agent 只获本轮输入和输出目录，不赋予确认文件写权限。规则安装保留既有规则并遵守 workspace 锁。输出协议和权限需在 M3 假 Agent 集成中验证，不能假定新事件规则已存在。

## 4. 每次调用的落盘记录

`rounds/0001/attempt-1/` 仅含 input.json、raw-output.txt 和 call.json，不另留工具调用明细。外部原文另在 messages 和 sources 保存并关联。

```json
{
  "round": 1,
  "attempt": 1,
  "input_message_id": "message:1",
  "started_at": "2026-11-07T16:00:00+08:00",
  "finished_at": "2026-11-07T16:00:12+08:00",
  "elapsed_ms": 12000,
  "status": "succeeded",
  "error": null
}
```

status 可为 running/succeeded/failed/timed-out/interrupted。模型调用返回与本地草稿校验分开：模型正常返回但 JSON 无效时，调用仍 succeeded，会话记 invalid-output。时间由程序写，拒绝使用模型自报耗时；等待用户的分钟或天数都不计入调用耗时。

先保存原始输出，再保存有效版本，最后提交会话状态。事件记录为必要状态提交及其引用，不复制外部交互正文。崩溃恢复以已有调用结果和版本为依据：已采纳的 attempt 不再次生成版本或调用模型；无法确定是否已发送则等待人工，不声称外部调用严格恰好一次。

## 5. 验证与实施顺序

M1 先做文档协议和完成检查；M2 实现会话、假 Agent 和计时；M3 接中台及 CLI；M4 人工试用。每步按 design.md 的提交与文档同步流程收口。

计时测试注入墙上时间与单调时钟：即使墙上时钟回拨，elapsed_ms 仍由 monotonic 正确计算；超时、失败、重试各自独立；中断时未知值不填零；等待用户时重复 show/check/confirm 不新增调用或增加耗时。其余验收按 requirements.md 的 R01～R11。

完成标准：假 Agent 端到端证明“输入想法→多轮回答→结构齐全→人工确认→固定版本导出”，记录可读且时间可比较；再用真实 Agent 验证可用性。设计文档通过不等于该标准已达到。
