"""Week 6 checkpoint 1 as a saved script: restart, scope, k, forget.

    python 06_checkpoint1.py        (run from the repo root)

Uses the week 6 keyword store (labs/week06/starter/memory.py), no model.
The restart check runs the second half in a SEPARATE PROCESS, so "different
behaviour on the second run" is observed rather than asserted.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRELUDE = f"import sys; sys.path.insert(0, {str(HERE)!r}); from memory import MemoryStore; from pathlib import Path"


def child(code: str) -> str:
    return subprocess.run([sys.executable, "-c", PRELUDE + "\n" + code],
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    path = Path(tempfile.mkdtemp()) / "store.json"
    p = repr(str(path))
    checks: dict[str, bool] = {}

    first = child(f"s=MemoryStore.load(Path({p}));"
                  f"print(len(s.search('A. Muller','address')))")
    child(f"s=MemoryStore.load(Path({p}));"
          f"s.write('A. Muller','address','lives at 12 rue de Hollerich')")
    second = child(f"s=MemoryStore.load(Path({p}));"
                   f"print(s.search('A. Muller','address'))")
    print(f"restart: process 1 recalls {first} fact(s); after a write, a NEW "
          f"process 2 recalls {second}")
    checks["store survives a process restart (0 facts, then the fact)"] = (
        first == "0" and "Hollerich" in second)

    sys.path.insert(0, str(HERE))
    import memory as m
    s = m.MemoryStore(path=Path(tempfile.mkdtemp()) / "s2.json")
    a = s.write("A. Muller", "address", "lives at 12 rue de Hollerich")
    s.write("A. Muller", "language", "prefers address letters in German")
    s.write("A. Muller", "contact", "address by email only")
    s.write("B. Weber", "address", "lives at 5 avenue Gaston Diderich")

    got_b = s.search("B. Weber", "address Hollerich rue")
    print("scope: B. Weber searching A's words ->", got_b)
    checks["other subject's facts do not come back"] = (
        all("Hollerich" not in t for t in got_b))

    k1, k2 = s.search("A. Muller", "address", k=1), s.search("A. Muller", "address", k=2)
    print(f"k: k=1 -> {len(k1)} fact(s), k=2 -> {len(k2)} fact(s)")
    checks["search respects k"] = len(k1) == 1 and len(k2) == 2

    print("handles:", a, "| sequential-looking?", a.endswith("0001"))
    checks["handle is not sequential"] = not a.endswith("0001")

    ok = s.forget(a)
    after = s.search("A. Muller", "Hollerich")
    print(f"forget: returned {ok}; searching 'Hollerich' now -> {after}; "
          f"forget again -> {s.forget(a)}")
    checks["forget removes the fact; second forget returns False"] = (
        ok and not after and s.forget(a) is False)

    print()
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
