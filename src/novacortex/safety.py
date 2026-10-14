"""Input safety: scope detection, injection filter, greeting and false-premise handling."""

import asyncio
import json
import logging
import re

from typing import Optional, Dict

from novacortex.knowledge.faculty import COLLOQUIAL_FACULTY_TERMS
from novacortex.knowledge.keywords import UNIVERSITY_CONTEXT_KEYWORDS
from novacortex.input_rules import INJECTION_PATTERNS, detect_injection
from novacortex.llm import llm_client

logger = logging.getLogger(__name__)

# ==================== SMART OUT-OF-SCOPE DETECTOR ====================
class SmartOutOfScopeDetector:
    def __init__(self, llm_client):
        self.client = llm_client
        self.cache = {}
        self.classification_prompt = """You are a scope classifier for Yarmouk University chatbot.
Your ONLY job: determine if a question is about Yarmouk University or not.
✅ IN SCOPE:
- Questions about faculties, colleges, departments
- Questions about admission, registration, fees, scholarships
- Questions about university services, facilities, staff, deans, president
- Questions about academic programs, courses, majors, study plans
- Questions about student life, housing, clubs, health insurance
- General questions answerable with university context
- Questions using colloquial names for faculties (IT, الحجاوي, الايتي, etc.)
❌ OUT OF SCOPE:
- Questions about OTHER universities (Harvard, الهاشمية, etc.)
- Sports/celebrities (Messi, رونالدو, etc.)
- Technology products (iPhone price, etc.)
- Weather, food recipes, movies, TV shows
- General life advice with NO university connection
RULES:
1. If "Yarmouk" or "اليرموك" mentioned → IN SCOPE
2. If comparison includes Yarmouk → IN SCOPE
3. If general but could relate to university → IN SCOPE
4. Another university only → OUT OF SCOPE
5. Celebrities/products → OUT OF SCOPE
Respond ONLY with JSON: {"is_in_scope": true/false, "confidence": 0.0-1.0, "reason": "brief"}
CRITICAL RULE: If the question mentions "Yarmouk" or "اليرموك" alongside false geographic or factual claims (e.g. Europe, Mars, 1850, astronaut training), it is STILL IN SCOPE. The bot needs to correct the false premise. Mark as is_in_scope: true."""
    def _check_colloquial_terms(self, question: str) -> bool:
        q_lower = question.lower().strip()
        for term in COLLOQUIAL_FACULTY_TERMS.keys():
            if term in q_lower:
                logger.info(f"Colloquial term '{term}' detected → IN SCOPE")
                return True
        for term in UNIVERSITY_CONTEXT_KEYWORDS:
            if term in q_lower:
                logger.info(f"University context term '{term}' detected → IN SCOPE")
                return True
        return False
    async def is_out_of_scope(self, question: str, has_context: bool = False) -> Optional[Dict]:
        if self._check_colloquial_terms(question):
            return None
        if has_context and len(question.split()) <= 4:
            logger.info("Short message with context -> skipping scope check")
            return None

        # ── Hard OOS — لا يحتاج LLM ──
        # ===== حماية الكلمات الجامعية الحساسة من scope filter =====
        ALWAYS_IN_SCOPE = [
            'أخصائي نفسي','مرشد نفسي','مستشار نفسي','إرشاد نفسي','counseling',
            'اتواصل مع أخصائي','كم ساعة تخرج','ساعة تخرج','ساعات التخرج',
        ]
        q_lower_ais = question.lower()
        if any(kw in q_lower_ais for kw in ALWAYS_IN_SCOPE):
            return None  # دائماً في النطاق

        HARD_OOS = [
            'كأس العالم','world cup','كرة قدم','football','soccer','ميسي','رونالدو',
            'فيلم','movies','netflix','مسلسل','anime','أنمي','أغنية','أغاني','موسيقى',
            'سعر الدولار','سعر الذهب','exchange rate','bitcoin','عملة رقمية',
            'طقس','weather','برج','horoscope','الأبراج','وصفة','recipe','طبخ',
            'فيسبوك حساب','تويتر حساب','انستغرام','tiktok','snapchat account',
            'اخبار','breaking news','آخر أخبار','latest news',
        ]
        q_lower_oos = question.lower()
        for kw in HARD_OOS:
            if kw in q_lower_oos:
                detected_lang = self._detect_language(question)
                msg = ("عذراً، هذا السؤال خارج نطاق تخصصي في جامعة اليرموك." if detected_lang == "ar"
                       else "Sorry, this topic is outside my specialization in Yarmouk University.")
                return {"message": msg, "reason": f"Hard OOS keyword: {kw}"}

        if question in self.cache:
            return self.cache[question]
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.classification_prompt},
                    {"role": "user", "content": f"Question: {question}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=150
            )
            result = json.loads(response.choices[0].message.content)
            is_in_scope = result.get("is_in_scope", True)
            confidence = result.get("confidence", 0.5)
            reason = result.get("reason", "")
            logger.info(f"Scope: {'IN' if is_in_scope else 'OUT'} (conf: {confidence:.2f}) - {reason}")
            if not is_in_scope and confidence >= 0.7:
                detected_lang = self._detect_language(question)
                if detected_lang == "ar":
                    rejection_message = {"message": "عذراً، أنا متخصص فقط في جامعة اليرموك 🎓", "reason": reason}
                else:
                    rejection_message = {"message": "Sorry, I specialize only in Yarmouk University 🎓", "reason": reason}
                self.cache[question] = rejection_message
                return rejection_message
            self.cache[question] = None
            return None
        except Exception as e:
            logger.error(f"Scope classification error: {e}")
            return None
    def _detect_language(self, text: str) -> str:
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        return "ar" if arabic_chars >= english_chars else "en"
def handle_greeting(question: str) -> Optional[str]:
    if not isinstance(question, str):
        return None
    q_lower = question.lower().strip()
    arabic_greetings = ["السلام", "مرحبا", "أهلا", "هلا", "صباح", "مساء"]
    english_greetings = ["hi", "hello", "hey", "good morning", "good evening"]
    if any(g in q_lower for g in arabic_greetings) and len(q_lower.split()) <= 3:
        return "أهلاً بك! كيف يمكنني مساعدتك؟"
    if any(g == q_lower or q_lower.startswith(g) for g in english_greetings) and len(q_lower.split()) <= 3:
        return "Hello! How can I help you?"
    return None
