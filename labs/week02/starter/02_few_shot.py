"""Block 3. The few-shot variant, and the honest comparison.

    python 02_few_shot.py --replay
    python 02_few_shot.py

Same schema, same scorer, same ten documents. One variable changes, which is
the presence of examples. That is the whole experimental design, and it is
the part most student comparisons get wrong.

Two ways to break it, both easy and both fatal:

  * editing the schema or the scorer between the two runs, which makes the
    two numbers incomparable
  * taking examples from DOCS, which turns the second measurement into a
    memory test. Examples come from EXAMPLE_POOL, which is held out for
    exactly this reason.

Two TODO markers.
"""

from __future__ import annotations

import argparse
import json

from documents import DOCS, EXAMPLE_POOL, GOLD
from extractor import SYSTEM_ZERO_SHOT, get_client, run_variant
from scoring import compare

from project.trace import write_json


# --------------------------------------------------------------------------
# TODO 5. Choose your examples and build the block.
# --------------------------------------------------------------------------

def few_shot_block(n: int = 4) -> str:
    """Return the example block that gets appended to the system prompt.

    Choose from EXAMPLE_POOL, never from DOCS. Three to five examples. Fewer
    is usually better than more, and you pay for every one of them in input
    tokens on every single call, forever.

    Choose deliberately, one per thing you could not say clearly in words:

      * a boundary you struggled to define, for example the line between
        facilities and hardware
      * a message with no stated deadline, which demonstrates the null
        convention rather than describing it
      * a message in a language other than English, because the corpus is
        multilingual and an all English example block quietly teaches the
        model that English is the norm

    Write the reason for each choice in DECISIONS.md. "It seemed useful" is
    not a reason, and at the checkpoint you will be asked which field each
    example was meant to move.

    One trap worth knowing before you fall into it. Whatever you show in the
    `quote` field of your examples is what the model will imitate. If your
    examples carry truncated or tidied quotes, you have just taught it to
    stop copying verbatim, and the field that scored perfectly zero-shot
    will get worse. Look at the recording if you want to see that happen.
    """
    by_id = {doc.id: (doc, gold) for doc, gold in EXAMPLE_POOL}
    chosen = [
        # EX-01, en: a badge reader is physical hardware, but the gold label
        # is "access" not "hardware" - this is the access/hardware boundary
        # the live run got wrong on REQ-08. Also a null due_date case.
        ("EX-01", "I can still get in through the main door, "
                  "so it is not blocking me."),
        # EX-02, fr: an elevator is a facility, not a device you'd call
        # "hardware" - the facilities/hardware boundary the live run got
        # wrong on REQ-04, the other side of it. Non-English, null date.
        ("EX-02", "Intervention immediate necessaire."),
        # EX-03, de: hardware, but WITH a real due_date, so the block shows
        # both the null convention and the "a date is present" convention,
        # not just one of them. Non-English.
        ("EX-03", "das Netzteil ist vermutlich defekt"),
        # EX-06, en: facilities again (a window, not a device at all),
        # reinforcing the boundary from the opposite direction of EX-03's
        # hardware example, and urgent rather than standard.
        ("EX-06", "This is getting worse by the hour."),
    ][:n]

    lines = ["", "Examples:", ""]
    for doc_id, quote in chosen:
        doc, gold = by_id[doc_id]
        due = f'"{gold.due_date}"' if gold.due_date else "null"
        lines.append(f"Message ({doc.lang}): {doc.text}")
        lines.append(
            f'Answer: category="{gold.category}", urgency="{gold.urgency}", '
            f'due_date={due}, quote="{quote}"')
        lines.append("")
    return "\n".join(lines)


SYSTEM_FEW_SHOT = SYSTEM_ZERO_SHOT + "\n"   # + few_shot_block(), once written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true")
    args = ap.parse_args()

    client = get_client(args.replay)

    zero_board, _, zero_metas = run_variant(client, SYSTEM_ZERO_SHOT,
                                            "zero-shot", DOCS, GOLD)
    few_board, _, few_metas = run_variant(
        client, SYSTEM_ZERO_SHOT + "\n" + few_shot_block(), "few-shot",
        DOCS, GOLD)

    print(compare(zero_board, few_board, "zero-shot", "few-shot"))

    zero_tok = sum(m["prompt_tokens"] for m in zero_metas)
    few_tok = sum(m["prompt_tokens"] for m in few_metas)
    per_call = (few_tok - zero_tok) / len(DOCS)
    print(f"\nexample block costs {per_call:.0f} input tokens per call, "
          f"{per_call * 1000:.0f} per thousand calls")

    write_json("artifacts/week02_comparison.json", {
        "zero_shot": {"hits": zero_board.hits, "invalid": zero_board.invalid},
        "few_shot": {"hits": few_board.hits, "invalid": few_board.invalid},
        "extra_input_tokens_per_call": round(per_call, 1),
    })

    # TODO 6. Read the comparison table and answer four questions in
    # DECISIONS.md. The table is the deliverable, not the two runs.
    #
    #   a. Which fields moved, and which did not move at all? Do not report
    #      one overall number. The interesting content is that they do not
    #      move together.
    #
    #   b. Did any field get WORSE? If one did, say which and diagnose it.
    #      This is the most valuable observation available today and it is
    #      the one students skip past looking for a win.
    #
    #   c. Did an error disappear, or did it change shape? A wrong label that
    #      became a different wrong label is not a fix. Look at the failure
    #      lines, not just the counts.
    #
    #   d. Would you ship the few-shot variant? Give the evidence, the token
    #      cost per thousand calls, and one sentence saying what would change
    #      your mind. "It scored higher" is not sufficient on ten records,
    #      and saying so is worth more marks than claiming a win.

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
