"""
YU Comprehensive Scraper v3.0  — Fixed URL Patterns
شغّله على جهازك: python scripts/yu_scraper.py

يعمل مع الداتا الحالية ويضيف عليها — ما يحذف شي.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FILE   = str(ROOT / "data" / "yarmouk_data_new.json")
EXISTING_FILE = str(ROOT / "data" / "yarmouk_data.json")
DELAY         = 1.0
TIMEOUT       = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://it.yu.edu.jo/",
}

session = requests.Session()
session.headers.update(HEADERS)

# ============================================================
#  HELPERS
# ============================================================

def get_page(url: str, retries: int = 2) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return BeautifulSoup(r.text, "lxml")
        except Exception as e:
            logger.warning(f"  Attempt {attempt+1} failed [{url[:60]}]: {e}")
            if attempt < retries - 1:
                time.sleep(2)
    logger.error(f"  Failed: {url[:70]}")
    return None


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def page_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(["nav", "footer", "script", "style", "noscript", "head"]):
        tag.decompose()
    for sel in ["article", "main", ".article-content", ".item-page",
                ".content-inner", "#content", ".container-inner"]:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 150:
            return clean(el.get_text(separator="\n", strip=True))
    body = soup.find("body")
    return clean(body.get_text(separator="\n", strip=True)) if body else ""


def table_to_text(table) -> str:
    rows = []
    for tr in table.find_all("tr"):
        cells = [clean(td.get_text()) for td in tr.find_all(["td", "th"])]
        row = " | ".join(c for c in cells if c)
        if row:
            rows.append(row)
    return "\n".join(rows)


def mk_item(title, content, url, category, description="", priority=2) -> dict:
    return {
        "title":       clean(title),
        "description": clean(description),
        "content":     clean(content),
        "url":         url,
        "category":    category,
        "priority":    priority,
        "scraped_at":  datetime.now().isoformat(),
    }


def scrape_page(url, title, category, priority=2, description="") -> Optional[dict]:
    soup = get_page(url)
    time.sleep(DELAY)
    if not soup:
        return None
    content = page_text(soup)
    for table in soup.find_all("table"):
        t = table_to_text(table)
        if t:
            content += "\n\n[جدول]\n" + t
    if len(content) < 80:
        logger.warning(f"  Too short ({len(content)} chars), skipped")
        return None
    logger.info(f"  OK {len(content)} chars — {title[:50]}")
    return mk_item(title, content, url, category, description, priority)


# ============================================================
#  IT FACULTY  — CORRECT Joomla URLs
# ============================================================

IT = "https://it.yu.edu.jo"

IT_PAGES = [
    (f"{IT}/index.php/home-ar/2026-02-05-11-07-01",
     "نبذة عن كلية IT", "faculty", 1),
    (f"{IT}/index.php/home-ar/university-presidency-ar",
     "إدارة كلية IT (العميد والنواب)", "faculty", 1),
    (f"{IT}/index.php/home-ar/board-of-trustees-ar",
     "مجلس كلية IT", "faculty", 2),
    (f"{IT}/index.php/home-ar/2022-09-02-18-49-07",
     "استراتيجية كلية IT", "faculty", 2),
    (f"{IT}/index.php/home-ar/2022-09-07-21-24-02",
     "مختبرات وقاعات كلية IT", "faculty", 2),
    (f"{IT}/index.php/2022-09-03-20-14-42/2022-09-02-20-42-27",
     "قسم علوم الحاسوب (CS) - نبذة", "programs", 1),
    (f"{IT}/index.php/2022-09-03-20-14-42/2022-09-03-20-41-55",
     "قسم نظم المعلومات (CIS) - نبذة", "programs", 1),
    (f"{IT}/index.php/2022-09-03-20-14-42/2022-09-03-20-45-40",
     "قسم تكنولوجيا المعلومات (IT) - نبذة", "programs", 1),
    (f"{IT}/index.php/2022-09-18-22-16-54",
     "وصف مساقات CS و CIS", "programs", 1),
    (f"{IT}/index.php/2022-09-21-10-18-46",
     "وصف جميع مساقات كلية IT", "programs", 1),
    (f"{IT}/index.php/cys",
     "وصف مساقات الأمن السيبراني (CYS)", "programs", 1),
    (f"{IT}/index.php/2022-09-21-21-25-20",
     "وصف مساقات تكنولوجيا معلومات الأعمال (BIT)", "programs", 1),
    (f"{IT}/index.php/2022-09-21-10-15-34",
     "وصف مساقات قسم IT", "programs", 1),
    (f"{IT}/index.php/academic-programs-3",
     "البرامج الأكاديمية - كلية IT", "programs", 1),
]

# PDF Study Plans — pdfplumber extracts these
IT_PDFS = [
    (f"{IT}/images/Latest_plans/Bacha/ITCS-CS-Study_Plan_2024.pdf",
     "الخطة الدراسية - علوم الحاسوب 2024", "CS"),
    (f"{IT}/images/Latest_plans/Bacha/ITCS-CIS-Study_Plan_2024.pdf",
     "الخطة الدراسية - نظم المعلومات الحاسوبية 2024", "CIS"),
    (f"{IT}/images/Latest_plans/Bacha/ITCS-CYS-Study_Plan_2024.pdf",
     "الخطة الدراسية - الأمن السيبراني 2024", "CYS"),
    (f"{IT}/images/Latest_plans/Bacha/ITCS-BIT-Study_Plan_2024.pdf",
     "الخطة الدراسية - تكنولوجيا معلومات الأعمال 2024", "BIT"),
    (f"{IT}/images/Latest_plans/Bacha/ITCS-DRG-Study_Plan_2024.pdf",
     "الخطة الدراسية - الواقع الرقمي وتطوير الألعاب 2024", "VR"),
    (f"{IT}/images/CS/StudyPlan-CS-Arabic-2021.pdf",
     "الخطة الدراسية - علوم الحاسوب 2021", "CS"),
    (f"{IT}/images/CIS/StudyPlan-CIS-_Arabic-2021.pdf",
     "الخطة الدراسية - نظم المعلومات الحاسوبية 2021", "CIS"),
    (f"{IT}/images/CYS/Study_Plan-CYS-Arabic-2021.pdf",
     "الخطة الدراسية - الأمن السيبراني 2021", "CYS"),
]

# Guessed DA/AI PDF URLs
IT_PDF_GUESSES = [
    f"{IT}/images/Latest_plans/Bacha/ITCS-DA-Study_Plan_2024.pdf",
    f"{IT}/images/Latest_plans/Bacha/ITCS-AI-Study_Plan_2024.pdf",
    f"{IT}/images/Latest_plans/Bacha/ITCS-DSAI-Study_Plan_2024.pdf",
]


def _fix_reversed_arabic(text: str) -> str:
    tokens = re.split(r"(\s+)", text)
    fixed = []
    for tok in tokens:
        if not tok.strip():
            fixed.append(tok)
        elif re.match(r"^[A-Za-z0-9()/\-.,;:%+]+$", tok):
            fixed.append(tok)
        elif re.search(r"[\u0600-\u06FF]", tok):
            fixed.append(tok[::-1])
        else:
            fixed.append(tok)
    return "".join(fixed)


def scrape_pdf(url: str, title: str, code: str) -> Optional[dict]:
    try:
        import pdfplumber, io
        logger.info(f"  PDF: {url.split('/')[-1]}")
        r = session.get(url, timeout=30)
        r.raise_for_status()
        pages_text = []
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t.strip())
        raw = "\n\n".join(pages_text)
        garbled_markers = ["بوساحلا مولع", "تامولعملا ايجولونكت", "سويرولاكبلا"]
        if any(m in raw[:600] for m in garbled_markers):
            raw = _fix_reversed_arabic(raw)
            logger.info("  Fixed reversed Arabic")
        if len(raw) < 200:
            return None
        content = f"الخطة الدراسية لتخصص {code}\n\n{raw}"
        logger.info(f"  OK PDF {len(content)} chars — {title}")
        return mk_item(title, content, url, "programs", priority=1)
    except ImportError:
        logger.warning("  pdfplumber not installed. Run: pip install pdfplumber")
        return None
    except Exception as e:
        logger.error(f"  PDF error: {e}")
        return None


def scrape_it_faculty() -> List[dict]:
    items_list = []
    logger.info("\n" + "="*55)
    logger.info("Scraping IT Faculty...")
    logger.info("="*55)
    for url, title, cat, pri in IT_PAGES:
        logger.info(f"-> {title[:55]}")
        d = scrape_page(url, title, cat, pri)
        if d:
            items_list.append(d)
    logger.info("\n-> PDF Study Plans...")
    for url, title, code in IT_PDFS:
        d = scrape_pdf(url, title, code)
        if d:
            items_list.append(d)
        time.sleep(DELAY)
    for url in IT_PDF_GUESSES:
        try:
            r = session.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                d = scrape_pdf(url, "الخطة الدراسية - علم البيانات والذكاء الاصطناعي 2024", "DA")
                if d:
                    items_list.append(d)
                break
        except:
            pass
    logger.info(f"\nIT Faculty total: {len(items_list)} items")
    return items_list


# ============================================================
#  STUDENT AFFAIRS  (dsa.yu.edu.jo)
# ============================================================

DSA = "http://dsa.yu.edu.jo"

DSA_PAGES = [
    (f"{DSA}/index.php/admissionar/2022-10-12-06-17-13",
     "التأمين الصحي للطلاب", "general", 1),
    (f"{DSA}/index.php/2022-12-20-10-39-44/2022-12-20-10-41-56/2022-12-20-10-56-42",
     "السكنات الطلابية", "general", 1),
    (f"{DSA}/index.php/2022-12-20-10-39-44/2022-12-20-10-41-56/2022-12-20-10-56-46",
     "المركز الصحي للطلاب", "general", 1),
    (f"{DSA}/index.php/2022-12-20-10-39-44/2022-12-20-10-46-49/2022-12-20-10-56-45",
     "خدمات ذوي الاحتياجات الخاصة", "general", 2),
    (f"{DSA}/index.php/2022-12-20-10-39-44/2022-12-20-10-41-56/2022-12-20-10-56-45",
     "المرافق الرياضية", "general", 2),
    (f"{DSA}/index.php/2022-12-20-10-39-44/2022-12-20-10-41-56/social-rooms",
     "غرف استراحة الطلبة", "general", 2),
]


def scrape_student_affairs() -> List[dict]:
    items_list = []
    logger.info("\n" + "="*55)
    logger.info("Scraping Student Affairs (dsa.yu.edu.jo)...")
    logger.info("="*55)
    for url, title, cat, pri in DSA_PAGES:
        logger.info(f"-> {title}")
        d = scrape_page(url, title, cat, pri)
        if d:
            items_list.append(d)
    logger.info(f"\nStudent Affairs total: {len(items_list)} items")
    return items_list


# ============================================================
#  ADMISSION & REGISTRATION  (admreg.yu.edu.jo)
# ============================================================

ADM = "https://admreg.yu.edu.jo"

ADM_PAGES = [
    (f"{ADM}/index.php/admission-3/yuadmission-m",
     "كيفية الالتحاق بالجامعة - شروط القبول", "admission", 1),
    (f"{ADM}/index.php/admission-3/2019-05-25-09-15-07",
     "قبول التفوق الفني والرياضي", "admission", 2),
    (f"{ADM}/index.php/admission-3/2019-05-25-09-15-8",
     "الانتقال من الجامعات الأخرى", "admission", 1),
    (f"{ADM}/index.php/home-page-3/admreg-ar",
     "عن عمادة القبول والتسجيل", "admission", 2),
    (f"{ADM}/index.php/2019-05-24-14-23-58",
     "الخطط الدراسية - جميع الكليات", "programs", 1),
]


def scrape_admreg() -> List[dict]:
    items_list = []
    logger.info("\n" + "="*55)
    logger.info("Scraping Admission & Registration...")
    logger.info("="*55)
    for url, title, cat, pri in ADM_PAGES:
        logger.info(f"-> {title}")
        d = scrape_page(url, title, cat, pri)
        if d:
            items_list.append(d)
    logger.info(f"\nAdmission total: {len(items_list)} items")
    return items_list


# ============================================================
#  LIBRARY  (library.yu.edu.jo)
# ============================================================

def scrape_library() -> List[dict]:
    items_list = []
    logger.info("\n" + "="*55)
    logger.info("Scraping Library...")
    logger.info("="*55)
    for url in ["https://library.yu.edu.jo", "http://library.yu.edu.jo",
                "https://library.yu.edu.jo/index.php"]:
        logger.info(f"-> {url}")
        d = scrape_page(url, "المكتبة الجامعية", "general", 1)
        if d and len(d["content"]) > 200:
            items_list.append(d)
            break
    logger.info(f"\nLibrary total: {len(items_list)} items")
    return items_list


# ============================================================
#  STATIC HIGH-QUALITY DATA
# ============================================================

def get_static_data() -> List[dict]:
    items_list = []

    items_list.append(mk_item(
        "نبذة شاملة عن جامعة اليرموك",
        """جامعة اليرموك جامعة حكومية أردنية في إربد، تأسست 1976.
