"""The memory store, exposed over MCP. TODO 4 and 5.

    python mcp_server.py            # serves on 8000
    PORT=8001 python mcp_server.py  # a second instance, same store

Targets MCP specification revision 2026-07-28. Every place this file relies
on that revision carries the date in a comment, because the protocol runs a
twelve month deprecation policy and a file without a date is a file nobody
can safely re-check.
"""

from __future__ import annotations

import asyncio
import os

try:                                    # week 7: dense search, same signature
    from app.memory import MemoryStore
except ImportError:                     # week 6 checkout without app/
    from memory import MemoryStore

try:
    from mcp.server import MCPServer   # revision 2026-07-28. SDK v1 had FastMCP.
except ImportError as exc:             # noqa: BLE001
    raise SystemExit(
        "Could not import MCPServer from mcp.server.\n"
        "The stable v1 line has no MCPServer class, so an unpinned install\n"
        "resolves to something that cannot run this file. Install the pin:\n"
        "    pip install --pre 'mcp==2.0.0rc1'\n"
    ) from exc


app = MCPServer("memory-desk")


# --------------------------------------------------------------------------
# TODO 4. The memory tools, over the wire.
# --------------------------------------------------------------------------
#
# These are the same three methods you wrote in block 1. What is new is that
# the description is now an interface contract for a model that is not in
# this process, which is the same lesson as week 4's tool schemas one layer
# further out.
#
# The store is loaded per call rather than held in a module global. That
# looks wasteful and it is the point: two server instances share one file, so
# each call reads the current state rather than a copy it cached at startup.
# A server that caches the store in memory is a server with session state
# hiding inside it, whatever the protocol says.

# TODO 4. Wrap the three memory methods as MCP tools.
#
#   remember(subject, kind, fact) -> handle
#   recall(subject, query, k=3)   -> list of facts
#   forget(handle)                -> bool
#
# Two things that are not obvious.
#
# The docstring becomes the tool description that a model in another process
# reads, so it is prompt engineering rather than documentation. Say what the
# tool returns, when NOT to use it, and what an empty result means, exactly
# as in week 4.
#
# Load the store per call rather than holding it in a module global. That
# looks wasteful and it is the point: two instances share one file, so each
# call must read the current state. A server that caches the store at startup
# has session state hiding inside it, whatever the protocol says.


# --------------------------------------------------------------------------
# TODO 5. The handle, which is the week's central move.
# --------------------------------------------------------------------------
#
# open_case mints a name for a piece of ongoing state, and every later call
# takes that name as an ordinary argument.
#
# That is the lecture's claim made executable. The protocol carries no
# session, so the state cannot hide in the transport. It has to be somewhere
# the request can point at, and the request is written by the model, so the
# state becomes something the model can see and reason about.
#
# Compare the two shapes:
#
#   session-based   the server remembers who you are between calls
#   stateless       you say who you are, every time, in the call
#
# The second is more typing and it is the one that scales, because any
# request can land on any instance. 02_stateless.py measures that at the
# wire.

# TODO 5. open_case(subject) -> handle, and case_subject(handle) -> subject.
#
# The handle is the state. Later calls pass it as an ordinary argument
# instead of the server remembering who you are.
#
# Write the two tools, then answer this in DECISIONS.md: what would the
# server have had to hold between calls if there were no handle, and what
# would that cost you when a second instance appears behind a load balancer?


# Revision 2026-07-28: tools are plain request/response. Nothing below reads
# or sets a session id; any instance can answer any call because the store is
# re-read from disk on every call (see the note above) and the case handle is
# an ordinary argument.


def _store() -> MemoryStore:
    return MemoryStore.load()


@app.tool()
def remember(subject: str, kind: str, fact: str) -> str:
    """Store one fact about one resident and return its handle.

    Returns a handle string like 'fact-1a2b3c4d5e6f'; keep it if you may need
    to forget the fact later. Writing a fact of the same kind for the same
    subject REPLACES the old one. Do not use this to log what was said in
    the conversation, only durable facts (address, preferred language).
    """
    return _store().write(subject, kind, fact)


@app.tool()
def recall(subject: str, query: str, k: int = 3) -> list[str]:
    """Return at most k remembered facts about ONE resident that match query.

    Only facts about `subject` are ever searched. An empty list means nothing
    stored about that subject matches, NOT that the resident has no record;
    do not guess a fact when the list is empty, say you do not know. Do not
    use this to look up opening hours or fees (use the handbook search).
    """
    return _store().search(subject, query, k)


@app.tool()
def forget(handle: str) -> bool:
    """Permanently delete one stored fact by its handle.

    Returns true if the fact existed and is now gone, false if the handle is
    unknown (it may already have been replaced or deleted). This does not
    remove the fact from any conversation it was already quoted in.
    """
    return _store().forget(handle)


# --------------------------------------------------------------------------
# TODO 5 (done). The handle: the server holds no per-client state between
# calls, so the state is a named thing the caller passes back.
#
# Without a handle the server would have had to remember "who is this
# connection" between calls, i.e. a session table. Behind a load balancer
# that table has to be shared or every client pinned to one instance
# (session affinity), which is exactly the cost the 2026-07-28 revision
# removed. With the handle, any instance answers any call.
#
# Authorization (homework): the handle is a bearer name, so each case records
# an owner and every case call must present the same `principal`. CAVEAT:
# here `principal` is a tool argument written by the model, so a hostile
# caller can simply claim to be the owner. A real deployment takes the
# principal from the authenticated transport (an OAuth token), never from an
# argument. Week 12 attacks this.
# --------------------------------------------------------------------------


@app.tool()
def open_case(subject: str, principal: str) -> str:
    """Open a case about one resident and return its handle.

    Returns 'case-<12 hex chars>'. Pass this handle back, with the same
    principal, to every later case_subject or recall_for_case call; the
    server remembers nothing else about you between calls.
    """
    return _store().open_case(subject, owner=principal)


@app.tool()
def case_subject(handle: str, principal: str) -> str:
    """Return the resident a case is about, or 'ERROR: unknown case'.

    The same error is returned for a handle that does not exist and for one
    that belongs to a different principal, so it cannot be used to probe
    which handles exist.
    """
    subject = _store().subject_of(handle, principal)
    return subject if subject is not None else "ERROR: unknown case"


@app.tool()
def recall_for_case(handle: str, principal: str, query: str,
                    k: int = 3) -> list[str]:
    """Search the facts of the resident a case is about.

    Returns up to k fact strings. Returns an empty list both when nothing
    matches and when the handle/principal pair is not valid; check
    case_subject first if you need to tell those apart.
    """
    store = _store()
    subject = store.subject_of(handle, principal)
    return store.search(subject, query, k) if subject is not None else []


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"MCP revision 2026-07-28, streamable HTTP, stateless")
    print(f"http://127.0.0.1:{port}/mcp")
    # stateless_http=True is the 2026-07-28 core: no initialize handshake,
    # no Mcp-Session-Id, every request self-describing. Leaving it off puts
    # the server back on session mode, where a header-less request without an
    # initialize is refused (400 Missing session ID); 02_stateless.py shows
    # that at the wire, and with --modern-headers shows the v2 SDK still
    # answers a fully self-describing request in session mode.
    asyncio.run(app.run_streamable_http_async(
        host="127.0.0.1", port=port, stateless_http=True))
