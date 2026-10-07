"""Semantic (embedding based) response cache."""

import hashlib
import logging
import re
import sqlite3

from datetime import datetime
from typing import Optional, Dict, Tuple

import numpy as np

from novacortex.config import DB_PATH
from novacortex.text import arabic_processor

logger = logging.getLogger(__name__)

# ==================== DYNAMIC CONFIDENCE THRESHOLD ====================
def compute_dynamic_threshold(question: str, source: str = "rag") -> float:
    """Compute a dynamic confidence threshold based on question type and source."""
    q_lower = question.lower()
    # Factual questions (numbers, names, dates) need higher confidence
    factual_kw = ['كم', 'عدد', 'من هو', 'مين', 'متى', 'how many', 'who is', 'when',
                  'رقم', 'هاتف', 'ايميل', 'email', 'phone', 'number']
    if any(kw in q_lower for kw in factual_kw):
        return 75.0
    # Descriptive questions can tolerate lower confidence
    descriptive_kw = ['ما هي', 'شو', 'اشرح', 'explain', 'tell me about', 'what is',
                      'خدمات', 'معلومات عن', 'احكيلي عن']
    if any(kw in q_lower for kw in descriptive_kw):
        return 60.0
    # Web source can have slightly lower threshold
    if source == "web":
        return 65.0
    return 70.0  # Default
# ==================== SEMANTIC CACHE ====================
def _is_incompatible_cache(new_question: str, cached_question: str) -> bool:
    """
    يتحقق إذا الجواب المخزن غير مناسب للسؤال الجديد رغم تشابه الجملتين شكلياً.
    """
    new_q = new_question.lower()
    cached_q = cached_question.lower()

    # ✅ FIX C: أسئلة المقارنة "الفرق بين X و Y" لا تُجاب بجواب عن X وحده
    comparison_kws = ['الفرق بين', 'فرق بين', 'difference between', 'مقارنة بين', 'compare between',
                      'أيهما أفضل', 'مقابل', 'vs', 'versus', 'شو الفرق']
    new_is_comparison = any(kw in new_q for kw in comparison_kws)
    cached_is_comparison = any(kw in cached_q for kw in comparison_kws)
    if new_is_comparison and not cached_is_comparison:
        return True  # سؤال مقارنة جديد لكن الكاش جواب عن موضوع واحد فقط
    if not new_is_comparison and cached_is_comparison:
        return True  # سؤال عن موضوع واحد لكن الكاش جواب مقارنة

    topic_groups = [
        ['تخصص', 'برنامج', 'major', 'program', 'بكالوريوس تخصص'],
        ['رسوم', 'تكلفة', 'fees', 'tuition'],
        ['عميد', 'dean', 'رئيس القسم', 'نائب العميد'],
        ['سكن', 'housing', 'dorm', 'سكنات'],
        ['أونلاين', 'online', 'وجاهي', 'عن بعد'],
        ['سعر', 'تكلف', 'price'],
        ['خطة دراسية', 'study plan', 'ساعة معتمدة', 'مساق'],
        ['ساعات', 'credit hours', 'ساعة معتمدة'],
    ]
    for group in topic_groups:
        new_has = any(kw in new_q for kw in group)
        cached_has = any(kw in cached_q for kw in group)
        if new_has and not cached_has:
            return True
    return False


