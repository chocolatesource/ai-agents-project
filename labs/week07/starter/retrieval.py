"""The index and the two retrievers. TODO 3.

Chroma is a black box here, exactly as the syllabus asks. You put vectors in
with metadata and you get ranked ids out. What is worth your attention is
what you put in and how you score what comes back.

Two retrievers, because block 2 compares them:

  dense     embeddings, cosine similarity. Good at meaning, indifferent to
            exact strings.
  keyword   term overlap. The reverse. Deliberately crude, so it is obvious
            what it is doing.
"""

from __future__ import annotations

import json
import re
import urllib.request

from chunking import Chunk

from project.models import EMBED, OLLAMA_URL

EMBED_MODEL = EMBED.name


def embed(texts: list[str], batch: int = 32) -> list[list[float]]:
    """TODO 3a. Embed a list of texts, in batches.

    One call per chunk is the obvious version and it is roughly thirty times
    slower on this corpus. The endpoint takes a list, so give it one.

    POST to f"{OLLAMA_URL}/api/embed" with a JSON body of
    {"model": EMBED_MODEL, "input": [...]} and read the "embeddings" key.
    """
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch):
        body = json.dumps({"model": EMBED_MODEL,
                           "input": texts[i:i + batch]}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embed", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            vectors.extend(json.loads(resp.read())["embeddings"])
    return vectors


class DenseIndex:
    """TODO 3b. Build once per configuration, then query it."""

    def __init__(self, chunks: list[Chunk], name: str = "run_a"):
        """Build the index.

        chromadb.EphemeralClient(), then get_or_create_collection(name),
        then add() with ids, embeddings, and metadatas carrying doc_id and
        section.

        Give the collection a NAME that encodes the configuration. Two
        chunkings have to be able to coexist during the block 3 sweep, and
        rebuilding without deleting is the classic way to end up with two
        chunkings in one index and numbers nobody can explain.

        Keep a dict from chunk_id to Chunk, because search has to map the
        ids Chroma returns back to objects. Set self.dim so the brief's
        conditions line has something to record.
        """
        import chromadb
        self.chunks = {c.chunk_id: c for c in chunks}
        vectors = embed([c.text for c in chunks])
        self.dim = len(vectors[0])
        self._client = chromadb.EphemeralClient()
        # EphemeralClient shares process-wide state, so drop a stale
        # collection of the same name instead of silently adding to it.
        try:
            self._client.delete_collection(name)
        except Exception:                                    # noqa: BLE001
            pass
        self._col = self._client.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine"})
        self._col.add(ids=[c.chunk_id for c in chunks], embeddings=vectors,
                      metadatas=[{"doc_id": c.doc_id, "section": c.section}
                                 for c in chunks])

    def search(self, query: str, k: int = 20) -> list[Chunk]:
        """Embed the query, ask the collection, map ids back to Chunks."""
        k = min(k, len(self.chunks))
        res = self._col.query(query_embeddings=embed([query]), n_results=k)
        return [self.chunks[i] for i in res["ids"][0]]


def keyword_search(chunks: list[Chunk], query: str,
                   k: int = 20) -> list[Chunk]:
    """TODO 3c. Term overlap. No model, no cost.

    Score each chunk by how many query terms appear in it, return the top k.
    Crude on purpose: in block 2 you will see a document that repeats a term
    in the wrong section outrank the section that answers the question.

    Break ties deterministically, by chunk_id, or two runs of your own code
    will disagree and you will spend ten minutes blaming the embedder.
    """
    terms = set(re.findall(r"[a-z0-9\-]+", query.lower()))
    scored = []
    for c in chunks:
        words = set(re.findall(r"[a-z0-9\-]+", c.text.lower()))
        scored.append((-len(terms & words), c.chunk_id, c))
    scored.sort(key=lambda t: (t[0], t[1]))        # ties broken by chunk_id
    return [c for _, _, c in scored[:k]]
