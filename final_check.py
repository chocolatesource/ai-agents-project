"""Final check: does the week 1-7 homework actually run?

    .venv\\Scripts\\python.exe final_check.py

Executes every script that needs NO language model (a few use the local
embedding model, nothing else), checks the outputs against what DECISIONS.md
claims, and prints PASS/FAIL per line. Exit code 0 only if everything passes.

Not covered on purpose: the live model runs (week 5 tables, week 6 memory
eval). They take minutes, are stochastic, and their saved results live in
artifacts/ and are only cross-checked here, not reproduced.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable
results: list[tuple[str, bool, str]] = []


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""),
          flush=True)


def main() -> int:
    print("== contract and gold set")
    rc, out = run([PY, "-m", "project.verify"])
    check("project.verify passes", rc == 0 and "match the contract" in out, out[-200:])
    g = json.loads((ROOT / "artifacts/goldset.json").read_text(encoding="utf-8"))
    by_week = {w: sum(1 for c in g["cases"] if c["week_added"] == w) for w in range(1, 8)}
    check("gold set has 58 cases (weeks 2,3,4,5,7 add 10,24,10,2,12)",
          len(g["cases"]) == 58 and [by_week[w] for w in (2, 3, 4, 5, 7)] == [10, 24, 10, 2, 12],
          str(by_week))

    print("== week 5")
    rc, out = run([PY, "labs/week05/toyrepo/run_tests.py"])
    check("toy repo has exactly one failure, and it is test_off_peak_starts_at_twenty",
          "failures=1" in out and "run=16" in out
          and "FAIL: test_off_peak_starts_at_twenty" in out, out[-120:])
    rc, out = run([PY, "-c",
        "import sys; sys.path.insert(0,'labs/week05/starter');"
        "from agents import Plan, validate_plan;"
        "ok=validate_plan(Plan(goal='g',steps=['read discounts.py','change > to >= in is_off_peak','run the tests to confirm'],suspect_file='discounts.py'));"
        "bad=validate_plan(Plan(goal='g',steps=['edit tests/test_pricing.py'],suspect_file='x.py'));"
        "print(ok[0], bad[0], len(bad[1]))"])
    check("validate_plan accepts a good plan and rejects a broken one with 4 problems",
          out.strip().endswith("True False 4"), out[-200:])
    rc, out = run([PY, "-c",
        "import sys; sys.path.insert(0,'labs/week05/starter');"
        "from repo import Work, apply_fix, run_tests;"
        "w=Work.fresh();"
        "r=[apply_fix(w,'tests/test_pricing.py','a','b'),apply_fix(w,'discounts.py','nope','x'),apply_fix(w,'discounts.py','return','yield')];"
        "f=apply_fix(w,'discounts.py','return start_hour > OFF_PEAK_FROM_HOUR','return start_hour >= OFF_PEAK_FROM_HOUR');"
        "print(sum(x.startswith('REFUSED') for x in r), f, run_tests(w).passed); w.cleanup()"])
    check("apply_fix refuses 3 bad edits, applies the real fix, suite goes green",
          out.strip().endswith("3 applied True"), out[-200:])
    t = json.loads((ROOT / "artifacts/week05_architectures.json").read_text(encoding="utf-8"))["rows"]
    green = {a: sum(r["green"] for r in t if r["architecture"] == a) for a in {r["architecture"] for r in t}}
    check("SAVED week 5 table (read, not re-run): 1/3 green each, 9 rows, tokens and seconds present",
          set(green.values()) == {1} and len(t) == 9
          and all("tokens" in r and "seconds" in r for r in t), str(green))

    print("== week 6")
    rc, out = run([PY, "labs/week06/starter/06_checkpoint1.py"])
    check("checkpoint 1: restart, scope, k, forget (5 checks, no FAIL)",
          rc == 0 and out.count("[PASS]") == 5 and "[FAIL]" not in out, out[-300:])
    for flag, expect_fail in (("", False), ("--control", True), ("--modern-headers", True)):
        rc, out = run([PY, "labs/week06/starter/02_stateless.py"] + ([flag] if flag else []), timeout=120)
        passes, fails = out.count("[PASS]"), out.count("[FAIL]")
        want = (2, 1) if expect_fail else (3, 0)
        failed_lines = [ln for ln in out.splitlines() if "[FAIL]" in ln]
        check(f"02_stateless.py {flag or '(default)'}: "
              f"{'ONLY the session-refusal check FAILs' if expect_fail else 'all 3 pass'}",
              (passes, fails) == want
              and (not expect_fail or "refused in session mode" in failed_lines[0]),
              f"pass={passes} fail={fails} {failed_lines}")
    rc, out = run([PY, "labs/week06/starter/02_stateless.py"], timeout=120)
    sess = [ln for ln in out.splitlines() if ln.strip().startswith("stateless_http=False")]
    check("session-mode row has status 400 AND the output quotes 'Bad Request: Missing session ID'",
          bool(sess) and " 400 " in sess[0] and "Bad Request: Missing session ID" in out, str(sess))
    rc, out = run([PY, "labs/week06/starter/04_a2a_channel.py"], timeout=120)
    check("A2A channel: 7 checks pass, no FAIL",
          rc == 0 and out.count("[PASS]") == 7 and "[FAIL]" not in out, out[-200:])
    rc, out = run([PY, "labs/week06/starter/03_a2a.py"], timeout=120)
    check("given A2A demo runs", rc == 0 and "5 an artifact" in out)
    src = "".join(p.read_text(encoding="utf-8") for p in
                  [ROOT / "labs/week06/starter/mcp_server.py", ROOT / "labs/week06/starter/01_mcp_client.py", ROOT / "app/memory.py"])
    check("no code sets an Mcp-Session-Id header", not re.search(r"['\"]Mcp-Session-Id['\"]\s*:", src, re.I))

    print("== week 7")
    rc, out = run([PY, "-m", "pytest", "-q", "labs/week07/starter/test_metrics.py"])
    check("hand-worked metric tests pass (3)", rc == 0 and "3 passed" in out, out[-150:])
    rc, out = run([PY, "-c",
        "from app.chunking import chunk_sections; from app.corpus_loader import load_sections;"
        "s=load_sections(); import itertools;"
        "bad=0\n"
        "for size,ov in ((300,40),(600,80),(1200,160)):\n"
        "    ch=chunk_sections(s,size,ov)\n"
        "    for sec in s:\n"
        "        assert any(c.key==sec.key for c in ch), sec.key\n"
        "        j=' '.join(c.text for c in ch if c.key==sec.key)\n"
        "        bad+=sum(1 for w in set(sec.text.split()) if w not in j)\n"
        "    assert len({c.chunk_id for c in ch})==len(ch)\n"
        "print('lost',bad,'sections',len(s))"])
    check("chunker loses no words at 300/600/1200 and ids are unique",
          "lost 0 sections 56" in out, out[-200:])
    rc, out = run([PY, "-m", "app.run", "--subject", "A. Muller", "Where does this resident live?"], timeout=180)
    check("app.run: memory.search is scoped and returns the fact (needs Ollama embedder)",
          "1 hit(s)" in out and "Hollerich" in out, out[-300:])
    rc, out = run([PY, "-m", "app.run", "--subject", "B. Weber", "Where does this resident live?"], timeout=180)
    check("app.run: B. Weber gets exactly her own fact (Diderich) and A. Muller's (Hollerich) appears nowhere",
          "memory.search('B. Weber'" in out and "1 hit(s)" in out
          and "Diderich" in out and "Hollerich" not in out, out[-300:])
    sw = json.loads((ROOT / "artifacts/week07_sweep.json").read_text(encoding="utf-8"))["table"]
    moved = [q for q, r in sw.items() if len({r[s]["dense_rank"] for s in ("300", "600", "1200")}) > 1]
    check("saved sweep: dense rank moves only on Q05", moved == ["Q05"], str(moved))
    sim = json.loads((ROOT / "artifacts/week07_memory_similarity.json").read_text(encoding="utf-8"))
    mem = (ROOT / "app/memory.py").read_text(encoding="utf-8")
    lowest_rel = min(x[0] for x in sim["relevant"])
    top_wrong = max(x[0] for x in sim["wrong_fact_top"])
    check("MIN_SIMILARITY 0.59 lies between the highest wrong-fact and lowest relevant saved score",
          "MIN_SIMILARITY = 0.59" in mem and top_wrong < 0.59 <= lowest_rel
          and sim["thresholds"]["0.59"]["wrong_fact_admitted"].startswith("0/"),
          f"{top_wrong} < 0.59 <= {lowest_rel}")

    print("== documents")
    d = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    for w in range(1, 8):
        check(f"DECISIONS.md has a '## Week {w}' section", f"\n## Week {w}\n" in d.replace("\r\n", "\n"))
    for w, n in ((5, 6), (6, 6), (7, 6)):
        sect = d.replace("\r\n", "\n").split(f"\n## Week {w}\n")[1].split("\n# Week")[0]
        check(f"week {w}: six numbered entries", len(re.findall(r"^### [1-6]\. ", sect, re.M)) == 6)

    dn = d.replace("\r\n", "\n")
    ev = json.loads((ROOT / "artifacts/week06_memory_eval.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "artifacts/week07_sweep.json").read_text(encoding="utf-8"))["meta"]
    tb = json.loads((ROOT / "artifacts/week05_task_b.json").read_text(encoding="utf-8"))["rows"]
    check("DECISIONS text matches artifacts: k tokens, 2,960 vs 1,176, 84 chunks, 0.74 s",
          list(ev["part1"]["prompt_tokens_by_k"].values()) == [56, 65, 81, 115]
          and ev["on_total"]["tokens"] == 2960 and ev["off_total"]["tokens"] == 1176
          and meta["600"]["chunks"] == 84 and meta["600"]["index_seconds"] == 0.74
          and "k=6 115" in dn and "2,960" in dn and "1,176" in dn and "**0.74 s**" in dn)
    check("DECISIONS Task B 0/3 done each: no row in the saved file is done",
          len(tb) == 9 and sum(r["done"] for r in tb) == 0 and "| 0/3 |" in dn)

    print("== git")
    rc, out = run(["git", "status", "--short"])
    check("working tree is clean (everything committed)", out.strip() == "", out[:200])
    rc, out = run(["git", "log", "origin/master..HEAD", "--oneline"])
    print(f"  [INFO] commits not yet pushed: {len(out.strip().splitlines())}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for n in failed:
        print("  FAILED:", n)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
