"""Knowledge base: load documents, split them into chunks, embed, store and search.

Flow:  file/URL -> plain text -> chunks -> embeddings (vectors) -> ChromaDB
Query: question -> embedding -> nearest chunks -> given to the LLM as context
"""

import hashlib
import logging
import re
from pathlib import Path

import chromadb
import httpx
from bs4 import BeautifulSoup
from chromadb.config import Settings as ChromaSettings
from fastembed import TextEmbedding
from pypdf import PdfReader

from app.config import Settings

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


# ---------- Loading ----------

def load_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {path.name}")


def load_url(url: str) -> str:
    response = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (support-agent-ingest)"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    lines = (line.strip() for line in main.get_text("\n").splitlines())
    return "\n\n".join(line for line in lines if line)


# ---------- Chunking ----------

def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Pack paragraphs into chunks of ~`size` characters, each starting with the
    last ~`overlap` characters of the previous one so context isn't cut mid-idea."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    pieces: list[str] = []
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        if len(para) <= size:
            pieces.append(para)
        else:
            pieces.extend(para[i:i + size] for i in range(0, len(para), size - overlap))

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > size:
            chunks.append(current)
            tail = current[-overlap:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail
            current = f"{tail}\n\n{piece}"
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


# ---------- Vector store ----------

class KnowledgeBase:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._embedder = TextEmbedding(settings.embedding_model, cache_dir=str(settings.storage_dir / "models"))
        client = chromadb.PersistentClient(
            path=str(settings.storage_dir / "chroma"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = client.get_or_create_collection("knowledge", metadata={"hnsw:space": "cosine"})

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._embedder.embed(texts)]

    def add_document(self, source: str, text: str) -> int:
        """Index one document. Re-adding the same source replaces its old chunks."""
        chunks = chunk_text(text, self._settings.chunk_size, self._settings.chunk_overlap)
        self._collection.delete(where={"source": source})
        if not chunks:
            return 0
        prefix = hashlib.sha1(source.encode()).hexdigest()[:12]
        self._collection.add(
            ids=[f"{prefix}-{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=self._embed(chunks),
            metadatas=[{"source": source, "chunk": i} for i in range(len(chunks))],
        )
        return len(chunks)

    def search(self, query: str, k: int | None = None) -> list[dict]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=self._embed([query]),
            n_results=min(k or self._settings.top_k, self._collection.count()),
        )
        return [
            {"text": doc, "source": meta["source"], "score": round(1 - dist, 3)}
            for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
        ]

    def sources(self) -> list[str]:
        metadatas = self._collection.get(include=["metadatas"])["metadatas"]
        return sorted({m["source"] for m in metadatas})

    def reset(self) -> None:
        ids = self._collection.get(include=[])["ids"]
        if ids:
            self._collection.delete(ids=ids)