عدد الكليات: 16 | رئيس الجامعة: أ.د. مالك أحمد الشرايري
التعليم وجاهي بالكامل.

روابط رسمية:
- الجامعة: https://yu.edu.jo
- القبول والتسجيل: https://admreg.yu.edu.jo
- التعلم الإلكتروني: https://elearning.yu.edu.jo
- دليل أعضاء التدريس: https://fmd.yu.edu.jo

الكليات الستة عشر:
1. كلية الطب | 2. كلية الصيدلة | 3. كلية التمريض
4. كلية العلوم | 5. كلية الحجاوي للهندسة التكنولوجية
6. كلية تكنولوجيا المعلومات وعلوم الحاسوب
7. كلية الآداب | 8. كلية الأعمال
9. كلية الشريعة والدراسات الإسلامية
10. كلية العلوم التربوية | 11. كلية القانون
12. كلية الإعلام | 13. كلية التربية البدنية وعلوم الرياضة
14. كلية الآثار والأنثروبولوجيا
15. كلية السياحة والفنادق | 16. كلية الفنون الجميلة""",
        "https://yu.edu.jo/ar/about", "general", priority=1))

    items_list.append(mk_item(
        "كلية تكنولوجيا المعلومات وعلوم الحاسوب - نبذة شاملة",
        """كلية IT جامعة اليرموك | https://it.yu.edu.jo
