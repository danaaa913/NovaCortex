"""
YU Comprehensive Scraper v2.0
يجيب بيانات جامعة اليرموك كاملة بـ JSON نظيف جاهز للـ RAG
شغّله على جهازك: python scripts/update_facts_db.py
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
#  CONFIG
# ============================================================
OUTPUT_FILE = str(Path(__file__).resolve().parents[1] / "data" / "yarmouk_data_new.json")
DATA_FILE = str(Path(__file__).resolve().parents[1] / "data" / "yarmouk_data.json")
DELAY = 1.2          # ثانية بين كل طلب — لا تحط أقل من 1
TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ar,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)

# ============================================================
#  HELPER FUNCTIONS
# ============================================================

def get_page(url: str, retries: int = 3) -> Optional[BeautifulSoup]:
    """Fetch a page and return BeautifulSoup, or None on failure."""
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or 'utf-8'
            return BeautifulSoup(r.text, 'lxml')
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 * (attempt + 1))
    logger.error(f"Failed to fetch: {url}")
    return None


def clean_text(text: str) -> str:
    """Remove extra whitespace and junk."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e]', '', text)  # Remove bidi markers
    return text


def make_item(title: str, content: str, url: str, category: str,
              description: str = "", priority: int = 2) -> dict:
    """Build a standard data item."""
    return {
        "title": clean_text(title),
        "description": clean_text(description),
        "content": clean_text(content),
        "url": url,
        "category": category,
        "priority": priority,
        "scraped_at": datetime.now().isoformat()
    }


def extract_main_content(soup: BeautifulSoup) -> str:
    """Extract meaningful text from a page, skipping nav/footer."""
    # Remove noise elements
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style',
                               'noscript', '.breadcrumb', '.pagination']):
        tag.decompose()

    # Try common content containers
    for selector in [
        'article', 'main', '.content', '#content',
        '.page-content', '.entry-content', '.post-content',
        '.container .row', 'section'
    ]:
        el = soup.select_one(selector)
        if el and len(el.get_text(strip=True)) > 200:
            return clean_text(el.get_text(separator='\n', strip=True))

    # Fallback: body
    body = soup.find('body')
    if body:
        return clean_text(body.get_text(separator='\n', strip=True))
    return ""


def extract_table_as_text(table) -> str:
    """Convert HTML table to readable text."""
    rows = []
    for tr in table.find_all('tr'):
        cells = [clean_text(td.get_text()) for td in tr.find_all(['td', 'th'])]
        if any(cells):
            rows.append(' | '.join(filter(None, cells)))
    return '\n'.join(rows)

# ============================================================
#  IT FACULTY SCRAPER  (it.yu.edu.jo)
# ============================================================

IT_BASE = "http://it.yu.edu.jo"

IT_PAGES = [
    # (url, title, category, priority, description)
    (f"{IT_BASE}/ar",                           "كلية تكنولوجيا المعلومات - الرئيسية",    "faculty",   1, "الصفحة الرئيسية لكلية IT"),
    (f"{IT_BASE}/ar/about",                     "نبذة عن كلية IT",                        "faculty",   1, ""),
    (f"{IT_BASE}/ar/administration",             "إدارة الكلية",                           "faculty",   1, "عميد ونواب عميد كلية IT"),
    (f"{IT_BASE}/ar/cs",                        "قسم علوم الحاسوب",                       "programs",  1, ""),
    (f"{IT_BASE}/ar/cis",                       "قسم نظم المعلومات",                      "programs",  1, ""),
    (f"{IT_BASE}/ar/it-dept",                   "قسم تكنولوجيا المعلومات",                "programs",  1, ""),
    (f"{IT_BASE}/ar/graduate",                  "الدراسات العليا - كلية IT",               "programs",  1, "ماجستير ودكتوراه"),
    (f"{IT_BASE}/ar/labs",                      "المختبرات والقاعات - كلية IT",            "faculty",   2, ""),
    (f"{IT_BASE}/ar/news",                      "أخبار كلية IT",                          "faculty",   3, ""),
    (f"{IT_BASE}/ar/achievements",              "إنجازات كلية IT",                        "faculty",   2, ""),
    (f"{IT_BASE}/ar/contact",                   "اتصل بنا - كلية IT",                     "faculty",   2, ""),
    # Study plans - the most important pages
    (f"{IT_BASE}/ar/study-plans",               "الخطط الدراسية - كلية IT",               "programs",  1, ""),
    (f"{IT_BASE}/ar/cs-study-plan",             "الخطة الدراسية - علوم الحاسوب",          "programs",  1, ""),
    (f"{IT_BASE}/ar/cis-study-plan",            "الخطة الدراسية - نظم المعلومات",         "programs",  1, ""),
    (f"{IT_BASE}/ar/it-study-plan",             "الخطة الدراسية - تكنولوجيا المعلومات",   "programs",  1, ""),
    (f"{IT_BASE}/ar/ai-study-plan",             "الخطة الدراسية - علم البيانات والذكاء الاصطناعي", "programs", 1, ""),
    (f"{IT_BASE}/ar/cys-study-plan",            "الخطة الدراسية - الأمن السيبراني",       "programs",  1, ""),
    (f"{IT_BASE}/ar/bit-study-plan",            "الخطة الدراسية - تكنولوجيا معلومات الأعمال", "programs", 1, ""),
    (f"{IT_BASE}/ar/vr-study-plan",             "الخطة الدراسية - الواقع الرقمي وتطوير الألعاب", "programs", 1, ""),
    # FMD (Faculty Member Directory) for IT
    ("http://fmd.yu.edu.jo/it",                 "دليل أعضاء هيئة التدريس - IT",           "faculty",   1, ""),
]

