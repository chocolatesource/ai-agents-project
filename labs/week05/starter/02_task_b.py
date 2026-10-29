"""Week 5 homework: Task B, the refactoring.

    python 02_task_b.py --runs 3

The four discount rates (10%, 20%, 15%, cap 30%) are written out in
discounts.py, again in pricing.py's discount_summary, again in report.py's
RATE_LABELS, and the off-peak hour is compared against a literal 20 in two
more places. Task B: make discounts.py the single source.

There is no failing test to point at, so the verifier has two halves:

  1. the suite is green (behaviour preserved), AND
  2. a structural check: no rate literal outside the constants block in
     discounts.py, and no bare `20` hour comparison outside discounts.py.

The starting repository has the week 5 bug already fixed (>= in is_off_peak),
so the suite starts green and "green" alone proves nothing: the structural
check is what makes this a task.

Architectures, same variable as 01_compare.py (how much structure sits between
model and edit), adapted because a refactor needs several edits:

  A  baseline   the free-form tool loop from agents.py
  B  planner    plan, then up to MAX_EDITS single-line proposals, each applied
                through apply_fix, stopping when the verifier passes
  C  B + reviewer  every proposal is shown to the reviewer first
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time

from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput

from agents import MODEL, Fix, Plan, baseline, planner, reviewer, validate_plan
from repo import Work, apply_fix, diff_summary, run_tests

from project.trace import write_json

MAX_EDITS = 8

TASK_B = ("The discount rates (10%, 20%, 15%, and the 30% cap) and the "
          "off-peak hour 20 are written out in several files. Make "
          "discounts.py the single source of truth: define each rate once "
          "there, and have pricing.py and report.py use it instead of typing "
          "the numbers again. Behaviour must not change and no test file may "
          "be edited.")

RATE_LITERALS = ["0.10", "0.20", "0.15", "0.30", "10%", "20%", "15%", "30%"]


def prepare() -> Work:
    """A fresh copy with the week 5 bug fixed, so the suite starts green."""
    work = Work.fresh()
    res = apply_fix(work, "discounts.py",
                    "return start_hour > OFF_PEAK_FROM_HOUR",
                    "return start_hour >= OFF_PEAK_FROM_HOUR")
    assert res == "applied", res
    # pricing.discount_summary still has its own `> 20`; that is part of the
    # duplication Task B is meant to remove.
    return work


def structural_problems(work: Work) -> list[str]:
    """Free, deterministic, and deliberately narrow (see DECISIONS.md)."""
    problems = []
    disc = work.read("discounts.py")
    for name in ("pricing.py", "report.py"):
        src = work.read(name)
        for lit in RATE_LITERALS:
            if lit in src:
                problems.append(f"{name} still contains {lit!r}")
        if re.search(r"start_hour\s*[<>]=?\s*20\b", src):
            problems.append(f"{name} still compares start_hour with a bare 20")
    # each rate literal appears at most once in discounts.py (its definition)
    for lit in ("0.10", "0.20", "0.15", "0.30"):
        n = disc.count(lit)
        if n != 1:
            problems.append(f"discounts.py has {lit!r} {n} times (want 1)")
    return problems


def verdict(work: Work) -> dict:
    tests = run_tests(work).passed
    problems = structural_problems(work)
    return {"tests_green": tests, "structural_problems": problems,
            "done": tests and not problems}


# ---------------------------------------------------------------- B and C

class Step(BaseModel):
    path: str
    old_line: str = Field(description="One existing line, copied exactly")
    new_line: str
    why: str


refactorer = Agent(MODEL, output_type=PromptedOutput(Step), retries=3,
                   system_prompt=(
    "You refactor a small Python repository one line at a time. You are "
    "given a plan, the current contents of every source file, and what is "
    "still wrong. Return exactly ONE line change that removes one remaining "
    "duplication, copying old_line character for character. Import shared "
    "names from discounts.py rather than retyping numbers. Never touch tests."))

PLAN_NOTE = ("Files: booking.py, discounts.py, pricing.py, report.py, tests/. "
             "Plan the refactor in two to six steps; one step must run the "
             "tests; suspect_file is the first file to change.")


def sources(work: Work) -> str:
    return "\n\n".join(f"### {n}\n{work.read(n)}"
                       for n in ("discounts.py", "pricing.py", "report.py"))


async def run_baseline(i: int) -> dict:
    work, t0, tokens = prepare(), time.perf_counter(), 0
    try:
        r = await baseline.run(TASK_B, deps=work)
        tokens = r.usage.total_tokens or 0
    except Exception as exc:                                  # noqa: BLE001
        print(f"    A run {i} raised {type(exc).__name__}")
    v = verdict(work)
    work.cleanup()
    return {"architecture": "A baseline", **v, "tokens": tokens,
            "edits": None, "seconds": round(time.perf_counter() - t0, 1)}


async def run_staged(i: int, with_reviewer: bool) -> dict:
    arch = "C planner+reviewer" if with_reviewer else "B planner"
    work, t0, tokens = prepare(), time.perf_counter(), 0
    log: list[str] = []
    try:
        p = await planner.run(f"{TASK_B}\n{PLAN_NOTE}")
        tokens += p.usage.total_tokens or 0
        ok, probs = validate_plan(p.output)
        plan_text = "; ".join(p.output.steps)
        applied = 0
        for _ in range(MAX_EDITS):
            v = verdict(work)
            if v["done"]:
                break
            r = await refactorer.run(
                f"Plan: {plan_text}\n\n{sources(work)}\n\n"
                f"Still wrong: {v['structural_problems'] or 'tests failing'}")
            tokens += r.usage.total_tokens or 0
            s = r.output
            if with_reviewer:
                d = diff_summary(work, s.path, s.old_line, s.new_line)
                rv = await reviewer.run(
                    f"Proposed change:\n{d}\n\nRefactoring goal: remove "
                    f"duplicated discount rates, behaviour unchanged.")
                tokens += rv.usage.total_tokens or 0
                if rv.output.decision == "reject":
                    log.append(f"rejected {s.path}")
                    continue
            res = apply_fix(work, s.path, s.old_line, s.new_line)
            log.append(f"{s.path}: {res}")
            applied += res == "applied"
    except Exception as exc:                                  # noqa: BLE001
        print(f"    {arch} run {i} raised {type(exc).__name__}")
        log.append(f"crashed: {type(exc).__name__}")
        applied = 0
    v = verdict(work)
    work.cleanup()
    return {"architecture": arch, **v, "tokens": tokens, "edits": applied,
            "log": log, "seconds": round(time.perf_counter() - t0, 1)}


async def main_async(runs: int) -> list[dict]:
    rows = []
    for i in range(1, runs + 1):
        rows.append(await run_baseline(i))
        rows.append(await run_staged(i, False))
        rows.append(await run_staged(i, True))
        print("  run", i, [(r["architecture"][:1], r["done"],
                            r["tests_green"], len(r["structural_problems"]))
                           for r in rows[-3:]], flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    # Control: the untouched starting point must NOT already count as done,
    # otherwise the verifier does nothing.
    w = prepare()
    start = verdict(w)
    w.cleanup()
    print("verifier on the starting repo:", start["tests_green"],
          len(start["structural_problems"]), "problems")
    assert start["tests_green"] and not start["done"], "verifier does nothing"

    rows = asyncio.run(main_async(args.runs))
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["architecture"], []).append(r)
    print(f"\n{'architecture':<22}{'done':>7}{'tests':>7}{'tokens':>9}{'secs':>7}")
    for a, g in by.items():
        print(f"{a:<22}{sum(x['done'] for x in g):>5}/{len(g)}"
              f"{sum(x['tests_green'] for x in g):>5}/{len(g)}"
              f"{sum(x['tokens'] for x in g) // len(g):>9}"
              f"{sum(x['seconds'] for x in g) / len(g):>7.1f}")
    write_json("artifacts/week05_task_b.json",
               {"start": start, "rows": rows})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