حاصلة على اعتماد ABET الأمريكي الدولي

الإدارة:
- العميد: د. قاسم الردايدة
- نائب العميد: د. عماد الشواقفة
- نائب العميد للاعتماد والجودة: د. خالد النهار
- مساعد العميد لشؤون الطلبة: د. قصي الزعبي

رؤساء الأقسام:
- قسم CS: د. بلال عبدالغني
- قسم CIS: د. ايناس خشاشنة
- قسم IT: د. علاء حمود

برامج البكالوريوس (6 تخصصات — 134 ساعة معتمدة لكل منها):
1. علوم الحاسوب (CS) | 2. نظم المعلومات الحاسوبية (CIS)
3. تكنولوجيا معلومات الأعمال (BIT)
4. علم البيانات والذكاء الاصطناعي (DA)
5. الأمن السيبراني (CYS)
6. الواقع الرقمي وتطوير الألعاب (VR)

ماجستير: ذكاء الأعمال | الذكاء الاصطناعي
توزيع الساعات: 15 جامعة + 119 كلية وتخصص | مدة: 4 سنوات""",
        "https://it.yu.edu.jo", "faculty", priority=1))

    programs = [
        ("علوم الحاسوب (CS)", "CS", "Computer Science", ["2021","2024"],
         ["مطور برمجيات","مهندس DevOps","باحث AI","مهندس أنظمة"],
         ["CS111 برمجة","CS253 خوارزميات","CS332 شبكات","CS499 مشروع تخرج"]),
        ("نظم المعلومات الحاسوبية (CIS)", "CIS", "Computer Information Systems",
         ["2021","2024"], ["محلل أنظمة","مدير قواعد بيانات","مطور تطبيقات أعمال"],
         ["CIS120 قواعد بيانات","CIS240 هندسة برمجيات","CIS260 نظم قواعد بيانات"]),
        ("تكنولوجيا معلومات الأعمال (BIT)", "BIT", "Business IT",
         ["2021","2024"], ["محلل أعمال","مدير مشاريع تقنية","مستشار تحول رقمي"],
         ["BIT222 ريادة أعمال","BIT381 تطوير إنترنت"]),
        ("علم البيانات والذكاء الاصطناعي (DA)", "DA", "Data Science & AI",
         ["2024"], ["عالم بيانات","مهندس ML","محلل بيانات","مطور AI"],
         ["DA202 علم البيانات","DA350 تعلم الآلة","مساقات Python وإحصاء"]),
        ("الأمن السيبراني (CYS)", "CYS", "Cyber Security",
         ["2021","2024"], ["محلل أمن معلومات","مختبر اختراق","مهندس أمن شبكات"],
         ["CYS230 مبادئ الأمن","مساقات أمن شبكات واختبار اختراق"]),
        ("الواقع الرقمي وتطوير الألعاب (VR)", "VR", "Digital Reality & Game Dev",
         ["2024"], ["مطور ألعاب","مصمم VR/AR","مطور تطبيقات افتراضية"],
         ["مساقات تطوير ألعاب 2D/3D","مساقات VR/AR"]),
    ]
    for major_ar, code, major_en, batches, careers, courses in programs:
        content = (
            f"تخصص {major_ar} — كلية IT جامعة اليرموك\n"
            f"الاسم الإنجليزي: {major_en} ({code})\n"
            f"الساعات المعتمدة: 134 ساعة | الدفعات: {', '.join(batches)}\n\n"
            f"المسارات المهنية:\n" + "\n".join(f"• {c}" for c in careers) + "\n\n"
            f"مساقات أساسية:\n" + "\n".join(f"• {c}" for c in courses) + "\n\n"
            f"للخطة التفصيلية حسب دفعتك: https://admreg.yu.edu.jo"
        )
        items_list.append(mk_item(
            f"تخصص {major_ar} - كلية IT",
            content, f"https://it.yu.edu.jo/index.php/{code.lower()}",
            "programs", priority=1))

    items_list.append(mk_item(
        "المكتبة الجامعية - خدماتها وكيفية الاستعارة",
        """مكتبة الحسين بن طلال — جامعة اليرموك | library.yu.edu.jo