# Alternative URL patterns to try
IT_URL_ALTERNATIVES = {
    "study-plans": [
        "/ar/study-plans", "/en/study-plans", "/ar/studyplans",
        "/ar/academic/study-plans", "/ar/programs"
    ],
    "about": ["/ar/about", "/ar/about-us", "/ar/introduction"],
    "administration": ["/ar/administration", "/ar/admin", "/ar/management", "/ar/council"],
}


def scrape_it_study_plans_deep(soup: BeautifulSoup, base_url: str, items: list):
    """
    Deeply scrape study plans from IT faculty.
    Looks for links to individual program pages.
    """
    if not soup:
        return

    # Look for links that contain study plan keywords
    plan_keywords = ['خطة', 'study', 'plan', 'cs', 'cis', 'bit', 'cys', 'ai', 'vr', 'it-dept']
    links = soup.find_all('a', href=True)

    found_links = set()
    for link in links:
        href = link['href']
        text = clean_text(link.get_text())
        full_url = urljoin(base_url, href)

        if any(kw in href.lower() or kw in text.lower() for kw in plan_keywords):
            if IT_BASE in full_url and full_url not in found_links:
                found_links.add(full_url)
                logger.info(f"  Found study plan link: {full_url}")

    for url in found_links:
        time.sleep(DELAY)
        sub_soup = get_page(url)
        if sub_soup:
            content = extract_main_content(sub_soup)
            # Extract tables
            tables = sub_soup.find_all('table')
            table_text = ""
            for table in tables:
                table_text += "\n" + extract_table_as_text(table)

            full_content = content
            if table_text.strip():
                full_content = content + "\n\n[جدول المساقات]\n" + table_text

            if len(full_content) > 200:
                title_tag = sub_soup.find('h1') or sub_soup.find('h2')
                title = clean_text(title_tag.get_text()) if title_tag else url.split('/')[-1]
                items.append(make_item(
                    title=f"الخطة الدراسية - {title}",
                    content=full_content,
                    url=url,
                    category="programs",
                    priority=1
                ))


def scrape_it_faculty() -> list:
    """Scrape all IT faculty pages."""
    items = []
    logger.info("=" * 50)
    logger.info("Scraping IT Faculty...")
    logger.info("=" * 50)

    for url, title, category, priority, description in IT_PAGES:
        logger.info(f"Fetching: {url}")
        soup = get_page(url)
        time.sleep(DELAY)

        if not soup:
            # Try alternative URLs
            for alt_path in IT_URL_ALTERNATIVES.get(url.split('/')[-1], []):
                alt_url = IT_BASE + alt_path
                logger.info(f"  Trying alternative: {alt_url}")
                soup = get_page(alt_url)
                if soup:
                    url = alt_url
                    break
            time.sleep(DELAY)

        if not soup:
            logger.warning(f"  Skipping (no response): {url}")
            continue

        content = extract_main_content(soup)

        # For study plan pages, also extract tables
        tables = soup.find_all('table')
        table_text = ""
        for table in tables:
            t = extract_table_as_text(table)
            if t:
                table_text += "\n\n" + t

        if table_text:
            content = content + "\n\n[بيانات منظمة]\n" + table_text

        if len(content) < 100:
            logger.warning(f"  Very short content ({len(content)} chars), skipping")
            continue

        items.append(make_item(title, content, url, category, description, priority))
        logger.info(f"  ✓ Got {len(content)} chars")

        # Deep crawl for study plans page
        if 'study-plan' in url or 'خطط' in title:
            scrape_it_study_plans_deep(soup, url, items)

    return items

# ============================================================
#  MAIN YU WEBSITE  (yu.edu.jo)
# ============================================================

YU_BASE = "http://www.yu.edu.jo"

