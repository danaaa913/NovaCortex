"""Evidence-based confidence helpers.

These scores are routing signals, not calibrated probabilities.  They are
derived from retrieval strength, query coverage and source diversity so a
successful model call is no longer treated as proof that an answer is right.
"""

import re
from typing import Iterable, List, Mapping, Sequence, Tuple
from urllib.parse import urlparse


VOLATILE_CACHE_KEYWORDS = [
    'اليوم', 'غداً', 'غدا', 'هذا الأسبوع', 'هذا الشهر', 'حاليا', 'حالياً',
    'آخر موعد', 'موعد التسجيل', 'موعد الامتحان', 'أخبار', 'خبر', 'جديد',
    'رسوم', 'تكلفة', 'سعر', 'منحة', 'قبول', 'تعيين', 'رئيس الجامعة',
    'دكتور', 'أستاذ', 'عميد', 'هاتف', 'رقم', 'ايميل', 'إيميل',
    'today', 'tomorrow', 'current', 'latest', 'deadline', 'registration',
    'fees', 'price', 'scholarship', 'admission', 'appointed', 'president',
    'professor', 'doctor', 'dean', 'phone', 'email',
]


def is_cacheable_question(question: str) -> bool:
    """Only cache questions whose answer is unlikely to change by entity/date."""
    q_lower = question.lower()
    if any(keyword in q_lower for keyword in VOLATILE_CACHE_KEYWORDS):
        return False
    if re.search(r'\b(?:19|20)\d{2}\b|[٠-٩]|\d', q_lower):
        return False
    return True


def split_telegram_message(text: str, limit: int = 3900) -> List[str]:
    """Split long responses on paragraph boundaries below Telegram's limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    return chunks


def is_official_yu_url(url: str) -> bool:
    """Accept the university host and its subdomains, rejecting lookalikes."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == "yu.edu.jo" or host.endswith(".yu.edu.jo")


def _terms(text: str) -> set:
    return {
        token.lower()
        for token in re.findall(r"[\w\u0600-\u06ff]+", text or "")
        if len(token) > 2
    }


def _coverage(question: str, evidence_text: str) -> float:
    question_terms = _terms(question)
    if not question_terms:
        return 0.0
    return len(question_terms & _terms(evidence_text)) / len(question_terms)


def retrieval_confidence(question: str, docs_with_scores: Sequence[Tuple]) -> int:
    """Score retrieved evidence using strength, lexical coverage and diversity."""
    if not docs_with_scores:
        return 0
    top_score = max(0.0, min(1.0, float(docs_with_scores[0][1])))
    evidence = " ".join(doc.page_content for doc, _ in docs_with_scores[:4])
    coverage = _coverage(question, evidence)
    sources = {
        doc.metadata.get("source") or doc.metadata.get("title")
        for doc, _ in docs_with_scores[:4]
        if doc.metadata.get("source") or doc.metadata.get("title")
    }
    diversity = min(1.0, len(sources) / 2.0)
    return round(100 * (0.55 * top_score + 0.25 * coverage + 0.20 * diversity))


def web_confidence(question: str, results: List[Mapping], evidence_text: str = "") -> int:
    """Score web evidence, strongly preferring official Yarmouk sources."""
    usable = [
        r for r in results[:3]
        if (r.get("snippet") or "").strip()
        or (evidence_text and (r.get("link") or "").strip())
    ]
    if not usable:
        return 0
    official = sum(is_official_yu_url(r.get("link") or "") for r in usable) / len(usable)
    evidence = evidence_text or " ".join(
        (r.get("title") or "") + " " + (r.get("snippet") or "") for r in usable
    )
    coverage = _coverage(question, evidence)
    quantity = min(1.0, len(usable) / 3.0)
    return round(100 * (0.45 * official + 0.35 * coverage + 0.20 * quantity))
