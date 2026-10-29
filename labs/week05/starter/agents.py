"""The three agents, on Pydantic AI. TODO 1 to 5.

This is the week the hand-rolled loop of weeks 1 to 4 gives way to a
framework. Read the week 4 `agent.py` next to this file: the loop, the
message list, the tool dispatch, and the schema envelope are all gone. What
is left is the part that was always the design.

Nothing underneath has changed. Pydantic AI is making the same calls to the
same endpoint in the same wire format. That is why you wrote the loop first.
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput, RunContext

from repo import Work, apply_fix, diff_summary, run_tests

from project.models import LARGE, pydantic_ai_model

MODEL = pydantic_ai_model(LARGE)

# DEVIATION FROM THE STARTER (measured, artifacts/week05_planner_modes.json,
# qwen2.5:7b, pydantic-ai 2.63.0, Ollama 0.30.8, 2026-10-29): with the default
# tool-call output, the flat Plan came back only 3 times in 10 and the rest
# died with "Exceeded maximum output retries" (the model answers with neither
# text nor a tool call). PromptedOutput puts the schema in the prompt instead
# and returned a valid plan 10 in 10 once the file names were listed.


# --------------------------------------------------------------------------
# TODO 1. The plan schema, and a warning about its shape.
# --------------------------------------------------------------------------
#
# The obvious schema for a plan is a list of structured steps:
#
#     class Step(BaseModel):
#         tool: Literal[...]
#         argument: str
#         why: str
#
# It fails on this model, every time, with "Exceeded maximum output
# retries". A flat list of strings works. That is measured, not folklore.


class Plan(BaseModel):
    """TODO 1. Three fields: a goal, the steps, and the file you suspect.

    Read the comment above before you choose the type of `steps`. The
    obvious answer, a list of nested Step objects, does not work on this
    model. Keep it flat.
    """

    goal: str
    # Flat on purpose: a list of plain strings. A nested Step object raised
    # "Exceeded maximum output retries" on this model (see DECISIONS.md).
    steps: list[str]
    suspect_file: str


planner = Agent(MODEL, output_type=PromptedOutput(Plan), retries=3,
                system_prompt=(
    "You plan a small change to a Python repository. You have NO tools and "
    "you must not attempt to act: you are producing a plan that a person "
    "will read before anything runs.\n"
    "Keep it to between two and six steps. Name the file you suspect. "
    "The repository contains exactly these files: booking.py, discounts.py, "
    "pricing.py, report.py, and tests/. suspect_file must be one of the four "
    ".py files. One step must run the tests."))


# --------------------------------------------------------------------------
# TODO 2. Validating the plan, for free, before anything runs.
# --------------------------------------------------------------------------

TASK_FOR_CHECK = ("A test is failing. The off-peak discount is meant to apply to bookings that start at 20:00 or later, but a booking starting exactly at 20:00 does not receive it. Fix the bug. Do not change any test file.")

KNOWN_FILES = {"booking.py", "discounts.py", "pricing.py", "report.py"}


def validate_plan(plan: Plan) -> tuple[bool, list[str]]:
    """TODO 2. Four free checks. No model, no cost, run before anything else.

    Return (ok, problems). Check that:

      * the step count is inside a range you choose and can defend
      * `suspect_file` names a file that actually exists in the repository
      * some step runs the tests, because a plan with no verification step
        has no way of knowing whether it worked
      * no step proposes editing a test, which `apply_fix` refuses anyway

    A plan is an artifact you inspect. Inspecting it takes fifteen seconds
    and catches most of the failures you would otherwise spend the session
    debugging.

    Decide what happens on a failed check, repair once or refuse, and write
    the decision in DECISIONS.md.
    """
    problems: list[str] = []
    # Two to six matches the planner's own instruction; fewer than two cannot
    # contain both a change and a verification, more than six is a plan that
    # has wandered.
    if not 2 <= len(plan.steps) <= 6:
        problems.append(f"step count {len(plan.steps)} is outside 2..6")
    if plan.suspect_file not in KNOWN_FILES:
        problems.append(f"suspect_file {plan.suspect_file!r} is not a file "
                        f"in the repository")
    text = [s.lower() for s in plan.steps]
    if not any("test" in s and any(v in s for v in
                                   ("run", "verify", "check", "confirm"))
               for s in text):
        problems.append("no step runs the tests")
    if any(("edit" in s or "modify" in s or "change" in s or "update" in s
            or "delete" in s or "remove" in s)
           and ("tests/" in s or "test file" in s or "test_" in s)
           for s in text):
        problems.append("a step proposes editing a test")
    return (not problems, problems)


# --------------------------------------------------------------------------
# TODO 3. The fix, as a proposal rather than an edit.
# --------------------------------------------------------------------------
#
# The executor does not edit the file. It proposes exactly one line change
# and `repo.apply_fix` decides whether to apply it.
#
# That is a deliberate narrowing and it is the difference between a session
# that works and one that does not. Given free-form editing tools, this model
# thrashes: measured at 32 and 38 tool calls, three to four minutes, and zero
# successful fixes in three attempts. Given one structured proposal, it is
# correct three times in four.
#
# The engineering point generalizes past this lab. The narrower the action
# your agent can take, the more reliably it takes it, and the easier it is to
# check before it happens. "Give the agent a shell" is the widest possible
# action and it is why coding agents are hard.

class Fix(BaseModel):
    """TODO 3. One proposed line change.

    Four fields: the path, the exact line to replace, the corrected line,
    and why. The description you give `old_line` matters more than the type
    does, because `repo.apply_fix` refuses the edit unless that string
    appears in the file character for character.
    """

    path: str = Field(description="File path relative to the repository "
                                  "root, for example 'discounts.py'.")
    old_line: str = Field(description="The one wrong line, copied character "
                                      "for character from the file, "
                                      "including its indentation.")
    new_line: str = Field(description="The corrected version of that line, "
                                      "with the same indentation.")
    why: str = Field(description="One sentence on why the old line is wrong.")


fixer = Agent(MODEL, output_type=PromptedOutput(Fix), retries=3,
              system_prompt=(
    "You propose exactly ONE line change that makes a failing test pass.\n"
    "You are given the whole file. Return the single wrong line, copied "
    "character for character, and the corrected version of it.\n"
    "Change the logic that is wrong. Do not change a constant to compensate "
    "for a wrong comparison, and never propose a change to a test."))


# --------------------------------------------------------------------------
# TODO 4. The baseline, for comparison. Given complete: read it.
# --------------------------------------------------------------------------

class Work_(BaseModel):
    root_str: str
    model_config = {"frozen": True}


baseline = Agent(MODEL, system_prompt=(
    "You fix a bug in a small Python repository using the tools provided.\n"
    "run_tests to see the failure, read_file to look at the source, "
    "replace_line to change one line, run_tests again to confirm.\n"
    "Never edit anything under tests/. Stop as soon as the tests pass."))


@baseline.tool
def list_files(ctx: RunContext[Work]) -> list[str]:
    """List the Python files in the repository."""
    return ctx.deps.files()


@baseline.tool
def read_file(ctx: RunContext[Work], path: str) -> str:
    """Read one file, by a path relative to the repository root."""
    return ctx.deps.read(path)


@baseline.tool
def replace_line(ctx: RunContext[Work], path: str, old_line: str,
                 new_line: str) -> str:
    """Replace one exact line. The old line must appear exactly once."""
    return apply_fix(ctx.deps, path, old_line, new_line)


@baseline.tool
def run_the_tests(ctx: RunContext[Work]) -> str:
    """Run the test suite and return its output."""
    return run_tests(ctx.deps).output


# --------------------------------------------------------------------------
# TODO 5. The reviewer, which is the second agent.
# --------------------------------------------------------------------------

class Verdict(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(max_length=200)


# TODO 5. Write the reviewer's instructions.
#
# It is given the diff and the failing test output, and nothing else. Decide
# what it should reject. At least one of the things it must catch is a change
# that makes the failing test pass while being wrong anyway, and the fixer
# really does propose one sometimes.
#
# Do NOT give it the fixer's reasoning. If it inherits the reasoning it
# inherits the mistake, and the second opinion stops being a second opinion.
reviewer = Agent(MODEL, output_type=PromptedOutput(Verdict), retries=3,
                 system_prompt=(
    "You review one proposed line change to a Python repository. You see "
    "only the diff and the output of the failing test. You do not see why "
    "the change was proposed and you must not assume it is right.\n"
    "REJECT the change if any of these is true:\n"
    "- it edits a test, or anything that makes a test easier to pass\n"
    "- it changes a constant or threshold to compensate for a wrong "
    "comparison, so that the failing case passes but neighbouring cases "
    "(for example the hour before) would now be treated wrongly\n"
    "- it special-cases the failing input\n"
    "- it does not address the cause named in the failing test output\n"
    "APPROVE only a minimal change to the logic that is wrong, such as a "
    "comparison operator. Give a reason of at most one sentence."))


# --------------------------------------------------------------------------
# What the reviewer is NOT given, and why it matters
# --------------------------------------------------------------------------
#
# It does not see the fixer's reasoning. It sees the artifact and the test
# output. If it inherited the reasoning it would inherit the mistake, and the
# second opinion would stop being a second opinion. That is the mechanism
# behind the critic pattern and it is the thing worth demonstrating today.


async def propose(work: Work, task: str, use_plan: bool) -> dict:
    """One attempt: optionally plan, then propose a fix, then verify."""
    out: dict = {"plan": None, "plan_ok": None, "plan_problems": [],
                 "fix": None, "applied": None, "tokens": 0}
    t0 = time.perf_counter()

    context = ""
    if use_plan:
        r = await planner.run(task)
        out["plan"] = r.output
        out["tokens"] += r.usage.total_tokens or 0
        ok, problems = validate_plan(r.output)
        out["plan_ok"], out["plan_problems"] = ok, problems
        context = (f"A plan has already been made. Suspect file: "
                   f"{r.output.suspect_file}. Goal: {r.output.goal}\n")
        source_name = (r.output.suspect_file if r.output.suspect_file
                       in KNOWN_FILES else "discounts.py")
    else:
        source_name = "discounts.py"

    failing = run_tests(work).output
    source = work.read(source_name)
    prompt = (f"{context}File {source_name}:\n{source}\n\n"
              f"Failing test output:\n{failing}\n\n{task}")
    r = await fixer.run(prompt)
    out["fix"] = r.output
    out["tokens"] += r.usage.total_tokens or 0
    out["seconds"] = time.perf_counter() - t0
    return out
