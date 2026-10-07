"""High level agent that ties retrieval, memory and safety together."""

import logging
import re

from typing import List, Dict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from novacortex.cache import SemanticResponseCache
from novacortex.config import CHROMA_PATH
from novacortex.db import get_user, log_question, update_user_activity
from novacortex.formatting import formatter
from novacortex.llm import llm_client
from novacortex.pipeline import EnhancedHybridPipeline
from novacortex.rag.retriever import ImprovedHybridRetriever
from novacortex.safety import SmartOutOfScopeDetector
from novacortex.text import arabic_processor

logger = logging.getLogger(__name__)

# ==================== AGENT ====================
class YarmoukAgent:
    def __init__(self):
        logger.info("Initializing YarmoukAgent v14.0...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-large-instruct",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vectorstore = Chroma(persist_directory=CHROMA_PATH, embedding_function=self.embeddings)
        all_docs = self._load_all_documents()
        self.retriever = ImprovedHybridRetriever(vectorstore=self.vectorstore, documents=all_docs)
        self.cache = SemanticResponseCache(embeddings_model=self.embeddings)
        self.scope_detector = SmartOutOfScopeDetector(llm_client)
        self.pipeline = EnhancedHybridPipeline(self.retriever, self.cache, self.scope_detector)
        logger.info("=== NovaCortex v14.0 — Competition Edition ===")
        logger.info("Upgrades: Semantic Cache | Dynamic Confidence | LLM Re-ranker | RAG-First | Source Attribution | Time-Aware Search")
    def _load_all_documents(self) -> List[Document]:
        try:
            all_ids = self.vectorstore.get()['ids']
            all_docs = []
            batch_size = 3000
            for i in range(0, len(all_ids), batch_size):
                batch = self.vectorstore.get(limit=min(batch_size, len(all_ids) - i), offset=i)
                if batch and batch.get("documents"):
                    for text, meta in zip(batch["documents"], batch.get("metadatas", [])):
                        all_docs.append(Document(page_content=text, metadata=meta or {}))
            logger.info(f"Loaded {len(all_docs)} documents")
            return all_docs
        except Exception as e:
            logger.error(f"Failed to load documents: {e}")
            return []
    def _sanitize_response(self, text: str) -> str:
        if not text:
            return text
        cleaned = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uffef]', '', text)
        cleaned = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]', '', cleaned)
        cleaned = re.sub(r' +', ' ', cleaned)
        return cleaned.strip()
    async def ask(self, question: str, user_id: int) -> Dict:
        try:
            user = get_user(user_id)
            study_level = user[5] if user and len(user) > 5 else "بكالوريوس"
            update_user_activity(user_id)
            detected_lang = arabic_processor.detect_language(question)
            result = await self.pipeline.process_question(
                question=question, user_id=user_id, study_level=study_level
            )
            result["response"] = self._sanitize_response(result["response"])
            result["response"] = formatter.format(
                result["response"],
                result["source"],
                language=detected_lang
            )
            log_question(
                user_id=user_id, username=user[1] if user else "unknown",
                question=question, response=result["response"],
                source=result["source"], confidence=result["confidence"],
                response_time_ms=result["response_time_ms"],
                docs_retrieved=result.get("docs_retrieved", 0), study_level=study_level
            )
            return result
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            detected_lang = arabic_processor.detect_language(question)
            return {
                "response": "⚠️ عذراً، حدث خطأ تقني." if detected_lang == "ar" else "⚠️ Sorry, a technical error occurred.",
                "source": "error", "confidence": 0, "response_time_ms": 0, "docs_retrieved": 0
            }