def is_comparison_question(question: str) -> bool:
    q_lower = question.lower().strip()
    comparison_words = [
        'مين احسن', 'مين أفضل', 'مقارنة بين', 'vs', 'versus', 'better than', 'who is better',
        'compare yarmouk with', 'compare with', 'مقارنة اليرموك',
    ]
    return any(word in q_lower for word in comparison_words)
def is_general_oos(question: str) -> bool:
    q_lower = question.lower().strip()
    general_oos = [
        'best university in jordan', 'أفضل جامعة في الأردن', 'أفضل جامعة',
        'what is the weather', 'weather in', 'tell me a joke', 'احكيلي نكتة', 'أخبرني نكتة',
        'نكتة', 'joke', 'funny story',
        'سعر الدولار', 'exchange rate', 'سعر الصرف', 'سعر اليورو',
        'وصفة', 'recipe for', 'كيف أطبخ', 'طريقة طبخ',
        'كم 2', 'كم يساوي', 'what is 2+', 'math problem',
        'من هو ميسي', 'who is messi', 'من هو رونالدو', 'من هو كريستيانو',
        'سعر ايفون', 'iphone price', 'اشتري', 'شراء',
    ]
    return any(kw in q_lower for kw in general_oos)
def detect_response_depth(question: str) -> str:
    q_lower = question.lower().strip()
    detail_kw = ['اشرح', 'بالتفصيل', 'احكيلي عن', 'شرح', 'explain', 'detail', 'tell me about', 'اعطيني معلومات عن']
    if any(kw in q_lower for kw in detail_kw):
        return "detailed"
    brief_kw = ['من هو', 'مين هو', 'مين', 'كم', 'هل', 'who is', 'how many', 'is there', 'what is the']
    if any(kw in q_lower for kw in brief_kw) and len(q_lower.split()) <= 8:
        return "brief"
    return "moderate"
