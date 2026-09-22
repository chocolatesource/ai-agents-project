"""Block 2. The zero-shot baseline, scored per field.

    python 01_zero_shot.py --replay     # the shipped recording, instant
    python 01_zero_shot.py              # your own model, about 45 seconds

Develop your scorer against `--replay`. The recording holds every model
answer for both variants, so your scorer runs in well under a second and you
can iterate on it properly instead of waiting forty-five seconds to find out
you compared the wrong field.

The recording contains real failures, because the model really does make
them. If your scorer reports forty out of forty, your scorer does nothing.

One TODO marker here. TODO 1 to 4 live in extractor.py and scoring.py, and
this file will not run until they are done.
"""

from __future__ import annotations

import argparse

from documents import DOCS, GOLD
from extractor import (PROMPT_VERSION, SYSTEM_ZERO_SHOT, get_client,
                       run_variant)

from project.contracts import GoldCase, GoldSet
from project.trace import write_json

# One sentence per document, written by hand rather than derived from the
# gold dict, because "extracts category X, urgency Y" is not what makes a
# behavior sentence useful - the part worth writing down is *why*, in the
# convention terms a grader would check against (relative vs. calendar date,
# an explicit "not urgent" phrase, a live safety risk).
EXPECTED_BEHAVIOR = {
    "REQ-01": "extracts category access and urgency urgent (needs the "
              "portal confirmation before an appointment), with due_date "
              "null because 'tomorrow' is relative, not a calendar date.",
    "REQ-02": "extracts category hardware and urgency standard, with "
              "due_date 2026-09-15 from the explicit European-format date "
              "15/09/2026.",
    "REQ-03": "extracts category billing and urgency standard (the message "
              "says 'Es eilt nicht' / not urgent, but a billing correction "
              "is still actionable, not purely informational), with "
              "due_date null since no date is stated.",
    "REQ-04": "extracts category facilities (a door/building fault, not a "
              "device) and urgency urgent (an active security risk, "
              "'someone needs to come immediately'), with due_date null.",
    "REQ-05": "extracts category access and urgency standard (explicitly "
              "'ce n'est pas urgent'), with due_date null because 'before "
              "the end of the month' is a relative deadline, not a date.",
    "REQ-06": "extracts category billing and urgency info (explicitly 'no "
              "action needed... just informing'), with due_date null.",
    "REQ-07": "extracts category facilities and urgency standard, with "
              "due_date 2026-10-01 from the explicit date of the next "
              "public session.",
    "REQ-08": "extracts category hardware (a file server outage) and "
              "urgency urgent ('bloquant pour toute l'equipe' today), with "
              "due_date null since no calendar date is mentioned.",
    "REQ-09": "extracts category other (a suggestion, not access, "
              "hardware, billing, or facilities) and urgency info, with "
              "due_date null.",
    "REQ-10": "extracts category access and urgency standard, with "
              "due_date null because 'before the end of the month' is "
              "relative, not a calendar date.",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true")
    args = ap.parse_args()

    client = get_client(args.replay)
    board, records, metas = run_variant(client, SYSTEM_ZERO_SHOT,
                                        "zero-shot", DOCS, GOLD)

    if board.failures:
        print("failures worth reading:")
        for doc_id, fieldname, note in board.failures[:10]:
            print(f"  {doc_id}  {fieldname:<9} {note}")

    write_json("artifacts/week02_zero_shot.json", {
        "variant": "zero-shot",
        "prompt_version": PROMPT_VERSION,
        "hits": board.hits, "total": board.total, "invalid": board.invalid,
    })

    # TODO 7. Write the gold set into the project spine.
    #
    #   Build a GoldSet out of the ten documents and their annotations and
    #   write it to artifacts/goldset.json with
    #   project.trace.write_json(...).
    #
    #   For each document, one GoldCase with:
    #     case_id           the document id
    #     week_added        2
    #     question          the document text
    #     expected          the gold annotation, as a dict
    #     expected_behavior one sentence a colleague could grade against.
    #                       "extracts category access and urgency standard,
    #                       with no due date because the message only says
    #                       'before the end of the month'" is a good one.
    #                       "works" is not.
    #     slice_tags        at least the language, so week 10 can report per
    #                       language instead of as one average
    #
    #   This is not busywork and it is not for today. Week 3 adds route
    #   labels to this file, week 7 adds retrieval questions, and week 10
    #   builds the evaluation harness on whatever is in it by then. Ten
    #   careful cases now is the cheapest week 10 you will ever have.
    #
    #   Then run: python -m project.verify

    docs_by_id = {d.id: d for d in DOCS}
    goldset = GoldSet(cases=[
        GoldCase(
            case_id=doc_id,
            week_added=2,
            question=docs_by_id[doc_id].text,
            expected={"category": gold.category, "urgency": gold.urgency,
                     "due_date": gold.due_date},
            expected_behavior=EXPECTED_BEHAVIOR[doc_id],
            slice_tags=[f"lang:{docs_by_id[doc_id].lang}",
                       f"category:{gold.category}"],
        )
        for doc_id, gold in GOLD.items()
    ])
    write_json("artifacts/goldset.json", goldset)
    print(f"wrote {len(goldset.cases)} gold cases to artifacts/goldset.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
