# 需求工作台使用

本机 CLI 和网页共用 `SessionStore` 后端与 `workspace/requirements/` 会话文件。命令从 AutoDev 仓库根运行；不需要安装 Python 包。

## 1. 无费用演示

```sh
PYTHONPATH=src python3 -m requirements --demo serve --port 8765
```

打开 `http://127.0.0.1:8765`。点“新需求”，填写项目和想法；示例按钮会填入完整演示资料。模拟器只识别“目标：、用户：、功能：、范围：、约束：、验收：”六类分行输入，不具备真实模型推理能力。网页始终标记“无费用演示”；演示审核通过不代表真实模型审核。真实/演示会话不能混用。

完整交互：新建→收到问题→补充→另一个角色审核→阅读当前版本→点“确认版本 N 并完成”→下载已确认版本。开启新修订后输入修改意见，会重新审核、确认；旧版本仍可导出。导入文本资料会填入输入框，发送前可检查。

## 2. 真实模式

需要项目既有、已登录的 Claude/Codex CLI，以及运行中的 agent-autoloop。模型完整 ID 和角色默认值来自 `config.yaml` 的 requirements_analyst / requirements_reviewer；审核上限默认 3，可在创建时覆盖。不要改全局模型默认值。

```sh
PYTHONPATH=src python3 -m requirements --home /path/to/autoloop/home serve --port 8765
```

真实调用会花额度。网页能分别选梳理和审核 Agent，厂商必须不同。中台规则按会话命名空间合并，已有规则保留。模型以无工具文本模式运行，不直接写需求版本或确认文件；失败/超时后明确展示错误，需手动重试。此版本不提供远程监听或多用户账号系统。

`--home` 应指向已启动的中台目录，不能把示例 `/path/to/...` 原样使用。项目现有中台的具体路径以 next.md 和本机实际状态为准。退出 `serve` 使用 Ctrl+C；如有进行中的调用，重启并点击继续以核对已有结果，不能因页面刷新就重派。

## 3. CLI 同样可以操作

全局参数放子命令之前。`ID`、`N`、`HASH` 用实际输出替换。真实推进时去掉 `--demo` 并给出 `--home`。

```sh
PYTHONPATH=src python3 -m requirements --demo create --project toy --request /path/to/idea.md
PYTHONPATH=src python3 -m requirements --demo list
PYTHONPATH=src python3 -m requirements --demo step ID
PYTHONPATH=src python3 -m requirements --demo reply ID --file /path/to/answer.md --message-id answer-1
PYTHONPATH=src python3 -m requirements --demo step ID
PYTHONPATH=src python3 -m requirements --demo --json show ID
PYTHONPATH=src python3 -m requirements --demo confirm ID --version N --hash HASH
PYTHONPATH=src python3 -m requirements --demo export ID --version N
PYTHONPATH=src python3 -m requirements --demo reopen ID
```

查看会话能看到问题、版本、审核及计时。`--json` 输出供其他程序消费，Python 可直接调用 `requirements.SessionStore`；程序调用不需要启动网页服务。CLI 与网页相同 `--root`、相同真实/演示模式时可交替操作。同一会话同时写入会明确报忙，不覆盖旧结果。

## 4. 记录与恢复

- `messages/` 保留用户原文；每轮 `calls/…/attempt-N/` 保存实际输入、原始模型回复和计时。
- `versions/` 是不可覆盖的需求版本；`reviews/` 关联审核版本/整包哈希；`confirmations/` 保存人工确认。
- `events.jsonl` 是顺序提交记录，`session.json` 是快照。异常时从已有结果恢复，不把不确定调用当作成功或自动重复收费。
- 失败与重试分别计时；用户等待不计入；中断时未知耗时保留未知。不会采集或复制 CLI 工具明细、模型内部推理及完整服务端上下文。
- 输入含敏感内容时应先自行去除凭证；原始交互仅保存在已忽略的本机 workspace，不提交 git。

## 5. 验证

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tests/f_requirements_hub.py
python3 tests/f2_pipeline.py --build
```

显式真实双模型冒烟（会花额度，使用新的空目录）：

```sh
python3 tests/f_requirements_real.py --real --root /tmp/requirements-real-new-run
```

该脚本使用匿名固定案例及独立中台，最后停在人确认前，不替用户确认真实需求。结果在所选根目录的 `result.json`。已有试用证据见 [验证报告](verification.md)。

## 6. 手机消息入口

通用消息组件见 [手机渠道接入说明](channels.md)。飞书入口已在现有机器人启用，手机可发送 `/需求` 开始；新建/回复会调用真实模型。已有会话可用 `python3 -m requirements pair ID` 签发配对码，再在飞书绑定。没有主动发测试消息，真实手机交互待用户验收；微信未接入。

## 7. 已启动的网页版（新版工作台）

本机真实入口：http://127.0.0.1:8766 ，launchd 服务 com.autodev.requirements-web，根目录为当前 AutoDev，使用独立 requirements-hub，与飞书共用真实需求会话。当前演示验证页：http://127.0.0.1:8767，数据在 /tmp/autodev-requirements-preview，临时进程不保证重启保留；8765 是更早启动的演示入口。真实入口会调用收费模型，演示入口明确标记无费用。

界面：左侧搜索和选择需求，中间交流与当前待办，右侧需求正文/审核意见/调用记录三个页签；当前版本通过审核后可确认并下载。连接飞书按钮会生成 5 分钟一次性配对码，在现有机器人发送即可；真实飞书入口不能绑定演示需求。

访问排查：上述 127.0.0.1 / localhost 是运行服务这台 Mac 的本机地址，不能在手机、另一台电脑或远程内置浏览器中直接访问。请在该 Mac 浏览器地址栏输入 `http://localhost:8766`，不要自动换成 https。2026-11-07 用户反馈打不开后复核：根页面、app.js、style.css 与 api/config 均返回 200，实际浏览器能显示工作台及会话；尚不能仅据此判断用户设备上的具体失败原因。跨设备网页访问须另行设计受保护入口，当前未开放远程监听。
