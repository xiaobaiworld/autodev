# AutoDev — 自动化代码生成系统

给定目标，自动完成代码生成、测试、自我优化的循环系统。

## 核心设计

```
goal.md（你写，不可变）
  → planner：分解任务
  → executor：调用 Claude Code / OpenHands 执行
  → evaluator：跑测试打分
  → evolver：更新 prompt + 积累 learnings
  → 下一轮循环
```

## 架构

```
autodev/
├── core/loop.py          # 核心驱动循环
├── plugins/
│   ├── planner.py        # 任务分解插件
│   ├── executor.py       # 代码执行插件
│   ├── evaluator.py      # 结果评分插件
│   └── evolver.py        # 自我进化插件
├── workspace/
│   ├── goal.md           # 目标（只读）
│   ├── plan.md           # 当前计划（planner 生成）
│   ├── learnings.jsonl   # 执行记录与经验积累
│   └── system_prompt.md  # executor 的 prompt（evolver 会优化它）
└── config.yaml           # 插件版本配置
```

## 借鉴来源

- [AutoResearch](https://github.com/karpathy/autoresearch) — goal.md 作为唯一接口
- [Aider](https://github.com/Aider-AI/aider) — repo map 给 LLM 全局上下文
- [MetaGPT](https://github.com/FoundationAgents/MetaGPT) — 发布-订阅消息传递
- [OpenHands](https://github.com/OpenHands/OpenHands) — 沙箱执行环境
- [EvoAgentX](https://github.com/EvoAgentX/EvoAgentX) — 进化式 workflow 优化

## 支持的应用类型

- **静态网站** — 成功标准：构建通过 + Lighthouse ≥ 90 + 无死链
- **Agent 工作台** — 成功标准：单元测试通过 + 核心 E2E 流程跑通

## 状态

🚧 设计阶段 — spec 进行中
