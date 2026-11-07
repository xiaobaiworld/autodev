# 定位: session.py 按 chat_id 持久化会话状态（项目路径、Agent、会话 ID）。
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("autodev.req")


class ReqSessionStore:
    def __init__(self, path: str, default_cwd: str, default_agent: str) -> None:
        self.path = path
        self.default_cwd = default_cwd
        self.default_agent = default_agent
        self._data: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                log.warning("加载需求会话存储失败: %s，使用空状态", e)
                self._data = {}

    def _save(self) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get(self, chat_id: str) -> dict[str, str]:
        if chat_id not in self._data:
            self._data[chat_id] = {
                "cwd": self.default_cwd,
                "agent": self.default_agent,
                "session_id": "",
            }
            self._save()
        return dict(self._data[chat_id])

    def reset_session(self, chat_id: str) -> None:
        curr = self.get(chat_id)
        curr["session_id"] = ""
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