YU_PAGES = [
    # General University Info
    (f"{YU_BASE}/ar",                                  "جامعة اليرموك - الرئيسية",              "general",   1),
    (f"{YU_BASE}/ar/about",                            "عن جامعة اليرموك",                      "general",   1),
    (f"{YU_BASE}/ar/president",                        "رئيس الجامعة",                          "general",   1),
    (f"{YU_BASE}/ar/university-council",               "مجلس الجامعة",                          "general",   2),
    (f"{YU_BASE}/ar/faculties",                        "الكليات - جامعة اليرموك",               "faculty",   1),
    (f"{YU_BASE}/ar/administration",                   "الإدارة العليا",                        "general",   1),
    (f"{YU_BASE}/ar/strategic-plan",                   "الخطة الاستراتيجية",                    "general",   2),
    (f"{YU_BASE}/ar/rankings",                         "تصنيفات الجامعة",                       "general",   2),

    # Admission & Registration
    ("http://admreg.yu.edu.jo/ar",                     "القبول والتسجيل",                       "admission", 1),
    ("http://admreg.yu.edu.jo/ar/admission",           "شروط القبول",                           "admission", 1),
    ("http://admreg.yu.edu.jo/ar/fees",                "الرسوم الدراسية",                       "fees",      1),
    ("http://admreg.yu.edu.jo/ar/scholarships",        "المنح الدراسية",                        "fees",      1),
    ("http://admreg.yu.edu.jo/ar/transfer",            "التحويل والانتساب",                     "admission", 2),
    ("http://admreg.yu.edu.jo/ar/grad-admission",      "قبول الدراسات العليا",                  "admission", 1),
    ("http://admreg.yu.edu.jo/ar/faq",                 "الأسئلة الشائعة - القبول والتسجيل",     "admission", 1),

    # Student Affairs
    (f"{YU_BASE}/ar/student-affairs",                  "عمادة شؤون الطلبة",                     "general",   1),
    (f"{YU_BASE}/ar/student-housing",                  "السكنات الطلابية",                      "general",   1),
    (f"{YU_BASE}/ar/health-insurance",                 "التأمين الصحي للطلاب",                  "general",   1),
    (f"{YU_BASE}/ar/student-clubs",                    "الأندية الطلابية",                      "general",   2),
    (f"{YU_BASE}/ar/student-guide",                    "دليل الطالب",                           "general",   1),

    # Library
    (f"{YU_BASE}/ar/library",                          "المكتبة الجامعية",                      "general",   1),
    (f"{YU_BASE}/ar/library/services",                 "خدمات المكتبة",                         "general",   1),
    (f"{YU_BASE}/ar/library/borrowing",                "استعارة الكتب",                         "general",   1),

    # E-Learning
    ("https://elearning.yu.edu.jo/ar",                 "نظام التعلم الإلكتروني",                "general",   1),
    (f"{YU_BASE}/ar/elearning",                        "التعلم الإلكتروني - اليرموك",           "general",   1),

    # Faculties - individual pages
    (f"{YU_BASE}/ar/medicine",                         "كلية الطب",                             "faculty",   2),
    (f"{YU_BASE}/ar/pharmacy",                         "كلية الصيدلة",                          "faculty",   2),
    (f"{YU_BASE}/ar/nursing",                          "كلية التمريض",                          "faculty",   2),
    (f"{YU_BASE}/ar/science",                          "كلية العلوم",                           "faculty",   2),
    (f"{YU_BASE}/ar/hijjawi",                          "كلية الحجاوي للهندسة التكنولوجية",      "faculty",   2),
    (f"{YU_BASE}/ar/arts",                             "كلية الآداب",                           "faculty",   2),
    (f"{YU_BASE}/ar/business",                         "كلية الأعمال",                          "faculty",   2),
    (f"{YU_BASE}/ar/education",                        "كلية العلوم التربوية",                  "faculty",   2),
    (f"{YU_BASE}/ar/sharia",                           "كلية الشريعة والدراسات الإسلامية",      "faculty",   2),
    (f"{YU_BASE}/ar/law",                              "كلية القانون",                          "faculty",   2),
    (f"{YU_BASE}/ar/mass-comm",                        "كلية الإعلام",                          "faculty",   2),
    (f"{YU_BASE}/ar/physical-edu",                     "كلية التربية البدنية وعلوم الرياضة",    "faculty",   2),
    (f"{YU_BASE}/ar/archaeology",                      "كلية الآثار والأنثروبولوجيا",           "faculty",   2),
    (f"{YU_BASE}/ar/tourism",                          "كلية السياحة والفنادق",                 "faculty",   2),
    (f"{YU_BASE}/ar/fine-arts",                        "كلية الفنون الجميلة",                   "faculty",   2),

    # Maps & Campus
    (f"{YU_BASE}/ar/campus-map",                       "خريطة الحرم الجامعي",                   "general",   2),
    (f"{YU_BASE}/ar/contact",                          "اتصل بنا - الجامعة",                    "general",   2),

    # Scientific Research
    (f"{YU_BASE}/ar/research",                         "عمادة البحث العلمي",                    "general",   2),
    (f"{YU_BASE}/ar/graduate-studies",                 "عمادة الدراسات العليا",                  "general",   1),

    # Alternative URL patterns
    ("http://yu.edu.jo/ar/faculties",                  "الكليات",                               "faculty",   1),
    ("http://yu.edu.jo/ar/student-affairs",            "شؤون الطلبة",                           "general",   1),
]

# Additional IT Faculty sub-pages based on typical Drupal/Joomla structure
IT_ADDITIONAL = [
    (f"{IT_BASE}/ar/node/1",    "IT - صفحة 1",  "faculty", 2),
    (f"{IT_BASE}/ar/node/2",    "IT - صفحة 2",  "faculty", 2),
    # Course descriptions
    (f"{IT_BASE}/ar/cs-courses",     "وصف مساقات علوم الحاسوب",     "programs", 1),
    (f"{IT_BASE}/ar/cis-courses",    "وصف مساقات نظم المعلومات",    "programs", 1),
    (f"{IT_BASE}/ar/it-courses",     "وصف مساقات تكنولوجيا المعلومات", "programs", 1),
    (f"{IT_BASE}/ar/course-desc",    "وصف المساقات",                  "programs", 1),
    (f"{IT_BASE}/ar/courses",        "المساقات الدراسية",             "programs", 1),
]


def scrape_yu_main() -> list:
    """Scrape main YU website pages."""
    items = []
    logger.info("=" * 50)
    logger.info("Scraping YU Main Website...")
    logger.info("=" * 50)

    all_pages = YU_PAGES + IT_ADDITIONAL

    seen_urls = set()
    for page_data in all_pages:
        url, title, category, priority = page_data
        if url in seen_urls:
            continue
        seen_urls.add(url)

        logger.info(f"Fetching: {url}")
        soup = get_page(url)
        time.sleep(DELAY)

        if not soup:
            logger.warning(f"  Skipping: {url}")
            continue

        content = extract_main_content(soup)

        # Extract tables for fees/structured data
        tables = soup.find_all('table')
        for table in tables:
            t_text = extract_table_as_text(table)
            if t_text:
                content += "\n\n[بيانات منظمة]\n" + t_text

        if len(content) < 80:
            logger.warning(f"  Too short, skipping")
            continue

        items.append(make_item(title, content, url, category, priority=priority))
        logger.info(f"  ✓ {len(content)} chars")

    return items