الخدمات:
• استعارة الكتب: حتى 5 كتب / أسبوعان (قابلة للتجديد)
• قواعد بيانات: IEEE, ACM, Elsevier, Springer
• قاعات دراسة هادئة وقاعات مجموعات
• خدمات طباعة ونسخ ومسح ضوئي

كيف تستعير كتاباً:
1. ابحث على library.yu.edu.jo
2. سجّل رقم التصنيف
3. ابحث عنه في الرفوف
4. توجه لمكتب الاستعارة ببطاقتك الجامعية

ساعات العمل:
• الأحد - الخميس: 8:00 ص - 9:00 م
• السبت: 9:00 ص - 2:00 ظ | الجمعة: مغلقة""",
        "https://library.yu.edu.jo", "general", priority=1))

    items_list.append(mk_item(
        "عمادة شؤون الطلبة - الخدمات الكاملة",
        """عمادة شؤون الطلبة (DSA) — dsa.yu.edu.jo

الخدمات:
1. التأمين الصحي (مدفوع ضمن الرسوم)
2. السكنات الطلابية (ذكور/إناث) — الأولوية لخارج إربد والمتفوقين
3. المركز الصحي داخل الحرم
4. مركز دعم ذوي الاحتياجات الخاصة
5. الأندية الطلابية: DEVIT, روبوتيكس, ريادة أعمال, YUCPC
6. الإرشاد الأكاديمي والتوجيه المهني
7. المرافق الرياضية (ملاعب, صالات)
8. غرف الاستراحة والمناطق الاجتماعية

