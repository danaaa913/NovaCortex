"""Persistent Chroma index plus JSON sidecars used by hybrid retrieval."""

import json
import shutil
import gc
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List
from uuid import uuid4

from .models import Chunk, ParentSection
from .ollama_client import OllamaClient


class DocumentStore:
    def __init__(self, index_dir: Path, collection_name: str):
        self.index_dir = index_dir
        self.collection_name = collection_name
        self.chunks_path = index_dir / "chunks.json"
        self.parents_path = index_dir / "parents.json"
        self.manifest_path = index_dir / "manifest.json"

    def _chroma(self, index_dir: Path | None = None):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Install chromadb before building or querying the index") from exc
        directory = index_dir or self.index_dir
        client = chromadb.PersistentClient(path=str(directory / "chroma"))
        return client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def build(
        self,
        parents: List[ParentSection],
        chunks: List[Chunk],
        ollama: OllamaClient,
        embedding_model: str,
        document_prefix: str = "",
        reset: bool = True,
        manifest_extra: dict | None = None,
    ) -> dict:
        if not chunks:
            raise RuntimeError("Chunking produced no searchable text")
        vectors = ollama.embed(embedding_model, [document_prefix + chunk.text for chunk in chunks])
        manifest = dict(manifest_extra or {})
        manifest.update({
            "schema_version": 2,
            "index_id": uuid4().hex,
            "built_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": embedding_model,
            "embedding_document_prefix": document_prefix,
            "documents": len({chunk.source for chunk in chunks}),
            "parents": len(parents),
            "chunks": len(chunks),
            "atomic_build": bool(reset),
        })
        if reset:
            self._atomic_rebuild(parents, chunks, vectors, manifest)
        else:
            self._write_index(self.index_dir, parents, chunks, vectors, manifest, incremental=True)
        return manifest

    def _write_index(
        self,
        target: Path,
        parents: List[ParentSection],
        chunks: List[Chunk],
        vectors: List[List[float]],
        manifest: dict,
        incremental: bool = False,
    ) -> None:
        target.mkdir(parents=True, exist_ok=True)
        collection = self._chroma(target)
        current_ids = {chunk.id for chunk in chunks}
        if incremental:
            existing_ids = set(collection.get().get("ids", []))
            stale_ids = sorted(existing_ids - current_ids)
            if stale_ids:
                collection.delete(ids=stale_ids)
        batch_size = 200
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            collection.upsert(
                ids=[chunk.id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                metadatas=[chunk.metadata() for chunk in batch],
                embeddings=vectors[start:start + batch_size],
            )
        (target / "chunks.json").write_text(
            json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False), encoding="utf-8"
        )
        (target / "parents.json").write_text(
            json.dumps([parent.to_dict() for parent in parents], ensure_ascii=False), encoding="utf-8"
        )
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        del collection
        gc.collect()

    def _atomic_rebuild(
        self,
        parents: List[ParentSection],
        chunks: List[Chunk],
        vectors: List[List[float]],
        manifest: dict,
    ) -> None:
        resolved = self.index_dir.resolve()
        if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
            raise RuntimeError(f"Refusing to replace unsafe index path: {resolved}")
        self.index_dir.parent.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        staging = self.index_dir.parent / f".{self.index_dir.name}.build-{token}"
        backup = self.index_dir.parent / f".{self.index_dir.name}.backup-{token}"
        try:
            self._write_index(staging, parents, chunks, vectors, manifest)
            required = [staging / "chunks.json", staging / "parents.json", staging / "manifest.json"]
            if not all(path.exists() and path.stat().st_size > 0 for path in required):
                raise RuntimeError("Staged index validation failed")
            if self.index_dir.exists():
                self.index_dir.rename(backup)
            try:
                staging.rename(self.index_dir)
            except Exception:
                if backup.exists() and not self.index_dir.exists():
                    backup.rename(self.index_dir)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
            if backup.exists() and self.index_dir.exists():
                shutil.rmtree(backup)

    def require_index(self) -> None:
        missing = [path.name for path in (self.chunks_path, self.parents_path, self.manifest_path) if not path.exists()]
        if missing:
            raise RuntimeError(f"Index is not ready; missing: {', '.join(missing)}. Run ingest first.")

    def load_chunks(self) -> List[Chunk]:
        self.require_index()
        return [Chunk(**item) for item in json.loads(self.chunks_path.read_text(encoding="utf-8"))]

    def load_parents(self) -> Dict[str, ParentSection]:
        self.require_index()
        values = [ParentSection(**item) for item in json.loads(self.parents_path.read_text(encoding="utf-8"))]
        return {parent.id: parent for parent in values}

    def vector_ids(self, query_vector: List[float], n_results: int) -> List[str]:
        collection = self._chroma()
        result = collection.query(query_embeddings=[query_vector], n_results=n_results, include=["distances"])
        return (result.get("ids") or [[]])[0]