# ============================================================
#  STATIC / HARDCODED HIGH-QUALITY DATA
# ============================================================

def get_static_data() -> list:
    """
    بيانات ثابتة عالية الجودة — موثوقة 100% وما تحتاج سكرابنغ.
    هاي الداتا مش هتتغير كثير فهي مناسبة تكون static.
    """
    items = []

    # ── 1. University Overview ──────────────────────────────
    items.append(make_item(
        title="نبذة شاملة عن جامعة اليرموك",
        content="""جامعة اليرموك هي جامعة حكومية أردنية تقع في مدينة إربد، تأسست عام 1976.
تُعدّ من أبرز الجامعات الأردنية والعربية، وحصلت على اعتمادات دولية متعددة.

المعلومات الأساسية:
- النوع: جامعة حكومية
- السنة التأسيسية: 1976
- الموقع: إربد، الأردن
- عدد الكليات: 16 كلية
- الموقع الرسمي: yu.edu.jo
- نظام التعليم: وجاهي بالكامل (لا يوجد تعليم عن بُعد للدرجات الجامعية)
- رئيس الجامعة: أ.د. مالك أحمد الشرايري

روابط مهمة:
- الموقع الرسمي: https://yu.edu.jo
- القبول والتسجيل: https://admreg.yu.edu.jo
- التعلم الإلكتروني: https://elearning.yu.edu.jo
- دليل أعضاء الهيئة التدريسية: https://fmd.yu.edu.jo

الكليات الستة عشر:
1. كلية الطب
2. كلية الصيدلة
3. كلية التمريض
4. كلية العلوم
5. كلية الحجاوي للهندسة التكنولوجية
6. كلية تكنولوجيا المعلومات وعلوم الحاسوب
7. كلية الآداب
8. كلية الأعمال
9. كلية الشريعة والدراسات الإسلامية
10. كلية العلوم التربوية
11. كلية القانون
12. كلية الإعلام
13. كلية التربية البدنية وعلوم الرياضة
14. كلية الآثار والأنثروبولوجيا
15. كلية السياحة والفنادق
16. كلية الفنون الجميلة""",
        url="https://yu.edu.jo/ar/about",
        category="general",
        priority=1
    ))

    # ── 2. IT Faculty Full Overview ─────────────────────────
    items.append(make_item(
        title="كلية تكنولوجيا المعلومات وعلوم الحاسوب - نبذة شاملة",
        content="""كلية تكنولوجيا المعلومات وعلوم الحاسوب (IT Faculty) في جامعة اليرموك.
تُعدّ من أبرز كليات تكنولوجيا المعلومات في الأردن وحاصلة على الاعتماد الأمريكي ABET.

الإدارة:
- العميد: د. قاسم الردايدة
- نائب العميد: د. عماد الشواقفة
- نائب العميد لشؤون الاعتماد والجودة: د. خالد النهار
- مساعد العميد لشؤون الطلبة: د. قصي الزعبي

الأقسام ورؤساؤها:
- قسم علوم الحاسوب (CS): رئيس القسم د. بلال عبدالغني
- قسم نظم المعلومات (CIS): رئيسة القسم د. ايناس خشاشنة
- قسم تكنولوجيا المعلومات (IT): رئيس القسم د. علاء حمود

برامج البكالوريوس (6 تخصصات - كل منها 134 ساعة معتمدة):
1. علوم الحاسوب (Computer Science - CS)
2. نظم المعلومات الحاسوبية (Computer Information Systems - CIS)
3. تكنولوجيا معلومات الأعمال (Business IT - BIT)
4. علم البيانات والذكاء الاصطناعي (Data Science & AI - DA)
5. الأمن السيبراني (Cyber Security - CYS)
6. الواقع الرقمي وتطوير الألعاب (Digital Reality & Game Development - VR)

برامج الماجستير:
- ماجستير ذكاء الأعمال (نظام رسالة + نظام امتحان شامل)
- ماجستير الذكاء الاصطناعي (نظام امتحان شامل)

الموقع الرسمي: http://it.yu.edu.jo""",
        url="http://it.yu.edu.jo/ar",
        category="faculty",
        priority=1
    ))

    # ── 3. IT Study Plans Structured ───────────────────────
    study_plans = [
        {
            "major": "علوم الحاسوب (CS)",
            "major_en": "Computer Science",
            "code": "CS",
            "total_hours": 134,
            "batches": ["2021", "2024"],
            "description": "يُعنى بدراسة الخوارزميات، البرمجة، الذكاء الاصطناعي، وتطوير البرمجيات",
            "career_paths": ["مطور برمجيات", "مهندس DevOps", "باحث في الذكاء الاصطناعي", "مهندس أنظمة"],
            "core_courses_2024": [
                "CS111 - مقدمة في البرمجة (3 ساعات)",
                "CS130 - أساسيات نظم التشغيل (3 ساعات)",
                "CS142 - منطق تصميم الحاسوب (3 ساعات)",
                "CS210 - البرمجة الكائنية (3 ساعات)",
                "CS253 - تراكيب البيانات والخوارزميات (3 ساعات)",
                "CS310 - برمجة متقدمة (3 ساعات)",
                "CS331 - نظم التشغيل (3 ساعات)",
                "CS332 - تراسل البيانات والشبكات (3 ساعات)",
                "CS355 - حل المسائل (3 ساعات)",
                "CS499A - مشروع تخرج 1 (3 ساعات)",
                "CS499B - مشروع تخرج 2 (3 ساعات)",
            ]
        },
        {
            "major": "نظم المعلومات الحاسوبية (CIS)",
            "major_en": "Computer Information Systems",
            "code": "CIS",
            "total_hours": 134,
            "batches": ["2021", "2024"],
            "description": "يجمع بين تقنية المعلومات وإدارة الأعمال وتطوير قواعد البيانات",
            "career_paths": ["محلل أنظمة", "مدير قواعد بيانات", "مطور تطبيقات أعمال", "مستشار تقني"],
        },
        {
            "major": "تكنولوجيا معلومات الأعمال (BIT)",
            "major_en": "Business Information Technology",
            "code": "BIT",
            "total_hours": 134,
            "batches": ["2021", "2024"],
            "description": "يركز على استخدام التكنولوجيا في دعم قرارات الأعمال والتحول الرقمي",
            "career_paths": ["محلل أعمال", "مدير مشاريع تقنية", "مستشار تحول رقمي"],
        },
        {
            "major": "علم البيانات والذكاء الاصطناعي (DA/AI)",
            "major_en": "Data Science and Artificial Intelligence",
            "code": "DA",
            "total_hours": 134,
            "batches": ["2024"],
            "description": "تخصص حديث يجمع تحليل البيانات الضخمة مع تقنيات الذكاء الاصطناعي والتعلم الآلي",
            "career_paths": ["عالم بيانات", "مهندس ML", "محلل بيانات", "مطور تطبيقات AI"],
        },
        {
            "major": "الأمن السيبراني (CYS)",
            "major_en": "Cyber Security",
            "code": "CYS",
            "total_hours": 134,
            "batches": ["2021", "2024"],
            "description": "يُعنى بحماية الأنظمة والشبكات وأمن المعلومات",
            "career_paths": ["محلل أمن معلومات", "مختبر اختراق", "مهندس أمن شبكات", "مستشار أمن سيبراني"],
        },
        {
            "major": "الواقع الرقمي وتطوير الألعاب (VR)",
            "major_en": "Digital Reality and Game Development",
            "code": "VR",
            "total_hours": 134,
            "batches": ["2024"],
            "description": "تخصص حديث يجمع تطوير الألعاب الإلكترونية مع تقنيات الواقع الافتراضي والمعزز",
            "career_paths": ["مطور ألعاب", "مصمم تجربة افتراضية", "مطور تطبيقات VR/AR"],
        },
    ]

    for plan in study_plans:
        content = f"""تخصص {plan['major']}
الاسم الإنجليزي: {plan['major_en']}
الرمز: {plan['code']}
عدد الساعات المعتمدة للتخرج: {plan['total_hours']} ساعة
الدفعات المتاحة: {', '.join(plan['batches'])}

الوصف: {plan['description']}

المسارات المهنية بعد التخرج:
{chr(10).join('- ' + c for c in plan['career_paths'])}
"""
        if 'core_courses_2024' in plan:
            content += "\nالمساقات الجوهرية (2024):\n"
            content += '\n'.join(plan['core_courses_2024'])

        content += f"""

ملاحظات مهمة:
- جميع تخصصات كلية IT تتطلب {plan['total_hours']} ساعة معتمدة للتخرج
- توزيع الساعات: 15 ساعة متطلبات جامعة + 119 ساعة متطلبات كلية وتخصص
- مدة الدراسة: 4 سنوات (8 فصول دراسية) في الحالة الاعتيادية
- يمكن الاستفسار عن خطتك الدراسية المحددة حسب دفعتك من قسمك"""

        items.append(make_item(
            title=f"تخصص {plan['major']} - كلية IT جامعة اليرموك",
            content=content,
            url=f"http://it.yu.edu.jo/ar/{plan['code'].lower()}-study-plan",
            category="programs",
            priority=1
        ))

    # ── 4. Library Services ─────────────────────────────────
    items.append(make_item(
        title="المكتبة الجامعية - خدماتها وكيفية الاستخدام",
        content="""المكتبة الجامعية في جامعة اليرموك هي من أكبر المكتبات الجامعية في الأردن.

خدمات المكتبة:
1. استعارة الكتب والمراجع
   - يمكن للطالب استعارة حتى 5 كتب في آنٍ واحد
   - مدة الاستعارة: أسبوعان قابلة للتجديد
   - تحتاج لبطاقة الطالب الجامعية لعملية الاستعارة
   - يمكن تجديد الاستعارة إلكترونياً أو حضورياً

2. قواعد البيانات الإلكترونية
   - الوصول لقواعد بيانات علمية دولية مثل IEEE, ACM, Elsevier
   - متاحة للطلاب وأعضاء الهيئة التدريسية
   - يمكن الوصول إليها من داخل الحرم الجامعي أو عبر VPN

3. القاعات الدراسية والمناطق الهادئة
   - قاعات مجموعات للعمل الجماعي (يتطلب حجزاً مسبقاً)
   - مناطق هادئة للدراسة الفردية
   - أجهزة حاسوب للبحث

4. خدمات الطباعة والنسخ والمسح الضوئي

5. الدوريات والمجلات العلمية
   - مجلات محلية وعربية وأجنبية

ساعات العمل (الاعتيادية):
- الأحد - الخميس: 8:00 صباحاً - 9:00 مساءً
- الجمعة: مغلقة
- السبت: 9:00 صباحاً - 2:00 ظهراً

كيفية استعارة كتاب:
1. ابحث في الفهرس الإلكتروني عن الكتاب المطلوب
2. دوّن رقم التصنيف
3. ابحث عن الكتاب في الرفوف المقابلة للرقم
4. توجه لمكتب الاستعارة بالكتاب وبطاقتك الجامعية
5. يُختم على الكتاب بتاريخ الإعادة المطلوب""",
        url="https://yu.edu.jo/ar/library",
        category="general",
        priority=1
    ))

    # ── 5. Student Housing ──────────────────────────────────
    items.append(make_item(
        title="السكنات الطلابية - جامعة اليرموك",
        content="""السكنات الطلابية في جامعة اليرموك توفر إقامة للطلاب داخل الحرم الجامعي.

السكنات المتوفرة:
- سكن للطلاب الذكور
- سكن للطالبات الإناث
- يعطى الأولوية للطلاب من خارج إربد وللمتفوقين أكاديمياً

المرافق المتوفرة:
- غرف مشتركة (2-4 طلاب)
- قاعات للدراسة المشتركة
- مطاعم وكافتيريات قريبة
- خدمات الإنترنت

شروط السكن:
- يقدم الطالب طلباً في بداية كل فصل دراسي
- يُعطى الأولوية لأصحاب المعدلات المرتفعة
- يُعطى الأولوية للطلاب من المناطق البعيدة عن إربد

للتقديم والاستفسار:
- التواصل مع عمادة شؤون الطلبة
- الموقع: داخل الحرم الجامعي
- أو من خلال بوابة الطالب الإلكترونية""",
        url="https://yu.edu.jo/ar/student-housing",
        category="general",
        priority=1
    ))

    # ── 6. Health Insurance ─────────────────────────────────
    items.append(make_item(
        title="التأمين الصحي للطلاب - جامعة اليرموك",
        content="""التأمين الصحي للطلاب في جامعة اليرموك.

عن التأمين الصحي:
- يُدفع التأمين الصحي ضمن الرسوم الدراسية الفصلية
- يغطي التأمين العلاج في المستشفيات والمراكز الصحية المعتمدة
- يشمل العمليات الجراحية والفحوصات الطبية

كيفية الاستخدام:
1. احتفظ ببطاقة التأمين (تُستلم من عمادة شؤون الطلبة أو مكتب التسجيل)
2. عند الحاجة للعلاج، توجه للمستشفيات والمراكز المعتمدة
3. قدّم بطاقة التأمين مع بطاقتك الجامعية

للاستفسار:
- عمادة شؤون الطلبة
- مبنى الإدارة المركزية - جامعة اليرموك""",
        url="https://yu.edu.jo/ar/student-affairs",
        category="general",
        priority=1
    ))

    # ── 7. Student Affairs Deanship ─────────────────────────
    items.append(make_item(
        title="عمادة شؤون الطلبة - خدماتها",
        content="""عمادة شؤون الطلبة في جامعة اليرموك هي الجهة المسؤولة عن كل ما يتعلق بالحياة الطلابية خارج القاعة.

الخدمات المقدمة:
1. التأمين الصحي
2. السكنات الطلابية والإقامة
3. الأندية والأنشطة الطلابية
4. الخدمات الاجتماعية للطلبة المحتاجين
5. مركز دعم ذوي الاحتياجات الخاصة
6. مركز الإرشاد الطلابي والتوجيه المهني
7. الأنشطة الثقافية والرياضية
8. مساعدة الطلاب في تصاريح العمل وشؤون الإقامة للطلاب الأجانب

الأندية الطلابية البارزة:
- نادي IT وتطوير الألعاب (DEVIT)
- نادي ريادة الأعمال
- النادي العلمي
- نادي الروبوتيكس
- النادي الثقافي والأدبي
- الفرق الرياضية المتعددة

الموقع: داخل الحرم الجامعي - مبنى عمادة شؤون الطلبة""",
        url="https://yu.edu.jo/ar/student-affairs",
        category="general",
        priority=1
    ))

    # ── 8. E-Learning System ────────────────────────────────
    items.append(make_item(
        title="نظام التعلم الإلكتروني - Moodle جامعة اليرموك",
        content="""نظام التعلم الإلكتروني (Moodle) في جامعة اليرموك هو المنصة الرسمية للمواد والواجبات الرقمية.

الرابط: https://elearning.yu.edu.jo

ما يمكنك فعله عبر المنصة:
- متابعة مواد المساقات (شرائح، ملفات PDF، مقاطع فيديو)
- تسليم الواجبات والمشاريع
- الاطلاع على الدرجات والتغذية الراجعة
- التواصل مع المدرس عبر المنتدى
- إجراء الاختبارات الإلكترونية (Quizzes)

كيفية الدخول:
1. افتح الرابط: https://elearning.yu.edu.jo
2. أدخل اسم المستخدم: رقمك الجامعي
3. كلمة المرور: تُحدد في بداية التسجيل (أو راجع قسم تقنية المعلومات)

في حال نسيان كلمة المرور:
- توجه لعمادة القبول والتسجيل أو قسم تقنية المعلومات في الجامعة
- أو استخدام خيار "نسيت كلمة المرور" في صفحة الدخول

ملاحظة: التعليم في اليرموك وجاهي بالكامل، وElearning مكمّل للتعليم وليس بديلاً عنه""",
        url="https://elearning.yu.edu.jo",
        category="general",
        priority=1
    ))

    # ── 9. Admission & Registration ─────────────────────────
    items.append(make_item(
        title="القبول والتسجيل - متطلبات وإجراءات",
        content="""عمادة القبول والتسجيل في جامعة اليرموك.
الرابط الرسمي: https://admreg.yu.edu.jo

متطلبات القبول للبكالوريوس:
- شهادة الثانوية العامة (التوجيهي الأردني أو ما يعادلها)
- يتحدد القبول بناءً على معدل التوجيهي والتخصص المطلوب
- يتم القبول عبر نظام القبول الموحد للجامعات الأردنية

التسجيل الفصلي:
1. الدخول لنظام التسجيل: https://admreg.yu.edu.jo
2. الاطلاع على الجدول الزمني للتسجيل
3. اختيار المساقات في الفترة المحددة
4. مراجعة المرشد الأكاديمي عند الحاجة
5. دفع الرسوم الدراسية خلال المدة المحددة

الرسوم الدراسية:
- تختلف الرسوم حسب التخصص (علمي/أدبي/طبي)
- يمكن مراجعة الرسوم التفصيلية من: https://admreg.yu.edu.jo/ar/fees
- المنح الدراسية: https://admreg.yu.edu.jo/ar/scholarships

المنح والإعفاءات:
- منح التفوق الأكاديمي
- منح أبناء الشهداء
- منح ذوي الدخل المحدود
- منح أعضاء هيئة التدريس وموظفي الجامعة""",
        url="https://admreg.yu.edu.jo",
        category="admission",
        priority=1
    ))

    # ── 10. Hijjawi Faculty ─────────────────────────────────
    items.append(make_item(
        title="كلية الحجاوي للهندسة التكنولوجية - نبذة",
        content="""كلية الحجاوي للهندسة التكنولوجية في جامعة اليرموك.
عميد الكلية: د. عوض سميران الزبن

التخصصات (6 تخصصات):
1. هندسة الحاسوب (Computer Engineering)
2. هندسة الاتصالات والإلكترونيات (Communications & Electronics Engineering)
3. هندسة الطاقة الكهربائية (Electrical Power Engineering)
4. هندسة الميكاترونيكس (Mechatronics Engineering)
5. الهندسة الصناعية وإدارة هندسية (Industrial Engineering & Engineering Management)
6. الهندسة المدنية (Civil Engineering)

مدة الدراسة: 5 سنوات
اللغة: العربية والإنجليزية
الحرم الجامعي: داخل حرم جامعة اليرموك - إربد""",
        url="https://yu.edu.jo/ar/hijjawi",
        category="faculty",
        priority=1
    ))

    # ── 11. Graduate Programs ───────────────────────────────
    items.append(make_item(
        title="الدراسات العليا في جامعة اليرموك",
        content="""الدراسات العليا (ماجستير ودكتوراه) في جامعة اليرموك.

أنواع البرامج:
1. الماجستير بالرسالة (Thesis Master's)
2. الماجستير بالامتحان الشامل (Coursework Master's)
3. الدكتوراه (PhD)

متطلبات القبول للماجستير:
- درجة البكالوريوس بمعدل لا يقل عن 70% أو 2.5/4
- اختبار الكفاءة في اللغة الإنجليزية (IELTS أو ما يعادله)
- مقابلة شخصية في بعض التخصصات

برامج الماجستير في كلية IT:
- ماجستير ذكاء الأعمال (Business Intelligence)
  * نظام رسالة: 33 ساعة
  * نظام امتحان شامل: 36 ساعة
- ماجستير الذكاء الاصطناعي (Artificial Intelligence)
  * نظام امتحان شامل: 36 ساعة

للتقديم: https://admreg.yu.edu.jo/ar/grad-admission
عمادة الدراسات العليا والبحث العلمي: https://yu.edu.jo/ar/graduate-studies""",
        url="https://yu.edu.jo/ar/graduate-studies",
        category="programs",
        priority=1
    ))

    # ── 11b. YouTube Resources for IT Courses ───────────────
    youtube_resources = [
        ("مقدمة في البرمجة / Python / Java", [
            "قناة Bro Code (إنجليزي) - Python وJava مبسطة | https://youtube.com/@BroCodez",
            "قناة CS50 Harvard (إنجليزي) - أفضل مقدمة للبرمجة | https://youtube.com/@cs50",
            "قناة Elzero Web School (عربي) - برمجة وويب | https://youtube.com/@ElzeroWebSchool",
        ]),
        ("تراكيب البيانات والخوارزميات (CS253)", [
            "قناة Abdul Bari (إنجليزي) - أفضل شرح للخوارزميات | https://youtube.com/@abdul_bari",
            "قناة WilliamFiset (إنجليزي) - Data Structures شاملة",
        ]),
        ("قواعد البيانات (CIS260)", [
            "قناة Caleb Curry (إنجليزي) - SQL وDatabase design",
            "قناة حسين الربيعي (عربي) - قواعد البيانات بالعربي",
        ]),
        ("الشبكات وتراسل البيانات (CS332)", [
            "قناة NetworkChuck (إنجليزي) - شبكات بأسلوب ممتع | https://youtube.com/@NetworkChuck",
            "قناة Professor Messer (إنجليزي) - CompTIA Network+",
        ]),
        ("الأمن السيبراني (CYS)", [
            "قناة David Bombal (إنجليزي) - ethical hacking | https://youtube.com/@davidbombal",
            "قناة John Hammond (إنجليزي) - CTF وأمن معلومات | https://youtube.com/@_JohnHammond",
        ]),
        ("الذكاء الاصطناعي وتعلم الآلة (AI/DA)", [
            "قناة 3Blue1Brown (إنجليزي) - رياضيات AI بصرياً | https://youtube.com/@3blue1brown",
            "قناة Krish Naik (إنجليزي) - Data Science شاملة",
            "قناة Sentdex (إنجليزي) - Python للـ ML | https://youtube.com/@sentdex",
        ]),
        ("تطوير الويب", [
            "قناة Traversy Media (إنجليزي) - تطوير ويب شامل | https://youtube.com/@TraversyMedia",
            "قناة Elzero Web School (عربي) - HTML/CSS/JS بالعربي",
            "قناة Hussein Nasser (إنجليزي/عربي) - Backend | https://youtube.com/@hnasr",
        ]),
        ("هندسة البرمجيات (CIS240)", [
            "قناة Fireship (إنجليزي) - تقنيات حديثة مختصرة | https://youtube.com/@Fireship",
            "قناة Hussein Nasser (إنجليزي/عربي) - Software Engineering",
        ]),
    ]

    for course_name, resources in youtube_resources:
        content = f"مصادر تعليمية مجانية على يوتيوب لمادة: {course_name}\n\n"
        content += "قنوات موصى بها:\n"
        for r in resources:
            content += f"- {r}\n"
        content += "\nهذه المصادر مجانية ومتاحة على YouTube، ننصح بمشاهدتها جنباً مع محاضرات الكلية."
        items.append(make_item(
            title=f"مصادر يوتيوب - {course_name}",
            content=content,
            url="https://youtube.com",
            category="programs",
            priority=2
        ))

    # ── 12. Nearby Bookstores/Services ──────────────────────
    items.append(make_item(
        title="المحلات والخدمات القريبة من جامعة اليرموك",
        content="""المحلات والخدمات القريبة من حرم جامعة اليرموك في إربد.

المكتبات ومحلات القرطاسية:
- منطقة البوابة الرئيسية (قرب الجامعة): تتوفر عدة محلات قرطاسية وطباعة
- شارع الجامعة: مجموعة من محلات الكتب والقرطاسية
- مجمع اليرموك: قريب من الجامعة يحتوي على خدمات متعددة

مقاهٍ ومطاعم قرب الجامعة:
- تتوفر العديد من المطاعم والكافتيريات في محيط الجامعة
- المطعم الرئيسي والكافتيريا داخل الحرم الجامعي

خدمات الطباعة والنسخ:
- تتوفر خدمات طباعة ونسخ بالقرب من البوابات الرئيسية
- داخل الجامعة في المكتبة ومبنى IT

خدمات الإنترنت والكمبيوتر:
- تتوفر مقاهي إنترنت في محيط الجامعة
- مختبرات الكلية متاحة للطلاب في ساعات محددة

الصيدليات والخدمات الصحية:
- تتوفر صيدليات قريبة من الجامعة
- العيادة الصحية داخل الجامعة""",
        url="https://yu.edu.jo/ar",
        category="general",
        priority=2
    ))

    return items