للتسجيل في السكن: قدّم طلباً في بداية كل فصل""",
        "http://dsa.yu.edu.jo", "general", priority=1))

    items_list.append(mk_item(
        "نظام التعلم الإلكتروني (Moodle)",
        """نظام التعلم الإلكتروني — https://elearning.yu.edu.jo

ما تجده على المنصة:
• ملفات المحاضرات (PDF, PPT, فيديو)
• تسليم الواجبات والمشاريع
• الاختبارات القصيرة (Quizzes)
• الإعلانات والدرجات
• منتدى التواصل

كيفية الدخول:
1. elearning.yu.edu.jo
2. اسم المستخدم: رقمك الجامعي
3. كلمة المرور: تُحدد عند أول تسجيل

نسيت كلمة المرور؟ استخدم "Forgot Password" أو راجع قسم تقنية المعلومات.
ملاحظة: التعليم وجاهي 100% — Elearning مكمّل وليس بديلاً.""",
        "https://elearning.yu.edu.jo", "general", priority=1))

    items_list.append(mk_item(
        "القبول والتسجيل - متطلبات وإجراءات",
        """عمادة القبول والتسجيل — https://admreg.yu.edu.jo

للبكالوريوس:
• شهادة التوجيهي أو ما يعادلها
• القبول عبر نظام القبول الموحد الأردني
• الحد الأدنى يختلف حسب التخصص

