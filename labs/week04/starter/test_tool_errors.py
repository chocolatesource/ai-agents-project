"""Checkpoint 1: force tool errors and check what text the model would see.

Run from the repo root:  python labs/week04/starter/test_tool_errors.py
Fails (exit 1) if any error text contains a file path.
"""
import re
import sys

import agent

PATH_LIKE = re.compile(r"([A-Za-z]:\\|/Users/|/home/|\\Users\\|\.py\b|Traceback)")


def boom_path(**_):
    raise FileNotFoundError(r"C:\Users\ASUS\secret\handbook.json not found")


def boom_generic(**_):
    raise RuntimeError("index at /home/app/data/idx.bin is corrupt")


cases = [
    ("invalid JSON", "search_services", "{not json"),
    ("arguments not an object", "search_services", "[1, 2]"),
    ("unknown tool", "delete_everything", "{}"),
    ("missing argument", "search_services", "{}"),
    ("wrong argument name", "compute", '{"expr": "1+1"}'),
    ("empty query (tool raises ValueError)", "search_services", '{"query": ""}'),
    ("unsafe expression (tool raises ValueError)", "compute",
     '{"expression": "__import__(\'os\').system(\'ls\')"}'),
]
agent.DISPATCH["leaky_path"] = boom_path
agent.DISPATCH["leaky_generic"] = boom_generic
cases += [("tool raises FileNotFoundError with a path", "leaky_path", "{}"),
          ("tool raises RuntimeError with a path", "leaky_generic", "{}")]

bad = 0
for label, name, args in cases:
    text, errored = agent.run_tool_call(name, args)
    leak = bool(PATH_LIKE.search(text))
    bad += leak
    print(f"[{'LEAK' if leak else 'ok  '}] {label}: errored={errored}\n        {text}")
print(f"\n{len(cases)} cases, {bad} leaked a path")
sys.exit(1 if bad else 0)