# ============================================================
#  MERGE WITH EXISTING DATA
# ============================================================

def load_existing_data(filepath: str) -> list:
    """Load existing yarmouk_data.json if it exists."""
    path = Path(filepath)
    if path.exists():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {len(data)} existing items from {filepath}")
            return data
        except Exception as e:
            logger.error(f"Could not load existing data: {e}")
    return []


def merge_data(existing: list, new_items: list) -> list:
    """Merge new scraped data with existing, avoiding duplicates by URL."""
    existing_urls = {item.get('url', '') for item in existing}
    merged = list(existing)
    added = 0
    for item in new_items:
        if item.get('url') and item['url'] not in existing_urls:
            merged.append(item)
            existing_urls.add(item['url'])
            added += 1
        elif not item.get('url'):
            merged.append(item)
            added += 1
    logger.info(f"Added {added} new items, kept {len(existing)} existing")
    return merged

# ============================================================
#  MAIN
# ============================================================

def main():
    logger.info("🚀 YU Scraper v2.0 Starting...")
    logger.info(f"Output: {OUTPUT_FILE}")

    all_new_items = []

    # 1. Static high-quality data (always included)
    logger.info("\n📌 Adding static data...")
    static = get_static_data()
    all_new_items.extend(static)
    logger.info(f"  Added {len(static)} static items")

    # 2. Scrape IT Faculty
    logger.info("\n🎓 Scraping IT Faculty...")
    try:
        it_items = scrape_it_faculty()
        all_new_items.extend(it_items)
        logger.info(f"  Got {len(it_items)} IT items")
    except Exception as e:
        logger.error(f"IT Faculty scraping failed: {e}")

    # 3. Scrape main YU website
    logger.info("\n🏫 Scraping YU Main Website...")
    try:
        yu_items = scrape_yu_main()
        all_new_items.extend(yu_items)
        logger.info(f"  Got {len(yu_items)} YU items")
    except Exception as e:
        logger.error(f"YU Main scraping failed: {e}")

    # 4. Merge with existing data
    logger.info("\n🔄 Merging with existing data...")
    existing = load_existing_data(DATA_FILE)
    final_data = merge_data(existing, all_new_items)

    # 5. Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ Done! Total items: {len(final_data)}")
    logger.info(f"📁 Saved to: {OUTPUT_FILE}")

    # Summary
    from collections import Counter
    cats = Counter(item.get('category', '?') for item in final_data)
    logger.info("\n📊 Category breakdown:")
    for cat, count in cats.most_common():
        logger.info(f"  {cat}: {count}")

    logger.info("\n⚠️  IMPORTANT: Review the output file, then rename it to data/yarmouk_data.json")
    logger.info("    and restart your bot to rebuild the vector store.")


if __name__ == "__main__":
    main()