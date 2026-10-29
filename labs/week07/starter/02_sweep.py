"""Week 7 homework: the chunk sweep at 300, 600, 1200. Names, not means.

    python 02_sweep.py

One gold set scores every size because it names sections, not chunk ids.
Records the embedding model, dimensionality, chunker settings and the
wall-clock time of each full indexing run.
"""
from __future__ import annotations

import time

from chunking import load_chunks
from goldset import GOLD
from metrics import score
from retrieval import DenseIndex, keyword_search

from project.trace import write_json

K = 5
CONFIGS = [(300, 40), (600, 80), (1200, 160)]   # overlap ~ 13% of size


def main() -> int:
    table: dict[str, dict] = {}
    meta = {}
    for size, overlap in CONFIGS:
        chunks = load_chunks(size, overlap)
        t0 = time.perf_counter()
        index = DenseIndex(chunks, name=f"sweep_{size}_{overlap}")
        meta[size] = {"chunks": len(chunks), "dim": index.dim,
                      "overlap": overlap,
                      "index_seconds": round(time.perf_counter() - t0, 2)}
        for q in GOLD:
            if not q.answerable:
                continue
            d = score(index.search(q.question, k=len(chunks)), q, k=K)
            kw = score(keyword_search(chunks, q.question, k=len(chunks)), q, k=K)
            table.setdefault(q.qid, {"tags": list(q.tags)})[str(size)] = {
                "dense_rank": d.rank, "dense_recall": d.recall_at_k,
                "kw_rank": kw.rank, "kw_recall": kw.recall_at_k}
    print(f"{'qid':<5}" + "".join(f"{'d@' + str(s):>7}{'k@' + str(s):>7}"
                                   for s, _ in CONFIGS) + "   tags")
    for qid, row in table.items():
        print(f"{qid:<5}" + "".join(
            f"{str(row[str(s)]['dense_rank']):>7}{str(row[str(s)]['kw_rank']):>7}"
            for s, _ in CONFIGS) + "   " + ",".join(row["tags"]))
    moved = [qid for qid, r in table.items()
             if len({r[str(s)]['dense_rank'] for s, _ in CONFIGS}) > 1]
    print("\ndense rank changes with chunk size on:", moved or "none")
    print({s: m for s, m in meta.items()})
    write_json("artifacts/week07_sweep.json",
               {"k": K, "meta": meta, "table": table,
                "embed_model": "nomic-embed-text"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
