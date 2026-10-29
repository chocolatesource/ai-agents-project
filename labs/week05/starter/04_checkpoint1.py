"""Week 5 checkpoint 1, as a saved script rather than a memory.

    python 04_checkpoint1.py

1. fresh copy, run the suite once: which test fails, which module it points at
2. one plan generated and printed in full, nothing applied
3. validate_plan on that plan and on a deliberately broken one
4. apply_fix refusals: a test file, a missing line, an ambiguous line
5. the nested Step schema, tried for real (5 trials) under the default
   tool-call output, versus the flat Plan under the same mode
"""
from __future__ import annotations

import asyncio
from typing import Literal

from agents import MODEL, Plan, planner, validate_plan, TASK_FOR_CHECK
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import UnexpectedModelBehavior
from repo import Work, apply_fix, run_tests


class Step(BaseModel):
    tool: Literal["read_file", "run_tests", "replace_line"]
    argument: str
    why: str


class NestedPlan(BaseModel):
    goal: str
    steps: list[Step]
    suspect_file: str


SYS = ("You plan a small change to a Python repository. You have NO tools. "
       "Between two and six steps. Files: booking.py, discounts.py, "
       "pricing.py, report.py.")


async def main() -> None:
    w = Work.fresh()
    t = run_tests(w)
    failing = [ln for ln in t.output.splitlines() if ln.startswith("FAIL:")]
    tb = [ln.strip() for ln in t.output.splitlines() if "test_pricing" in ln][:1]
    print("1. suite on a fresh copy:", f"ran={t.ran} failures={t.failures}")
    print("   failing:", failing, "| traceback points at:", tb)

    r = await planner.run(TASK_FOR_CHECK)
    print("\n2. plan, printed in full before anything is applied:")
    print("   goal:", r.output.goal)
    for i, s in enumerate(r.output.steps, 1):
        print(f"   {i}. {s}")
    print("   suspect_file:", r.output.suspect_file)
    print("   validate_plan(real plan) ->", validate_plan(r.output))

    bad = Plan(goal="x", steps=["edit tests/test_pricing.py"],
               suspect_file="engine.py")
    print("\n3. deliberately broken plan ->", validate_plan(bad))

    print("\n4. apply_fix refusals")
    print("   test file :", apply_fix(w, "tests/test_pricing.py", "assertEqual", "x"))
    print("   no such line:", apply_fix(w, "discounts.py", "return banana", "x"))
    print("   ambiguous   :", apply_fix(w, "discounts.py", "return", "yield"))
    print("   real fix    :", apply_fix(w, "discounts.py",
          "return start_hour > OFF_PEAK_FROM_HOUR",
          "return start_hour >= OFF_PEAK_FROM_HOUR"))
    print("   run_tests after (verifier, not the agent's claim):",
          run_tests(w).passed)
    w.cleanup()

    print("\n5. schema trial, default tool-call output, 5 trials each")
    for name, ot in (("flat Plan", Plan), ("nested Step list", NestedPlan)):
        ag = Agent(MODEL, output_type=ot, retries=3, system_prompt=SYS)
        ok, err = 0, set()
        for _ in range(5):
            try:
                await ag.run(TASK_FOR_CHECK); ok += 1
            except UnexpectedModelBehavior as e:
                err.add(str(e)[:60])
        print(f"   {name:<18} returned {ok}/5  errors: {sorted(err)}")


if __name__ == "__main__":
    asyncio.run(main())
