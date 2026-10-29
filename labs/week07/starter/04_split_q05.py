"""Week 7 'if you finish early': fix the compositional question by splitting it.

    python 04_split_q05.py

Q05 needs two sections from two documents and fails on both retrievers at every
chunk size. Split it into one question per need, retrieve for each, merge the
two lists (interleaved, deduplicated) and score the merged list with the SAME
metrics. Reports what it fixes and what it costs (embedding calls).
"""
from __future__ import annotations

from chunking import load_chunks
from goldset import GOLD
from metrics import score
from retrieval import DenseIndex, keyword_search

from project.trace import write_json

SPLIT = ["I have just moved to Remerbaach. What do I have to do at the commune?",
         "I own a car. What do I have to do at the commune?"]


def merge(lists):
    out, seen = [], set()
    for rank in range(max(len(x) for x in lists)):
        for lst in lists:
            if rank < len(lst) and lst[rank].chunk_id not in seen:
                seen.add(lst[rank].chunk_id); out.append(lst[rank])
    return out


def main() -> int:
    q5 = next(q for q in GOLD if q.qid == "Q05")
    res = {}
    for size, ov in ((300, 40), (600, 80), (1200, 160)):
        chunks = load_chunks(size, ov)
        idx = DenseIndex(chunks, name=f"split_{size}")
        n = len(chunks)
        for name, search in (("dense", lambda q: idx.search(q, k=n)),
                             ("keyword", lambda q: keyword_search(chunks, q, k=n))):
            whole = score(search(q5.question), q5, k=5)
            merged = score(merge([search(s) for s in SPLIT]), q5, k=5)
            res[f"{name}@{size}"] = {"whole_rank": whole.rank, "whole_recall5": whole.recall_at_k,
                                     "split_rank": merged.rank, "split_recall5": merged.recall_at_k}
            print(f"{name:<8}{size:>5}  whole: rank {whole.rank}, recall@5 {whole.recall_at_k}"
                  f"   split+merge: rank {merged.rank}, recall@5 {merged.recall_at_k}")
    res["cost"] = "2 query embeddings instead of 1; the split itself was written by hand"
    write_json("artifacts/week07_split_q05.json", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
