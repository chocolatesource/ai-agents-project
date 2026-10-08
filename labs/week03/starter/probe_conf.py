"""Block 2 probe: print the confidence distribution before choosing a floor.

Usage: python labs/week03/starter/probe_conf.py [model]

Prints one line per query and saves everything to
artifacts/week03_probe_<model>.json so the numbers can be rechecked.
"""
import json
import sys
from datetime import date

from openai import OpenAI
from queries import QUERIES
from router import classify

from project.models import BASE_URL, API_KEY
from project.trace import write_json

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b-instruct"
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
rows, right = [], 0
for q in QUERIES:
    d, m = classify(client, q.text, model)
    if d is None:
        print(q.id, "INVALID", m["error"])
        rows.append({"id": q.id, "gold": q.route, "invalid": m["error"]})
        continue
    ok = d.route == q.route
    right += ok
    verbatim = d.evidence in q.text
    print(f"{q.id} gold={q.route:<9} got={d.route:<9} conf={d.confidence:.2f} "
          f"{'ok ' if ok else 'XX '}{'amb ' if q.ambiguous else '    '}"
          f"verbatim={verbatim}  {d.evidence[:50]!r}")
    rows.append({"id": q.id, "gold": q.route, "got": d.route,
                 "confidence": d.confidence, "correct": ok,
                 "ambiguous": q.ambiguous, "evidence": d.evidence,
                 "evidence_verbatim": verbatim,
                 "seconds": round(m["seconds"], 3)})
confs = sorted({r["confidence"] for r in rows if "confidence" in r})
print(model, right, "/", len(QUERIES), "distinct conf:", confs)
safe = model.replace(":", "_").replace("/", "_")
write_json(f"artifacts/week03_probe_{safe}.json", {
    "model": model, "date": date.today().isoformat(),
    "correct_by_intention": right, "total": len(QUERIES),
    "distinct_confidences": confs,
    "evidence_verbatim": sum(1 for r in rows if r.get("evidence_verbatim")),
    "rows": rows})
