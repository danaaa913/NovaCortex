"""End-to-end ingestion, retrieval and local answer pipeline."""

import json
import statistics
from pathlib import Path
from typing import List

from .answering import GroundedAnswerer
from .chunking import build_chunks
from .cleaning import clean_text
from .config import HackathonConfig
from .loaders import document_inventory, load_documents
from .models import Answer, RetrievedChunk
from .ollama_client import OllamaClient
from .retrieval import HybridRetriever
from .store import DocumentStore


class HackathonRAG:
    def __init__(self, config: HackathonConfig | None = None):
        self.config = config or HackathonConfig()
        self.config.validate()
        self.ollama = OllamaClient(self.config.ollama_base_url, self.config.request_timeout)
        self.store = DocumentStore(self.config.index_dir, self.config.collection_name)
        self._retriever = None

    def ingest(self, reset: bool = True) -> dict:
        inventory = document_inventory(self.config.documents_dir)
        units = load_documents(self.config.documents_dir)
        parents, chunks = build_chunks(
            units,
            parent_size=self.config.parent_size,
            child_size=self.config.child_size,
            overlap=self.config.child_overlap,
            minimum=self.config.min_chunk_size,
        )
        manifest = self.store.build(
            parents,
            chunks,
            self.ollama,
            self.config.embedding_model,
            document_prefix=self.config.embedding_document_prefix,
            reset=reset,
        )
        manifest["inventory"] = inventory
        manifest["extracted_units"] = len(units)
        self.store.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._retriever = None
        return manifest

    def preview(self, output_path: Path | None = None, sample_count: int = 30) -> dict:
        """Inspect extraction and chunks before downloading models or embedding."""
        inventory = document_inventory(self.config.documents_dir)
        units = load_documents(self.config.documents_dir)
        parents, chunks = build_chunks(
            units,
            parent_size=self.config.parent_size,
            child_size=self.config.child_size,
            overlap=self.config.child_overlap,
            minimum=self.config.min_chunk_size,
        )
        lengths = [len(chunk.body) for chunk in chunks]
        ordered = sorted(chunks, key=lambda chunk: len(chunk.body))
        shortest = ordered[: min(5, len(ordered))]
        longest = ordered[-min(5, len(ordered)):]
        remaining = max(0, sample_count - len(shortest) - len(longest))
        step = max(1, len(chunks) // max(1, remaining))
        spread = chunks[::step][:remaining]
        chosen = []
        seen = set()
        for chunk in shortest + spread + longest:
            if chunk.id not in seen:
                chosen.append(chunk)
                seen.add(chunk.id)
        report = {
            "inventory": inventory,
            "extracted_units": len(units),
            "parents": len(parents),
            "chunks": len(chunks),
            "chunk_lengths": {
                "minimum": min(lengths) if lengths else 0,
                "median": statistics.median(lengths) if lengths else 0,
                "mean": round(statistics.mean(lengths), 1) if lengths else 0,
                "maximum": max(lengths) if lengths else 0,
                "below_configured_minimum": sum(length < self.config.min_chunk_size for length in lengths),
            },
            "sources": sorted({chunk.source for chunk in chunks}),
            "samples": [
                {
                    "source": chunk.source,
                    "page": chunk.page,
                    "section": chunk.section,
                    "length": len(chunk.body),
                    "text": chunk.text,
                }
                for chunk in chosen
            ],
        }
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _get_retriever(self) -> HybridRetriever:
        if self._retriever is None:
            self.store.require_index()
            manifest = json.loads(self.store.manifest_path.read_text(encoding="utf-8"))
            indexed_model = manifest.get("embedding_model")
            if indexed_model != self.config.embedding_model:
                raise RuntimeError(
                    f"Index uses embedding model {indexed_model!r}, but configuration uses "
                    f"{self.config.embedding_model!r}. Re-run ingest."
                )
            indexed_prefix = manifest.get("embedding_document_prefix", "")
            if indexed_prefix != self.config.embedding_document_prefix:
                raise RuntimeError("Embedding document prefix changed. Re-run ingest.")
            self._retriever = HybridRetriever(
                self.store,
                self.ollama,
                self.config.embedding_model,
                query_prefix=self.config.embedding_query_prefix,
                candidates=self.config.retrieve_candidates,
                final_k=self.config.final_k,
                max_per_source=self.config.max_per_source,
            )
        return self._retriever

    def retrieve(self, question: str) -> List[RetrievedChunk]:
        question = clean_text(question)
        if not question:
            raise ValueError("Question cannot be empty")
        return self._get_retriever().retrieve(question)

    def ask(self, question: str) -> Answer:
        retrieved = self.retrieve(question)
        parents = self.store.load_parents()
        answerer = GroundedAnswerer(self.ollama, self.config.chat_model, self.config.max_context_chars)
        return answerer.answer(question, retrieved, parents)

    def doctor(self) -> dict:
        result = {
            "ollama_url": self.config.ollama_base_url,
            "chat_model": self.config.chat_model,
            "embedding_model": self.config.embedding_model,
            "documents_dir": str(self.config.documents_dir),
            "index_dir": str(self.config.index_dir),
        }
        try:
            models = self.ollama.tags()
            result["ollama_reachable"] = True
            result["installed_models"] = models
            result["chat_model_ready"] = any(name == self.config.chat_model or name.startswith(self.config.chat_model + ":") for name in models)
            result["embedding_model_ready"] = any(name == self.config.embedding_model or name.startswith(self.config.embedding_model + ":") for name in models)
        except Exception as exc:
            result["ollama_reachable"] = False
            result["error"] = str(exc)
        return result
