"""Project-level RAG - document chunking and semantic search.

Enables the agent to find relevant code/docs by semantic similarity
rather than exact keyword matching.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)


class SimpleEmbedder:
    """Lightweight text embedder using character n-gram overlap.

    Full embedding models (sentence-transformers) are optional.
    This provides a dependency-free baseline for semantic similarity.
    """

    def __init__(self, ngram_size: int = 3):
        self.ngram_size = ngram_size

    def _ngrams(self, text: str) -> set[str]:
        """Extract character n-grams."""
        text = text.lower()
        return set(
            text[i:i + self.ngram_size]
            for i in range(len(text) - self.ngram_size + 1)
        )

    def similarity(self, text1: str, text2: str) -> float:
        """Compute Jaccard similarity between two texts."""
        ngrams1 = self._ngrams(text1)
        ngrams2 = self._ngrams(text2)
        if not ngrams1 or not ngrams2:
            return 0.0
        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2
        return len(intersection) / len(union)

    def embed(self, text: str) -> set[str]:
        """Get n-gram set as embedding."""
        return self._ngrams(text)


class ProjectRAG:
    """Document chunking and semantic search for project files.

    Splits documents into overlapping chunks, indexes them with
    n-gram embeddings, and supports similarity-based retrieval.
    """

    CHUNK_SIZE = 500      # chars per chunk
    CHUNK_OVERLAP = 100   # overlap between chunks
    MAX_DOCUMENTS = 200

    def __init__(
        self,
        workdir: Path | None = None,
        index_dir: Path | None = None,
    ):
        self.workdir = workdir or Path.cwd()
        self.index_dir = index_dir or Path.home() / ".terry" / "rag"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.embedder = SimpleEmbedder()
        self.chunks: list[dict[str, Any]] = []

    def add_document(self, path: str, content: str) -> int:
        """Chunk and index a document. Returns number of chunks."""
        chunks = self._chunk_text(content)
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.sha256(
                f"{path}:{i}".encode()
            ).hexdigest()[:12]
            self.chunks.append({
                "id": chunk_id,
                "source": path,
                "index": i,
                "content": chunk,
                "embedding": self.embedder.embed(chunk),
            })

        # Prune old chunks
        while len(self.chunks) > self.MAX_DOCUMENTS * 10:
            self.chunks.pop(0)

        return len(chunks)

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.CHUNK_SIZE:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            start += self.CHUNK_SIZE - self.CHUNK_OVERLAP
        return chunks

    def query(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search for chunks relevant to a question.

        Args:
            question: Search query
            top_k: Number of results to return

        Returns:
            List of relevant chunks with scores
        """
        if not self.chunks:
            return []

        scored = []
        for chunk in self.chunks:
            score = self.embedder.similarity(question, chunk["content"])
            if score > 0.05:  # Minimum relevance threshold
                scored.append({**chunk, "score": round(score, 3)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def index_file(self, file_path: str) -> int:
        """Index a single file by path."""
        full_path = self.workdir / file_path
        if not full_path.exists():
            return 0
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            return self.add_document(file_path, content)
        except Exception:
            return 0

    def index_project(self, max_files: int = 100) -> int:
        """Index all project files. Returns total chunks."""
        total_chunks = 0
        file_count = 0
        for path in self.workdir.rglob("*"):
            if file_count >= max_files:
                break
            if not path.is_file():
                continue
            if any(
                d in path.relative_to(self.workdir).parts
                for d in {".git", "__pycache__", "node_modules", ".venv"}
            ):
                continue
            if path.suffix in {".py", ".md", ".yaml", ".json", ".toml", ".txt"}:
                n = self.index_file(
                    str(path.relative_to(self.workdir))
                )
                total_chunks += n
                file_count += 1
        return total_chunks

    def save_index(self) -> Path:
        """Persist the chunk index to disk."""
        index_path = self.index_dir / "rag_index.json"
        data = {
            "chunks": [
                {
                    "id": c["id"],
                    "source": c["source"],
                    "index": c["index"],
                    "content": c["content"],
                    "embedding": list(c["embedding"]),
                }
                for c in self.chunks
            ]
        }
        index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return index_path

    def load_index(self) -> int:
        """Load the chunk index from disk. Returns chunk count."""
        index_path = self.index_dir / "rag_index.json"
        if not index_path.exists():
            return 0
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self.chunks = [
                {
                    "id": c["id"],
                    "source": c["source"],
                    "index": c["index"],
                    "content": c["content"],
                    "embedding": set(c.get("embedding", [])),
                }
                for c in data.get("chunks", [])
            ]
            return len(self.chunks)
        except Exception:
            return 0
