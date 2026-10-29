"""Block 2, first half: call the memory tools over MCP. TODO 6.

    python mcp_server.py &          # in one terminal
    PORT=8001 python mcp_server.py & # and a second instance
    python 01_mcp_client.py

Three things happen here and the third is the one to watch.
"""

from __future__ import annotations

import asyncio

from mcp.client import Client

SUBJECT = "A. Muller"


def text_of(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        return getattr(content[0], "text", str(content[0]))
    return str(content)


async def call(port: int, tool: str, **args):
    async with Client(f"http://127.0.0.1:{port}/mcp") as client:
        return await client.call_tool(tool, args)


async def main() -> int:
    """TODO 6. Three steps, and the third has a warning attached.

    1. Connect to :8000 and print the tool catalog. Seeing it arrive over
       HTTP is what makes the boundary real: these tools are not in this
       process.

    2. Call open_case and then remember on :8000. Watch
       artifacts/memory_store.json change while it runs.

    3. Redeem the SAME handle on :8001, the second instance, and recall from
       it.

    The warning: step 3 on its own does not prove the protocol is stateless.
    It would work under the old session-based protocol too, because each
    call opens its own connection and the state is on disk. It shows that a
    file is a file. 02_stateless.py is the demonstration that actually
    distinguishes the two, and it is the next thing you run.
    """
    import json
    from pathlib import Path

    store = Path("artifacts/memory_store.json")   # run from the repo root

    def snapshot() -> str:
        return store.read_text(encoding="utf-8") if store.exists() else ""

    # Revision 2026-07-28: no initialize handshake, no session id. Client()
    # just sends self-describing requests.
    # 1. the catalog, discovered over HTTP
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()
    names = sorted(t.name for t in getattr(tools, "tools", tools))
    print(f"catalog discovered on :8000 ({len(names)} tools): {names}")

    # 2. open a case and write a fact on :8000, watching the file change
    before = snapshot()
    handle = text_of(await call(8000, "open_case", subject=SUBJECT,
                                principal="alice"))
    fact_handle = text_of(await call(8000, "remember", subject=SUBJECT,
                                     kind="language",
                                     fact="prefers correspondence in German"))
    after = snapshot()
    data = json.loads(after) if after else {}
    print(f"case handle: {handle}   fact handle: {fact_handle}")
    print(f"store file changed: {before != after}   "
          f"(facts={len(data.get('facts', []))}, "
          f"cases={len(data.get('cases', {}))})")

    # 3. redeem the SAME handle on :8001 (second instance)
    on_b = text_of(await call(8001, "case_subject", handle=handle,
                              principal="alice"))
    recalled = text_of(await call(8001, "recall_for_case", handle=handle,
                                  principal="alice", query="language"))
    print(f"on :8001 case_subject -> {on_b!r}")
    print(f"on :8001 recall_for_case -> {recalled!r}")

    # authorization: the right handle with the wrong principal gets nothing
    denied = text_of(await call(8001, "case_subject", handle=handle,
                                principal="mallory"))
    print(f"on :8001 wrong principal -> {denied!r}")

    ok = (on_b == SUBJECT and "German" in recalled
          and denied == "ERROR: unknown case" and before != after)
    print()
    print(("PASS" if ok else "FAIL") +
          ": handle redeemed on a second instance (this alone does NOT prove "
          "statelessness; see 02_stateless.py)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
