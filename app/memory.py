"""The memory store, and the handle. TODO 1 to 3.

Two things live here and they are easy to confuse.

**Memory** is what the agent remembers about a resident across runs: facts,
written once and searched later. It is a store.

**A handle** is a name for a piece of state that the agent carries in its own
messages. It is not memory, it is an address. `open_case` mints one, and
every later call passes it back as an ordinary argument.

The distinction is the whole week. Block 2 shows why: when the protocol stops
carrying state for you, the state does not vanish, it becomes an argument
with a name the model can see.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path("artifacts/memory_store.json")

# Retention: a fact older than this is treated as gone by search. Declared
# rather than left implicit (DECISIONS.md, week 6 entry 2).
RETENTION_DAYS = 365


# Minimum cosine similarity for a fact to count as a hit. Chosen from the
# measurement in artifacts/week07_memory_similarity.json (nomic-embed-text,
# 2026-10-29): queries with no relevant fact scored at most 0.448, the lowest
# relevant pair scored 0.601, and the right fact ranked first on 8 of 8 queries.
# The margin comes from a 12-query sample; re-measure before trusting it.
MIN_SIMILARITY = 0.50


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass
class Fact:
    subject: str
    kind: str
    text: str
    handle: str
    written_at: str


@dataclass
class MemoryStore:
    """A file-backed store. Deliberately not a database and not a vector store.

    Week 7 replaces `search` with real retrieval over embeddings. Keep the
    keyword version behind this one method and next week costs you ten lines
    instead of a refactor.
    """

    path: Path = DEFAULT_PATH
    facts: list[Fact] = field(default_factory=list)
    cases: dict[str, str] = field(default_factory=dict)
    owners: dict[str, str] = field(default_factory=dict)   # handle -> principal

    # ----------------------------------------------------------------
    # TODO 1. Writing, and the handle it returns.
    # ----------------------------------------------------------------

    def write(self, subject: str, kind: str, text: str) -> str:
        """TODO 1. Append one fact and return a handle for it.

        Three decisions here, and all three go in DECISIONS.md with a reason.

        What does a handle look like? A sequential `fact-0007` tells anyone
        who sees it how many facts exist and lets them guess `fact-0006`,
        which is a read of somebody else's data. Week 12 attacks exactly
        this.

        What happens when a new fact contradicts an older one? Keeping both
        means `recall` can return two contradictory facts and something has
        to cope. Overwriting means losing what changed and when. Pick one.

        How long does a record live? Nothing here expires, which is a choice
        and the wrong one for a real service holding residents' data. If you
        keep it, say so rather than leaving it unsaid.
        """
        # Conflict policy: one live fact per (subject, kind). A new write of the
        # same kind replaces the old one (overwrite), so recall never has to
        # cope with two contradictory facts. The cost is losing what changed.
        self.facts = [f for f in self.facts
                      if not (f.subject == subject and f.kind == kind)]
        # Unguessable handle: 48 random bits, no counter, so a handle reveals
        # neither how many facts exist nor what a neighbouring one is called.
        handle = f"fact-{secrets.token_hex(6)}"
        self.facts.append(Fact(
            subject=subject, kind=kind, text=text, handle=handle,
            written_at=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.save()
        return handle

    # ----------------------------------------------------------------
    # TODO 2. Searching, and what k costs.
    # ----------------------------------------------------------------

    def search(self, subject: str, query: str, k: int = 3) -> list[str]:
        """Return at most k remembered facts about ONE subject.

        Week 7: the body is now dense retrieval; the signature, and the
        scoping-before-scoring boundary, are unchanged from week 6. If the
        embedding server is unreachable it falls back to the week 6 keyword
        match, so memory degrades instead of failing.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        pool = [f for f in self.facts if f.subject == subject      # SCOPE first
                and datetime.fromisoformat(f.written_at) >= cutoff]
        if not pool or k <= 0:
            return []
        try:
            from .retrieval import embed
            vecs = embed([query] + [f"{f.kind}: {f.text}" for f in pool])
            q, docs = vecs[0], vecs[1:]
            scored = [(_cosine(q, d), f) for d, f in zip(docs, pool)]
            scored = [(s, f) for s, f in scored if s >= MIN_SIMILARITY]
            scored.sort(key=lambda p: (-p[0], p[1].handle))
            return [f.text for _, f in scored[:k]]
        except OSError:                       # embedder down: week 6 behaviour
            return self._keyword_search(pool, query, k)

    @staticmethod
    def _keyword_search(pool: list[Fact], query: str, k: int) -> list[str]:
        q = _tokens(query)
        scored = [(len(q & _tokens(f"{f.kind} {f.text}")), f) for f in pool]
        scored = [(n, f) for n, f in scored if n > 0]
        scored.sort(key=lambda p: (-p[0], p[1].written_at))
        return [f.text for _, f in scored[:k]]

    # ----------------------------------------------------------------
    # TODO 3. Forgetting, which is not optional.
    # ----------------------------------------------------------------

    def forget(self, handle: str) -> bool:
        """TODO 3. Hard delete by handle. Return whether it existed.

        Not optional. A store that can only be written to is not a store you
        can operate, and "we keep everything forever" is an answer with a
        legal department attached to it.

        One line in DECISIONS.md about what this does NOT reach: anything
        already copied into a running conversation's messages. Deleting the
        fact does not un-say it.
        """
        before = len(self.facts)
        self.facts = [f for f in self.facts if f.handle != handle]
        existed = len(self.facts) < before
        if existed:
            self.save()
        return existed

    # ----------------------------------------------------------------
    # The handle, which is block 2's subject
    # ----------------------------------------------------------------

    def open_case(self, subject: str, owner: str = "") -> str:
        """Mint an explicit handle for a piece of ongoing state.

        `owner` is the principal who opened the case. Homework (week 6): a
        handle alone no longer grants access, the caller must also be the
        owner. See `subject_of`.
        """
        handle = f"case-{secrets.token_hex(6)}"
        self.cases[handle] = subject
        self.owners[handle] = owner
        self.save()
        return handle

    def subject_of(self, handle: str, principal: str | None = None) -> str | None:
        """Resolve a handle to its subject, if the caller may.

        Authorization check: the handle is a bearer name, so holding it is
        necessary but not sufficient. When `principal` is given it must equal
        the owner recorded at open_case, otherwise this returns None, exactly
        as for an unknown handle (no oracle for which handles exist).
        Passing principal=None skips the check and exists only for the
        week 6 starter scripts; the MCP server never does.
        """
        if handle not in self.cases:
            return None
        if principal is not None and self.owners.get(handle, "") != principal:
            return None
        return self.cases[handle]

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "facts": [vars(f) for f in self.facts],
            "cases": self.cases,
            "owners": self.owners,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "MemoryStore":
        store = cls(path=path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            store.facts = [Fact(**f) for f in data.get("facts", [])]
            store.cases = data.get("cases", {})
            store.owners = data.get("owners", {})
        return store
