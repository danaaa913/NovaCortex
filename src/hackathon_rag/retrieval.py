"""Hybrid vector + BM25 retrieval with RRF and source diversity."""

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Sequence

from .models import Chunk, RetrievedChunk
from .ollama_client import OllamaClient
from .store import DocumentStore


ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u0600-\u06ff]+")


def tokenize(text: str) -> List[str]:
    text = ARABIC_DIACRITICS.sub("", text.casefold())
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    return [token for token in TOKEN_RE.findall(text) if len(token) > 1 or token.isdigit()]


class LightweightBM25:
    """Dependency-free BM25 suitable for a hackathon-sized corpus."""

    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.tokens = [tokenize(document) for document in documents]
        self.k1 = k1
        self.b = b
        self.avgdl = sum(map(len, self.tokens)) / max(1, len(self.tokens))
        document_frequency = Counter()
        for tokens in self.tokens:
            document_frequency.update(set(tokens))
        count = len(self.tokens)
        self.idf = {
            token: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def scores(self, query: str) -> List[float]:
        terms = tokenize(query)
        output = []
        for tokens in self.tokens:
            frequencies = Counter(tokens)
            length = len(tokens)
            score = 0.0
            for term in terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (1 - self.b + self.b * length / max(1.0, self.avgdl))
                score += self.idf.get(term, 0.0) * frequency * (self.k1 + 1) / denominator
            output.append(score)
        return output


class HybridRetriever:
    def __init__(
        self,
        store: DocumentStore,
        ollama: OllamaClient,
        embedding_model: str,
        query_prefix: str = "",
        candidates: int = 24,
        final_k: int = 6,
        max_per_source: int = 2,
    ):
        self.store = store
        self.ollama = ollama
        self.embedding_model = embedding_model
        self.query_prefix = query_prefix
        self.candidates = candidates
        self.final_k = final_k
        self.max_per_source = max_per_source
        self.chunks = store.load_chunks()
        self.by_id = {chunk.id: chunk for chunk in self.chunks}
        self.bm25 = LightweightBM25([chunk.text for chunk in self.chunks])

    def retrieve(self, question: str) -> List[RetrievedChunk]:
        query_vector = self.ollama.embed(self.embedding_model, [self.query_prefix + question], batch_size=1)[0]
        vector_ids = self.store.vector_ids(query_vector, min(self.candidates, len(self.chunks)))
        vector_rank = {chunk_id: rank for rank, chunk_id in enumerate(vector_ids, 1)}

        keyword_scores = self.bm25.scores(question)
        keyword_indices = sorted(range(len(keyword_scores)), key=keyword_scores.__getitem__, reverse=True)
        keyword_indices = [index for index in keyword_indices if keyword_scores[index] > 0][:self.candidates]
        keyword_rank = {self.chunks[index].id: rank for rank, index in enumerate(keyword_indices, 1)}

        fused: Dict[str, float] = defaultdict(float)
        for chunk_id, rank in vector_rank.items():
            fused[chunk_id] += 1.0 / (60 + rank)
        for chunk_id, rank in keyword_rank.items():
            fused[chunk_id] += 1.0 / (60 + rank)

        query_numbers = set(re.findall(r"\d+", question))
        for chunk_id in list(fused):
            if query_numbers and query_numbers & set(re.findall(r"\d+", self.by_id[chunk_id].text)):
                fused[chunk_id] *= 1.15

        ranked = sorted(fused, key=fused.get, reverse=True)
        selected = []
        source_counts = Counter()
        seen_parents = set()

        def add_result(chunk_id: str) -> None:
            chunk = self.by_id[chunk_id]
            selected.append(RetrievedChunk(
                chunk=chunk,
                score=fused[chunk_id],
                vector_rank=vector_rank.get(chunk_id),
                keyword_rank=keyword_rank.get(chunk_id),
            ))
            source_counts[chunk.source] += 1
            seen_parents.add(chunk.parent_id)

        for chunk_id in ranked:
            chunk = self.by_id[chunk_id]
            if source_counts[chunk.source] >= self.max_per_source:
                continue
            if chunk.parent_id in seen_parents:
                continue
            add_result(chunk_id)
            if len(selected) >= self.final_k:
                break
        # Diversity is a preference, not a reason to return too little context.
        if len(selected) < self.final_k:
            for chunk_id in ranked:
                chunk = self.by_id[chunk_id]
                if chunk.parent_id in seen_parents:
                    continue
                add_result(chunk_id)
                if len(selected) >= self.final_k:
                    break
        return selected
