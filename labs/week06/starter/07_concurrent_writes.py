"""Week 6 'if you finish early': two instances writing at the same moment.

    python 07_concurrent_writes.py

The MCP server loads the store, changes it and saves it on every call, with no
lock. Two processes each make N writes of DIFFERENT facts (so the overwrite
policy cannot explain a loss) and we count what survives. Expected: 2N.
"""
from __future__ import annotations

import multiprocessing as mp
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory import MemoryStore  # noqa: E402

N = 40


def worker(path: str, name: str, start_at: float) -> None:
    import time
    while time.time() < start_at:
        pass
    for i in range(N):
        s = MemoryStore.load(Path(path))          # load per call, like the server
        s.write(name, f"kind{i}", f"fact {i} from {name}")


def main() -> int:
    import time
    path = Path(tempfile.mkdtemp()) / "store.json"
    MemoryStore(path=path).save()
    go = time.time() + 2.0
    ps = [mp.Process(target=worker, args=(str(path), n, go)) for n in ("A", "B")]
    [p.start() for p in ps]; [p.join() for p in ps]
    final = MemoryStore.load(path)
    by = {n: sum(1 for f in final.facts if f.subject == n) for n in ("A", "B")}
    print(f"expected {2 * N} facts, found {len(final.facts)} (A {by['A']}/{N}, B {by['B']}/{N})")
    print("LOST UPDATES" if len(final.facts) < 2 * N else "no loss this run (race not hit)")
    return 0


if __name__ == "__main__":
    mp.set_start_method("spawn")
    raise SystemExit(main())