التسجيل الفصلي:
1. الدخول لـ admreg.yu.edu.jo في الوقت المحدد
2. اختيار المساقات مع مراعاة المتطلبات السابقة
3. مراجعة المرشد الأكاديمي عند الحاجة
4. دفع الرسوم خلال المدة المحددة

المنح والإعفاءات:
• منح تفوق أكاديمي | أبناء الشهداء
• ذوو الدخل المحدود | أبناء موظفي الجامعة

الانتقال من جامعة أخرى:
• طلب + كشف علامات مصدّق → دراسته من قِبل القسم""",
        "https://admreg.yu.edu.jo", "admission", priority=1))

    items_list.append(mk_item(
        "كلية الحجاوي للهندسة التكنولوجية",
        """كلية الحجاوي — جامعة اليرموك
العميد: د. عوض سميران الزبن | مدة الدراسة: 5 سنوات

التخصصات (6):
1. هندسة الحاسوب | 2. هندسة الاتصالات والإلكترونيات
3. هندسة الطاقة الكهربائية | 4. هندسة الميكاترونيكس
5. الهندسة الصناعية وإدارة هندسية | 6. الهندسة المدنية

الفرق عن كلية IT:
• الحجاوي: هندسة تقنية (hardware, circuits, civil)
• IT: برمجيات وأنظمة (software, data, security)""",
        "https://yu.edu.jo/ar/hijjawi", "faculty", priority=1))

    items_list.append(mk_item(
        "الدراسات العليا - ماجستير ودكتوراه",
        """الدراسات العليا — graduatestudies.yu.edu.jo

الأنواع:
• ماجستير بالرسالة: 33 ساعة + رسالة بحثية
• ماجستير بالامتحان الشامل: 36 ساعة
• دكتوراه (PhD)

ماجستير كلية IT:
1. ذكاء الأعمال (رسالة 33ساعة / شامل 36ساعة)
2. الذكاء الاصطناعي (شامل 36ساعة)

متطلبات القبول:
• بكالوريوس بمعدل ≥ 70% (2.5/4)
• اختبار كفاءة إنجليزية (TOEFL/IELTS)
• مقابلة في بعض التخصصات

