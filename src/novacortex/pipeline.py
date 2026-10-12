"""Answer pipeline: routing, RAG, web search and LLM fallback."""

import asyncio
import json
import logging
import re
import time

from typing import List, Optional, Dict

from novacortex.cache import compute_dynamic_threshold
from novacortex.db import update_daily_stats
from novacortex.formatting import NO_RESULT_MESSAGE_AR, NO_RESULT_MESSAGE_EN, formatter
from novacortex.intents import expand_colloquial_terms, facts_router, semantic_parser
from novacortex.input_rules import needs_false_premise_check
from novacortex.knowledge.careers import CV_TEMPLATES, SKILL_GAP_DATA
from novacortex.knowledge.facts import VERIFIED_FACTS
from novacortex.knowledge.faculty import COUNSELING_CONTACTS, FACULTY_DB, FMD_BASE_URL, FMD_SEARCH_URL, GRADUATION_HOURS, HARD_COURSES_BY_MAJOR
from novacortex.knowledge.keywords import ACADEMIC_SOS_KEYWORDS, CRISIS_KEYWORDS, CV_BUILDER_KEYWORDS, FEES_KEYWORDS, GRADUATION_SIMULATOR_KEYWORDS, LINKEDIN_GUIDE_KEYWORDS, SCHOLARSHIP_KEYWORDS, SKILL_GAP_KEYWORDS
from novacortex.llm import llm_client
from novacortex.memory import memory_system
from novacortex.quality import retrieval_confidence, web_confidence
from novacortex.rag.generation import apply_proxy_prompt, llm_generator
from novacortex.rag.reranking import reranker
from novacortex.rag.web_search import web_searcher
from novacortex.safety import check_false_premise, check_false_premise_llm, detect_injection, detect_response_depth, handle_greeting, is_comparison_question, is_general_oos, scope_detector
from novacortex.text import arabic_processor

logger = logging.getLogger(__name__)

