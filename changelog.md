# changelog

## 2026-11-05
- 驾驶舱 P0：`hc` 标签、发命令、退出、清屏、三个 Agent 启动实验，记入 `docs/lessons.md` L004、L005
- 模型名一律写完整 ID：`config.yaml`、`docs/MODELS.md`
- 驾驶舱 P1：窗格认领（标签为主、手填地址为备用）、`cockpit` 配置段、缺块或重复拒绝启动（`src/cockpit/`，`tests/`）
- 驾驶舱 P2：状态区（窗格状态映射为运行中、等待、已结束、丢失、空闲，文字渲染，每 `refresh_seconds` 重绘，`hc` 或 `state.json` 出错只显示错误并继续）
- 驾驶舱 P3（假 Agent 部分）：一次 Agent 调用（启动、发提示、等 done.json、退出并确认回到 shell），用 pid 判断是否回到 shell