# ==================== FALSE PREMISE CORRECTOR ====================
async def check_false_premise_llm(question: str, lang: str, llm_client) -> Optional[str]:
    q_lower = question.lower()
    if not re.search(r'اليرموك|yarmouk', q_lower, re.IGNORECASE):
        return None
    try:
        response = await asyncio.to_thread(
            llm_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "You are a fact checker for Yarmouk University.\n"
                    "Known facts: founded 1976, located in Irbid Jordan, public university, no space programs, no online degrees.\n"
                    "If the question contains a FALSE claim about Yarmouk University, respond with JSON:\n"
                    "{\"has_false_premise\": true, \"correction_ar\": \"...\", \"correction_en\": \"...\"}\n"
                    "If no false claim, respond: {\"has_false_premise\": false}\n"
                    "ONLY flag clear factual errors, not opinions or questions."
                )},
                {"role": "user", "content": f"Question: {question}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=200
        )
        result = json.loads(response.choices[0].message.content)
        if result.get("has_false_premise"):
            correction = result.get("correction_ar" if lang == "ar" else "correction_en", "")
            if correction:
                logger.info(f"[FIX-5] LLM false premise detected: '{question[:60]}'")
                return f"❌ {correction}"
    except Exception as e:
        logger.warning(f"[FIX-5] LLM false premise check failed, using fallback: {e}")
        return _check_false_premise_fallback(question, lang)
    return None
def _check_false_premise_fallback(question: str, lang: str) -> Optional[str]:
    # تحويل الأرقام العربية إلى إنجليزية
    q_norm = question
    for i, c in enumerate('٠١٢٣٤٥٦٧٨٩'):
        q_norm = q_norm.replace(c, str(i))
    q_lower = q_norm.lower()

    # فحص حكومية/خاصة مع أو بدون ذكر اليرموك
    if re.search(r'اليرموك|yarmouk', q_lower, re.IGNORECASE):
        if re.search(r'جامعة\s*خاصة|private\s*university|مش\s*حكومية|ليست\s*حكومية|مو\s*حكومية', q_lower, re.IGNORECASE):
            return ("❌ معلومة غير صحيحة. جامعة اليرموك جامعة حكومية أردنية. ✅"
                    if lang == "ar" else
                    "❌ Incorrect. Yarmouk University is a public (governmental) Jordanian university. ✅")

    if not re.search(r'اليرموك|yarmouk', q_lower, re.IGNORECASE):
        return None

    assertive_foreign = (
        r'(?:located?\s+in|is\s+in|based\s+in|found\s+in|in\s+(?:europe|mars|canada|france|germany|usa|uk|america))'
        r'|(?:في\s*(?:أوروبا|المريخ|كندا|فرنسا|ألمانيا|أمريكا|بريطانيا|عمان|العاصمة|عملن|عمَّان|عمّان))'
        r'|(?:تقع\s*في\s*(?:أوروبا|خارج|عمان|العاصمة|عملن|عمَّان|عمّان))'
        r'|(?:on\s+mars)'
    )
    if re.search(assertive_foreign, q_lower, re.IGNORECASE):
        return ("❌ معلومة غير صحيحة. جامعة اليرموك تقع في مدينة إربد، الأردن. ✅"
                if lang == "ar" else
                "❌ Incorrect. Yarmouk University is located in Irbid, Jordan. ✅")

    year_match = re.search(r'\b(1[89]\d\d|200\d|201\d)\b', q_lower)
    if year_match and year_match.group() != '1976':
        if re.search(r'تأسست|founded|established|أسست', q_lower, re.IGNORECASE):
            return ("❌ معلومة غير صحيحة. تأسست جامعة اليرموك عام 1976. ✅"
                    if lang == "ar" else
                    "❌ Incorrect. Yarmouk University was established in 1976. ✅")

    if re.search(r'رواد فضاء|تدريب فضاء|astronaut|space training', q_lower, re.IGNORECASE):
        return ("❌ لا تقدم جامعة اليرموك برامج تدريب رواد فضاء. ✅" if lang == "ar"
                else "❌ Yarmouk University does not offer astronaut training programs. ✅")

    if re.search(r'أقدم من الإنترنت|older than the internet|أقدم من الانترنت', q_lower, re.IGNORECASE):
        return ("❌ الإنترنت نشأ عام 1969، بينما تأسست اليرموك عام 1976 — الإنترنت أقدم. ✅" if lang == "ar"
                else "❌ The internet (ARPANET 1969) predates Yarmouk University (1976). ✅")

    if re.search(r'فروع على|campus.*mars|campuses.*mars|كوكب المريخ', q_lower, re.IGNORECASE):
        return ("❌ لا تمتلك جامعة اليرموك أي فروع خارج إربد، الأردن. 🌍" if lang == "ar"
                else "❌ Yarmouk University has no campuses outside Irbid, Jordan. 🌍")

    return None
def check_false_premise(question: str, lang: str) -> Optional[str]:
    return _check_false_premise_fallback(question, lang)
scope_detector = SmartOutOfScopeDetector(llm_client)
