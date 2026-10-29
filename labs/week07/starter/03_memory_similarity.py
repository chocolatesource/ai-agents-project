"""Choose app.memory.MIN_SIMILARITY from data rather than by feel.

    python 03_memory_similarity.py

Five facts about one resident and twelve queries: for each query the fact
that SHOULD come back (or none). Prints the cosine of every relevant pair and
the highest cosine of any irrelevant pair, then reports the gap.
"""
from __future__ import annotations

from app.memory import _cosine
from app.retrieval import embed

from project.trace import write_json

FACTS = {
    "address": "lives at 12 rue de Hollerich, Luxembourg",
    "language": "prefers correspondence in German",
    "vehicle": "owns a car with plate AB1234",
    "household": "lives with two children aged 4 and 7",
    "contact": "can be reached by email only, no phone calls",
}
QUERIES = [  # (query, relevant fact key or None)
    ("where does this person live", "address"),
    ("what is their home address", "address"),
    ("which language should letters be in", "language"),
    ("do they speak German", "language"),
    ("do they have a vehicle that needs a parking permit", "vehicle"),
    ("how many kids are in the household", "household"),
    ("how should we get in touch", "contact"),
    ("can I phone them", "contact"),
    ("what are the swimming pool opening hours", None),
    ("how much does a passport cost", None),
    ("when is waste collected", None),
    ("tell me about the town council meeting", None),
]


def main() -> int:
    keys = list(FACTS)
    fvec = embed([f"{k}: {FACTS[k]}" for k in keys])
    qvec = embed([q for q, _ in QUERIES])
    rel, irr = [], []
    for (q, want), qv in zip(QUERIES, qvec):
        for k, fv in zip(keys, fvec):
            c = _cosine(qv, fv)
            (rel if k == want else irr).append((round(c, 3), q, k))
    rel.sort(); irr.sort(reverse=True)
    print("lowest relevant:", rel[:3])
    print("highest irrelevant:", irr[:3])
    gap = rel[0][0] - irr[0][0]
    print(f"relevant min {rel[0][0]}  irrelevant max {irr[0][0]}  gap {gap:.3f}")
    write_json("artifacts/week07_memory_similarity.json",
               {"relevant": rel, "irrelevant_top": irr[:10], "gap": gap})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
