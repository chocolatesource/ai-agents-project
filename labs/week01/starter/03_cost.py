"""Block 4. What one call costs, in the three currencies that matter here.

    python 03_cost.py

You are running locally, so nothing you do today costs money. That is
convenient and it is also a distortion, because in any job you take,
somebody watches the bill. So this block measures the two costs that are
real on your machine, and estimates the one that is not.

  seconds   measured, and it is dominated by how much the model writes
  memory    measured, and it decides which model you can run at all
  euros     estimated from a dated price list, and labeled as an estimate

Two TODO markers.
"""

from __future__ import annotations

import subprocess
import time

from openai import OpenAI

from project.models import BASE_URL, API_KEY, LARGE, SMALL
from project.prices import CURRENCY, PRICE_DATE, estimate, local_cost_note
from project.trace import write_json

SHORT = "What is the capital of Luxembourg? Answer in one word."
LONG = ("A resident asks whether they need a parking vignette if they park "
        "in a visitor bay. Explain what information you would need before "
        "answering, and why.")


def timed(client, prompt: str, model: str, max_tokens: int = 200):
    t0 = time.perf_counter()
    reply = client.chat.completions.create(
        model=model, temperature=0.0, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}])
    return reply, time.perf_counter() - t0


def main() -> int:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    rows = []

    # Cost one, seconds. Two prompts, same model, same settings, and the
    # only thing that changes is how much the model has to write.
    for label, prompt in (("short", SHORT), ("long", LONG)):
        reply, secs = timed(client, prompt, SMALL.name)
        rows.append({
            "case": label, "model": SMALL.name, "seconds": round(secs, 3),
            "prompt_tokens": reply.usage.prompt_tokens,
            "completion_tokens": reply.usage.completion_tokens,
        })
        print(f"{label:<6} {secs:>6.2f}s  "
              f"in {reply.usage.prompt_tokens:>4} "
              f"out {reply.usage.completion_tokens:>4}")

    ratio = rows[1]["seconds"] / max(rows[0]["seconds"], 1e-9)
    print(f"\nThe long answer took {ratio:.0f} times as long as the short "
          f"one.\nCompare that with the ratio of their output tokens.\n")

    # TODO 7. Cold start: unload the model, then time a cold call vs a warm one.
    subprocess.run(["ollama", "stop", SMALL.name])
    cold_reply, cold_secs = timed(client, SHORT, SMALL.name)
    warm_reply, warm_secs = timed(client, SHORT, SMALL.name)
    rows.append({"case": "cold_start", "model": SMALL.name,
                "seconds": round(cold_secs, 3),
                "prompt_tokens": cold_reply.usage.prompt_tokens,
                "completion_tokens": cold_reply.usage.completion_tokens})
    rows.append({"case": "warm", "model": SMALL.name,
                "seconds": round(warm_secs, 3),
                "prompt_tokens": warm_reply.usage.prompt_tokens,
                "completion_tokens": warm_reply.usage.completion_tokens})
    print(f"\ncold start {cold_secs:.2f}s vs warm {warm_secs:.2f}s "
          f"({cold_secs / max(warm_secs, 1e-9):.0f}x)")

    # TODO 8. Estimate a nightly hosted evaluation run: 200 cases, each
    # costing what the `long` case above cost in tokens, once a night for
    # the 14 weeks of this course.
    long_in = rows[1]["prompt_tokens"]
    long_out = rows[1]["completion_tokens"]
    cases_per_night, nights = 200, 14
    print()
    for tier in ("small", "large"):
        est = estimate(long_in, long_out, tier=tier)
        semester_total = est.total * cases_per_night * nights
        print(f"{tier:<6} tier: {est.summary()}")
        print(f"       -> {cases_per_night} cases/night x {nights} nights "
              f"= {semester_total:.2f} {CURRENCY} for the semester "
              f"(estimate, {PRICE_DATE} price list)")

    write_json("artifacts/week01_cost.json",
               {"rows": rows, "price_list_date": PRICE_DATE})
    print(local_cost_note())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
