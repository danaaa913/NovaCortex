"""Intent parsing and verified-facts routing."""

import json
import logging
import re

from typing import List, Optional, Dict

from novacortex.knowledge.facts import VERIFIED_FACTS
from novacortex.knowledge.faculty import COLLOQUIAL_FACULTY_TERMS
from novacortex.knowledge.keywords import COST_SPECIFIC_KEYWORDS
from novacortex.knowledge.localization import INTERNATIONAL_DATA, LANGUAGE_BRIDGE
from novacortex.llm import llm_client
from novacortex.safety import detect_response_depth

logger = logging.getLogger(__name__)

# ==================== SEMANTIC INTENT PARSER ====================
class SemanticIntentParser:
    INTENT_SCHEMA = """You are a question intent classifier for Yarmouk University chatbot.
Analyze the FULL question meaning (not just keywords) and return ONLY this JSON:
{
  "intent_key": "<one of the keys below>",
  "entity": "<specific thing mentioned e.g. faculty name or professor name>"
}
INTENT KEYS - pick the MOST SPECIFIC one:
- "list_faculties" → user wants a list/count of ALL faculties
- "count_faculties" → user asks specifically "how many?" faculties
- "list_programs" → user wants programs/majors INSIDE a specific faculty
- "list_departments" → user wants departments/أقسام INSIDE a specific faculty
- "faculty_dean" → user asks who is the DEAN (عميد) of a specific faculty
- "faculty_vice_dean" → user asks about VICE DEAN (نائب العميد) or ASSISTANT DEAN (مساعد العميد)
- "department_head" → user asks about HEAD OF DEPARTMENT (رئيس قسم)
- "faculty_info" → user wants general info about a SPECIFIC faculty
- "credit_hours" → how many credit hours for a program/major
- "student_housing" → dormitories/accommodation
- "health_insurance" → medical insurance for students
- "online_learning_policy" → user asks if they can study online / stay home
- "elearning_system" → user asks how to access Moodle, Teams, Portals, electronical systems
- "university_president" → who is the president/رئيس الجامعة
- "university_type" → is it public/private? حكومية أم خاصة
- "university_info" → general info about the WHOLE university
- "fees_inquiry" → user asks about tuition fees, costs, prices
- "scholarship_inquiry" → user asks about scholarships, grants, financial aid
- "cost_inquiry" → user asks about cost of specific things like housing
- "faculty_member_search" → user asks about a specific professor/faculty member
- "graduate_programs" → user asks if YU has master/PhD/graduate programs
- "instruction_language" → user asks about language of teaching/instruction
- "library_services" → user asks about library services or facilities
- "student_clubs" → user asks about clubs, activities, extracurricular
- "university_gates" → user asks about gates/entrances of the university
- "rag_needed" → anything else
Return ONLY the JSON, no other text."""
    def __init__(self, client):
        self.client = client
        self._cache: Dict[str, Dict] = {}
    def parse(self, question: str) -> Dict:
        # --- FIX: Define q_low for detection ---
        q_low = question.lower().strip()
        
        if any(kw in q_low for kw in ['إقامة', 'residenc', 'بنك', 'bank', 'مطار', 'airport', 'مواصلات']):
            return {"intent_key": "intl_onboarding", "entity": "onboarding"}
        if any(kw in q_low for kw in ['ترجم', 'معنى كلمة', 'شو يعني', 'translate', 'meaning of']):
            return {"intent_key": "language_bridge", "entity": "bridge"}
        q_key = question.strip().lower()
        response_depth = detect_response_depth(question)
        faculty_keywords = [
            'دكتور', 'دكتورة', 'أستاذ', 'بروفيسور', 'dr', 'prof', 'professor', 'الدكتور', 'البروفيسور',
            'إيميل', 'ايميل', 'بريد', 'تواصل', 'مكتب', 'email', 'contact', 'office'
        ]
        if any(kw in q_key for kw in faculty_keywords) and not any(kw in q_key for kw in ['عميد', 'dean', 'رئيس']):
            logger.info("Faculty member/contact search detected")
            words = q_key.split()
            entity = "faculty_member"
            for i, word in enumerate(words):
                if word in ['دكتور', 'الدكتور', 'dr', 'prof', 'أستاذ'] and i+1 < len(words):
                    entity = words[i+1]
                    break
            return {"intent_key": "faculty_member_search", "entity": entity, "response_depth": response_depth}
        _admission_kw = [
            'شروط القبول', 'متطلبات القبول', 'شروط التسجيل', 'متطلبات التسجيل',
            'كيفية القبول', 'طريقة القبول', 'قبول في الجامعة', 'admission requirements',
            'what are the admission', 'admission requirement', 'requirements to join',
            'how to apply', 'كيف أتقدم', 'كيف اتقدم', 'شروط الالتحاق',
            'ما هي شروط', 'شروط الدراسة'
        ]
        if any(kw in q_key for kw in _admission_kw):
            return {"intent_key": "rag_needed", "entity": "admission", "response_depth": response_depth}
        # ===== credit hours — ساعات التخرج =====
        _credit_kw = ['كم ساعة تخرج','ساعة تخرج','ساعات التخرج','ساعات اللازمة للتخرج',
                      'how many credit hours','credit hours for','total hours',
                      'مجموع ساعات','كم ساعة لتخصص','كم ساعة للتخرج']
        if any(kw in q_key for kw in _credit_kw):
            return {"intent_key": "credit_hours", "entity": "program", "response_depth": response_depth}

        # ===== FIX: مساقات الخطط الدراسية → RAG أولاً (قبل list_faculties) =====
        _courses_kw = ['مساق', 'مساقات', 'مادة', 'مواد', 'كورس', 'كورسات', 'course', 'courses',
                       'subject', 'curriculum', 'منهج', 'مناهج', 'مقرر', 'مقررات', 'شو بدرسوا',
                       'شو بيدرسوا', 'شو بدرس', 'ماذا يدرس', 'ماذا ندرس', 'ماذا تدرس']
        _prog_kw    = ['cs','cis','cys','bit','da','drg','علوم الحاسوب','نظم المعلومات',
                       'الأمن السيبراني','امن سيبراني','علم البيانات','واقع رقمي','ألعاب','تكنولوجيا معلومات الأعمال']
        if any(kw in q_key for kw in _courses_kw) and any(kw in q_key for kw in _prog_kw):
            # استخرج السنة إذا ذكرها
            year_mentioned = next((y for y in ['2019','2021','2023','2024','2025'] if y in q_key), None)
            return {"intent_key": "rag_needed", "entity": f"courses_{year_mentioned or 'ask_year'}",
                    "response_depth": response_depth}

        # ===== FIX: سؤال عن مساقات بدون تحديد تخصص → اطلب توضيح =====
        if any(kw in q_key for kw in _courses_kw) and not any(kw in q_key for kw in _prog_kw):
            return {"intent_key": "ask_clarification", "entity": "missing_major",
                    "response_depth": response_depth}

        # ===== FIX: خطة دراسية بدون تحديد سنة → نسأل =====
        _study_plan_kw = ['خطة دراس', 'خطه دراس', 'study plan', 'خطة البكالوريوس', 'خطة التخصص',
                          'مواد دراسية', 'مناهج', 'مقررات', 'كورسات', 'curriculum']
        if any(kw in q_key for kw in _study_plan_kw):
            year_mentioned = next((y for y in ['2019','2021','2023','2024','2025'] if y in q_key), None)
            entity = f"study_plan_{year_mentioned}" if year_mentioned else "study_plan_ask_year"
            return {"intent_key": "rag_needed", "entity": entity, "response_depth": response_depth}

        _count_kw = ['كم عدد الكليات', 'كم كلية', 'كم عدد كلي', 'how many faculties', 'number of faculties']
        _listfac_kw = ['ما هي الكليات', 'ما هي كليات', 'اذكر كليات', 'اذكر لي كليات', 'جميع الكليات',
                       'كل الكليات', 'list all', 'list the faculties', 'all faculties', 'كليات الجامعة', 'كليات اليرموك']
        if any(kw in q_key for kw in _count_kw):
            return {"intent_key": "count_faculties", "entity": "", "response_depth": response_depth}
        if any(kw in q_key for kw in _listfac_kw):
            return {"intent_key": "list_faculties", "entity": "", "response_depth": response_depth}
        _housing_kw = ['سكن', 'مسكن', 'إقامة', 'سكن طلاب', 'سكن جامعي', 'dorm', 'dormitory', 'dormitories', 'housing', 'accommodation', 'on-campus housing']
        if any(kw in q_key for kw in _housing_kw):
            return {"intent_key": "student_housing", "entity": "housing", "response_depth": response_depth}

        # ===== SMART: كشف أسئلة المعدل المنخفض وخطة الإنقاذ =====
        _gpa_rescue_kw = [
            'معدلي', 'معدل منخفض', 'رسبت', 'إنذار', 'انذار', 'مراقبة أكاديمية',
            'خطر فصل', 'فصل من الجامعة', 'كيف أرفع معدلي', 'معدلي منخفض',
            'معدلي 5', 'معدلي 6', 'معدل أقل', 'تحت الحد', 'gpa low',
        ]
        if any(kw in q_key for kw in _gpa_rescue_kw):
            return {"intent_key": "rag_needed", "entity": "gpa_rescue", "response_depth": response_depth}

        # ===== SMART: كشف أسئلة What-if / تغيير التخصص =====
        _whatif_kw = [
            'ماذا لو', 'لو غيرت', 'what if', 'تغيير تخصص', 'تحويل تخصص',
            'لو بدلت', 'لو انتقلت', 'من cs ل', 'من cis ل', 'من cys ل',
            'أغير تخصصي', 'مواد مشتركة', 'تحويل من',
        ]
        if any(kw in q_key for kw in _whatif_kw):
            return {"intent_key": "rag_needed", "entity": "whatif_analysis", "response_depth": response_depth}

        # ===== SMART: كشف أسئلة مشاريع التخرج =====
        _grad_proj_kw = [
            'مشروع تخرج', 'مشاريع التخرج', 'فكرة مشروع', 'graduation project',
            'أفكار مشاريع', 'اقتراح مشروع', 'مشاريع cs', 'مشاريع cys',
            'مشاريع da', 'مشاريع bit', 'project ideas',
        ]
        if any(kw in q_key for kw in _grad_proj_kw):
            return {"intent_key": "rag_needed", "entity": "grad_projects", "response_depth": response_depth}

        # ===== SMART: كشف أسئلة الفرق بين التخصصات → RAG =====
        _spec_compare_kw = [
            'الفرق بين cs', 'الفرق بين cis', 'الفرق بين bit', 'الفرق بين cys',
            'فرق cs cis', 'مقارنة تخصصات', 'أي تخصص أختار', 'شو الفرق بين',
            'difference between cs', 'compare cs cis', 'cs vs cis', 'cs vs cys',
        ]
        if any(kw in q_key for kw in _spec_compare_kw):
            return {"intent_key": "rag_needed", "entity": "compare_majors", "response_depth": response_depth}
        _clubs_kw = ['نادي', 'أندية', 'اندية', 'نوادي', 'club', 'clubs', 'أنشطة طلابية', 'نشاطات طلابية', 'نشاط طلابي']
        if any(kw in q_key for kw in _clubs_kw):
            return {"intent_key": "student_clubs", "entity": None, "response_depth": response_depth}
        _grad_kw = ['دراسات عليا', 'ماجستير', 'دكتوراه', 'graduate', 'postgraduate', "master's", 'masters', 'phd', 'doctorate']
        _grad_question_kw = ['هل', 'يوجد', 'يتوفر', 'تقدم', 'does', 'offer', 'have', 'available', 'is there']
        if any(kw in q_key for kw in _grad_kw) and any(kw in q_key for kw in _grad_question_kw):
            return {"intent_key": "graduate_programs", "entity": None, "response_depth": response_depth}
        _lang_kw = ['لغة التدريس', 'لغة الدراسة', 'لغة المواد', 'language of instruction', 'teaching language', 'what language',
                    'اللغة المعتمدة', 'شو اللغة', 'بأي لغة']
        if any(kw in q_key for kw in _lang_kw):
            return {"intent_key": "instruction_language", "entity": None, "response_depth": response_depth}
        _calendar_kw = [
            'تقويم أكاديمي', 'تقويم اكاديمي', 'التقويم الاكاديمي', 'التقويم الأكاديمي',
            'مواعيد الامتحانات', 'مواعيد الاختبارات', 'جدول الامتحانات',
            'academic calendar', 'exam schedule', 'exam dates',
            'موعد الامتحان', 'متى الامتحانات', 'مواعيد التسجيل',
        ]
        if any(kw in q_key for kw in _calendar_kw):
            return {"intent_key": "academic_calendar", "entity": None, "response_depth": response_depth}
        _lib_kw = [
            'خدمات المكتبة', 'library services', 'what does the library',
            'ماذا تقدم المكتبة', 'خدمات مكتبة',
            'مكتبة الجامعة', 'مكتبة الجامعه',
            'تقدمها مكتبة', 'المكتبة تقدم',
            'خدمات تقدمها المكتبة',
            'the library offer', 'library provides',
            'مكتبه الجامعه', 'خدمات مكتبه',
            'الخدمات التي تقدمها مكتبة',
            'الخدمات التي تقدمها المكتبة',
            'دور مكتبة', 'دور المكتبة',
        ]
        if any(kw in q_key for kw in _lib_kw):
            return {"intent_key": "library_services", "entity": None, "response_depth": response_depth}
        # ===== FIX 4: كشف أسئلة البوابات =====
        _gates_kw = ['بوابة', 'بوابات', 'gate', 'gates', 'مدخل', 'مداخل', 'بوابه']
        if any(kw in q_key for kw in _gates_kw):
            return {"intent_key": "university_gates", "entity": None, "response_depth": response_depth}
        # Do not route the bare word "ساعة" to credit hours.  It can mean
        # office hours, opening time or clock time.  The specific graduation
        # and credit-hour phrases above are the safe rule-based route.
        # ===== FIX: رئيس الجامعة — rule-based بدون LLM =====
        _president_kw = ['رئيس الجامعه', 'رئيس الجامعة', 'رئيس اليرموك',
                         'مين رئيس', 'من رئيس', 'university president',
                         'who is president', 'الشرايري', 'من هو رئيس']
        if any(kw in q_key for kw in _president_kw):
            return {"intent_key": "university_president", "entity": "", "response_depth": response_depth}

        # ===== FIX: التأمين الصحي — rule-based =====
        _health_kw = ['التامين الصحي', 'التأمين الصحي', 'تامين صحي', 'تأمين صحي',
                      'health insurance', 'التامين', 'التأمين', 'تامين طلاب', 'تأمين طلاب']
        if any(kw in q_key for kw in _health_kw):
            return {"intent_key": "health_insurance", "entity": "", "response_depth": response_depth}

        # ===== FIX: تخصصات كلية IT — rule-based =====
        _it_prog_kw = ['تخصصات الايتي', 'تخصصات كليه الايتي', 'تخصصات كلية الايتي',
                       'تخصصات كلية it', 'تخصصات كلية تكنولوجيا',
                       'it programs', 'it majors', 'تخصصات it']
        if any(kw in q_key for kw in _it_prog_kw):
            return {"intent_key": "list_programs", "entity": "it", "response_depth": response_depth}
        if any(kw in question.lower() for kw in ['كم بكلف', 'كم تكلف', 'سعر', 'تكلفة']):
            if any(kw in question.lower() for kw in COST_SPECIFIC_KEYWORDS['housing']):
                return {"intent_key": "cost_inquiry", "entity": "housing", "response_depth": response_depth}
            if any(kw in question.lower() for kw in COST_SPECIFIC_KEYWORDS['transport']):
                return {"intent_key": "cost_inquiry", "entity": "transport", "response_depth": response_depth}
        if q_key in self._cache:
            cached = self._cache[q_key].copy()
            cached["response_depth"] = response_depth
            return cached
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.INTENT_SCHEMA},
                    {"role": "user", "content": f"Q: {question}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=100
            )
            result = json.loads(response.choices[0].message.content)
            if "intent_key" not in result:
                result["intent_key"] = "rag_needed"
            result["response_depth"] = response_depth
            logger.info(f"Intent: {result['intent_key']} | entity: {result.get('entity')} | depth: {response_depth}")
            self._cache[q_key] = result
            return result
        except Exception as e:
            logger.error(f"SemanticIntentParser error: {e}")
            return {"intent_key": "rag_needed", "entity": None, "response_depth": response_depth}
