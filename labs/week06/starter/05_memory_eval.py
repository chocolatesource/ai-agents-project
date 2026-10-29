"""Week 6 entries 3 and 4: what k costs, and memory off against memory on.

    python 05_memory_eval.py

Part 1  prompt tokens added per call as k grows (Ollama prompt_eval_count),
        and search latency with 5 versus 400 facts for one subject.
Part 2  six questions whose answer is a stored fact. Memory OFF: the model
        has no recall tool, and a simulated user supplies the missing fact
        when asked (one extra turn). Memory ON: the model has a recall tool.
        Counted: model calls ('turns'), total tokens, correct final answers.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from app.memory import MemoryStore

from project.models import LARGE, client_for
from project.trace import write_json

SUBJECT = "A. Muller"
FACTS = [("address", "lives at 12 rue de Hollerich"),
         ("language", "prefers correspondence in German"),
         ("vehicle", "owns a car with plate AB1234"),
         ("household", "lives with two children aged 4 and 7"),
         ("contact", "can be reached by email only, no phone calls"),
         ("birthday", "was born on 3 March 1988")]
QUESTIONS = [("In which language should I write to this resident?", "German"),
             ("What is the resident's plate number?", "AB1234"),
             ("How many children does the resident have?", "two"),
             ("May I phone this resident?", "email"),
             ("Which street does the resident live on?", "Hollerich"),
             ("What is the resident's date of birth?", "1988")]
SYSTEM = ("You help a commune help desk. Answer in one short sentence. "
          "Never guess a personal detail about the resident: if you do not "
          "have it, say exactly 'I do not have that'.")
TOOLS = [{"type": "function", "function": {
    "name": "recall", "description":
    "Return remembered facts about the resident. Empty list = nothing stored.",
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string"}}, "required": ["query"]}}}]


def part1(store: MemoryStore, client) -> dict:
    out = {"prompt_tokens_by_k": {}}
    base = None
    for k in (0, 1, 3, 6):
        # inject k stored facts directly: this measures the cost of k, not of
        # whether a generic query clears the similarity threshold
        facts = [f.text for f in store.facts[:k]]
        msg = SYSTEM + "\nFacts: " + "; ".join(facts)
        r = client.chat.completions.create(
            model=LARGE.name, temperature=0, max_tokens=1,
            messages=[{"role": "system", "content": msg},
                      {"role": "user", "content": "Hello"}])
        out["prompt_tokens_by_k"][k] = r.usage.prompt_tokens
        base = base or r.usage.prompt_tokens
    big = MemoryStore(path=Path(tempfile.mkdtemp()) / "big.json")
    for i in range(400):
        big.facts.append(type(store.facts[0])(
            SUBJECT, f"note{i}", f"remembered detail number {i} about errand {i}",
            f"fact-{i:04d}", "2026-10-29T00:00:00+00:00"))
    t0 = time.perf_counter(); store.search(SUBJECT, "address", k=3)
    out["search_seconds_6_facts"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter(); big.search(SUBJECT, "address", k=3)
    out["search_seconds_400_facts"] = round(time.perf_counter() - t0, 2)
    return out


def run_off(client, question: str, gold: str, fact_sentence: str) -> dict:
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": question}]
    turns = tokens = 0
    for _ in range(3):
        r = client.chat.completions.create(model=LARGE.name, temperature=0,
                                           messages=msgs, max_tokens=80)
        turns += 1; tokens += r.usage.total_tokens
        text = r.choices[0].message.content or ""
        if gold.lower() in text.lower():
            return {"correct": True, "turns": turns, "tokens": tokens}
        # simulated user supplies the fact once the model has asked/declined
        msgs += [{"role": "assistant", "content": text},
                 {"role": "user", "content": f"The file says: {fact_sentence}"}]
    return {"correct": False, "turns": turns, "tokens": tokens}


SYSTEM_ON = (SYSTEM + " You have a recall tool that returns the resident's "
             "stored facts. Call it BEFORE answering any question about the "
             "resident.")


def run_on(client, store, question: str, gold: str) -> dict:
    msgs = [{"role": "system", "content": SYSTEM_ON},
            {"role": "user", "content": question}]
    turns = tokens = 0
    for _ in range(4):
        r = client.chat.completions.create(model=LARGE.name, temperature=0,
                                           messages=msgs, tools=TOOLS,
                                           max_tokens=80)
        turns += 1; tokens += r.usage.total_tokens
        m = r.choices[0].message
        if not m.tool_calls:
            return {"correct": gold.lower() in (m.content or "").lower(),
                    "turns": turns, "tokens": tokens}
        msgs.append(m.model_dump(exclude_none=True))
        for tc in m.tool_calls:
            q = json.loads(tc.function.arguments).get("query", question)
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(store.search(SUBJECT, q, k=3))})
    return {"correct": False, "turns": turns, "tokens": tokens}


def main() -> int:
    client = client_for(LARGE)
    store = MemoryStore(path=Path(tempfile.mkdtemp()) / "s.json")
    for kind, text in FACTS:
        store.write(SUBJECT, kind, text)
    res = {"model": LARGE.name, "part1": part1(store, client), "off": [], "on": []}
    print("part 1:", res["part1"])
    for (q, gold), (_, sentence) in zip(QUESTIONS, [
            FACTS[1], FACTS[2], FACTS[3], FACTS[4], FACTS[0], FACTS[5]]):
        off, on = run_off(client, q, gold, sentence), run_on(client, store, q, gold)
        res["off"].append(off); res["on"].append(on)
        print(f"{q[:44]:<46} off {off}  on {on}", flush=True)
    for side in ("off", "on"):
        rows = res[side]
        res[side + "_total"] = {
            "correct": sum(r["correct"] for r in rows),
            "turns": sum(r["turns"] for r in rows),
            "tokens": sum(r["tokens"] for r in rows), "n": len(rows)}
        print(side, res[side + "_total"])
    write_json("artifacts/week06_memory_eval.json", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
