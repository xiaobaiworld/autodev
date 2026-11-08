# 软件需求规格说明书（部署工程规范）：AutoDev 统一网页客户端本机守护部署与健康自检工程

## 1. 需求标识与元数据
- **需求编号**：REQ-DEPLOY-WEB_DAEMON-20261108
- **需求名称**：AutoDev 统一网页客户端本机守护部署与健康自检工程
- **需求类型**：DEPLOYMENT (偏环境部署与脚本工程)
- **提出人**：项目负责人 (Owner)
- **分析师**：AutoDev 需求分析师 (req-guided-v6)
- **归属项目**：`/Users/bai/code/autodev`
- **定稿时间**：2026-11-08 11:45:00

---

## 2. 需求规模分类与需求关联网络
- 🧭 **需求类型**：`DEPLOYMENT (偏环境部署与脚本工程)` — 核心产物为可执行部署脚本、LaunchAgent 守护配置与健康检查探针脚本。
- 🏷️ **需求规模类别**：`标准功能需求 (Feature)` — 单机本机回环守护部署与自检闭环。
- 📂 **功能层级与模块归属**：归属于 `deploy/`（环境部署与守护工程目录），服务于 `src/web/server.py`。
- 🔗 **需求关联网络**：
  - `Parent（所属父需求）`：`REQ-WEB-UNIFIED_CLIENT-20261107`（全系统统一网页客户端的配套环境部署子项）
  - `Depends-on（前置依赖）`：`REQ-WEB-UNIFIED_CLIENT-20261107`（依赖 `python -m web.server` 服务入口就绪）
  - `Relates-to（业务协同）`：`deploy/install-req-bot.sh`（与飞书机器人守护进程 `com.autodev.req-bot` 采用统一的 LaunchAgent 运维规范）

---

## 3. 核心背景与业务目标 (Why & What)
- **业务背景**：AutoDev 全系统统一网页客户端（`127.0.0.1:8765`）目前已实现代码功能，但每次机器重启或终端关闭后需手工启动进程，缺少像飞书守护服务一样的开机自启、崩溃自动拉起、健康探针检查与一键卸载回滚脚本。
- **业务目标**：交付一套标准化、幂等可重复执行的本机部署脚本（`deploy/install-web-client.sh`、`deploy/check-web-health.sh`、`deploy/uninstall-web-client.sh`），实现 15 秒内完成安装或平滑重启，连续重复执行 3 次以上保持单实例零报错。

---

## 4. 业务用例与核心流程 (Scope)
- **拟生成的部署脚本与配置文件清单**：
  1. `deploy/com.autodev.web-client.plist`：macOS LaunchAgent 守护声明文件（固定绑定 `127.0.0.1:8765`）；
  2. `deploy/install-web-client.sh`：一键环境预检、plist 安装、服务平滑重启与探针验真脚本；
  3. `deploy/check-web-health.sh`：检查 `com.autodev.web-client` 进程 PID、`127.0.0.1:8765` 端口监听及 `/api/overview` HTTP 200 响应的健康探针脚本；
  4. `deploy/uninstall-web-client.sh`：一键停止守护进程、移除 LaunchAgent 软链并回滚到未安装状态的脚本。
- **五步标准部署生命周期流程**：
  1. **环境预检 (Pre-check)**：检查 `.venv/bin/python`、`src/web/server.py` 与 `logs/` 目录是否存在，缺失时立即输出可读报错并以非 0 状态码退出；
  2. **配置渲染与挂载**：将 `com.autodev.web-client.plist` 安装至 `~/Library/LaunchAgents/`，设置 `PYTHONPATH=src` 与 `KeepAlive=true`；
  3. **平滑卸载旧实例与重加载**：先执行 `launchctl unload` 清理旧实例，再执行 `launchctl load` 拉起新守护进程，标准输出与错误日志落盘至 `logs/web-client.out.log` 与 `logs/web-client.err.log`；
  4. **升级与幂等重跑 (Idempotency)**：重复运行 `install-web-client.sh` 时自动完成平滑重启，不产生重复监听进程或端口冲突；
  5. **健康探针与回滚卸载**：安装末尾自动调用 `check-web-health.sh` 校验 `/api/overview` 返回 `{"ok": true}`；需要停用时执行 `uninstall-web-client.sh` 一键卸载。

