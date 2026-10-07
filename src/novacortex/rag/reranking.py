"""LLM based reranking of retrieved chunks."""

import json
import logging

from typing import List, Tuple

from novacortex.llm import llm_client

logger = logging.getLogger(__name__)

# ==================== LLM RE-RANKER ====================
class LLMReranker:
    """Re-rank retrieved documents using LLM scoring."""
    def __init__(self, client):
        self.client = client
    def rerank(self, question: str, docs_with_scores: List[Tuple], top_k: int = 3) -> List[Tuple]:
        """Re-rank documents by LLM relevance scoring."""
        if not docs_with_scores or len(docs_with_scores) <= top_k:
            return docs_with_scores
        # Build a batch prompt for efficiency (one LLM call)
        doc_summaries = []
        for i, (doc, score) in enumerate(docs_with_scores[:8]):  # Max 8 docs to evaluate
            snippet = doc.page_content[:200].replace('\n', ' ')
            doc_summaries.append(f"[Doc {i+1}]: {snippet}")
        docs_text = "\n".join(doc_summaries)
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{
                    "role": "user",
                    "content": (
                        f"Rate each document's relevance to the question (1-10). "
                        f"Return JSON: {{\"scores\": [score1, score2, ...]}}\n\n"
                        f"Question: {question}\n\n{docs_text}"
                    )
                }],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=100
            )
            result = json.loads(response.choices[0].message.content)
            scores = result.get("scores", [])
            if scores and len(scores) == len(docs_with_scores[:8]):
                # Combine original score with LLM score
                reranked = []
                for i, (doc, orig_score) in enumerate(docs_with_scores[:8]):
                    llm_score = scores[i] / 10.0 if i < len(scores) else 0.5
                    combined_score = 0.4 * orig_score + 0.6 * llm_score
                    reranked.append((doc, combined_score))
                reranked.sort(key=lambda x: x[1], reverse=True)
                logger.info(f"[RERANK] Re-ranked {len(reranked)} docs for: '{question[:40]}'")
                return reranked[:top_k]
        except Exception as e:
            logger.warning(f"[RERANK] LLM re-ranking failed, using original order: {e}")
        return docs_with_scores[:top_k]
reranker = LLMReranker(llm_client)
