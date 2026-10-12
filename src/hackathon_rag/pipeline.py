"""End-to-end ingestion, retrieval and local answer pipeline."""

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import uuid4

from .answering import GroundedAnswerer
from .chunking import build_chunks
from .cleaning import clean_text
from .config import HackathonConfig
from .loaders import document_inventory, load_documents
from .models import Answer, RetrievedChunk
from .ollama_client import OllamaClient
from .retrieval import HybridRetriever
from .store import DocumentStore
from .workflow import DeterministicRAGWorkflow


class HackathonRAG:
    def __init__(self, config: HackathonConfig | None = None):
        self.config = config or HackathonConfig()
        self.config.validate()
        self.ollama = OllamaClient(self.config.ollama_base_url, self.config.request_timeout)
        self.store = DocumentStore(self.config.index_dir, self.config.collection_name)
        self._retriever = None
        self._workflow = None

    def ingest(self, reset: bool = True) -> dict:
        inventory = document_inventory(self.config.documents_dir)
        extraction = {}
        units = load_documents(
            self.config.documents_dir,
            diagnostics=extraction,
            quarantine_suspicious=self.config.quarantine_suspicious,
        )
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
            manifest_extra={
                "inventory": inventory,
                "extracted_units": len(units),
                "extraction": extraction,
                "chunking": {
                    "parent_size": self.config.parent_size,
                    "child_size": self.config.child_size,
                    "overlap": self.config.child_overlap,
                    "minimum": self.config.min_chunk_size,
                },
                "security": {
                    "quarantine_enabled": self.config.quarantine_suspicious,
                    "quarantined_files": extraction.get("quarantined", 0),
                },
            },
        )
        self._retriever = None
        self._workflow = None
        return manifest

    def preview(self, output_path: Path | None = None, sample_count: int = 30) -> dict:
        """Inspect extraction and chunks before downloading models or embedding."""
        inventory = document_inventory(self.config.documents_dir)
        extraction = {}
        units = load_documents(
            self.config.documents_dir,
            diagnostics=extraction,
            quarantine_suspicious=self.config.quarantine_suspicious,
        )
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
            "extraction": extraction,
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
        if self._workflow is None:
            answerer = GroundedAnswerer(self.ollama, self.config.chat_model, self.config.max_context_chars)
            self._workflow = DeterministicRAGWorkflow(
                retrieve=self.retrieve,
                load_parents=self.store.load_parents,
                answer=answerer.answer,
            )
        result = self._workflow.invoke(question)
        result.request_id = uuid4().hex
        if self.config.trace_enabled:
            self._write_trace(question, result)
        return result

    def _write_trace(self, question: str, result: Answer) -> None:
        """Write non-sensitive operational metadata for reproducible debugging."""
        try:
            manifest = json.loads(self.store.manifest_path.read_text(encoding="utf-8"))
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": result.request_id,
                "question_sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
                "index_id": manifest.get("index_id"),
                "chat_model": self.config.chat_model,
                "embedding_model": self.config.embedding_model,
                "supported": result.supported,
                "latency_ms": result.latency_ms,
                "timings_ms": result.timings_ms,
                "retrieved_chunk_ids": [item.get("chunk_id") for item in result.retrieved],
                "citations": [item.get("evidence_id") for item in result.citations],
            }
            trace_path = self.config.index_dir.parent / "rag_traces.jsonl"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except (OSError, ValueError, TypeError):
            # Tracing must never make an otherwise valid answer fail.
            return

    def doctor(self) -> dict:
        import importlib.util

        dependencies = {
            "requests": "requests",
            "chromadb": "chromadb",
            "pdfplumber": "pdfplumber",
            "docx": "docx",
            "pptx": "pptx",
            "openpyxl": "openpyxl",
            "streamlit": "streamlit",
            "langgraph": "langgraph",
            "mcp": "mcp",
        }
        result = {
            "ollama_url": self.config.ollama_base_url,
            "chat_model": self.config.chat_model,
            "embedding_model": self.config.embedding_model,
            "documents_dir": str(self.config.documents_dir),
            "index_dir": str(self.config.index_dir),
            "quarantine_suspicious": self.config.quarantine_suspicious,
            "trace_enabled": self.config.trace_enabled,
            "trace_path": str(self.config.index_dir.parent / "rag_traces.jsonl"),
            "documents_directory_exists": self.config.documents_dir.exists(),
            "index_ready": all(
                path.exists()
                for path in (self.store.chunks_path, self.store.parents_path, self.store.manifest_path)
            ),
            "dependencies": {
                label: importlib.util.find_spec(module) is not None
                for label, module in dependencies.items()
            },
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
