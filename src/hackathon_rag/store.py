"""Persistent Chroma index plus JSON sidecars used by hybrid retrieval."""

import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List

from .models import Chunk, ParentSection
from .ollama_client import OllamaClient


class DocumentStore:
    def __init__(self, index_dir: Path, collection_name: str):
        self.index_dir = index_dir
        self.collection_name = collection_name
        self.chunks_path = index_dir / "chunks.json"
        self.parents_path = index_dir / "parents.json"
        self.manifest_path = index_dir / "manifest.json"

    def _chroma(self):
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Install chromadb before building or querying the index") from exc
        client = chromadb.PersistentClient(path=str(self.index_dir / "chroma"))
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
    ) -> dict:
        if not chunks:
            raise RuntimeError("Chunking produced no searchable text")
        resolved = self.index_dir.resolve()
        if reset and self.index_dir.exists():
            if resolved == Path(resolved.anchor) or len(resolved.parts) < 3:
                raise RuntimeError(f"Refusing to reset unsafe index path: {resolved}")
            shutil.rmtree(self.index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        vectors = ollama.embed(embedding_model, [document_prefix + chunk.text for chunk in chunks])
        collection = self._chroma()
        current_ids = {chunk.id for chunk in chunks}
        if not reset:
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
        self.chunks_path.write_text(json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False), encoding="utf-8")
        self.parents_path.write_text(json.dumps([parent.to_dict() for parent in parents], ensure_ascii=False), encoding="utf-8")
        manifest = {
            "embedding_model": embedding_model,
            "embedding_document_prefix": document_prefix,
            "documents": len({chunk.source for chunk in chunks}),
            "parents": len(parents),
            "chunks": len(chunks),
        }
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

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
