# 第一版程序协议

状态：2026-11-07 实施协议，已在代码落地；使用与验证见 usage.md、verification.md。上游需求已确认为 [v0.9](baselines/v0.9.md)，含模型选择与双模型审核；循环见 [design.md](design.md)，实施顺序见 [dev-plan.md](dev-plan.md)。字段名可在对应步骤内调整，不能改变已确认的范围和完成条件。

## 1. 模块结构和调用方式

```text
src/requirements/
  __init__.py      # 暴露会话操作
  session.py       # 状态循环、消息和版本提交、确认及导出
  document.py      # 清单/草稿校验、生成 Markdown、计算哈希
  agent.py         # 按梳理／审核角色向现有中台派活；测试注入假实现
  __main__.py      # 参数解析和展示，调用同一组 Python 操作
```

第一版使用标准库，不新增 Web 框架或数据库。文件和模块按实际实现可合并，不为每个操作创建一层服务。Python 调用构造 `SessionStore(root, invoke, wall_clock, monotonic)`，测试注入假 Agent 和时钟；API 名称沿用 design.md 第 5 节。

后端 API 供 CLI、未来网页和上层项目共同使用：返回结构化状态、问题、需求版本、审核与确认信息，不打印、不交互式读取、不退出进程；异常携带稳定错误类型，CLI 自行映射为文字与退出码。会话操作不依赖当前工作目录、CLI argv 或 Web request。耗时调用与可快速读取的 status 分开；未来 HTTP 层把推进交给后台任务，调用同一 advance，不另建业务状态机。本期实现本机 HTTP 与网页，后台线程调用同一 advance，不引入任务队列；同一会话拒绝并发推进。

CLI 拟为 `PYTHONPATH=src python3 -m requirements`，支持：

| 子命令 | 行为 |
| --- | --- |
| `create --project ID --request FILE --config FILE` | 保存初始文本、清单及角色配置快照，返回会话 ID；可用 --analyst/--reviewer 指定配置中的 Agent，--review-limit 指定正整数上限，不自动联网 |
| `reply ID --file FILE --message-id KEY` | 追加回答并置 ready，不启动模型 |
| `step ID --home DIR --config FILE` | 推进梳理与有界审核修订至等人或出错，显示回复、审核结论、文档路径及缺项；若已在等人则不调用 |
| `show ID` | 显示状态、最新回复、待确认项、文档版本/哈希和每次调用时段/耗时 |
| `confirm ID --version N --hash HASH` | 本地校验当前版本与独立审核通过记录，再由人确认；成功后 completed，重复同一确认返回原结果 |
| `export ID --version N` | 输出已确认版本的文件引用与归属信息 |
| `retry ID` | error 时创建新的 attempt，仍需 step 执行，不自动花额度 |
| `reopen ID` | completed 转 waiting-human，保留旧基线，下一条回答开启修订 |

`--root` 指向 AutoDev 数据根目录。会话 ID 由程序生成并校验；回复仅在 waiting-human 接受，ready/working 不接受第二条未处理消息。重复 message-id 且内容相同返回原结果，内容不同报冲突。retry 和 confirm 不接受模型输出代替人工命令。

拟在现有 roles 中增加 requirements_analyst、requirements_reviewer，绑定已有 agents 条目；在 limits 中增加 requirements_review_rounds。创建时可选择角色对应的 Agent，使用完整模型 ID、校验厂商不同并保存有效配置快照。具体默认模型和轮次上限未定；真实调用前必须显式配置，不静默选值。运行中的模型热切换不纳入本版。

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

梳理／修订模型返回一个 JSON 对象：`reply`（对人展示的问题/说明）和 `draft`（上述结构）；修订时另逐项回应审核意见。raw-output.txt 原样保存模型可取得的回复文本，不记录底层 CLI 工具事件；解析失败仍保留输出，并显示 error，不损坏上一版。合法草稿有缺项时转 waiting-human；结构齐全时转 reviewing，不因缺项自动再问模型。

