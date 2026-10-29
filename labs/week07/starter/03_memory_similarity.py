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
    rel, wrong, off_topic_best, top1, n_rel = [], [], [], 0, 0
    for (q, want), qv in zip(QUERIES, qvec):
        scores = sorted(((round(_cosine(qv, fv), 3), k)
                         for k, fv in zip(keys, fvec)), reverse=True)
        if want is None:                       # nothing relevant is stored
            off_topic_best.append((scores[0][0], q, scores[0][1]))
            continue
        n_rel += 1
        top1 += scores[0][1] == want
        for sc, k in scores:
            (rel if k == want else wrong).append((sc, q, k))
    rel.sort(); wrong.sort(reverse=True); off_topic_best.sort(reverse=True)
    print(f"top-1 correct: {top1}/{n_rel}")
    print("lowest relevant pairs:", rel[:3])
    print("highest wrong-fact pairs (same subject, other fact):", wrong[:3])
    print("highest score on a query with NO relevant fact:", off_topic_best[:2])
    table = {}
    for t in (0.50, 0.55, 0.59, 0.60):
        hit_rel = sum(1 for sc, *_ in rel if sc >= t)
        hit_wrong = sum(1 for sc, *_ in wrong if sc >= t)
        hit_off = sum(1 for sc, *_ in off_topic_best if sc >= t)
        table[str(t)] = {"relevant_kept": f"{hit_rel}/{len(rel)}",
                         "wrong_fact_admitted": f"{hit_wrong}/{len(wrong)}",
                         "off_topic_queries_answered": f"{hit_off}/{len(off_topic_best)}"}
        print(f"threshold {t}: relevant kept {hit_rel}/{len(rel)}, wrong-fact "
              f"pairs admitted {hit_wrong}/{len(wrong)}, off-topic queries "
              f"that still return a fact {hit_off}/{len(off_topic_best)}")
    write_json("artifacts/week07_memory_similarity.json", {
        "embed_model": "nomic-embed-text", "date": "2026-10-29",
        "queries": len(QUERIES), "facts": len(FACTS),
        "top1_correct": f"{top1}/{n_rel}", "relevant": rel,
        "wrong_fact_top": wrong[:10], "off_topic_best": off_topic_best,
        "thresholds": table})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
