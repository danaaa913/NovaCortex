"""Hybrid (BM25 + vector) retriever with reciprocal rank fusion."""

import hashlib
import logging

from typing import List, Tuple

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from novacortex.text import arabic_processor

logger = logging.getLogger(__name__)

synthetic_retriever = None
# ==================== HYBRID RETRIEVER ====================
class ImprovedHybridRetriever:
    def __init__(self, vectorstore, documents: List[Document]):
        self.vectorstore = vectorstore
        self.documents = documents
        self.bm25 = self._init_bm25()
    def _init_bm25(self):
        logger.info("Initializing BM25 index...")
        texts = [doc.page_content for doc in self.documents]
        tokenized_corpus = [arabic_processor.tokenize(t) for t in texts]
        return BM25Okapi(tokenized_corpus)
    def retrieve(self, query: str, final_k: int = 5) -> List[Tuple[Document, float]]:
        try:
            vector_results = self.vectorstore.similarity_search_with_relevance_scores(query, k=final_k * 4)
            filtered_docs = [doc for doc, score in vector_results if score > 0.25]
            if len(filtered_docs) < 3:
                filtered_docs = [doc for doc, _ in vector_results[:final_k * 2]]
        except:
            filtered_docs = self.vectorstore.similarity_search(query, k=final_k * 2)
        tokenized_query = arabic_processor.tokenize(query)
        bm25_results = self.bm25.get_top_n(tokenized_query, self.documents, n=final_k * 3)
        fused = self._reciprocal_rank_fusion(filtered_docs, bm25_results)
        # ✅ FIX 2: تطبيق priority boost — المصادر الرئيسية تحصل على تعزيز، الأخبار تحصل على خفض
        boosted = []
        for doc, score in fused:
            priority = doc.metadata.get("priority", 2)
            if priority == 1:
                score = score * 1.35  # تعزيز 35% للمصادر الأكاديمية الرئيسية
            elif priority == 3:
                score = score * 0.65  # خفض 35% للأخبار والوثائق العامة الضخمة
            boosted.append((doc, score))
        boosted.sort(key=lambda x: x[1], reverse=True)
        unique = self._deduplicate(boosted)
        return unique[:final_k]
    def _reciprocal_rank_fusion(self, vector_docs, bm25_docs, k=60):
        rrf_scores = {}
        for rank, doc in enumerate(vector_docs, 1):
            h = self._hash(doc.page_content)
            rrf_scores[h] = {"doc": doc, "score": 1.0 / (k + rank)}
        for rank, doc in enumerate(bm25_docs, 1):
            h = self._hash(doc.page_content)
            if h in rrf_scores:
                rrf_scores[h]["score"] += 1.0 / (k + rank)
            else:
                rrf_scores[h] = {"doc": doc, "score": 1.0 / (k + rank)}
        return [(v["doc"], v["score"]) for v in sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)]
    def _deduplicate(self, docs_with_scores):
        seen, unique = set(), []
        for doc, score in docs_with_scores:
            h = self._hash(doc.page_content)
            if h not in seen:
                seen.add(h)
                unique.append((doc, score))
        return unique
    def _hash(self, content: str) -> str:
        return hashlib.md5(content[:300].encode()).hexdigest()
