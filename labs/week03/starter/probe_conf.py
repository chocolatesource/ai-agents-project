"""Block 2 probe: print the confidence distribution before choosing a floor."""
import sys
from openai import OpenAI
from queries import QUERIES
from router import classify
from project.models import BASE_URL, API_KEY

model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:4b-instruct"
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
confs, right = [], 0
for q in QUERIES:
    d, m = classify(client, q.text, model)
    if d is None:
        print(q.id, "INVALID", m["error"]); continue
    ok = d.route == q.route; right += ok
    confs.append((d.confidence, ok))
    print(f"{q.id} gold={q.route:<9} got={d.route:<9} conf={d.confidence:.2f} "
          f"{'ok ' if ok else 'XX '}{'amb ' if q.ambiguous else '    '}"
          f"verbatim={d.evidence in q.text}  {d.evidence[:50]!r}")
print(model, right, "/", len(QUERIES), "distinct conf:",
      sorted({c for c, _ in confs}))