للتقديم: admreg.yu.edu.jo""",
        "https://graduatestudies.yu.edu.jo", "programs", priority=1))

    yt_resources = [
        ("مقدمة في البرمجة / Python",
         ["Bro Code (EN) — Python/Java | youtube.com/@BroCodez",
          "CS50 Harvard (EN) | youtube.com/@cs50",
          "Elzero Web School (AR) | youtube.com/@ElzeroWebSchool"]),
        ("تراكيب البيانات والخوارزميات (CS253)",
         ["Abdul Bari (EN) | youtube.com/@abdul_bari",
          "WilliamFiset (EN) — Data Structures"]),
        ("قواعد البيانات (CIS260)",
         ["Caleb Curry (EN) — SQL & DB",
          "حسين الربيعي (AR)"]),
        ("الشبكات (CS332)",
         ["NetworkChuck (EN) | youtube.com/@NetworkChuck",
          "Professor Messer (EN)"]),
        ("الأمن السيبراني (CYS)",
         ["David Bombal (EN) | youtube.com/@davidbombal",
          "John Hammond (EN) | youtube.com/@_JohnHammond"]),
        ("الذكاء الاصطناعي (DA/AI)",
         ["3Blue1Brown (EN) | youtube.com/@3blue1brown",
          "Krish Naik (EN)", "Sentdex (EN) | youtube.com/@sentdex"]),
        ("تطوير الويب",
         ["Traversy Media (EN) | youtube.com/@TraversyMedia",
          "Elzero Web School (AR)",
          "Hussein Nasser (EN/AR) | youtube.com/@hnasr"]),
        ("هندسة البرمجيات (CIS240)",
         ["Fireship (EN) | youtube.com/@Fireship",
          "Hussein Nasser — Software Architecture"]),
    ]
    for course_name, resources in yt_resources:
        content = (f"مصادر يوتيوب مجانية لمادة: {course_name}\n\n"
                   + "\n".join("• " + r for r in resources)
                   + "\n\nمجانية على YouTube — ننصح بها جنباً مع محاضرات الكلية.")
        items_list.append(mk_item(
            f"مصادر يوتيوب - {course_name}",
            content, "https://youtube.com", "programs", priority=2))

    items_list.append(mk_item(
        "الخدمات والمحلات القريبة من جامعة اليرموك",
        """المحلات القريبة من حرم اليرموك — إربد

القرطاسية والطباعة:
• شارع الجامعة: محلات قرطاسية وطباعة قرب البوابة الرئيسية
• داخل الجامعة: طباعة في مبنى المكتبة وبعض الكليات

المطاعم:
• كافتيريات داخل الحرم الجامعي
• مطاعم متعددة على شارع الجامعة

خدمات أخرى:
• صيدليات على شارع الجامعة
• بنوك وصرافات قرب البوابة الرئيسية
• مقاهي إنترنت في المنطقة

المواصلات:
• باصات تربط الجامعة بإربد
• Uber/Careem متاحة في إربد""",
        "https://yu.edu.jo", "general", priority=2))

    return items_list


# ============================================================
#  MERGE & SAVE
# ============================================================

def load_existing(filepath: str) -> List[dict]:
    path = Path(filepath)
    if path.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} existing items from {filepath}")
            return data
        except Exception as e:
            logger.error(f"Could not load: {e}")
    return []


def merge(existing: List[dict], new_items: List[dict]) -> List[dict]:
    existing_urls = {it.get("url", "") for it in existing}
    merged = list(existing)
    added = 0
    for it in new_items:
        url = it.get("url", "")
        if url and url in existing_urls:
            continue
        merged.append(it)
        existing_urls.add(url)
        added += 1
    logger.info(f"Added {added} new items | Total: {len(merged)}")
    return merged


# ============================================================
#  MAIN
# ============================================================

def main():
    logger.info("YU Scraper v3.0 — Fixed URL Patterns")
    logger.info(f"Output: {OUTPUT_FILE}\n")

    all_new: List[dict] = []

    logger.info("Building static data...")
    all_new += get_static_data()
    logger.info(f"Static: {len(all_new)} items\n")

    all_new += scrape_it_faculty()
    all_new += scrape_student_affairs()
    all_new += scrape_admreg()
    all_new += scrape_library()

    logger.info("\nMerging with existing data...")
    existing = load_existing(EXISTING_FILE)
    final = merge(existing, all_new)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    logger.info(f"\nSaved {len(final)} items to {OUTPUT_FILE}")

    from collections import Counter
    cats = Counter(it.get("category", "?") for it in final)
    logger.info("\nCategories:")
    for cat, count in cats.most_common():
        logger.info(f"  {cat:<15} {count}")

    logger.info("""
Next steps:
  1. Review data/yarmouk_data_new.json
  2. If OK: copy data/yarmouk_data_new.json data/yarmouk_data.json
  3. Restart bot — it rebuilds automatically
""")


if __name__ == "__main__":
    main()