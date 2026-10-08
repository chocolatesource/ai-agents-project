"""Rescore the recorded runs two ways: full scorer vs answer-text-only."""
import sys
from agent import run_task
from scoring import norm
from tasks import TASKS
from project.fixtures import ReplayClient

client = ReplayClient.from_lab("week04_react_tool_use")


def text_only(task, answer):
    g = norm(answer)
    return (all(norm(x) in g for x in task.gold_all)
            and (not task.gold_any or any(norm(x) in g for x in task.gold_any)))


for model in ("qwen2.5:7b", "qwen3:4b-instruct"):
    runs = [run_task(client, t, model=model) for t in TASKS]
    ok = [t.id for t, r in zip(TASKS, runs) if text_only(t, r.answer)]
    print(model, "gold-text-only:", len(ok), "/10", "passes:", ok)