审核模型只输出审核意见，不直接改需求正文。输入包含外部原文、当前草稿及版本/整包哈希、清单、已有人决定和本轮回应；输出含 reply、所审版本/哈希、verdict（PASS/REWORK/NEEDS_HUMAN）及 findings。每项问题含稳定 ID、位置、依据、预期修正和是否阻碍通过；PASS 不能仍含阻碍项。程序保存关联审核记录；REWORK 交梳理模型回应修订，再检查与复核；NEEDS_HUMAN 或达到配置上限时展示未决问题并等人。人补充后重新形成草稿、送审；最终仍须人显式确认。两个模型对业务事实无权通过协商补造答案。

中台适配复用 Hub.emit、Hub.facts、RunTracker 和现有配置；新增独立的 requirements.clarify、requirements.revise、requirements.review 事件规则，subject 指向受控调用目录；不复用读取流水线 state 的 make_invoke。Agent 只获本次输入和输出目录，不赋予确认文件写权限。规则安装保留既有规则并遵守 workspace 锁；现有 build_rules 会丢弃旧规则，不能直接调用它生成需求模块规则。输出协议和权限需在 M5 假 Agent 集成中验证，不能假定新事件规则或权限隔离已存在。

## 4. 每次调用的落盘记录

为避免一轮中梳理、审核、修订互相覆盖，拟用 `rounds/0001/calls/0001/attempt-1/` 保存 input.json、raw-output.txt 和 call.json；call.json 增加调用角色、类型（clarify/review/revise）、有效模型配置及提示词版本引用。同一轮每次逻辑调用分配新 call 序号；失败重试只增加该 call 的 attempt。不另留工具调用明细。外部原文另在 messages 和 sources 保存并关联。下例省略角色配置等字段，只展示计时部分：

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

按 dev-plan.md 的 M1～M6 实施：文档与审核协议、会话与版本、双模型闭环、CLI、中台适配、人工试用。每步按该计划的提交与文档同步流程收口。

计时测试注入墙上时间与单调时钟：即使墙上时钟回拨，elapsed_ms 仍由 monotonic 正确计算；梳理、审核、修订、超时、失败、重试各自独立；中断时未知值不填零；等待用户时重复 show/check/confirm 不新增调用或增加耗时。其余验收按 requirements.md 的 R01～R16。

完成标准：假 Agent 端到端证明“输入想法→多轮回答→结构齐全→另一模型审核→必要的修订复核或人介入→当前版本审核通过→人工确认→固定版本导出”，记录可读且时间可比较；再用真实两模型验证可用性。设计文档通过不等于该标准已达到。

## 6. 本机网页协议（v0.9）

`serve --host 127.0.0.1 --port 8765` 提供网页；只允许 loopback。GET /api/config 返回可选模型和本机写操作令牌；GET /api/sessions 与 /api/sessions/ID 返回结构化列表或会话。POST /api/sessions 创建；POST /api/sessions/ID/reply、step、confirm、retry、reopen 对应同名应用操作；GET /api/sessions/ID/export?version=N 导出已确认版本。step 启动后台线程并立即返回 202，页面轮询状态；线程不改变业务状态机。

修改请求必须同源且携带页面取得的 CSRF 令牌，严格检查 Host/Origin，拒绝跨站请求、超大或非法 JSON；不开放 CORS。输入输出按纯文本显示，静态文件固定白名单，网页无权指定服务器文件路径或任意命令。错误返回稳定类型，页面显示可操作的恢复方式。CLI 与网页共享 backend、存储目录和锁。

实际实现说明：中台采用独立 command worker，模型只返回文本，后端负责所有文件提交；事件类型带会话命名空间，避免相互抢任务。CLI 全局 --config 在子命令前指定，create 提供 --analyst/--reviewer/--review-limit。纯本地后端校验为固定 JSON 契约的标准库校验器，无新增运行依赖。
