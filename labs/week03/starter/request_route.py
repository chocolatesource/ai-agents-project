"""Homework: the week 2 extractor behind the `request` route.

The request specialist stops producing prose and produces a validated
ServiceRequest record. Everything the router sends to `request` goes through
week 2's `extract` with its zero-shot prompt; anything else keeps its prose
specialist.

    python labs/week03/starter/request_route.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from openai import OpenAI

from queries import QUERIES
from router import apply_policy, classify

from project.models import BASE_URL, API_KEY, SMALL
from project.trace import write_json

_ext_path = Path(__file__).resolve().parents[2] / "week02" / "starter" / "extractor.py"
_spec = importlib.util.spec_from_file_location("week02_extractor", _ext_path)
ext = importlib.util.module_from_spec(_spec)
sys.modules["week02_extractor"] = ext
_spec.loader.exec_module(ext)


def handle_request(client, text: str):
    """Return (validated record or None, meta). No prose."""
    return ext.extract(client, ext.SYSTEM_ZERO_SHOT, text)


def main() -> int:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    rows, valid, verbatim = [], 0, 0
    for q in QUERIES:
        d, _ = classify(client, q.text)
        routed = apply_policy(d, q.text)
        if routed.applied_route != "request":
            continue
        record, meta = handle_request(client, q.text)
        ok = record is not None
        valid += ok
        quote_ok = ok and record.quote in q.text
        verbatim += quote_ok
        print(f"{q.id} gold={q.route:<8} valid={ok} quote_verbatim={quote_ok} "
              f"{record.model_dump(mode='json') if ok else meta['error']}")
        rows.append({"case": q.id, "valid": ok, "quote_verbatim": quote_ok,
                     "record": record.model_dump(mode="json") if ok else None})
    print(f"\n{len(rows)} messages reached the request route: "
          f"{valid} valid records, {verbatim} with a verbatim quote")
    write_json("artifacts/week03_request_route.json",
               {"model": SMALL.name, "routed": len(rows), "valid": valid,
                "quote_verbatim": verbatim, "rows": rows})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