class SemanticResponseCache:
    """
    Cache ذكي ثلاثي المسارات:
    1. Exact hash  -> فوري (~1ms)
    2. Vector similarity -> سريع لان الـ vectors مخزنة مسبقاً (~5ms)
    3. Fallback -> None
    """
    SIMILARITY_THRESHOLD = 0.88
    def __init__(self, embeddings_model=None):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._embeddings_model = embeddings_model
        # قاموس: hash -> (entry_dict, vector_np)
        self._cache_vectors: Dict[str, Tuple] = {}
        self._load_cache()

    def _load_cache(self):
        """تحميل الـ cache مع بناء الـ vectors مرة واحدة عند الاقلاع."""
        try:
            c = self.conn.cursor()
            c.execute("""SELECT question_hash, question, response, confidence, source
                         FROM response_cache
                         WHERE confidence >= 60
                           AND last_used > datetime('now', '-7 days')""")
            rows = c.fetchall()
            self._cache_vectors = {}
            if self._embeddings_model and rows:
                questions = [r[1] for r in rows]
                try:
                    vecs = self._embeddings_model.embed_documents(questions)
                    for row, vec in zip(rows, vecs):
                        entry = {
                            "hash": row[0], "question": row[1],
                            "response": row[2], "confidence": row[3], "source": row[4]
                        }
                        self._cache_vectors[row[0]] = (entry, np.array(vec))
                except Exception:
                    for row in rows:
                        entry = {
                            "hash": row[0], "question": row[1],
                            "response": row[2], "confidence": row[3], "source": row[4]
                        }
                        self._cache_vectors[row[0]] = (entry, None)
            else:
                for row in rows:
                    entry = {
                        "hash": row[0], "question": row[1],
                        "response": row[2], "confidence": row[3], "source": row[4]
                    }
                    self._cache_vectors[row[0]] = (entry, None)
            logger.info(f"Cache loaded: {len(self._cache_vectors)} entries with pre-built vectors")
        except Exception as e:
            logger.error(f"Cache load error: {e}")
            self._cache_vectors = {}

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        if self._embeddings_model is None:
            return None
        try:
            return np.array(self._embeddings_model.embed_query(text))
        except Exception:
            return None

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def get(self, question: str) -> Optional[Dict]:
        c = self.conn.cursor()

        # PATH 1: Exact hash (~1ms)
        q_hash = self._hash_question(question)
        c.execute("""SELECT response, confidence, source FROM response_cache
                     WHERE question_hash = ? AND confidence >= 60
                       AND last_used > datetime('now', '-7 days')""", (q_hash,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE response_cache SET hit_count = hit_count + 1, last_used = ? WHERE question_hash = ?",
                (datetime.now().isoformat(), q_hash))
            self.conn.commit()
            logger.info(f"[CACHE] Exact hit: '{question[:50]}'")
            return {"response": row[0], "confidence": row[1], "source": "cache"}

        # PATH 2: Vector similarity — vectors مخزنة مسبقاً (~5ms بدل ~200ms × N)
        if not self._cache_vectors:
            return None
        has_vectors = any(v is not None for _, v in self._cache_vectors.values())
        if not has_vectors or self._embeddings_model is None:
            return None

        query_vec = self._get_embedding(question)
        if query_vec is None:
            return None

        best_sim, best_entry = 0.0, None
        for h, (entry, vec) in self._cache_vectors.items():
            if vec is None:
                continue
            sim = self._cosine_sim(query_vec, vec)
            if sim > best_sim:
                best_sim, best_entry = sim, entry

        if best_sim >= self.SIMILARITY_THRESHOLD and best_entry:
            if _is_incompatible_cache(question, best_entry["question"]):
                logger.info(f"[CACHE] Blocked incompatible (sim={best_sim:.3f})")
                return None
            logger.info(f"[CACHE] Semantic hit (sim={best_sim:.3f}): '{question[:50]}'")
            c.execute("UPDATE response_cache SET hit_count = hit_count + 1, last_used = ? WHERE question_hash = ?",
                (datetime.now().isoformat(), best_entry["hash"]))
            self.conn.commit()
            return {"response": best_entry["response"], "confidence": best_entry["confidence"], "source": "cache"}

        return None
    def set(self, question: str, response: str, confidence: float, source: str):
        # لا تخزن أسئلة "قوائم/أسماء" — تسبب false hits لأن الـ embeddings تتشابه مع أسئلة مختلفة
        list_kws = ['اسماء', 'أسماء', 'اذكر', 'جميع', 'كل الكليات', 'قائمة', 'names', 'list all', 'اعطيني الاسماء']
        if any(kw in question.lower() for kw in list_kws):
            logger.info(f"[CACHE] Skipping cache for list-type question: '{question[:40]}'")
            return
        threshold = compute_dynamic_threshold(question, source)
        if confidence < threshold:
            return
        cleaned = response.strip()
        if not cleaned or len(cleaned) < 3:
            return
        q_hash = self._hash_question(question)
        now = datetime.now().isoformat()
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO response_cache (question_hash, question, response, confidence, source, created_at, last_used, hit_count) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (q_hash, question, cleaned, confidence, source, now, now))
        self.conn.commit()
        # Update in-memory cache (_cache_vectors هو المرجع الصحيح وليس _cache_entries)
        entry = {
            "hash": q_hash, "question": question, "response": cleaned,
            "confidence": confidence, "source": source
        }
        vec = self._get_embedding(question) if self._embeddings_model else None
        self._cache_vectors[q_hash] = (entry, vec)
    def _hash_question(self, question: str) -> str:
        normalized = arabic_processor.normalize(question)
        normalized = re.sub(r'[\u0600-\u060B\u060D-\u061A\u061C-\u061F\u066A-\u066D\u06D4]', ' ', normalized)
        tokens = arabic_processor.tokenize(normalized)
        unique_tokens = sorted(set(tokens))
        key = " ".join(unique_tokens)
        return hashlib.md5(key.encode()).hexdigest()