# ==================== HYBRID PIPELINE ====================
class EnhancedHybridPipeline:
    def __init__(self, retriever, cache, scope_detector):
        self.retriever = retriever
        self.cache = cache
        self.scope_detector = scope_detector
        self.memory = memory_system
        self.semantic_parser = semantic_parser
        self.facts_router = facts_router
    # ==================== FEATURE 1: GRADUATION SIMULATOR ====================
    def _extract_major(self, text: str) -> Optional[str]:
        """يستخرج تخصص الطالب من النص."""
        t = text.upper()
        major_map = {
            'CS': ['CS', 'علوم الحاسوب', 'COMPUTER SCIENCE'],
            'CIS': ['CIS', 'نظم المعلومات', 'INFORMATION SYSTEMS'],
            'CYS': ['CYS', 'الأمن السيبراني', 'CYBERSECURITY', 'CYBER'],
            'BIT': ['BIT', 'تكنولوجيا معلومات الأعمال', 'BUSINESS IT'],
            'DA': ['DA', 'علم البيانات', 'DATA SCIENCE', 'ARTIFICIAL INTELLIGENCE', 'ذكاء اصطناعي'],
            'VR': ['VR', 'DRG', 'الواقع الرقمي', 'تطوير الألعاب', 'GAME DEV'],
        }
        for major, aliases in major_map.items():
            for alias in aliases:
                if alias.upper() in t or alias in text:
                    return major
        return None

    def _extract_hours(self, text: str) -> Optional[int]:
        """يستخرج عدد الساعات المكتملة من النص."""
        patterns = [
            r'أنهيت\s+(\d+)', r'أكملت\s+(\d+)', r'خلصت\s+(\d+)', r'عندي\s+(\d+)',
            r'اكملت\s+(\d+)', r'قطعت\s+(\d+)', r'سجلت\s+(\d+)',
            r'(\d+)\s+ساعة', r'(\d+)\s+ساعات', r'(\d+)\s+credits', r'(\d+)\s+hours',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                val = int(m.group(1))
                if 0 < val < 200:
                    return val
        return None

    # ==================== FEATURE 0-A: CRISIS SUPPORT ====================
    async def _handle_crisis_support(self, question: str, user_id: int, detected_lang: str) -> Optional[Dict]:
        """دعم نفسي فوري — يسمع ويهدّئ ويُحيل لمتخصص. لا يقيّم الخطر بنفسه."""
        lang = detected_lang if detected_lang == "en" else "ar"
        contacts = COUNSELING_CONTACTS[lang]

        if lang == "ar":
            response = (
                "أنا سامعك، وأنا هون معك. 💙\n\n"
                "اللي تحس فيه الحين صعب، وما لازم تمر فيه لحالك.\n\n"
                "**خطوة وحدة بس الحين — تواصل مع شخص متخصص:**\n\n"
                f"🟢 **{contacts['primary']['name']}** — {contacts['primary']['title']}\n"
                f"📧 {contacts['primary']['email']}\n"
                f"📞 {contacts['primary']['phone']}\n"
                f"🕐 {contacts['primary'].get('hours','')}\n\n"
                f"🆘 **خط الدعم النفسي الأردني:** {contacts['crisis_line']['number']} "
                f"({contacts['crisis_line']['note']})\n\n"
                f"📧 **مركز الإرشاد النفسي:** {contacts['mental_health_center']['email']} | "
                f"{contacts['mental_health_center']['phone']}\n\n"
                "---\n"
                "أنا هنا لو بدك تحكي، لكن هالأشخاص يقدروا يساعدوك بشكل أعمق. "
                "الطلب للمساعدة هو أشجع شيء ممكن تعمله. 🤍"
            )
        else:
            response = (
                "I hear you, and I'm here. 💙\n\n"
                "What you're feeling is real, and you don't have to go through it alone.\n\n"
                "**One step right now — reach out to someone who can really help:**\n\n"
                f"🟢 **{contacts['primary']['name']}** — {contacts['primary']['title']}\n"
                f"📧 {contacts['primary']['email']}\n"
                f"📞 {contacts['primary']['phone']}\n\n"
                f"🆘 **Crisis Line:** {contacts['crisis_line']['number']} ({contacts['crisis_line']['note']})\n\n"
                "---\n"
                "I'm here if you want to talk, but these people can help you much more deeply. "
                "Asking for help is the bravest thing you can do. 🤍"
            )
        return {"response": response, "source": "mental_health_support", "confidence": 100, "docs_retrieved": 0}

    # ==================== FEATURE 0-B: FACULTY LOOKUP ====================
    def _handle_faculty_lookup(self, question: str, detected_lang: str) -> Optional[Dict]:
        """يبحث في FACULTY_DB عن عضو هيئة تدريس بالاسم أو التخصص أو الدور."""
        q = question.lower()
        matched = None

        # Search by keys
        for member_key, info in FACULTY_DB.items():
            if any(k.lower() in q for k in info.get("keys", [])):
                matched = info
                break

        # If not found → return general search link
        if not matched:
            if detected_lang == "en":
                resp = (
                    "I can search the faculty database for you!\n\n"
                    f"🔍 Search by name at: {FMD_SEARCH_URL}\n\n"
                    "Or tell me the professor's name and I'll check if I have their info."
                )
            else:
                resp = (
                    "ما عندي معلومات عن هاد الأستاذ تحديداً.\n\n"
                    f"🔍 ابحث عنه مباشرة في: {FMD_SEARCH_URL}\n\n"
                    "أو قولي اسمه وأشوف إذا عندي بياناته."
                )
            return {"response": resp, "source": "faculty_lookup", "confidence": 70, "docs_retrieved": 0}

        # Format matched faculty card
        m = matched
        if detected_lang == "en":
            resp = (
                f"👤 **{m.get('name_en', m.get('name_ar',''))}**\n"
                f"🏛️ {m.get('dept','')}{' | ' + m.get('role','') if m.get('role') else ''}\n"
                f"🎓 {m.get('rank','')} — {m.get('specialty','')}\n"
                f"📧 {m.get('email','')}\n"
                + (f"📍 {m.get('office','')}\n" if m.get('office') else "")
                + (f"📞 {m.get('phone','')}\n" if m.get('phone') else "")
                + f"\n🔗 Full profile: {m.get('fmd_url', FMD_BASE_URL)}"
            )
        else:
            resp = (
                f"👤 **{m.get('name_ar', m.get('name_en',''))}**\n"
                f"🏛️ {m.get('dept','')}{' | ' + m.get('role','') if m.get('role') else ''}\n"
                f"🎓 {m.get('rank','')} — {m.get('specialty','')}\n"
                f"📧 {m.get('email','')}\n"
                + (f"📍 {m.get('office','')}\n" if m.get('office') else "")
                + (f"📞 {m.get('phone','')}\n" if m.get('phone') else "")
                + f"\n🔗 الملف الكامل: {m.get('fmd_url', FMD_BASE_URL)}"
            )
        return {"response": resp, "source": "faculty_lookup", "confidence": 95, "docs_retrieved": 0}

    # ==================== FEATURE 0-C: CV BUILDER ====================
    async def _handle_cv_builder(self, question: str, user_id: int, detected_lang: str) -> Optional[Dict]:
        """يبني CV مخصص لتخصص الطالب مع مهارات وشهادات ونصائح."""
        lang   = detected_lang if detected_lang == "en" else "ar"
        major  = self._extract_major(question)
        tmpl   = CV_TEMPLATES.get(major) if major else None

        # If no major detected → ask
        if not tmpl:
            if lang == "ar":
                resp = (
                    "📄 **CV Builder — NovaCortex**\n\n"
                    "عشان أبني سيرة ذاتية مخصصة إلك، أخبرني:\n"
                    "• تخصصك: CS / CIS / CYS / DA / BIT / DRG\n"
                    "• سنتك الدراسية\n"
                    "• أي مشاريع أو مهارات عندك بالفعل؟\n\n"
                    "مثال: \"أنا طالب CYS سنة ثالثة، عندي تجربة CTF\""
                )
            else:
                resp = (
                    "📄 **CV Builder — NovaCortex**\n\n"
                    "To build you a tailored CV, tell me:\n"
                    "• Your major: CS / CIS / CYS / DA / BIT / DRG\n"
                    "• Your year of study\n"
                    "• Any existing projects or skills?\n\n"
                    "Example: \"I'm a 3rd year CYS student, I've done CTF competitions\""
                )
            return {"response": resp, "source": "cv_builder", "confidence": 90, "docs_retrieved": 0}

        # Build CV
        skills_str = "\n".join(f"  • {s}" for s in tmpl["key_skills"])
        certs_str  = "\n".join(f"  • {c}" for c in tmpl["certifications"])
        proj_str   = "\n".join(f"  • {p}" for p in tmpl["project_ideas"])

        if lang == "ar":
            context_block = f"""أنت NovaCortex — مرشد مهني لطلاب IT في جامعة اليرموك.
مهمتك: بناء نموذج CV احترافي مخصص لتخصص {major} بالعربي.

البيانات المتوفرة:
- التخصص: {major}
- المهارات الأساسية المطلوبة بسوق العمل الأردني 2026:
{skills_str}
- الشهادات الموصى بها:
{certs_str}
- أفكار مشاريع لتقويتها:
{proj_str}
- LinkedIn Headline المقترح: {tmpl['linkedin_headline']}
- نصيحة GitHub: {tmpl['github_tip']}

بنية الـ CV الموصى بها لطالب IT:
1. اسم + رابط LinkedIn + رابط GitHub + إيميل
2. Summary: جملتان تصفان تخصصك وطموحك
3. Education: جامعة اليرموك | {major} | [سنة التخرج المتوقعة]
4. Technical Skills: (المهارات مصنّفة: Languages / Tools / Concepts)
5. Projects: اذكر 2-3 مشاريع مع الوصف والتقنيات المستخدمة
6. Certifications: إن وجدت
7. Activities: نادي DEVIT، هاكاثون، CTF

السؤال: {question}

اكتب template CV جاهز للتعديل، موجز واحترافي. استخدم بنية واضحة."""
        else:
            context_block = f"""You are NovaCortex — career advisor for IT students at Yarmouk University.
Task: Build a professional CV template for {major} major, tailored for the 2026 Jordanian/MENA job market.

Key skills for this major:
{skills_str}
Recommended certifications:
{certs_str}
Project ideas to strengthen the CV:
{proj_str}
LinkedIn Headline: {tmpl['linkedin_headline']}
GitHub tip: {tmpl['github_tip']}

CV structure for IT students:
1. Name + LinkedIn + GitHub + Email
2. Summary: 2 lines about your specialty and ambition
3. Education: Yarmouk University | {major} | [Expected graduation year]
4. Technical Skills (categorized: Languages / Tools / Concepts)
5. Projects: 2-3 projects with description and tech stack
6. Certifications
7. Activities: clubs, hackathons, competitions

Question: {question}"""

        try:
            resp = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": context_block}],
                temperature=0.3,
                max_tokens=900,
            )
            answer = resp.choices[0].message.content.strip()
            header = f"📄 **CV Builder — {major} | NovaCortex**\n\n"
            footer = (
                f"\n\n---\n💡 **نصيحة GitHub:** {tmpl['github_tip']}\n"
                f"🔗 **LinkedIn Headline:** `{tmpl['linkedin_headline']}`"
                if lang == "ar" else
                f"\n\n---\n💡 **GitHub tip:** {tmpl['github_tip']}\n"
                f"🔗 **LinkedIn Headline:** `{tmpl['linkedin_headline']}`"
            )
            return {"response": header + answer + footer,
                    "source": "cv_builder", "confidence": 88, "docs_retrieved": 0}
        except Exception as e:
            logger.error(f"[CVBuilder] LLM error: {e}")
            return None

    # ==================== FEATURE 0-D: LINKEDIN / GITHUB GUIDE ====================
    def _handle_linkedin_github_guide(self, question: str, detected_lang: str) -> Optional[Dict]:
        """دليل عملي لبناء LinkedIn و GitHub لطالب IT."""
        lang  = detected_lang if detected_lang == "en" else "ar"
        major = self._extract_major(question)
        tmpl  = CV_TEMPLATES.get(major) if major else None
        q     = question.lower()

        is_github   = any(k in q for k in ['github','جيتهب','repository','repo','مشاريع'])
        is_linkedin = any(k in q for k in ['linkedin','لينكدان','بروفايل','profile'])

        if lang == "ar":
            guide = "🔗 **دليل LinkedIn + GitHub لطالب IT — اليرموك**\n\n"
            if not is_github and not is_linkedin:
                is_github = is_linkedin = True  # show both

            if is_linkedin:
                headline = tmpl["linkedin_headline"] if tmpl else "IT Student @ Yarmouk University | Open to Internships"
                guide += (
                    "**LinkedIn — كيف تبني بروفايل يجذب الشركات:**\n"
                    f"1️⃣ **Headline:** `{headline}`\n"
                    "2️⃣ **About:** 3-4 جمل — من أنت، تخصصك، وأبرز مهاراتك\n"
                    "3️⃣ **Education:** جامعة اليرموك — كلية IT — تخصصك — سنة التخرج\n"
                    "4️⃣ **Skills:** أضف 5-7 مهارات تقنية رئيسية (بتظهر بالبحث)\n"
                    "5️⃣ **Projects:** لكل مشروع: اسم + وصف + تقنيات + رابط GitHub\n"
                    "6️⃣ **تواصل:** أضف 50+ connection للبداية — أساتذتك، زملاءك، طلاب خريجين\n"
                    "7️⃣ **اشترك بـ:** صفحات Orange Jordan، Zain، ScopeX، Makeen للإشعارات\n\n"
                    f"🔗 ابحث: linkedin.com/jobs → 'IT internship Jordan 2026'\n\n"
                )
            if is_github:
                github_tip = tmpl["github_tip"] if tmpl else "Pin مشروعك الأقوى وأضف README واضح لكل مشروع"
                guide += (
                    "**GitHub — كيف تبني portfolio يُبهر المحكّمين:**\n"
                    f"1️⃣ **اسم المستخدم:** استخدم اسمك الحقيقي أو قريب منه\n"
                    "2️⃣ **Profile README:** ملف README.md بمعرفك — يظهر بالأعلى\n"
                    "3️⃣ **Pin 6 repos:** اختار أفضل 6 مشاريع واعرضها بالأعلى\n"
                    "4️⃣ **كل repo يحتاج:** README واضح، screenshots، تعليمات التشغيل\n"
                    "5️⃣ **Commit بانتظام:** الـ contribution graph الأخضر مهم!\n"
                    f"💡 {github_tip}\n\n"
                    "📌 مثال ممتاز: مشروع تخرجك CS 499 لازم يكون أول repo مُصنَّف"
                )
        else:
            guide = "🔗 **LinkedIn + GitHub Guide for IT Students @ Yarmouk**\n\n"
            headline = tmpl["linkedin_headline"] if tmpl else "IT Student @ Yarmouk University | Open to Internships"
            github_tip = tmpl["github_tip"] if tmpl else "Pin your best projects with a clear README"
            guide += (
                "**LinkedIn — How to build a profile that attracts companies:**\n"
                f"1️⃣ Headline: `{headline}`\n"
                "2️⃣ About: 3-4 lines — who you are, your major, top skills\n"
                "3️⃣ Education: Yarmouk University | IT Faculty | Your major\n"
                "4️⃣ Skills: Add 5-7 technical skills (they appear in recruiter searches)\n"
                "5️⃣ Projects: For each — name, description, tech stack, GitHub link\n"
                "6️⃣ Connect: Add 50+ connections — professors, classmates, alumni\n\n"
                "**GitHub — How to build an impressive portfolio:**\n"
                "1️⃣ Username: Use your real name or close to it\n"
                "2️⃣ Profile README: A README.md file that appears at the top\n"
                "3️⃣ Pin 6 repos: Show your best 6 projects at the top\n"
                "4️⃣ Each repo needs: Clear README, screenshots, run instructions\n"
                f"💡 {github_tip}"
            )
        return {"response": guide, "source": "linkedin_github_guide", "confidence": 92, "docs_retrieved": 0}

    async def _handle_graduation_simulator(self, question: str, user_id: int, detected_lang: str) -> Optional[Dict]:
        """ميزة محاكي التخرج: يحسب الساعات المتبقية ويرسم خطة توزيع المواد."""
        major     = self._extract_major(question)
        completed = self._extract_hours(question)
        total     = GRADUATION_HOURS.get(major, GRADUATION_HOURS['default']) if major else GRADUATION_HOURS['default']
        remaining = (total - completed) if completed is not None else None
        hard_courses = HARD_COURSES_BY_MAJOR.get(major, HARD_COURSES_BY_MAJOR.get('CS', []))

        # ── تحديد سنة الطالب من الساعات ──
        year_in_program = None
        if completed is not None:
            if completed < 36:   year_in_program = "السنة الأولى"
            elif completed < 72: year_in_program = "السنة الثانية"
            elif completed < 108: year_in_program = "السنة الثالثة"
            else:                year_in_program = "السنة الرابعة"

        # ── إذا ناقصة معلومات أساسية → اطلب توضيح ──
        missing_info = []
        if not major:
            missing_info.append("تخصصك (CS / CIS / CYS / DA / BIT / DRG)")
        if completed is None:
            missing_info.append("كم ساعة معتمدة أنهيت")

        if missing_info:
            clarify_ar = (
                f"🎓 **محاكي التخرج — NovaCortex**\n\n"
                f"عشان أرسملك خطة دقيقة، بحتاج منك:\n"
                + "".join(f"• {m}\n" for m in missing_info)
                + "\nمثال: \"أنهيت 90 ساعة بتخصص CYS\""
            )
            clarify_en = (
                f"🎓 **Graduation Planner — NovaCortex**\n\n"
                f"To build your plan accurately, I need:\n"
                + "".join(f"• {m}\n" for m in missing_info)
                + "\nExample: \"I completed 90 credit hours in CYS\""
            )
            resp_text = clarify_en if detected_lang == "en" else clarify_ar
            return {"response": resp_text, "source": "graduation_simulator", "confidence": 90, "docs_retrieved": 0}

        # ── تنبيه مهم: لا نعرف المواد المنجزة بالضبط ──
        important_note = (
            "⚠️ **ملاحظة مهمة:** الخطة مبنية على الساعات فقط. "
            "بعض المواد المقترحة قد تكون أنجزتها بالفعل! "
            "تحقق من سجلك الأكاديمي على بوابة الطالب قبل التسجيل.\n\n"
            if detected_lang != "en" else
            "⚠️ **Important:** This plan is based on credit hours only. "
            "Some suggested courses may already be completed! "
            "Always verify against your academic record.\n\n"
        )

        context_block = f"""أنت نظام محاكي التخرج الذكي لجامعة اليرموك — كلية IT.
هدفك: مساعدة الطالب على حساب ساعاته المتبقية ورسم أسهل طريق للتخرج بأعلى معدل.

المعطيات:
- التخصص: {major}
- الساعات المنجزة: {completed} ساعة
- إجمالي ساعات التخرج: {total} ساعة
- الساعات المتبقية: {remaining} ساعة
- المرحلة الدراسية التقريبية: {year_in_program}
- المواد الصعبة التي يجب توزيعها بحكمة: {', '.join(hard_courses[:4])}

قواعد الخطة:
- فصل عادي: 15-18 ساعة (5-6 مواد)
- الصيفي: 6-9 ساعات
- لا أكثر من مادة صعبة واحدة + مادتين متوسطتين بفصل
- وزّع مشروع التخرج في آخر أو قبل آخر فصل
- اقترح عدد الفصول المتبقية لا مواد محددة (لأن الطالب أنجز مواد لا نعرفها)
- قل للطالب: "راجع خطتك على بوابة الطالب للتأكد من المواد المتبقية فعلياً"

السؤال: {question}"""

        try:
            resp = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": context_block}],
                temperature=0.3,
                max_tokens=800,
            )
            answer = resp.choices[0].message.content.strip()
            # أضف التنبيه المهم
            answer = important_note + answer
            return {"response": answer, "source": "graduation_simulator", "confidence": 90, "docs_retrieved": 0}
        except Exception as e:
            logger.error(f"[GradSim] LLM error: {e}")
            return None

    # ==================== FEATURE 2: SKILL GAP DETECTOR ====================
    def _extract_job_role(self, text: str) -> Optional[str]:
        """يستخرج المسار الوظيفي المطلوب من النص."""
        t = text.lower()
        role_map = {
            'Web Dev':          ['web dev', 'تطوير ويب', 'full stack', 'فرونت', 'frontend', 'backend', 'node', 'react', 'next.js'],
            'Mobile Dev':       ['موبايل', 'mobile', 'flutter', 'android', 'ios', 'react native'],
            'AI/ML':            ['ai', 'ml', 'machine learning', 'ذكاء اصطناعي', 'تعلم آلي', 'data science', 'علم بيانات'],
            'DevOps':           ['devops', 'ديف اوبس', 'docker', 'kubernetes', 'cloud', 'سحابة', 'aws', 'azure'],
            'Data Analytics':   ['تحليل بيانات', 'data analytics', 'power bi', 'tableau', 'excel'],
            'Cybersecurity':    ['أمن', 'security', 'hacking', 'penetration', 'soc', 'ethical hacking'],
            'Game Dev':         ['game', 'ألعاب', 'unity', 'unreal', 'vr', 'xr'],
            'Backend':          ['backend', 'باكند', 'api', 'server', 'django', 'spring'],
            'Digital Marketing':['تسويق', 'marketing', 'seo', 'google ads', 'social media'],
            'Project Mgmt':     ['project manager', 'pm', 'scrum', 'agile', 'إدارة مشاريع'],
        }
        for role, keywords in role_map.items():
            for kw in keywords:
                if kw in t:
                    return role
        return None

    async def _handle_skill_gap_detector(self, question: str, user_id: int, detected_lang: str) -> Optional[Dict]:
        """ميزة كاشف الفجوة المهارية: يقارن المنهج بمتطلبات LinkedIn 2026."""
        major    = self._extract_major(question)
        job_role = self._extract_job_role(question)
        gap_data = SKILL_GAP_DATA.get(major, {}) if major else {}
        covered  = gap_data.get('covered', [])
        missing_by_role = gap_data.get('missing', {})
        missing  = missing_by_role.get(job_role, []) if job_role else []

        # ── إذا ناقص التخصص → اطلب توضيح ──
        if not major:
            clarify_ar = (
                "🔍 **كاشف الفجوة المهارية — NovaCortex**\n\n"
                "عشان أقارن منهجك مع سوق العمل 2026، أخبرني:\n"
                "• ما تخصصك؟ (CS / CIS / CYS / DA / BIT / DRG)\n"
                "• وما المجال الذي تريد العمل فيه؟\n\n"
                "مثال: \"أنا طالب CYS وبدي اشتغل في أمن سيبراني\""
            )
            clarify_en = (
                "🔍 **Skill Gap Detector — NovaCortex**\n\n"
                "To compare your curriculum with the 2026 job market, tell me:\n"
                "• What's your major? (CS / CIS / CYS / DA / BIT / DRG)\n"
                "• What field do you want to work in?\n\n"
                "Example: \"I'm a CYS student interested in cybersecurity\""
            )
            return {
                "response": clarify_en if detected_lang == "en" else clarify_ar,
                "source": "skill_gap_detector", "confidence": 90, "docs_retrieved": 0
            }

        # إذا ما حدد مسار: نعطيه نظرة عامة على كل المسارات
        all_missing_roles_str = ""
        if not job_role and missing_by_role:
            all_missing_roles_str = "\n".join([f"- {r}: {', '.join(skills[:3])}" for r, skills in list(missing_by_role.items())[:4]])

        context_block = f"""أنت كاشف الفجوة المهارية الذكي — NovaCortex لجامعة اليرموك.
مهمتك: تحويل الطالب من خريج جامعي إلى مرشح جاهز لسوق العمل في الأردن و MENA 2026.
هذه مقارنة مبنية على بيانات LinkedIn Jobs و Wuzzuf و Bayt لسنة 2026.

التخصص: {major}
المسار الوظيفي: {job_role if job_role else 'غير محدد — قدّم نظرة عامة لكل المسارات'}
ما يغطيه المنهج بقوة: {', '.join(covered) if covered else 'محدود'}
ما ينقص للمسار: {', '.join(missing) if missing else (all_missing_roles_str if all_missing_roles_str else 'حدد المسار للتفاصيل')}

تعليمات الإجابة:
1. ابدأ بـ "جامعتك غطّت لك: ✅" ثم اذكر ما تعلمه الطالب بإيجاز
2. ثم "لكن ينقصك للعمل في {job_role if job_role else 'هذا المجال'}: ⚡" + المهارات مرتبة بالأولوية
3. أضف "خطة الـ 90 يوم" — 3 مراحل عملية لسد الفجوة
4. اختم بـ "أهم مصادر مجانية" — Coursera / YouTube / roadmap.sh / GitHub
5. الأسلوب: مباشر، عملي، فيه أمل وليس تخويف
6. إذا لم يحدد مسارًا وظيفيًا: اعطِه مقارنة سريعة لكل المسارات مع نصيحة باختيار الأنسب

السؤال: {question}"""

        try:
            resp = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": context_block}],
                temperature=0.45,
                max_tokens=1000,
            )
            answer = resp.choices[0].message.content.strip()
            return {"response": answer, "source": "skill_gap_detector", "confidence": 90, "docs_retrieved": 0}
        except Exception as e:
            logger.error(f"[SkillGap] LLM error: {e}")
            return None

    # ==================== FEATURE 3: ACADEMIC SOS ====================
    def _extract_failed_course(self, text: str) -> Optional[str]:
        """يستخرج اسم المادة الراسبة من النص."""
        # أولوية: كود المادة الأكاديمي (مثل CS 310، CYS 440)
        code_match = re.search(r'([A-Z]{2,3}\s*\d{3}[A-Z]?)', text, re.IGNORECASE)
        if code_match:
            return code_match.group(1).strip().upper()
        # ثانياً: اسم المادة بعد "رسبت في" أو ما شابه
        patterns = [
            r'رسبت\s+(?:في|ب|بـ)\s+([\w\s]{3,40})(?:،|,|\.|$)',
            r'راسب\s+(?:في|ب|بـ)\s+([\w\s]{3,40})(?:،|,|\.|$)',
            r'فشلت\s+(?:في|ب)\s+([\w\s]{3,40})(?:،|,|\.|$)',
            r'مادة\s+([\w\s]{3,40})\s+(?:راسب|رسبت)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def _extract_gpa(self, text: str) -> Optional[float]:
        """يستخرج المعدل من النص."""
        patterns = [
            r'معدلي\s+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s+(?:معدل|gpa)',
            r'gpa\s+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s+(?:تحت|أقل)',
            r'نزل\s+(?:إلى|ل|لـ)?\s*(\d+(?:\.\d+)?)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 0.0 <= val <= 4.0:
                    return val
                if 50.0 <= val <= 100.0:
                    return val  # percentage scale
        return None

    async def _handle_academic_sos(self, question: str, user_id: int, detected_lang: str) -> Optional[Dict]:
        """ميزة خطة الطوارئ الأكاديمية: Recovery Plan فوري وذكي."""
        failed_course = self._extract_failed_course(question)
        gpa = self._extract_gpa(question)
        major = self._extract_major(question)

        # تحديد حدة الأزمة — المعدل من 100 في اليرموك
        if gpa is not None:
            if gpa <= 60:
                crisis_level = "حرجة — خطر الإنذار الأكاديمي (تحت 60/100)"
            elif gpa <= 70:
                crisis_level = "متوسطة — المعدل تحت المقبول (60-70/100)"
            else:
                crisis_level = "خفيفة — المعدل قابل للتحسين (فوق 70/100)"
        elif failed_course:
            crisis_level = "رسوب في مادة"
        else:
            crisis_level = "متوسطة"

        context_block = f"""
أنت نظام الطوارئ الأكاديمية (Academic SOS) لجامعة اليرموك.
مهمتك: إنقاذ الطالب من الأزمة الأكاديمية بخطة عملية دقيقة — لا كلام إنشائي.

المعطيات:
- التخصص: {major if major else 'غير محدد'}
- المادة الراسبة: {failed_course if failed_course else 'غير محددة'}
- المعدل الحالي: {gpa if gpa is not None else 'غير محدد'}
- مستوى الأزمة: {crisis_level}

بنية إجابتك المطلوبة (لا تخرج عنها):

1. 🚨 تشخيص الوضع (جملتان)
2. ⚡ خطة الاسترداد الفورية (3-5 خطوات رقمية ومباشرة):
   - في حال رسوب مادة: أعد تسجيل المادة + استراتيجية الدراسة الجديدة + أفضل وقت للتسجيل
   - في حال انخفاض المعدل: مواد اختيارية سهلة معروفة (علوم عسكرية، القدس، تربية رياضية) + تقليل ساعات + إعادة أعلى مادة D
   - الساعات الموصى بها للفصل القادم حسب المعدل: تحت 60 → 12 ساعة | 60-70 → 15 ساعة | فوق 70 → 18 ساعة
   - تذكر: المعدل في اليرموك من 100 (ليس من 4)
3. 📊 جدول فصلين للتعافي (فصل 1 | فصل 2) بعدد ساعات محدد
4. 💡 نصيحة سرية (شيء واقعي يعرفه الطلاب المجربون عن جامعة اليرموك)
5. 🔮 الهدف الواقعي: المعدل المتوقع بعد التطبيق

القاعدة الذهبية: لا تعطِ تشجيعاً فارغاً — أعطِ خطة رقمية قابلة للتنفيذ غداً.
NovaCortex لا يعطيك نصائح، بل يعطيك خريطة الطريق للنجاة.

السؤال: {question}
"""
        try:
            resp = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": context_block}],
                temperature=0.35,
                max_tokens=900,
            )
            answer = resp.choices[0].message.content.strip()
            # إضافة header طوارئ
            header = "🆘 **خطة الطوارئ الأكاديمية — Academic SOS**\n\n"
            return {"response": header + answer, "source": "academic_sos", "confidence": 90, "docs_retrieved": 0}
        except Exception as e:
            logger.error(f"[AcademicSOS] LLM error: {e}")
            return None

    async def split_complex_question(self, question: str, lang: str) -> List[str]:
        if not isinstance(question, str):
            return [str(question)]
        if len(question.split()) < 12:
            return [question]
        split_prompt = (
            "أنت مساعد متخصص بتقسيم الأسئلة المركبة.\n"
            "إذا كان السؤال يحتوي أكثر من موضوع مستقل، قسمه لأسئلة منفصلة.\n"
            "إذا كان السؤال عن موضوع واحد فقط، أعده كما هو.\n"
            "أعد JSON بالشكل: {\"questions\": [\"سؤال 1\", \"سؤال 2\"]}\n\n"
            "قواعد:\n"
            "- كل سؤال ناتج لازم يكون مفهوم لوحده بدون السؤال الأصلي\n"
            "- لا تضف معلومات غير موجودة بالسؤال الأصلي\n"
            "- حافظ على لغة السؤال الأصلية"
        )
        try:
            response = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": split_prompt},
                    {"role": "user", "content": f"السؤال: {question}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1, max_tokens=300
            )
            result = json.loads(response.choices[0].message.content)
            questions = result.get("questions", [question])
            cleaned = []
            for q in questions:
                if isinstance(q, str) and len(q.split()) >= 3:
                    cleaned.append(q)
                elif isinstance(q, dict):
                    val = str(list(q.values())[0]) if q.values() else question
                    if len(val.split()) >= 3:
                        cleaned.append(val)
            return cleaned if cleaned else [question]
        except:
            return [question]
    async def process_question(self, question: str, user_id: int, study_level: str = "بكالوريوس") -> Dict:
        start_time = time.time()
        detected_lang = arabic_processor.detect_language(question)
        greeting_response = handle_greeting(question)
        if greeting_response:
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", greeting_response)
            return {"response": greeting_response, "source": "greeting", "confidence": 100,
                    "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
        context = self.memory.get_context(user_id, max_messages=6)
        has_context = len(context) > 0
        false_premise_correction = check_false_premise(question, detected_lang)
        if not false_premise_correction and needs_false_premise_check(question):
            false_premise_correction = await check_false_premise_llm(question, detected_lang, llm_client)
        if false_premise_correction:
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", false_premise_correction)
            return {
                "response": false_premise_correction, "source": "false_premise_corrected",
                "confidence": 100, "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0
            }
        scope_result = await self.scope_detector.is_out_of_scope(question, has_context=has_context)
        if scope_result:
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", scope_result["message"])
            return {
                "response": scope_result["message"], "source": "out_of_scope",
                "confidence": 100, "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0
            }
        sub_questions = await self.split_complex_question(question, detected_lang)
        if len(sub_questions) > 1:
            all_results = []
            for sub_q in sub_questions:
                res = await self._process_single_question(sub_q, user_id, study_level, detected_lang)
                all_results.append(res)
            return {
                "response": "\n\n".join(res["response"] for res in all_results),
                "source": "multi_query",
                "confidence": min((res.get("confidence", 0) for res in all_results), default=0),
                "response_time_ms": int((time.time() - start_time) * 1000),
                "docs_retrieved": sum(res.get("docs_retrieved", 0) for res in all_results)
            }
        return await self._process_single_question(question, user_id, study_level, detected_lang)
    async def _process_single_question(self, question: str, user_id: int, study_level: str, detected_lang: str) -> Dict:
        start_time = time.time()
        if is_general_oos(question):
            msg = "عذراً، هذا السؤال خارج نطاق تخصصي في جامعة اليرموك." if detected_lang == "ar" else "Sorry, this question is outside the scope of Yarmouk University."
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", msg)
            return {"response": msg, "source": "out_of_scope", "confidence": 100,
                    "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
        if detect_injection(question):
            msg = "أنا مساعد جامعة اليرموك فقط. كيف يمكنني مساعدتك؟" if detected_lang == "ar" else "I am Yarmouk University's assistant only. How can I help you?"
            logger.warning(f"Injection attempt detected: '{question[:80]}...'")
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", msg)
            return {"response": msg, "source": "injection_blocked", "confidence": 100,
                    "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}

        # ===== VF FAST-PATH: credit hours + counselors + GPA + gates (بدون LLM) =====
        q_fast = question.lower()
        # أيضاً فحص النص بعد الـ proxy (ايميل → معلومات التواصل)
        _proxied_q = apply_proxy_prompt(question).lower()
        _vf_fast_checks = [
            (['كم ساعة تخرج','ساعة تخرج','ساعات التخرج','ساعات اللازمة','كم ساعة للتخرج',
              'how many credit hours','total credit hours'],
             lambda: VERIFIED_FACTS[detected_lang].get("it_credit_hours",{}).get(
                 "note", "جميع تخصصات كلية IT تتطلب 134 ساعة معتمدة للتخرج ✅")),
            (['مرشد نفسي','المرشد النفسي','أخصائي نفسي','الأخصائي النفسي',
              'مستشار نفسي','إرشاد نفسي','صحة نفسية',
              'اتواصل مع أخصائي','اتواصل مع مرشد','psychological counselor',
              'counseling email','mental health contact','معلومات التواصل لـ المرشد',
              'معلومات المرشد','معلومات التواصل لـ أخصائي','تواصل مع أخصائي'],
             lambda: VERIFIED_FACTS[detected_lang].get("psychological_counselors",{}).get("details","")),
            (['نظام المعدل','كيف يحسب المعدل','المعدل من 100','gpa scale','من مئة'],
             lambda: VERIFIED_FACTS[detected_lang].get("gpa_scale",{}).get("details","")),
            (['كم بوابة','البوابة الشرقية','البوابة الرئيسية','بوابات الجامعة'],
             lambda: VERIFIED_FACTS[detected_lang].get("gates",{}).get("details","")),
        ]
        for kws, vf_fn in _vf_fast_checks:
            if any(kw in q_fast for kw in kws) or any(kw in _proxied_q for kw in kws):
                answer = vf_fn()
                if answer:
                    fmt_answer = formatter.format(answer, "verified_facts", detected_lang)
                    await self.memory.add_message(user_id, "user", question)
                    await self.memory.add_message(user_id, "assistant", fmt_answer)
                    return {"response": fmt_answer, "source": "verified_facts",
                            "confidence": 100,
                            "response_time_ms": int((time.time()-start_time)*1000),
                            "docs_retrieved": 0}

        # ===== FEATURE 0-A: CRISIS / MENTAL HEALTH SUPPORT (أعلى أولوية) =====
        q_lower_feat = question.lower()
        if any(kw in q_lower_feat for kw in CRISIS_KEYWORDS):
            logger.info(f"[Crisis] Mental health trigger: '{question[:60]}'")
            crisis_result = await self._handle_crisis_support(question, user_id, detected_lang)
            if crisis_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", crisis_result["response"])
                crisis_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return crisis_result

        # ===== FEATURE 0-B: FACULTY LOOKUP — من أعطى مادة، بيانات دكتور =====
        _fac_kw = ['مين يدرس','من يدرس','مين يدرّس','ساعات مكتب',
                   'office hours','ايميل دكتور','رقم دكتور','معلومات دكتور','faculty member',
                   'بيانات دكتور','شو ايميل','معلومات عن دكتور',
                   'شهابات','الردايدة','الزعبي','الخطيب','مهاوش','نواصرة',
                   'معلومات عن رعد','معلومات عن جعفر','معلومات عن خالد',
                   'بدي معلومات دكتور','بدي ايميل دكتور']
        # استثن: المرشد النفسي يذهب لـ VF
        _counselor_q = any(kw in q_lower_feat for kw in [
            'مرشد نفسي','مستشار نفسي','أخصائي نفسي','إرشاد نفسي','نفسي','صحة نفسية','counseling'])
        # استثن: أسئلة رئيس/عميد العام (لا اسم محدد)
        _has_specific_name = any(k in q_lower_feat for k in [
            'الردايدة','الزعبي','الخطيب','مهاوش','نواصرة','شهابات','حمدان',
            'radaideh','zoubi','khatib','mhawish','nawasreh','shahabat'])
        _vf_protected_generic = ['رئيس الجامعة','رئيس اليرموك','من عميد','who is the dean',
                                  'who is the president','university president']
        _is_vf = not _has_specific_name and any(kw in q_lower_feat for kw in _vf_protected_generic)
        if not _is_vf and not _counselor_q and any(kw in q_lower_feat for kw in _fac_kw):
            fac_result = self._handle_faculty_lookup(question, detected_lang)
            if fac_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", fac_result["response"])
                fac_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return fac_result

        # ===== FEATURE 0-C: CV BUILDER =====
        if any(kw in q_lower_feat for kw in CV_BUILDER_KEYWORDS):
            logger.info(f"[CVBuilder] Triggered: '{question[:60]}'")
            cv_result = await self._handle_cv_builder(question, user_id, detected_lang)
            if cv_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", cv_result["response"])
                cv_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return cv_result

        # ===== FEATURE 0-D: LINKEDIN / GITHUB GUIDE =====
        if any(kw in q_lower_feat for kw in LINKEDIN_GUIDE_KEYWORDS):
            logger.info(f"[LinkedIn] Triggered: '{question[:60]}'")
            li_result = self._handle_linkedin_github_guide(question, detected_lang)
            if li_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", li_result["response"])
                li_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return li_result

        # ===== FEATURE 1: GRADUATION SIMULATOR =====
        if any(kw in q_lower_feat for kw in GRADUATION_SIMULATOR_KEYWORDS):
            logger.info(f"[GradSim] Triggered for: '{question[:60]}'")
            grad_result = await self._handle_graduation_simulator(question, user_id, detected_lang)
            if grad_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", grad_result["response"])
                grad_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return grad_result

        # ===== FEATURE 2: SKILL GAP DETECTOR =====
        if any(kw in q_lower_feat for kw in SKILL_GAP_KEYWORDS):
            logger.info(f"[SkillGap] Triggered for: '{question[:60]}'")
            skill_result = await self._handle_skill_gap_detector(question, user_id, detected_lang)
            if skill_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", skill_result["response"])
                skill_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return skill_result

        # ===== FEATURE 3: ACADEMIC SOS =====
        if any(kw in q_lower_feat for kw in ACADEMIC_SOS_KEYWORDS):
            logger.info(f"[AcademicSOS] Triggered for: '{question[:60]}'")
            sos_result = await self._handle_academic_sos(question, user_id, detected_lang)
            if sos_result:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", sos_result["response"])
                sos_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return sos_result
        # Advisory questions continue through facts/RAG so the answer can use
        # the student's actual major and evidence instead of returning the
        # same generic university paragraph for every recommendation request.
        if is_comparison_question(question):
            # ✅ FIX: نفرّق بين نوعين من المقارنة:
            # 1) "مين أحسن / أفضل" → رأي شخصي → نرفض
            # 2) "شو الفرق بين X و Y" → سؤال معلوماتي → نجاوب من LLM
            preferential_kws = ['مين احسن', 'مين أفضل', 'أيهما أفضل', 'who is better', 'better than', 'احسن من']
            is_preferential = any(kw in question.lower() for kw in preferential_kws)

            if is_preferential:
                # رأي تفضيلي → نرفض ونعطي معلومات موضوعية
                clean_q = re.sub(r'(مين احسن|أفضل|better|احسن).*$', '', question, flags=re.IGNORECASE).strip()
                if clean_q and len(clean_q) > 3:
                    result = await self._process_single_question(clean_q, user_id, study_level, detected_lang)
                    msg = result["response"] + "\n\nعذراً، لا أقدم مقارنات تفضيلية بين التخصصات."
                    return {"response": msg, "source": "comparison_rejected", "confidence": 100,
                            "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
                else:
                    msg = "عذراً، لا يمكنني إجراء مقارنات تفضيلية." if detected_lang == "ar" else "Sorry, I cannot make preferential comparisons."
                    await self.memory.add_message(user_id, "user", question)
                    await self.memory.add_message(user_id, "assistant", msg)
                    return {"response": msg, "source": "comparison_rejected", "confidence": 100,
                            "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
            else:
                # سؤال "الفرق بين" → معلوماتي → جرّب RAG أولاً ثم LLM fallback
                logger.info(f"[COMPARISON] Informational comparison detected, allowing LLM fallback: '{question[:50]}'")
                # جرب RAG أولاً
                _comp_depth = detect_response_depth(question)
                rag_q = expand_colloquial_terms(question)
                rag_result = await self._rag_path(rag_q, study_level, detected_lang, [], _comp_depth)
                rag_resp = rag_result.get("response", "")
                rag_ok = rag_result.get("confidence", 0) >= 70 and not any(
                    p in rag_resp for p in ['لا تتوفر', 'لا أعلم', 'لا أملك']
                )
                if rag_ok:
                    await self.memory.add_message(user_id, "user", question)
                    await self.memory.add_message(user_id, "assistant", rag_resp)
                    rag_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                    return rag_result
                # RAG ما عنده جواب كافٍ → LLM يجاوب من معرفته العامة
                fallback = await self._llm_fallback_response(question, detected_lang)
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", fallback["response"])
                fallback["response_time_ms"] = int((time.time() - start_time) * 1000)
                return fallback
        proxied_question = apply_proxy_prompt(question)
        if proxied_question != question:
            logger.info(f"Question proxied: '{question}' → '{proxied_question}'")
        context = self.memory.get_context(user_id, max_messages=6)
        parsed_intent = await asyncio.to_thread(self.semantic_parser.parse, proxied_question)
        response_depth = parsed_intent.get("response_depth", "moderate")
        enriched_question = proxied_question
        if context:
            followup_words = [
                'أكثر', 'اكثر', 'more', 'tell me', 'explain', 'detail',
                'كم', 'عددهم', 'how many', 'count',
                'الرابط', 'رابط', 'link', 'url', 'website',
                'طيب', 'ok', 'then'
            ]
            is_short = len(question.split()) <= 4
            has_no_entity = not any(kw in question.lower() for kw in [
                'كلية', 'قسم', 'دكتور', 'جامعة', 'اليرموك',
                'تخصص', 'تخصصات', 'برامج', 'برنامج', 'programs', 'majors',
                'it', 'حجاوي', 'هندسة', 'طب', 'صيدلة', 'فنون', 'قانون',
                'آداب', 'اداب', 'شريعة', 'تربية', 'اعلام', 'سياحة',
                'رسوم', 'منح', 'سكن', 'تأمين', 'مكتبة',
            ])
            is_implicit = is_short and (has_no_entity or any(kw in question.lower() for kw in followup_words))
            if is_implicit:
                last_entity = None
                last_user_q = None
                for msg in reversed(context):
                    if msg.get("entity"):
                        last_entity = msg["entity"]
                    if msg["role"] == "user" and not last_user_q:
                        last_user_q = msg["content"]
                if last_entity:
                    enriched_question = f"Context: {last_entity} | Question: {proxied_question}"
                elif last_user_q:
                    enriched_question = f"{last_user_q} - {proxied_question}"
                logger.info(f"Context enriched: '{question}' -> '{enriched_question}'")
        if parsed_intent.get("intent_key") == "faculty_member_search":
            # ✅ FIX 5: تحقق من VERIFIED_FACTS أولاً قبل Web Search
            _it_admin = VERIFIED_FACTS[detected_lang]["it_admin"]
            _q_lower = question.lower()
            _found_in_facts = None

            # تحقق من العميد
            _dean = _it_admin["dean"]
            _dean_name_parts = _dean["name"].replace("د. ", "").replace("Dr. ", "").split()
            if any(part in _q_lower for part in _dean_name_parts if len(part) > 3):
                _found_in_facts = f"{_dean['name']} — {_dean['title']}"

            # تحقق من نواب العميد
            if not _found_in_facts:
                for _vd in _it_admin["vice_deans"]:
                    _vd_parts = _vd["name"].replace("د. ", "").replace("Dr. ", "").split()
                    if any(part in _q_lower for part in _vd_parts if len(part) > 3):
                        _found_in_facts = f"{_vd['name']} — {_vd['title']}"
                        break

            # تحقق من مساعد العميد
            if not _found_in_facts:
                _asst = _it_admin["assistant_dean"]
                _asst_parts = _asst["name"].replace("د. ", "").replace("Dr. ", "").split()
                if any(part in _q_lower for part in _asst_parts if len(part) > 3):
                    _found_in_facts = f"{_asst['name']} — {_asst['title']}"

            # تحقق من رؤساء الأقسام
            if not _found_in_facts:
                for _dept_key, _head in _it_admin["department_heads"].items():
                    _head_parts = _head["name"].replace("د. ", "").replace("Dr. ", "").split()
                    if any(part in _q_lower for part in _head_parts if len(part) > 3):
                        _found_in_facts = f"{_head['name']} — رئيس {_head['dept']}" if detected_lang == "ar" else f"{_head['name']} — Head of {_head['dept']}"
                        break

            if _found_in_facts:
                logger.info(f"[FACTS] Faculty member found in VERIFIED_FACTS: {_found_in_facts[:60]}")
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", _found_in_facts)
                return {"response": _found_in_facts, "source": "verified_facts", "confidence": 100,
                        "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}

            # إذا ما لاقى في VERIFIED_FACTS → جرّب RAG أولاً ثم Web
            _rag_faculty = await self._rag_path(enriched_question, study_level, detected_lang, context, response_depth)
            if _rag_faculty.get("confidence", 0) >= 60 and len(_rag_faculty.get("response", "")) > 50:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", _rag_faculty["response"])
                _rag_faculty["response_time_ms"] = int((time.time() - start_time) * 1000)
                return _rag_faculty

            result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth, is_faculty_search=True)
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", result["response"])
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            return result
        if parsed_intent.get("intent_key") == "cost_inquiry":
            direct_answer = self.facts_router.route(enriched_question, parsed_intent, detected_lang, context)
            if direct_answer:
                await self.memory.add_message(user_id, "user", question, entity=parsed_intent.get("entity"))
                await self.memory.add_message(user_id, "assistant", direct_answer)
                return {"response": direct_answer, "source": "verified_facts", "confidence": 90,
                        "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
            result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth)
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", result["response"])
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            return result
        is_financial_intent = parsed_intent.get("intent_key") in ("fees_inquiry", "scholarship_inquiry")
        is_scholarship_kw = any(word in proxied_question.lower() for word in SCHOLARSHIP_KEYWORDS)
        is_fees_kw = any(word in proxied_question.lower() for word in FEES_KEYWORDS)
        if is_fees_kw and not is_scholarship_kw:
            direct_answer = self.facts_router.route(enriched_question, parsed_intent, detected_lang, context)
            if direct_answer:
                await self.memory.add_message(user_id, "user", question, entity=parsed_intent.get("entity"))
                await self.memory.add_message(user_id, "assistant", direct_answer)
                return {"response": direct_answer, "source": "verified_facts", "confidence": 100,
                        "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
            rag_result = await self._rag_path(enriched_question, study_level, detected_lang, context, response_depth)
            if rag_result.get("confidence", 0) >= 70:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", rag_result["response"])
                rag_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return rag_result
            result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth)
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", result["response"])
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            return result
        if is_scholarship_kw or (is_financial_intent and parsed_intent.get("intent_key") == "scholarship_inquiry"):
            rag_result = await self._rag_path(enriched_question, study_level, detected_lang, context, response_depth)
            if rag_result.get("confidence", 0) >= 70:
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", rag_result["response"])
                rag_result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return rag_result
            result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth)
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", result["response"])
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
            return result
        direct_answer = self.facts_router.route(enriched_question, parsed_intent, detected_lang, context)
        if direct_answer:
            await self.memory.add_message(user_id, "user", question, entity=parsed_intent.get("entity"))
            await self.memory.add_message(user_id, "assistant", direct_answer)
            return {"response": direct_answer, "source": "verified_facts", "confidence": 100,
                    "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}

        # ✅ FIX 2: اكتشاف follow-up "شو اسماءهم / اذكر الأسماء" بعد إجابة عدد الكليات
        _faculties_followup_kws = ['اسماء', 'أسماء', 'اسمها', 'names', 'ما هي', 'شو', 'بسميها', 'عددها', 'اذكر', 'قائمة', 'list']
        _last_was_count = False
        if context:
            for _msg in reversed(context):
                if _msg['role'] == 'assistant':
                    _resp_stripped = _msg['content'].strip()
                    if _resp_stripped in ['16', '١٦', '16 كلية'] or _resp_stripped.startswith('16\n') or '16 كلية' in _resp_stripped:
                        _last_was_count = True
                    break
        if _last_was_count and any(kw in question.lower() for kw in _faculties_followup_kws):
            _faculties = VERIFIED_FACTS[detected_lang]["faculties_list"]
            _fac_answer = "\n".join([f"• {f}" for f in _faculties])
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", _fac_answer)
            return {"response": _fac_answer, "source": "verified_facts", "confidence": 100,
                    "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}

        if any(kw in question.lower() for kw in ['كم', 'كم عدد', 'عدد', 'من كم', 'كم بوابة', 'كم مبنى', 'how many', 'number of']):
            direct = self.facts_router.route(enriched_question, parsed_intent, detected_lang, context)
            if direct:
                await self.memory.add_message(user_id, "user", question, entity=parsed_intent.get("entity"))
                await self.memory.add_message(user_id, "assistant", direct)
                return {"response": direct, "source": "verified_facts", "confidence": 100,
                        "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
            else:
                result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth)
                await self.memory.add_message(user_id, "user", question)
                await self.memory.add_message(user_id, "assistant", result["response"])
                result["response_time_ms"] = int((time.time() - start_time) * 1000)
                return result
        cached = self.cache.get(enriched_question)
        if cached:
            await self.memory.add_message(user_id, "user", question)
            await self.memory.add_message(user_id, "assistant", cached["response"])
            return {**cached, "response_time_ms": int((time.time() - start_time) * 1000), "docs_retrieved": 0}
        rag_question = expand_colloquial_terms(enriched_question)
        if self._needs_web_search(enriched_question):
            result = await self._web_search_path(enriched_question, study_level, detected_lang, response_depth)
        else:
            result = await self._rag_path(rag_question, study_level, detected_lang, context, response_depth, parsed_intent=parsed_intent)
        await self.memory.add_message(user_id, "user", question)
        await self.memory.add_message(user_id, "assistant", result["response"])
        # Use dynamic confidence threshold for caching
        cache_threshold = compute_dynamic_threshold(enriched_question, result["source"])
        if result["confidence"] >= cache_threshold:
            self.cache.set(enriched_question, result["response"], result["confidence"], result["source"])
        result["response_time_ms"] = int((time.time() - start_time) * 1000)
        update_daily_stats(result["source"], result["confidence"], result["response_time_ms"])
        return result
    def _needs_web_search(self, question: str) -> bool:
        q_lower = question.lower()
        time_sensitive = [
            'آخر موعد', 'deadline', 'أخبار', 'خبر', 'إعلان جديد',
            'متى تعيين', 'تاريخ تعيين', 'كم صارله', 'when appointed',
            'آخر أخبار', 'latest news', 'موعد التسجيل', 'registration deadline'
        ]
        return any(phrase in q_lower for phrase in time_sensitive)
    async def _rag_path(self, question: str, study_level: str, language: str, context: List[Dict], response_depth: str = "moderate", parsed_intent: Dict = None) -> Dict:
        docs_with_scores = await asyncio.to_thread(self.retriever.retrieve, question, final_k=8)
        if not docs_with_scores:
            return await self._web_search_path(question, study_level, language, response_depth, _from_rag=True)
        # Apply LLM re-ranking
        reranked = await asyncio.to_thread(reranker.rerank, question, docs_with_scores, top_k=4)
        evidence_confidence = retrieval_confidence(question, reranked)
        if evidence_confidence < 55:
            logger.info(
                "[RAG→WEB] Evidence below threshold (%s) for: '%s'",
                evidence_confidence, question[:50]
            )
            return await self._web_search_path(
                question, study_level, language, response_depth, _from_rag=True
            )
        docs = [doc for doc, score in reranked]
        # Include metadata for source attribution
        raw_parts = []
        sources_used = []
        for doc in docs:
            raw_parts.append(doc.page_content)
            src = doc.metadata.get('title', doc.metadata.get('source', ''))
            if src and src not in sources_used:
                sources_used.append(src)
        raw_data = "\n".join(raw_parts)[:3500]
        history_str = ""
        if context:
            history_str = self.memory.format_context_for_llm(context)
        llm_result = await asyncio.to_thread(
            llm_generator.generate_answer, question, raw_data, language,
            history=history_str, response_depth=response_depth, parsed_intent=parsed_intent
        )
        if not llm_result["success"] or not llm_result["answer"]:
            return await self._web_search_path(question, study_level, language, response_depth, _from_rag=True)
        answer = llm_result["answer"]
        # ✅ FIX: إذا الـ RAG أجاب بـ "لا تتوفر" → صعّد للويب بدل إرجاع إجابة فارغة
        no_info_phrases = [
            'لا تتوفر لدي', 'لا أعلم', 'لا أملك', 'لا توجد معلومات',
            'غير متوفرة', 'لا تتوفر هذه المعلومة', 'لم أجد',
            "i don't have", 'not available', 'no information', 'i cannot find'
        ]
        rag_failed = any(phrase in answer.lower() for phrase in no_info_phrases)
        if rag_failed:
            logger.info(f"[RAG→WEB] RAG no-info answer, escalating to web: '{question[:50]}'")
            web_result = await self._web_search_path(question, study_level, language, response_depth, _from_rag=True)
            web_resp = web_result.get("response", "")
            if web_result.get("confidence", 0) > 0 and "لا تتوفر" not in web_resp:
                return web_result
        # Add source attribution
        if sources_used and len(answer) > 30 and not rag_failed:
            top_source = sources_used[0]
            if language == "ar":
                answer += f"\n\n📌 المصدر: {top_source}"
            else:
                answer += f"\n\n📌 Source: {top_source}"
        confidence = min(40, evidence_confidence) if rag_failed else evidence_confidence
        return {"response": answer, "source": "rag", "confidence": confidence, "docs_retrieved": len(docs)}
    async def _web_search_path(
        self,
        question: str,
        study_level: str,
        language: str,
        response_depth: str = "moderate",
        is_faculty_search: bool = False,
        _from_rag: bool = False
    ) -> Dict:
        faculty_name = None
        if is_faculty_search:
            name_match = re.search(
                r'(?:دكتور|الدكتور|أستاذ|professor)\s+([\w\s]+?)(?:\s+|\Z|\.)',
                question, re.IGNORECASE
            )
            if name_match:
                faculty_name = name_match.group(1).strip()
        results = await asyncio.to_thread(
            web_searcher.search_multi, question, study_level, is_faculty_search, faculty_name
        )
        grounded_context = await asyncio.to_thread(
            web_searcher.build_grounded_context, results, top_n=3
        )
        combined_snippets = grounded_context or web_searcher.combine_top_snippets(results, top_n=3)
        evidence_confidence = web_confidence(question, results, grounded_context)
        if combined_snippets and len(combined_snippets) >= 40:
            llm_result = await asyncio.to_thread(
                llm_generator.generate_answer,
                question, combined_snippets, language, response_depth=response_depth
            )
            if llm_result["success"] and llm_result["answer"]:
                source_links = []
                for item in results[:3]:
                    link = (item.get("link") or "").strip()
                    if link and link not in source_links:
                        source_links.append(link)
                answer = llm_result["answer"]
                if source_links:
                    label = "المصادر" if language == "ar" else "Sources"
                    answer += "\n\n📌 " + label + ":\n" + "\n".join(
                        f"• {link}" for link in source_links
                    )
                return {
                    "response": answer,
                    "source": "web",
                    "confidence": evidence_confidence,
                    "docs_retrieved": len(results)
                }
        logger.warning(f"[IMPROVEMENT 2] All sources failed for: '{question[:60]}' - using LLM fallback")
        fallback_result = await self._llm_fallback_response(question, language)
        return fallback_result
    async def _llm_fallback_response(self, question: str, language: str) -> Dict:
        # ✅ FIX: أسئلة المقارنة والشرح العام لا تحتاج تحذير "قد تحتاج تحقق"
        # الـ LLM يعرف الفرق بين التخصصات بشكل موثوق
        comparison_kws = ['الفرق بين', 'فرق بين', 'difference between', 'مقارنة', 'شو الفرق']
        is_comparison = any(kw in question.lower() for kw in comparison_kws)
        try:
            if language == "ar":
                if is_comparison:
                    prompt = (
                        f"أنت مساعد جامعة اليرموك. أجب عن هذا السؤال بشكل مفيد وواضح. "
                        f"يمكنك استخدام معرفتك العامة بالتخصصات الجامعية للإجابة. "
                        f"اذكر الفروق الجوهرية بشكل مختصر ومنظم.\n\n"
                        f"السؤال: {question}"
                    )
                    note = ""
                else:
                    prompt = (
                        f"أنت مساعد جامعة اليرموك. أجب عن هذا السؤال باقتضاب بناءً على معرفتك العامة. "
                        f"⚠️ لا تخترع أرقام أو تفاصيل غير متأكد منها. إذا لم تكن متأكداً، قل لست متأكداً. "
                        f"أضف ملاحظة قصيرة أن المعلومة قد تحتاج تحقق من الموقع الرسمي yu.edu.jo\n\n"
                        f"السؤال: {question}"
                    )
                    note = "\n\n⚠️ *قد تحتاج هذه المعلومة للتحقق من الموقع الرسمي: yu.edu.jo*"
            else:
                if is_comparison:
                    prompt = (
                        f"You are Yarmouk University assistant. Answer this comparison question clearly. "
                        f"You can use your general knowledge about university programs. "
                        f"Be concise and organized.\n\nQuestion: {question}"
                    )
                    note = ""
                else:
                    prompt = (
                        f"You are Yarmouk University assistant. Answer this question briefly based on your general knowledge. "
                        f"⚠️ Do NOT fabricate numbers or details you are unsure of. If unsure, say so. "
                        f"Add a short note that the info may need verification from yu.edu.jo\n\n"
                        f"Question: {question}"
                    )
                    note = "\n\n⚠️ *This information may need verification at: yu.edu.jo*"
            response = await asyncio.to_thread(
                llm_client.chat.completions.create,
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=350
            )
            answer = response.choices[0].message.content.strip()
            if answer and len(answer) > 20:
                return {
                    "response": answer + note,
                    "source": "llm_fallback",
                    "confidence": 55,
                    "docs_retrieved": 0
                }
        except Exception as e:
            logger.error(f"LLM fallback error: {e}")
        _reg_kw = ['تسجيل', 'موعد', 'deadline', 'enrollment', 'registration', 'قبول', 'التقديم']
        if any(kw in question.lower() for kw in _reg_kw):
            if language == "ar":
                return {
                    "response": (
                        "لا تتوفر لدي هذه المعلومة حالياً بشكل دقيق، لكن يمكنك التحقق من:\n\n"
                        "📋 نظام القبول والتسجيل: https://admreg.yu.edu.jo\n"
                        "🌐 الموقع الرسمي للجامعة: https://yu.edu.jo\n"
                        "📞 أو التواصل مع عمادة القبول والتسجيل مباشرة"
                    ),
                    "source": "web_empty", "confidence": 0, "docs_retrieved": 0
                }
            else:
                return {
                    "response": (
                        "I don't have this information currently, but you can check:\n\n"
                        "📋 Admission & Registration: https://admreg.yu.edu.jo\n"
                        "🌐 Official Website: https://yu.edu.jo"
                    ),
                    "source": "web_empty", "confidence": 0, "docs_retrieved": 0
                }
        return {
            "response": NO_RESULT_MESSAGE_AR if language == "ar" else NO_RESULT_MESSAGE_EN,
            "source": "web_empty",
            "confidence": 0,
            "docs_retrieved": 0
        }
