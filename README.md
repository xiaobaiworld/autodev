# AutoDev

AutoDev 是本机运行的需求驱动开发流程。当前设计由确定性程序控制状态与阶段，Agent 分别负责需求分析、设计、编码、审查和验收。

## 当前状态

项目处于设计阶段，已有设计文档和配置，但还没有可运行的控制程序、CLI、Web 界面、schemas、rules 或测试。当前状态和未决事项见 [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) 与 [`next.md`](next.md)。

## 在另一台 Mac 继续

AutoDev 仓库：`https://github.com/xiaobaiworld/autodev.git`。如果本地目录不存在：

```sh
mkdir -p ~/code
git clone https://github.com/xiaobaiworld/autodev.git ~/code/autodev
```

如果目录已存在，先检查分支和工作区；确认干净后再用 fast-forward-only 方式更新。随后先读 `AGENT_HANDOFF.md`，再读 `next.md` 和其中列出的设计文档。AutoDev 仓库为公开仓库；目标项目 personagent 是另一个私有仓库，需要 GitHub 登录权限。

首期目标项目通常放在 `~/code/personagent`。新克隆不会带来另一台 Mac 上的未提交改动；交接文件说明了这些改动的本地补丁位置和转移方法。该补丁没有放入公开的 AutoDev 仓库。

## 主要文档

- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)：跨机器恢复说明和当前状态快照。
- [`next.md`](next.md)：当前待办。
- [`docs/design/2026-11-02-autodev-design.md`](docs/design/2026-11-02-autodev-design.md)：流水线设计和未决问题。
- [`docs/DATA_SPEC.md`](docs/DATA_SPEC.md)：持久化数据结构。
- [`docs/DECISIONS.md`](docs/DECISIONS.md)：已接受及提议中的设计决策。
- [`config.yaml`](config.yaml)：项目、Agent、角色和轮次上限配置。
