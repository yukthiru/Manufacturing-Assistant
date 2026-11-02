"""PDF ingestion + retrieval-augmented answering.

Pipeline: PyMuPDF text per page -> chunks (page number kept) -> embeddings stored
in the DB -> cosine search HARD-FILTERED to the selected machine -> LLM answers
only from the retrieved passages, or we report insufficient information.
"""
import logging
import re
import zlib

import fitz  # PyMuPDF
import numpy as np
import requests
from django.conf import settings
from django.db import transaction

from .models import Chunk

log = logging.getLogger(__name__)

NO_INFO = "The manuals for the selected machine do not contain enough information to answer this question."
DIM = 512
STOP = set("""a an and are as at be by can do does for from how i in is it its of on or should
that the their then there these this to was what when where which who why will with you your
our we need must use used using per each every""".split())


# ---------- ingestion ----------
def extract_pages(data: bytes):
    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for number, page in enumerate(doc, start=1):
            pages.append((number, page.get_text("text")))
    return pages


def chunk_text(text, size=700, overlap=100):
    text = re.sub(r"[ \t]+", " ", text).strip()
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(". ", start, end)
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@transaction.atomic
def ingest_manual(manual):
    manual.file.open("rb")
    try:
        data = manual.file.read()
    finally:
        manual.file.close()
    try:
        pages = extract_pages(data)
    except Exception as exc:
        raise ValueError("The file could not be read as a PDF.") from exc
    rows = [(no, c) for no, text in pages for c in chunk_text(text)]
    if not rows:
        raise ValueError("No extractable text found in this PDF (scanned PDFs need OCR, which is not supported).")
    vectors = embed_texts([c for _, c in rows])
    manual.chunks.all().delete()
    Chunk.objects.bulk_create([
        Chunk(manual=manual, machine=manual.machine, page_number=no, text=c, embedding=v)
        for (no, c), v in zip(rows, vectors)
    ])
    manual.page_count = len(pages)
    manual.save(update_fields=["page_count"])


# ---------- embeddings ----------
def _tokens(text):
    out = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if tok in STOP:
            continue
        if len(tok) > 3 and tok.endswith("s"):
            tok = tok[:-1]
        out.append(tok)
    return out


def _hash_embed(text):
    """Offline fallback: hashed bag-of-words. Good enough for demos/tests."""
    vec = np.zeros(DIM)
    for tok in _tokens(text):
        vec[zlib.crc32(tok.encode()) % DIM] += 1.0
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm else vec.tolist()


def _api_headers():
    return {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}


def _api_embed(texts):
    out = []
    for i in range(0, len(texts), 64):
        resp = requests.post(f"{settings.LLM_BASE_URL}/embeddings", headers=_api_headers(), timeout=60,
                             json={"model": settings.EMBEDDING_MODEL, "input": texts[i:i + 64]})
        resp.raise_for_status()
        out.extend(d["embedding"] for d in sorted(resp.json()["data"], key=lambda d: d["index"]))
    return out


def embed_texts(texts):
    if settings.LLM_API_KEY:
        return _api_embed(texts)
    return [_hash_embed(t) for t in texts]


# ---------- retrieval ----------
def retrieve(machine, query, k=None):
    """Top-k (chunk, score) pairs from the selected machine's manuals ONLY."""
    k = k or settings.RAG_TOP_K
    chunks = list(Chunk.objects.filter(machine=machine).select_related("manual"))
    if not chunks:
        return []
    q = np.array(embed_texts([query])[0], dtype=float)
    m = np.array([c.embedding for c in chunks], dtype=float)
    denom = np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)
    denom[denom == 0] = 1.0
    scores = (m @ q) / denom
    order = np.argsort(-scores)[:k]
    return [(chunks[i], float(scores[i])) for i in order]


# ---------- generation ----------
def _llm_answer(question, hits):
    context = "\n\n".join(
        f"[{n}] ({c.manual.title}, rev {c.manual.revision}, page {c.page_number})\n{c.text}"
        for n, (c, _) in enumerate(hits, start=1)
    )
    system = ("You are a maintenance assistant for factory engineers. Answer ONLY from the numbered "
              "excerpts. Cite excerpts like [1]. If the excerpts do not contain the answer, reply with "
              "exactly: INSUFFICIENT_INFORMATION")
    resp = requests.post(f"{settings.LLM_BASE_URL}/chat/completions", headers=_api_headers(), timeout=90, json={
        "model": settings.LLM_MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {question}"}],
    })
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _source(n, chunk, score):
    return {"ref": n, "manual_id": chunk.manual_id, "manual_title": chunk.manual.title,
            "revision": chunk.manual.revision, "page": chunk.page_number, "passage": chunk.text,
            "score": round(score, 3), "file_url": f"/api/manuals/{chunk.manual_id}/file/"}


def answer_question(machine, question):
    hits = [(c, s) for c, s in retrieve(machine, question) if s >= settings.RAG_MIN_SCORE]
    if not hits:
        return {"answered": False, "answer": NO_INFO, "sources": []}
    if settings.LLM_API_KEY:
        answer = _llm_answer(question, hits)
        if "INSUFFICIENT_INFORMATION" in answer:
            return {"answered": False, "answer": NO_INFO, "sources": []}
    else:  # offline fallback: quote the best passage
        answer = f"Based on the manual: {hits[0][0].text}"
    return {"answered": True, "answer": answer,
            "sources": [_source(n, c, s) for n, (c, s) in enumerate(hits, start=1)]}
