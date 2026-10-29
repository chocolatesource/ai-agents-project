"""Week 6 homework: an A2A-style channel, built rather than watched.

    python 04_a2a_channel.py

A2A-STYLE, not a certified implementation (same caveat as 03_a2a.py).
A2A is a different protocol from MCP, so the MCP revision 2026-07-28 does not
apply here; this is modelled on the A2A agent-card / task / artifact vocabulary
as of 2026-10-29. Stdlib
only, no model, no network beyond localhost. Built from the three pieces the
demonstration names (agent card, task lifecycle, artifact) and extended with
the two things 03_a2a.py leaves out:

  * a TASK STORE on the server, so a task id that the client kept after a
    timeout can be asked about later (tasks/get) or cancelled (tasks/cancel);
  * a CLIENT that decides from the card, handles every terminal state, and
    never stringifies an artifact it cannot read.

The server runs a "summary" skill for resident-facing handbook text. It is
deliberately slow on request, to exercise the timeout path.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8981
BASE = f"http://127.0.0.1:{PORT}"

CARD = {
    "name": "handbook-summary-agent",
    "description": "Summarises short handbook passages for residents.",
    "url": BASE,
    "version": "1.0",
    "skills": [{"id": "summarize", "name": "Summarise a passage",
                "inputModes": ["text/plain"], "outputModes": ["text/plain"]}],
}

# ----------------------------------------------------------------------------
# Server: task store + lifecycle
# ----------------------------------------------------------------------------
# States. submitted -> working -> completed | failed | canceled. The last three
# are terminal; a task never leaves a terminal state.
TERMINAL = {"completed", "failed", "canceled"}


@dataclass
class Task:
    id: str
    state: str = "submitted"
    artifact: dict | None = None
    error: str | None = None
    history: list[str] = field(default_factory=lambda: ["submitted"])

    def move(self, state: str) -> None:
        if self.state in TERMINAL:          # no resurrection of a done task
            return
        self.state = state
        self.history.append(state)


TASKS: dict[str, Task] = {}
LOCK = threading.Lock()


def work(task: Task, text: str) -> None:
    """The remote agent's job, run in a thread so POST returns immediately."""
    with LOCK:
        task.move("working")
    if "FAIL" in text:
        with LOCK:
            task.error = "the passage is not in a language I can summarise"
            task.move("failed")
        return
    delay = 3.0 if "SLOW" in text else 0.1
    deadline = time.time() + delay
    while time.time() < deadline:           # cancellable sleep
        if task.state == "canceled":
            return
        time.sleep(0.05)
    with LOCK:
        if task.state == "canceled":
            return
        if "EMPTY" in text:                 # an artifact with no text part
            task.artifact = {"parts": [{"data": {"n": 1}}]}
        else:
            task.artifact = {"parts": [{"text": text.strip()[:60] + "..."}]}
        task.move("completed")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _view(self, t: Task) -> dict:
        v = {"taskId": t.id, "state": t.state, "history": t.history}
        if t.artifact:
            v["artifact"] = t.artifact
        if t.error:
            v["error"] = t.error
        return v

    def do_GET(self):
        if self.path == "/.well-known/agent.json":
            return self._send(200, CARD)
        if self.path.startswith("/tasks/"):
            t = TASKS.get(self.path.rsplit("/", 1)[1])
            return (self._send(200, self._view(t)) if t
                    else self._send(404, {"error": "unknown task"}))
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        if self.path.endswith(":cancel"):
            t = TASKS.get(self.path.split("/")[-1].split(":")[0])
            if not t:
                return self._send(404, {"error": "unknown task"})
            with LOCK:
                t.move("canceled")
            return self._send(200, self._view(t))
        # The server refuses a skill it does not declare, on its own side too.
        if req.get("skill") != "summarize":
            return self._send(400, {"error": "unsupported skill"})
        text = req.get("message", {}).get("parts", [{}])[0].get("text", "")
        task = Task(id=req.get("taskId") or f"task-{len(TASKS) + 1}")
        TASKS[task.id] = task
        threading.Thread(target=work, args=(task, text), daemon=True).start()
        self._send(202, self._view(task))   # accepted, not finished


