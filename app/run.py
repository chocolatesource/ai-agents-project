"""Prove the retriever is wired into memory.search.

    python -m app.run --subject "A. Muller" "How do I register a new address?"

Prints the memory.search line (ending in a hit count) and the top handbook
chunks for the same question at the chunk size DECISIONS.md chose (600/80).
Uses a throwaway store so it never touches artifacts/memory_store.json.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .chunking import load_chunks
from .memory import MemoryStore
from .retrieval import DenseIndex


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--subject", default="A. Muller")
    args = ap.parse_args()

    store = MemoryStore(path=Path(tempfile.mkdtemp()) / "store.json")
    store.write(args.subject, "address", "lives at 12 rue de Hollerich")
    store.write(args.subject, "language", "prefers correspondence in German")
    store.write("B. Weber", "address", "lives at 5 avenue Gaston Diderich")
    hits = store.search(args.subject, args.question, k=3)
    print(f"memory.search({args.subject!r}, {args.question!r}) -> "
          f"{len(hits)} hit(s): {hits}")

    chunks = load_chunks(600, 80)
    index = DenseIndex(chunks, name="run_600_80")
    print(f"handbook: {len(chunks)} chunks, top 3:")
    for c in index.search(args.question, k=3):
        print(f"  {c.doc_id} / {c.section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