---

## 5. 明确非目标与边界 (Non-goals)
- ❌ **不监听 `0.0.0.0` 或暴露局域网/公网端口**：严格遵守安全基线，仅监听 `127.0.0.1:8765`；
- ❌ **不修改用户已有的 Herdr 空间（如 `pro1`）或飞书机器人守护配置（`com.autodev.req-bot`）**；
- ❌ **不使用 `sudo` 修改 `/Library/LaunchDaemons` 系统级目录**：仅在当前用户 `~/Library/LaunchAgents` 下操作。

---

## 6. 外部界面原型草图 (UI Wireframe)
```text
┌────────────────────────────────────────────────┐
│ [部署架构拓扑与命令交互示意]                   │
├────────────────────────────────────────────────┤
│ $ bash deploy/install-web-client.sh            │
│   ├─► [1/3] 预检 .venv 与 src/web/server.py    │
│   ├─► [2/3] 注册 ~/Library/LaunchAgents/*.plist│
│   └─► [3/3] 启动守护进程 com.autodev.web-client│
│                 │                              │
│                 ▼                              │
│  ┌──────────────────────────────────────────┐  │
│  │ launchd (KeepAlive=true)                 │  │
│  │  ├─► 进程: .venv/bin/python -m web.server│  │
│  │  ├─► 地址: http://127.0.0.1:8765         │  │
│  │  └─► 日志: logs/web-client.{out,err}.log │  │
│  └──────────────────────────────────────────┘  │
│                 │                              │
│                 ▼                              │
│ $ bash deploy/check-web-health.sh              │
│   └─► [✅ HEALTHY] HTTP 200 (/api/overview)    │
└────────────────────────────────────────────────┘
```

---

## 7. 业务约束与前置依赖
- **目标环境基线**：macOS 系统（具备 `launchctl`、`curl`），项目根目录存在 `.venv` 虚拟环境；
- **身份与权限约束**：仅需当前登录用户权限，严禁请求 root / `sudo` 权限；
- **安全与配置约束**：脚本开头强制启用 `set -euo pipefail`，严禁在部署脚本与 plist 中硬编码任何敏感凭证。

---

## 8. 可量化验收标准清单 (Acceptance Criteria)
1. **场景 1（首次一键安装与健康探针验证）**：
   - *Given* 本机 `.venv` 已就绪；
   - *When* 执行 `bash deploy/install-web-client.sh` 并调用 `bash deploy/check-web-health.sh`；
   - *Then* 脚本退出码为 `0`，`launchctl list` 中存在 `com.autodev.web-client`，且 `http://127.0.0.1:8765/api/overview` 返回 HTTP 200。
2. **场景 2（幂等重复运行验证 — 连续执行 3 次）**：
   - *Given* 服务已通过部署脚本启动；
   - *When* 连续重复执行 `bash deploy/install-web-client.sh` 3 次；
   - *Then* 3 次执行退出码均为 `0`，端口 `8765` 始终仅有 1 个监听进程，日志无 `Address already in use` 报错。
3. **场景 3（一键卸载回滚与异常预检阻断）**：
   - *Given* 服务正在运行或预检环境缺失；
   - *When* 执行 `bash deploy/uninstall-web-client.sh` 或在缺少 `.venv` 的目录下运行安装脚本；
   - *Then* 卸载后 `com.autodev.web-client` 从 `launchctl` 移除；预检缺失时输出明确中文错误并以非 `0` 退出码中止。

---

## 9. 下游架构设计关注点
1. 部署脚本切换守护进程时，若此前已有非 launchd 方式手动启动的 `web.server` 占用 8765 端口，需在预检或重启阶段安全探测并提示/平滑接管；
2. 健康探针脚本需支持重试等待（如最多等待 5 秒，每 0.5 秒轮询一次 `/api/overview`），防止进程刚拉起尚未完成端口绑定导致误判失败；
3. 下游 S4 编码阶段生成脚本后，必须设置可执行权限（`chmod +x deploy/*.sh`）并通过 `bash -n` 语法校验。

<!-- SPEC-VALIDATED: PASS -->