def serve() -> None:
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


# ----------------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------------

def _req(method: str, path: str, body: dict | None = None,
         timeout: float = 3.0) -> tuple[int, dict]:
    r = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


class Channel:
    """Delegates to the remote agent, deciding from its card."""

    def __init__(self) -> None:
        _, self.card = _req("GET", "/.well-known/agent.json")
        self.skills = {s["id"] for s in self.card["skills"]}
        self.pending: dict[str, str] = {}     # task ids we gave up waiting on

    def delegate(self, skill: str, text: str, task_id: str,
                 wait: float = 2.0) -> dict:
        # 1. decide locally from the card: no round trip for an undeclared skill
        if skill not in self.skills:
            return {"status": "local", "reason": f"card declares no {skill!r}"}
        _, view = _req("POST", "/", {"skill": skill, "taskId": task_id,
                                      "message": {"parts": [{"text": text}]}})
        # 2. poll until terminal or our own deadline
        deadline = time.time() + wait
        while view["state"] not in TERMINAL and time.time() < deadline:
            time.sleep(0.1)
            _, view = _req("GET", f"/tasks/{task_id}")
        # 3. every outcome is a value, never an exception or a bare string
        if view["state"] == "completed":
            parts = view.get("artifact", {}).get("parts", [])
            texts = [p["text"] for p in parts if "text" in p]
            if not texts:       # report the mismatch, do not str() the dict
                return {"status": "mismatch", "task": task_id, "parts": parts}
            return {"status": "ok", "task": task_id, "text": texts[0]}
        if view["state"] == "failed":
            return {"status": "failed", "task": task_id,
                    "error": view.get("error")}
        if view["state"] == "canceled":
            return {"status": "canceled", "task": task_id}
        self.pending[task_id] = view["state"]   # KEEP the id: work continues
        return {"status": "timeout", "task": task_id, "state": view["state"]}

    def chase(self, task_id: str) -> dict:
        _, view = _req("GET", f"/tasks/{task_id}")
        return view

    def cancel(self, task_id: str) -> dict:
        _, view = _req("POST", f"/tasks/{task_id}:cancel", {})
        self.pending.pop(task_id, None)
        return view


def main() -> int:
    server = mp.Process(target=serve, daemon=True)
    server.start()
    time.sleep(1.0)
    checks: dict[str, bool] = {}
    try:
        ch = Channel()
        print(f"card: {ch.card['name']}, skills {sorted(ch.skills)}\n")

        r = ch.delegate("summarize", "Waste is collected on Tuesdays.", "t1")
        print("1 ok         ", r)
        checks["completed task returns text"] = r["status"] == "ok"

        r = ch.delegate("translate", "hello", "t2")
        print("2 not sent   ", r)
        checks["undeclared skill decided locally, nothing sent"] = (
            r["status"] == "local" and _req("GET", "/tasks/t2")[0] == 404)

        r = ch.delegate("summarize", "FAIL this", "t3")
        print("3 failed     ", r)
        checks["failed is a value with the error"] = (
            r["status"] == "failed" and bool(r["error"]))

        r = ch.delegate("summarize", "SLOW one", "t4", wait=1.0)
        print("4 timeout    ", r)
        checks["timeout keeps the task id"] = (
            r["status"] == "timeout" and "t4" in ch.pending)
        time.sleep(3.0)
        later = ch.chase("t4")
        print("  chased later", later["state"], later["history"])
        checks["kept id lets us collect the result later"] = (
            later["state"] == "completed")

        r = ch.delegate("summarize", "EMPTY please", "t5")
        print("5 mismatch   ", r)
        checks["non-text artifact reported, not stringified"] = (
            r["status"] == "mismatch")

        r = ch.delegate("summarize", "SLOW two", "t6", wait=0.5)
        cancelled = ch.cancel("t6")
        time.sleep(3.3)
        final = ch.chase("t6")
        print("6 cancel     ", cancelled["state"], "->", final["state"])
        checks["cancelled task stays cancelled (no late completion)"] = (
            final["state"] == "canceled" and "artifact" not in final)
    finally:
        server.terminate()

    print()
    for name, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    mp.set_start_method("spawn")
    raise SystemExit(main())
