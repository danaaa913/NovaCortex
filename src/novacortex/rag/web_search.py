"""Serper based web search helpers."""

import json
import logging
import re
import time

from typing import List, Optional, Dict

import requests

from novacortex.config import CURRENT_YEAR, SERPER_API_KEY
from novacortex.knowledge.keywords import FEES_KEYWORDS, SCHOLARSHIP_KEYWORDS
from novacortex.rag.pdf import PDFExtractor
from novacortex.text import arabic_processor

logger = logging.getLogger(__name__)

# ==================== DEEP FACULTY SEARCH ====================
def generate_deep_faculty_query(question: str, faculty_name: str = None) -> List[str]:
    detected_lang = arabic_processor.detect_language(question)
    if not faculty_name:
        name_pattern = r'(?:دكتور|الدكتور|أستاذ|البروفيسور|dr|prof)\s+([\w\s]+?)(?:\s+|\Z|\.)'
        match = re.search(name_pattern, question, re.IGNORECASE)
        if match:
            faculty_name = match.group(1).strip()
        else:
            faculty_name = question
    queries = []
    if detected_lang == "ar":
        queries = [
            f"site:fmd.yu.edu.jo {faculty_name} البريد الإلكتروني مكتب هاتف",
            f"site:fmd.yu.edu.jo {faculty_name} email office phone",
            f"موقع جامعة اليرموك {faculty_name} بريد إلكتروني رقم هاتف",
            f"fmd.yu.edu.jo {faculty_name} contact information",
        ]
    else:
        queries = [
            f"site:fmd.yu.edu.jo {faculty_name} email office phone",
            f"site:fmd.yu.edu.jo {faculty_name} contact information",
            f"Yarmouk University faculty {faculty_name} email address office",
            f"fmd.yu.edu.jo {faculty_name} contact details",
        ]
    return queries
# ==================== RAW DATA EXTRACTION ====================
def extract_raw_contact_data(text: str) -> Dict[str, List[str]]:
    extracted = {"emails": [], "offices": [], "phones": []}
    if not text:
        return extracted
    email_pattern = r'\b[\w\.-]+@yu\.edu\.jo\b'
    emails = re.findall(email_pattern, text, re.IGNORECASE)
    extracted["emails"] = list(set(emails))
    office_patterns = [
        r'(?:مكتب|office|room|غرفة|مبنى|building)\s*:?\s*([^،\n\r]+)',
        r'([^،\n\r]+?)\s*(?:مكتب|office)',
        r'location\s*:?\s*([^،\n\r]+)',
        r'الموقع\s*:?\s*([^،\n\r]+)'
    ]
    for pattern in office_patterns:
        offices = re.findall(pattern, text, re.IGNORECASE)
        extracted["offices"].extend([o.strip() for o in offices if o.strip()])
    phone_patterns = [
        r'(?:هاتف|tel|phone|mobile|جوال|خلوي)\s*:?\s*([\d\s\+\-\(\)]{7,})',
        r'([\d\s\+\-\(\)]{10,})'
    ]
    for pattern in phone_patterns:
        phones = re.findall(pattern, text, re.IGNORECASE)
        extracted["phones"].extend([p.strip() for p in phones if p.strip()])
    extracted["offices"] = list(set(extracted["offices"]))
    extracted["phones"] = list(set([re.sub(r'\s+', ' ', p) for p in extracted["phones"]]))
    return extracted