# ==================== SMART FACTS ROUTER ====================
class SmartFactsRouter:
    IT_FACULTY_KEYWORDS = [
        "معلومات", "حاسوب", "it", "computer", "ايتي", "الايتي",
        "information technology", "تكنولوجيا المعلومات"
    ]
    OTHER_UNIVERSITIES = [
        'harvard', 'stanford', 'mit', 'oxford', 'cambridge', 'tokyo', 'cornell', 'yale',
        'university of jordan', 'hashemite', 'mutah', 'just university', 'petra university',
        'هارفارد', 'ستانفورد', 'أكسفورد', 'طوكيو', 'كامبريدج',
        'الجامعة الأردنية', 'الهاشمية', 'مؤتة', 'جامعة البترا',
    ]
    def route(self, question: str, parsed_intent: Dict, lang: str, context_memory: List[Dict] = None) -> Optional[str]:
        # --- FIX: Define local variables for the router ---
        intent = parsed_intent.get("intent_key")
        q_low = question.lower().strip()

        if intent == "intl_onboarding":
            data = INTERNATIONAL_DATA[lang]
            if any(kw in q_low for kw in ['بنك', 'bank', 'حساب']): return data['banking']
            if any(kw in q_low for kw in ['إقامة', 'residenc']): return data['residency']
            if any(kw in q_low for kw in ['مطار', 'airport', 'مواصلات']): return data['transportation']
            if any(kw in q_low for kw in ['زميل', 'صديق', 'buddy']): return data['buddy']
            return data.get("essentials", "كيف يمكنني مساعدتك في دليل إربد؟")

        if intent == "language_bridge":
            # البحث من العربي للإنجليزي
            for ar, en in LANGUAGE_BRIDGE['ar_to_en'].items():
                if ar in q_low: return f"المصطلح الإنجليزي لـ '**{ar}**' هو: **{en}** (ضمن السياق الأكاديمي)."
            # البحث من الإنجليزي للعربي
            for en, ar in LANGUAGE_BRIDGE['en_to_ar'].items():
                if en in q_low: return f"The term '**{en}**' in Arabic is: **{ar}**."
            return "يمكنني ترجمة المصطلحات الأكاديمية (مثل: خطة دراسية، عميد، معدل). ماذا تريد أن تترجم؟"
        intent_key = parsed_intent.get("intent_key", "rag_needed")
        entity = (parsed_intent.get("entity") or "").lower()
        depth = parsed_intent.get("response_depth", "moderate")
        q_lower = question.lower()
        if any(u in q_lower for u in self.OTHER_UNIVERSITIES):
            return None
        if intent_key == "faculty_member_search":
            return None
        # ===== FIX 1: سنة التأسيس — يجب أن تكون قبل أي return None =====
        if any(kw in q_lower for kw in ['تأسست', 'تأسيس', 'متى تأسست', 'متى تم إنشاء',
                                          'متى تم تأسيس', 'founded', 'established', 'تأسست الجامعة',
                                          'سنة التأسيس', 'عام التأسيس']):
            if any(kw in q_lower for kw in ['الجامعة', 'yarmouk', 'اليرموك']):
                year = VERIFIED_FACTS[lang]["founded_year"]
                if depth == "brief":
                    return year
                if lang == "ar":
                    return f"تأسست جامعة اليرموك عام {year}."
                return f"Yarmouk University was founded in {year}."
        # ===== FIX 2: برامج كلية الآداب → RAG-FIRST =====
        if any(kw in q_lower for kw in ['برامج', 'تخصصات', 'برنامج', 'programs', 'majors']) and \
           any(kw in q_lower for kw in ['اداب', 'آداب', 'arts', 'الآداب', 'الاداب']):
            return None  # Let RAG handle faculty programs
        # ===== FIX 3: خدمات المكتبة → RAG-FIRST (was hardcoded) =====
        if intent_key == "library_services":
            return None  # Let RAG handle it — demonstrates RAG capability for competition
        # ===== FIX 4: بوابات الجامعة =====
        if intent_key == "university_gates":
            gates = VERIFIED_FACTS[lang].get("gates", {})
            if any(kw in q_lower for kw in ['كم', 'عدد', 'how many', 'number']):
                return gates.get("count", "3")
            return gates.get("details", "")
        if intent_key == "faculty_dean":
            deans = VERIFIED_FACTS[lang]["deans"]
            for dean_info in deans.values():
                if any(match_kw in q_lower for match_kw in dean_info.get("match", [])):
                    if depth == "brief":
                        return dean_info["name"]
                    elif depth == "detailed":
                        return f"{dean_info['name']}\n{dean_info['title']}"
                    else:
                        return f"{dean_info['name']} - {dean_info['title']}"
            return None
        if intent_key == "department_head":
            heads = VERIFIED_FACTS[lang]["it_admin"]["department_heads"]
            res = None
            if any(kw in q_lower for kw in ['حاسوب', 'cs']):
                res = heads['cs']
            elif any(kw in q_lower for kw in ['نظم', 'cis']):
                res = heads['cis']
            elif any(kw in q_lower for kw in ['تكنولوجيا', 'it']):
                res = heads['it']
            if res:
                if depth == "brief":
                    return res['name']
                return f"{res['name']} - رئيس {res['dept']}"
            return None
        if intent_key == "faculty_vice_dean":
            if any(kw in q_lower for kw in self.IT_FACULTY_KEYWORDS):
                it_admin = VERIFIED_FACTS[lang]["it_admin"]
                if 'مساعد' in q_lower or 'assistant' in q_lower:
                    if depth == "brief":
                        return it_admin["assistant_dean"]["name"]
                    return f"{it_admin['assistant_dean']['name']}\n{it_admin['assistant_dean']['title']}"
                else:
                    if depth == "brief":
                        return "، ".join([vd["name"] for vd in it_admin["vice_deans"]])
                    return "\n".join([f"{vd['name']} - {vd['title']}" for vd in it_admin["vice_deans"]])
            return None
        if intent_key == "list_faculties":
            return "\n".join(VERIFIED_FACTS[lang]["faculties_list"])
        if intent_key == "count_faculties":
            return VERIFIED_FACTS[lang]["num_faculties"]

        # ✅ NEW: سؤال عن أي قسم ينتمي له تخصص معين
        _dept_q_kws = ['أي قسم', 'تحت أي قسم', 'قسم ما', 'which department', 'قسم cs', 'قسم cis', 'قسم da', 'قسم cys', 'قسم bit', 'قسم vr']
        if any(kw in q_lower for kw in _dept_q_kws):
            dept_map = VERIFIED_FACTS[lang].get("it_dept_structure", {})
            for code in ['CS','VR','CIS','DA','BIT','CYS']:
                if code.lower() in q_lower and code in dept_map:
                    return dept_map[code]
            return None

        # ✅ FIX A: الساعات المعتمدة لتخصصات كلية IT
        if intent_key == "credit_hours":
            credit_info = VERIFIED_FACTS[lang].get("it_credit_hours", {})
            if credit_info:
                # تحقق إذا السؤال عن تخصص محدد
                specific_program = None
                for prog in credit_info:
                    if prog in q_lower and prog != "default" and prog != "note":
                        specific_program = prog
                        break
                if specific_program:
                    if lang == "ar":
                        return f"تخصص {specific_program} يتطلب {credit_info[specific_program]} ساعة معتمدة للتخرج."
                    return f"{specific_program} requires {credit_info[specific_program]} credit hours to graduate."
                # سؤال عام عن كلية IT
                if any(kw in q_lower for kw in ['ايتي', 'الايتي', 'it', 'تكنولوجيا المعلومات', 'تخصصات الكلية', 'كلية الحاسوب']):
                    note = credit_info.get("note", "")
                    if lang == "ar":
                        programs_list = "\n".join([f"• {p}: {credit_info[p]} ساعة" 
                                                    for p in credit_info 
                                                    if p not in ("default","note")])
                        return f"عدد الساعات المعتمدة لتخصصات كلية تكنولوجيا المعلومات:\n{programs_list}"
                    return f"All IT Faculty programs require {credit_info['default']} credit hours to graduate."
            return None

        # ✅ FIX B: تخصصات كلية الحجاوي
        hijjawi_kws = ['حجاوي', 'هندسة', 'hijjawi', 'engineering']
        if any(kw in q_lower for kw in hijjawi_kws):
            hijjawi_programs = VERIFIED_FACTS[lang].get("hijjawi_programs", [])
            if hijjawi_programs:
                list_kws = ['كم', 'تخصص', 'تخصصات', 'برامج', 'برنامج', 'programs', 'majors', 'how many', 'اسماء', 'أسماء', 'شو']
                if any(kw in q_lower for kw in list_kws):
                    if lang == "ar":
                        programs_str = "\n".join([f"• {p}" for p in hijjawi_programs])
                        return f"كلية الحجاوي للهندسة التكنولوجية تضم {len(hijjawi_programs)} تخصصات:\n{programs_str}"
                    else:
                        programs_str = "\n".join([f"• {p}" for p in hijjawi_programs])
                        return f"Hijjawi Faculty has {len(hijjawi_programs)} programs:\n{programs_str}"

        if intent_key == "elearning_system":
            url = VERIFIED_FACTS[lang]["elearning_url"]
            if lang == "ar":
                return f"يمكنك الوصول لنظام التعلم الإلكتروني عبر الرابط: {url}"
            return f"You can access the E-learning system via: {url}"
        if intent_key == "university_type":
            return VERIFIED_FACTS[lang]["university_type_full"]
        if intent_key == "university_president":
            dynamic_keywords = ['متى', 'تعيين', 'تاريخ', 'كم سنة', 'كم خدم', 'منذ متى']
            if any(kw in q_lower for kw in dynamic_keywords):
                return None
            if depth == "brief":
                return VERIFIED_FACTS[lang]["president"]
            return f"{VERIFIED_FACTS[lang]['president']}\n{VERIFIED_FACTS[lang]['president_title']}"
        
        # ===== FIX: Intents حُذفت من النسخة الجديدة — أُعيدت هنا =====
        # ===== FIX: شركات التدريب والتوظيف → من VERIFIED_FACTS مباشرة =====
        _companies_kw = ['شركة تقنية','شركات تقنية','متدرب','internship','orange jordan','zain jordan',
                         'scopex','makeen','estarta','mawdoo3','umniah','job fair','تدريب صيفي',
                         'شركات الأردن','فرص تدريب','برنامج التدريب','شركات تستقبل','شركات بتشتغل']
        if any(kw in q_lower for kw in _companies_kw):
            return VERIFIED_FACTS[lang].get("companies_and_training")

        # ===== FIX: مسارات التوظيف → من VERIFIED_FACTS مباشرة =====
        _career_kw = ['مسار مهني','مسارات مهنية','خريجي كلية','وظائف خريجي','career path',
                      'بعد التخرج أشتغل','شو بشتغل بعد','ماذا أعمل بعد التخرج','career opportunities']
        if any(kw in q_lower for kw in _career_kw):
            return VERIFIED_FACTS[lang].get("career_paths")

        # ===== FIX: طلب توضيح عند نقص المعلومات =====
        # ===== FIX: إنجازات الكلية والهاكاثون → VERIFIED_FACTS =====
        _hackathon_kw = ['هاكاثون','هاكثون','hackathon','مسابقة برمجة','مسابقات الكلية',
                         'ناسا','nasa','nova brainlytics','datadrip','tech arabi','ctf',
                         'إنجازات الكلية','انجازات الكلية','حققت الكلية','فازت الكلية']
        if any(kw in q_lower for kw in _hackathon_kw):
            return VERIFIED_FACTS[lang].get("hackathon_achievements")

        # ===== FIX: مشاريع التخرج → VERIFIED_FACTS =====
        _gradproj_kw = ['مشروع تخرج','مشاريع التخرج','يوم التخرج','يوم المشاريع',
                        'graduation project','عرض المشاريع','أمثلة مشاريع','أفكار مشاريع']
        if any(kw in q_lower for kw in _gradproj_kw):
            return VERIFIED_FACTS[lang].get("graduation_projects_info")

        # ===== FIX: شروط القبول → من VERIFIED_FACTS مباشرة =====
        _admission_direct_kw = ['شروط القبول','requirements to join','admission requirements',
                                'admission requirement','كيف أتقدم للجامعة','how to apply',
                                'requirements for cs','requirements for cis','requirements for cys']
        if any(kw in q_lower for kw in _admission_direct_kw):
            return VERIFIED_FACTS[lang].get("admission_requirements")

        # ===== بوابات الجامعة =====
        _gates_direct_kw = ['بوابة','بوابات','gate','gates','مدخل','مداخل',
                            'البوابة الرئيسية','البوابة الشرقية','كم بوابة']
        if any(kw in q_lower for kw in _gates_direct_kw):
            gates = VERIFIED_FACTS[lang].get("gates",{})
            return gates.get("details","")

        # ===== ساعات التخرج / credit hours =====
        _credit_kw = ['كم ساعة تخرج','ساعة تخرج','ساعات التخرج','ساعات اللازمة للتخرج',
                      'how many credit hours','credit hours for','total hours','مجموع ساعات']
        if any(kw in q_lower for kw in _credit_kw):
            credit = VERIFIED_FACTS[lang].get("it_credit_hours",{})
            note = credit.get("note","") or credit.get("note_en","")
            return f"🎓 {note}" if note else "134 ساعة لجميع تخصصات كلية IT"

        # ===== نظام المعدل / GPA scale =====
        _gpa_scale_kw = ['من 100','من مئة','معدل من 100','نظام المعدل','gpa scale',
                         'كيف يحسب المعدل','يحسب الـ gpa','100 نقطة','مش من 4',
                         'المعدل بالمئة','كيف المعدل','نظام الدرجات']
        if any(kw in q_lower for kw in _gpa_scale_kw):
            gpa_info = VERIFIED_FACTS[lang].get("gpa_scale",{})
            return gpa_info.get("details","")

        # ===== مرشدون نفسيون =====
        _counselor_kw = ['مرشد نفسي','إرشاد نفسي','مستشار نفسي','طبيب نفسي',
                         'counseling','ايميل المرشد','مرشدين نفسيين',
                         'psychological counselor','mental health email',
                         'أخصائي نفسي','أخصائيون نفسيون','صحة نفسية جامعة',
                         'اتواصل مع أخصائي','اتواصل مع مرشد']
        if any(kw in q_lower for kw in _counselor_kw):
            counselors = VERIFIED_FACTS[lang].get("psychological_counselors",{})
            return counselors.get("details","")

        # ===== برامج الحجاوي — تفصيل =====
        _hijjawi_detail_kw = ['أقسام الحجاوي','تخصصات الحجاوي','برامج الحجاوي',
                              'hijjawi programs','hijjawi departments',
                              'كم قسم بالحجاوي','الحجاوي أونلاين','أونلاين الحجاوي']
        if any(kw in q_lower for kw in _hijjawi_detail_kw):
            note = VERIFIED_FACTS[lang].get("hijjawi_note","")
            progs = VERIFIED_FACTS[lang].get("hijjawi_programs",[])
            progs_str = "\n".join(f"• {p}" for p in progs)
            if lang == "ar":
                return f"كلية الحجاوي للهندسة التكنولوجية — 9 أقسام:\n{progs_str}\n\n💡 {note}"
            else:
                return f"Hijjawi Faculty of Engineering Technology — 9 departments:\n{progs_str}"

        if intent_key == "ask_clarification":
            entity = parsed_intent.get("entity","")
            if entity == "missing_major":
                if lang == "ar":
                    return ("🤔 أيّ تخصص تقصد؟ عندي مساقات لكل التخصصات:\n"
                            "• علوم الحاسوب (CS)\n"
                            "• نظم المعلومات الحاسوبية (CIS)\n"
                            "• الأمن السيبراني (CYS)\n"
                            "• علم البيانات والذكاء الاصطناعي (DA)\n"
                            "• تكنولوجيا معلومات الأعمال (BIT)\n"
                            "• الواقع الرقمي وتطوير الألعاب (DRG)\n\n"
                            "قل لي تخصصك وأعطيك المساقات مباشرة 👇")
                else:
                    return ("🤔 Which major do you mean? I have course lists for all programs:\n"
                            "CS | CIS | CYS | DA | BIT | DRG\n\n"
                            "Tell me your major and I'll give you the full course list 👇")
            return None

        if intent_key == "student_housing":
            housing = VERIFIED_FACTS[lang]["student_housing"]
            return housing["details"]

        if intent_key == "health_insurance":
            return VERIFIED_FACTS[lang]["health_insurance"]["details"]

        if intent_key == "online_learning_policy":
            return VERIFIED_FACTS[lang].get(
                "online_policy",
                "التعليم في جامعة اليرموك وجاهي بالكامل، ولا تتوفر برامج دراسية عن بُعد."
                if lang == "ar" else
                "Education at Yarmouk University is entirely in-person."
            )
        _online_direct = ['عن بُعد', 'عن بعد', 'أونلاين', 'اونلاين', 'دراسة أونلاين',
                          'online programs', 'online degree', 'distance learning', 'remotely']
        if any(kw in q_lower for kw in _online_direct):
            return VERIFIED_FACTS[lang].get(
                "online_policy",
                "التعليم في جامعة اليرموك وجاهي بالكامل، ولا تتوفر برامج دراسية عن بُعد."
                if lang == "ar" else
                "Education at Yarmouk University is entirely in-person."
            )

        if intent_key == "list_programs":
            it_kw = ['معلومات', 'حاسوب', 'it', 'ايتي', 'الايتي', 'تكنولوجيا']
            if any(kw in q_lower for kw in it_kw):
                return "\n".join(VERIFIED_FACTS[lang]["it_programs"])
            return None

        if intent_key == "university_info":
            if any(kw in q_lower for kw in ['تأسست', 'تأسيس', 'founded', 'established', 'متى']):
                year = VERIFIED_FACTS[lang]["founded_year"]
                return (f"تأسست جامعة اليرموك عام {year}." if lang == "ar"
                        else f"Yarmouk University was founded in {year}.")
            return VERIFIED_FACTS[lang].get("university_info_answer")

        # All descriptive, informational questions must go to RAG.
        return None
def expand_colloquial_terms(question: str) -> str:
    result = question
    for colloquial, formal in COLLOQUIAL_FACULTY_TERMS.items():
        if colloquial in result.lower():
            result = re.sub(re.escape(colloquial), formal, result, flags=re.IGNORECASE)
    return result
semantic_parser = SemanticIntentParser(llm_client)
facts_router = SmartFactsRouter()
