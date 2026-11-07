# 定位: session.py 按 chat_id 持久化会话状态（项目路径、模型名、调用方式、会话 ID、问答历史与最近定稿路径）。
from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("autodev.req")


class ReqSessionStore:
    def __init__(
        self,
        path: str,
        default_cwd: str,
        default_agent: str,
        default_mode: str = "cli_session",
    ) -> None:
        self.path = path
        self.default_cwd = default_cwd
        self.default_agent = "claude-sonnet" if default_agent == "cc" else default_agent
        self.default_mode = default_mode
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                self._data = {
                    cid: self._ensure_defaults(dict(entry))
                    for cid, entry in (raw_data or {}).items()
                    if isinstance(entry, dict)
                }
            except Exception as e:
                log.warning("加载需求会话存储失败: %s，使用空状态", e)
                self._data = {}

    def get_active_chat_id(self, fallback: str = "web_workbench_default") -> str:
        """返回最近活跃的会话 ID（优先返回已建立 session_id 或有历史对话的飞书/Web 会话，使双端默认互通）。"""
        for cid, entry in self._data.items():
            if entry.get("session_id") or entry.get("history"):
                return cid
        if self._data:
            return next(iter(self._data.keys()))
        return fallback

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        return {cid: dict(self._ensure_defaults(dict(entry))) for cid, entry in self._data.items()}

    def _save(self) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def _ensure_defaults(self, entry: dict[str, Any]) -> dict[str, Any]:
        entry.setdefault("cwd", self.default_cwd)
        raw_agent = entry.get("agent") or self.default_agent
        entry["agent"] = "claude-sonnet" if raw_agent == "cc" else raw_agent
        entry.setdefault("mode", self.default_mode)
        entry.setdefault("session_id", "")
        entry.setdefault("history", [])
        entry.setdefault("last_archived_req", "")
        return entry

    def get(self, chat_id: str) -> dict[str, Any]:
        if chat_id not in self._data:
            self._data[chat_id] = self._ensure_defaults({})
            self._save()
        else:
            self._data[chat_id] = self._ensure_defaults(dict(self._data[chat_id]))
        return dict(self._data[chat_id])

    def reset_session(self, chat_id: str) -> None:
        curr = self.get(chat_id)
        curr["session_id"] = ""
        curr["history"] = []
        self._data[chat_id] = curr
        self._save()

    def update_session_id(self, chat_id: str, session_id: str) -> None:
        curr = self.get(chat_id)
        curr["session_id"] = session_id
        self._data[chat_id] = curr
        self._save()

    def set_cwd(self, chat_id: str, cwd: str) -> None:
        curr = self.get(chat_id)
        curr["cwd"] = cwd
        self._data[chat_id] = curr
        self._save()

    def set_agent(self, chat_id: str, agent: str) -> None:
        curr = self.get(chat_id)
        normalized = "claude-sonnet" if agent == "cc" else agent
        if curr.get("agent") != normalized:
            curr["session_id"] = ""
        curr["agent"] = normalized
        self._data[chat_id] = curr
        self._save()

    def set_mode(self, chat_id: str, mode: str) -> None:
        if mode not in ("cli_session", "cli_stateless"):
            raise ValueError(f"不支持的调用模式: {mode!r}")
        curr = self.get(chat_id)
        curr["mode"] = mode
        self._data[chat_id] = curr
        self._save()

    def append_history(
        self,
        chat_id: str,
        user_text: str,
        assistant_text: str,
        max_turns: int = 10,
    ) -> None:
        curr = self.get(chat_id)
        hist = list(curr.get("history") or [])
        hist.append({"user": user_text, "assistant": assistant_text})
        if len(hist) > max_turns:
            hist = hist[-max_turns:]
        curr["history"] = hist
        self._data[chat_id] = curr
        self._save()

    def set_last_archived_req(self, chat_id: str, req_path: str) -> None:
        curr = self.get(chat_id)
        curr["last_archived_req"] = req_path
        self._data[chat_id] = curr
        self._save()
