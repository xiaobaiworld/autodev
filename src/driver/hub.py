"""和 agent-autoloop 中台通信：发事件、读事实日志、判断某个事件的那一轮到了哪一步。

只用标准库。中台的协议见 ~/code/agent-autoloop/docs/protocol.md；这里只用到
POST /v1/events、GET /v1/stream、POST /v1/runs/<n>/cancel 三个口子。
"""
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

# 轮次在中台里的终点。failed 不是终点：中台会把它放回 queued 并带上 attempts、error 重试。
TERMINAL = {"done", "nothing", "cancelled"}


class HubError(Exception):
    pass


def load_config(home):
    d = json.loads((Path(home) / "config.json").read_text(encoding="utf-8"))
    return {"url": d["url"], "owner": d["owner"], "source": d["source"]["key"]}


class RunTracker:
    """按序喂入事实，维护 事件 -> 轮次 的最新状态。纯逻辑，不碰网络，方便用录下来的事实测试。"""

    def __init__(self):
        self.events = {}      # (source 内的) 事件 key -> 事件 id
        self.links = {}       # 事件 id -> 轮次 id
        self.runs = {}        # 轮次 id -> 最新的行
        self.seq = 0

    def feed(self, fact):
        self.seq = max(self.seq, fact.get("seq", 0))
        for c in fact.get("changes", []):
            row = c.get("row")
            if row is None:
                continue
            t = c.get("table")
            if t == "events":
                self.events[row["key"]] = row["id"]
            elif t == "run_events":
                self.links[row["event_id"]] = row["run_id"]
            elif t == "runs":
                self.runs[row["id"]] = row

    def run_of(self, event_key):
        eid = self.events.get(event_key)
        rid = self.links.get(eid)
        return self.runs.get(rid) if rid is not None else None

    def status(self, event_key):
        """返回 None（还没有对应的轮次）或 dict：
        state=running|ended|retrying，另有 run、attempts、error、summary。"""
        r = self.run_of(event_key)
        if r is None:
            return None
        base = {"run": r["id"], "attempts": r.get("attempts") or 0, "error": r.get("error"),
                "summary": r.get("summary"), "raw": r["state"]}
        if r["state"] in TERMINAL:
            return dict(base, state="ended")
        if r["state"] == "queued" and base["attempts"] > 0:
            return dict(base, state="retrying")
        return dict(base, state="running")


class Hub:
    def __init__(self, cfg):
        self.url, self.owner, self.source = cfg["url"], cfg["owner"], cfg["source"]

    def _call(self, path, key, body=None, method=None, timeout=15):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, data=data, method=method or ("POST" if data else "GET"),
                                     headers={"authorization": f"Bearer {key}", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raise HubError(f"{path} 返回 {e.code}：{e.read().decode()[:200]}") from None
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            raise HubError(f"{path} 连不上中台：{e}") from None

    def emit(self, event_id, etype, subject, summary):
        """同一个 event_id 重发只记一次，所以可以放心重试。subject 只能是标识符和 / . _ : # @ -。"""
        return self._call("/v1/events", self.source,
                          {"id": event_id, "type": etype, "subject": subject, "summary": summary})

    def state(self):
        """总览：/v1/state，只读，本人的密钥。"""
        return self._call("/v1/state", self.owner)

    def cancel(self, run):
        return self._call(f"/v1/runs/{run}/cancel", self.owner, {})

    def facts(self, after=0, timeout=60):
        """SSE 事实流。超时或断线时正常结束，调用方带着最后的序号再来一次。"""
        req = urllib.request.Request(f"{self.url}/v1/stream?after={after}",
                                     headers={"authorization": f"Bearer {self.owner}"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                for raw in r:
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        yield json.loads(line[5:])
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            if not isinstance(e, socket.timeout):
                raise HubError(f"事实流断了：{e}") from None
