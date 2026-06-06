"""Local embedding model integration for semantic code search.

Uses sentence-transformers (optional) or a lightweight fallback
for generating text embeddings locally without external APIs.
"""

from __future__ import annotations

import math


class LocalEmbedder:
    """Local text embedding with optional sentence-transformers support.

    Falls back to TF-IDF-like character n-gram weighting if
    sentence-transformers is not installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._fallback = True
        self._init_model()

    def _init_model(self) -> None:
        """Try to load sentence-transformers, fall back to n-gram."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._fallback = False
        except ImportError:
            self._fallback = True

    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Input text

        Returns:
            Embedding vector (384d with MiniLM, or 128d with fallback)
        """
        if not self._fallback and self._model:
            try:
                result = self._model.encode(text)
                return result.tolist()
            except Exception:
                pass

        # Fallback: character n-gram TF-IDF-like embedding
        return self._ngram_embed(text, dim=128)

    def _ngram_embed(self, text: str, dim: int = 128) -> list[float]:
        """Generate a simple n-gram hash embedding."""
        text = text.lower()
        ngrams = {}
        for n in (2, 3, 4):
            for i in range(len(text) - n + 1):
                ng = text[i:i + n]
                ngrams[ng] = ngrams.get(ng, 0) + 1

        # Hash n-grams into fixed-dim vector
        vec = [0.0] * dim
        for ng, count in ngrams.items():
            h = hash(ng) % dim
            vec[h] += count * (1.0 / max(len(ngrams), 1))

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        return self._cosine_sim(emb1, emb2)

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(
        self, query: str, documents: list[str], top_k: int = 5
    ) -> list[tuple[int, float]]:
        """Search documents by semantic similarity.

        Returns list of (doc_index, similarity_score) tuples.
        """
        query_emb = self.embed(query)
        scored = []
        for i, doc in enumerate(documents):
            doc_emb = self.embed(doc)
            sim = self._cosine_sim(query_emb, doc_emb)
            if sim > 0.1:
                scored.append((i, round(sim, 3)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