# ==================== WEB SEARCHER ====================
class EnhancedWebSearcher:
    def __init__(self):
        self.api_key = SERPER_API_KEY
        self.last_call_time = 0
        self.min_delay = 0.5
        self.pdf_extractor = PDFExtractor()
        self.faculty_site = "site:fmd.yu.edu.jo"
    # ==================== TIME-AWARE SEARCH ====================
    TIME_SENSITIVE_KW = [
        'موعد', 'مواعيد', 'آخر موعد', 'deadline', 'تسجيل', 'registration',
        'تقويم', 'calendar', 'جديد', 'أخبار', 'news', 'إعلان',
        'رسوم', 'fees', 'القبول', 'admission', CURRENT_YEAR,
    ]
    def _is_time_sensitive(self, question: str) -> bool:
        q_lower = question.lower()
        return any(str(kw) in q_lower for kw in self.TIME_SENSITIVE_KW)
    def search_multi(self, question: str, study_level: str = "بكالوريوس", is_faculty_search: bool = False, faculty_name: str = None) -> List[Dict]:
        if is_faculty_search:
            queries = generate_deep_faculty_query(question, faculty_name)
        else:
            queries = self._generate_queries(question, study_level)
        all_results = []
        time_sensitive = self._is_time_sensitive(question)
        for query in queries:
            now = time.time()
            if now - self.last_call_time < self.min_delay:
                time.sleep(self.min_delay - (now - self.last_call_time))
            url = "https://google.serper.dev/search"
            search_params = {"q": query, "num": 8}
            # Prioritize recent results for time-sensitive queries
            if time_sensitive:
                search_params["tbs"] = "qdr:y"  # Last year
                logger.info(f"[TIME-AWARE] Using recency filter for: '{query[:50]}'")
            payload = json.dumps(search_params)
            headers = {'X-API-KEY': self.api_key, 'Content-Type': 'application/json'}
            try:
                response = requests.post(url, headers=headers, data=payload, timeout=15)
                response.raise_for_status()
                self.last_call_time = time.time()
                data = response.json()
                if "organic" in data:
                    all_results.extend(data["organic"])
            except Exception as e:
                logger.error(f"Search error: {e}")
        return self._filter_and_rank(all_results, is_faculty_search)
    def _generate_queries(self, question: str, study_level: str = "بكالوريوس") -> List[str]:
        detected_lang = arabic_processor.detect_language(question)
        is_scholarship = any(word in question.lower() for word in SCHOLARSHIP_KEYWORDS)
        is_fees = any(word in question.lower() for word in FEES_KEYWORDS)
        president_keywords = ['تعيين', 'رئيس الجامعة', 'الشرايري', 'president', 'appointed', 'tenure', 'خدم', 'صارله',
                             'leads yarmouk', 'who leads', 'is malik', 'مين رئيس', 'مين هو رئيس']
        is_president_question = any(kw in question.lower() for kw in president_keywords)
        if is_president_question:
            return (
                ["مالك الشرايري رئيس جامعة اليرموك تاريخ التعيين"]
                if detected_lang == "ar" else
                ["Malik Al-Shariri Yarmouk University president appointment date"]
            )
        if is_scholarship:
            return (["المنح الدراسية المتاحة جامعة اليرموك"] if detected_lang == "ar" else ["Available scholarships Yarmouk University"])
        if is_fees:
            return ([f"الرسوم الدراسية اليرموك"] if detected_lang == "ar" else [f"Tuition fees YU"])
        return ([f"{question} جامعة اليرموك"] if detected_lang == "ar" else [f"{question} Yarmouk University"])
    def _filter_and_rank(self, results: List[Dict], is_faculty_search: bool = False) -> List[Dict]:
        if not results:
            return []
        seen_links = set()
        unique_results = []
        for r in results:
            link = r.get('link', '')
            if link not in seen_links:
                seen_links.add(link)
                score = 0
                if is_faculty_search and 'fmd.yu.edu.jo' in link:
                    score += 100
                elif 'yu.edu.jo' in link:
                    score += 50
                if '.pdf' in link.lower():
                    score += 40
                snippet = r.get('snippet', '').lower()
                if '@yu.edu.jo' in snippet:
                    score += 30
                if 'مكتب' in snippet or 'office' in snippet:
                    score += 20
                r['quality_score'] = score
                unique_results.append(r)
        return sorted(unique_results, key=lambda x: x['quality_score'], reverse=True)
    def find_best_result(self, results: List[Dict]) -> Optional[Dict]:
        return results[0] if results else None
    def combine_top_snippets(self, results: List[Dict], top_n: int = 3) -> str:
        snippets = []
        for i, r in enumerate(results[:top_n]):
            snippet = r.get("snippet", "").strip()
            title = r.get("title", "").strip()
            if snippet and len(snippet) > 30:
                labeled = f"[المصدر {i+1} - {title}]:\n{snippet}" if title else f"[المصدر {i+1}]:\n{snippet}"
                snippets.append(labeled)
        combined = "\n\n".join(snippets)
        logger.info(f"[IMPROVEMENT 1] Combined {len(snippets)} snippets ({len(combined)} chars)")
        return combined
web_searcher = EnhancedWebSearcher()
