"""Run the ten tasks N times and report how often the behavior repeats.

    python labs/week04/starter/03_consistency.py [--runs 3] [--guard] [--model M]

Per task: were the step count, the tool sequence, and the pass/fail verdict
the same on every run? And was the final answer text identical? Saved to
artifacts/week04_consistency<tag>.json.
"""
from __future__ import annotations

import argparse
from datetime import date

from openai import OpenAI

from agent import run_task
from scoring import score_all
from tasks import TASKS

from project.models import BASE_URL, API_KEY, LARGE
from project.trace import write_json


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--guard", action="store_true")
    ap.add_argument("--model", default=LARGE.name)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    per_run = []
    for n in range(args.runs):
        runs = [run_task(client, t, model=args.model,
                         guard_refusal=args.guard) for t in TASKS]
        board = score_all(TASKS, runs)
        passed = {r.task_id: r.passed for r in board.results}
        per_run.append({"runs": runs, "passed": passed,
                        "score": board.passed})
        print(f"run {n + 1}: {board.passed}/10  failed {board.failed_ids}")

    rows = []
    print(f"\n{'task':<6}{'steps':<8}{'tools':<8}{'verdict':<9}{'answer':<8}detail")
    for t in TASKS:
        rs = [pr["runs"][[x.task_id for x in pr["runs"]].index(t.id)]
              for pr in per_run]
        steps = [r.steps for r in rs]
        tools = [tuple(r.tool_calls) for r in rs]
        verdicts = [pr["passed"][t.id] for pr in per_run]
        answers = [r.answer.strip() for r in rs]
        same = (len(set(steps)) == 1, len(set(tools)) == 1,
                len(set(verdicts)) == 1, len(set(answers)) == 1)
        rows.append({"task": t.id, "steps": steps,
                     "tools": [list(x) for x in tools],
                     "verdicts": verdicts,
                     "same_steps": same[0], "same_tools": same[1],
                     "same_verdict": same[2], "same_answer": same[3]})
        yn = lambda b: "same" if b else "DIFF"
        print(f"{t.id:<6}{yn(same[0]):<8}{yn(same[1]):<8}{yn(same[2]):<9}"
              f"{yn(same[3]):<8}steps={steps} verdicts={verdicts}")

    n = len(TASKS)
    summary = {k: sum(r[k] for r in rows) for k in
               ("same_steps", "same_tools", "same_verdict", "same_answer")}
    print(f"\nidentical on every run, out of {n} tasks: {summary}")
    print(f"scores per run: {[pr['score'] for pr in per_run]}")
    write_json(f"artifacts/week04_consistency{args.tag}.json", {
        "model": args.model, "guard": args.guard, "runs": args.runs,
        "date": date.today().isoformat(), "scores": [p["score"] for p in per_run],
        "identical_on_all_runs": summary, "tasks": rows})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
