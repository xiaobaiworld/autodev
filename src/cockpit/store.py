"""文件层：原子写、单实例锁、先事件后状态的提交顺序（DATA_SPEC 5.3，设计 5.1）。"""
import fcntl
import json
import os
from datetime import datetime
from pathlib import Path


class LockError(Exception):
    pass


class StateError(Exception):
    pass


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def acquire_lock(path):
    """返回需要一直持有的文件对象；进程退出（含 kill -9）时系统自动释放。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        raise LockError(f"已有主控在运行（锁 {path}）")
    f.write(str(os.getpid()))
    f.flush()
    return f


class Run:
    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        self.state_path = self.dir / "state.json"
        self.events_path = self.dir / "events.jsonl"

    def read(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _last_event(self):
        if not self.events_path.exists():
            return None
        lines = self.events_path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1]) if lines else None

    def commit(self, state, etype, actor="controller", data=None):
        """先追加事件（带新 seq 与状态快照），再原子写 state.json。返回新状态。"""
        state = dict(state)
        state["seq"] = state.get("seq", 0) + 1
        state["updated_at"] = now_iso()
        ev = {"schema_version": 1, "seq": state["seq"], "ts": state["updated_at"],
              "id": state["id"], "type": etype, "stage": state["stage"],
              "round": state["round"], "actor": actor,
              "data": dict(data or {}, state_after=state)}
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        atomic_write(self.state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        return state

    def load(self):
        """读状态并校验 seq；事件比状态多 1 时按事件里的快照补写（崩溃在两步之间）。"""
        state = self.read()
        ev = self._last_event()
        if ev is None or ev["seq"] == state["seq"]:
            return state
        if ev["seq"] == state["seq"] + 1:
            fixed = ev["data"]["state_after"]
            atomic_write(self.state_path, json.dumps(fixed, ensure_ascii=False, indent=2) + "\n")
            return self.commit(fixed, "state.repaired", data={"from_seq": state["seq"]})
        raise StateError(f"seq 不连续：state={state['seq']} events={ev['seq']}，转 needs-human")
