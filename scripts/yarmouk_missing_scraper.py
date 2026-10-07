"""
yarmouk_missing_scraper.py  (v3 — fixed URLs + BIT plans)
==========================================================
إصلاحات v3:
  - CYS 2025: الـ URL الصح هو ITCS-CSE-Study_Plan_2025.pdf
  - أضاف خطط BIT 2023 و BIT 2025
  - أضاف VR 2023 و BIT 2023 من مسار الـ 2024 كـ fallback

الاستخدام:
    pip install requests beautifulsoup4 PyMuPDF
    python scripts/yarmouk_missing_scraper.py --input data/yarmouk_data_final.json
    python scripts/yarmouk_missing_scraper.py --only bit_plan_2025 bit_plan_2023
    python scripts/yarmouk_missing_scraper.py --skip-pdf
"""

import json, re, time, argparse
from datetime import datetime
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("pip install requests beautifulsoup4")

try:
    import fitz
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("PyMuPDF not found — PDFs disabled.  pip install PyMuPDF")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en;q=0.9",
    "Referer": "https://it.yu.edu.jo/",
}
TIMEOUT = 20
DELAY   = 1.5

# ── Base paths ────────────────────────────────────────────────
_B25  = "https://it.yu.edu.jo/images/2026website/Bac_plan2025/"
_B24  = "https://it.yu.edu.jo/images/Latest_plans/Bacha/"
_B21  = "https://it.yu.edu.jo/images/"

TARGETS = {
    # ── Course descriptions ────────────────────────────────────
    "cs_courses":  {
        "url":   "https://it.yu.edu.jo/index.php/2022-09-18-22-16-54",
        "title": "وصف مساقات قسم علوم الحاسوب — CS",
        "major": "CS",
        "type":  "course_desc_table",
    },
    "cis_courses": {
        "url":   "https://it.yu.edu.jo/index.php/ar/2022-09-21-10-18-46",
        "title": "وصف مساقات نظم المعلومات الحاسوبية — CIS",
        "major": "CIS",
        "type":  "course_desc_table",
    },
    "bit_courses": {
        "url":   "https://it.yu.edu.jo/index.php/2022-09-21-21-25-20",
        "title": "وصف مساقات تكنولوجيا معلومات الأعمال — BIT",
        "major": "BIT",
        "type":  "course_desc_table",
    },
    "cys_courses": {
        "url":   "https://it.yu.edu.jo/index.php/cys",
        "title": "وصف مساقات الأمن السيبراني — CYS",
        "major": "CYS",
        "type":  "course_desc_table",
    },

    # ── Study Plans 2025 ───────────────────────────────────────
    "cs_plan_2025": {
        "url":   _B25 + "ITCS-CS-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية CS 2025",
        "major": "CS",  "year": "2025",
        "type":  "study_plan_pdf",
    },
    "cis_plan_2025": {
        "url":   _B25 + "ITCS-CIS-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية CIS 2025",
        "major": "CIS", "year": "2025",
        "type":  "study_plan_pdf",
    },
    "da_plan_2025": {
        "url":   _B25 + "ITCS-DA-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية DA 2025",
        "major": "DA",  "year": "2025",
        "type":  "study_plan_pdf",
    },
    "vr_plan_2025": {
        "url":   _B25 + "ITCS-DRG-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية VR 2025",
        "major": "VR",  "year": "2025",
        "type":  "study_plan_pdf",
    },
    # ✅ إصلاح: الاسم الصحيح لـ CYS 2025 هو CSE مش CYS
    "cys_plan_2025": {
        "url":   _B25 + "ITCS-CSE-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية CYS 2025",
        "major": "CYS", "year": "2025",
        "type":  "study_plan_pdf",
    },
    # ✅ جديد: BIT 2025
    "bit_plan_2025": {
        "url":   _B25 + "ITCS-BIT-Study_Plan_2025.pdf",
        "title": "الخطة الدراسية BIT 2025",
        "major": "BIT", "year": "2025",
        "type":  "study_plan_pdf",
    },

    # ── Study Plans 2023 ───────────────────────────────────────
    # ✅ جديد: BIT 2023 (جرب مسارين)
    "bit_plan_2023_v1": {
        "url":   _B24 + "ITCS-BIT-Study_Plan_2023.pdf",
        "title": "الخطة الدراسية BIT 2023",
        "major": "BIT", "year": "2023",
        "type":  "study_plan_pdf",
    },
    "bit_plan_2023_v2": {
        "url":   _B24 + "ITCS-BIT-Study_Plan_2024.pdf",
        "title": "الخطة الدراسية BIT 2024",
        "major": "BIT", "year": "2024",
        "type":  "study_plan_pdf",
    },
    # ✅ جديد: VR 2023 / 2024
    "vr_plan_2024": {
        "url":   _B24 + "ITCS-DRG-Study_Plan_2024.pdf",
        "title": "الخطة الدراسية VR 2024",
        "major": "VR",  "year": "2024",
        "type":  "study_plan_pdf",
    },

    # ── Academic Regulations ───────────────────────────────────
    "academic_regs": {
        "url":   "https://admreg.yu.edu.jo/index.php/languages-3/qrpt",
        "title": "تعليمات الدراسة والامتحانات للبكالوريوس",
        "major": None,
        "type":  "html_page",
        "category": "academic_rules",
    },
}


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────
def now_iso(): return datetime.now().isoformat()
def cl(t):    return re.sub(r'\s+', ' ', t or '').strip()

def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        print(f"  ✅ HTML {len(r.text):,} chars")
        return r.text
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        return None

def fetch_pdf(url):
    if not HAS_PDF:
        print("  ⚠️  PyMuPDF not installed — skipping PDF")
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        doc  = fitz.open(stream=r.content, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        doc.close()
        print(f"  ✅ PDF {len(text):,} chars")
        return text
    except Exception as e:
        print(f"  ⚠️  فشل PDF: {e}")
        return None

def make_entry(title, url, content, category, **kw):
    return {
        "title":        title,
        "description":  kw.pop("desc", ""),
        "url":          url,
        "content":      content,
        "category":     category,
        "priority":     1,
        "quality_score": kw.pop("qs", 88),
        "is_refined":   True,
        "scraped_at":   now_iso(),
        **kw,
    }


# ─────────────────────────────────────────────────────────────
#  Course page parser
# ─────────────────────────────────────────────────────────────
CODE_RE = re.compile(r'\b(CS|CIS|CYS|BIT|DA|VR|MATH|STAT)\s*(\d{3}[A-Z]?)\b')

def _build_course_entry(code, name, hours, prereq, desc, major, url):
    return make_entry(
        title          = f"وصف مساق {code}{' — '+name if name else ''}",
        url            = url,
        content        = (
            f"اسم المساق: {name}\n"
            f"رمز المساق: {code}\n"
            f"الساعات المعتمدة: {hours}\n"
            f"المتطلب السابق: {prereq}\n"
            f"لغة التدريس: الإنجليزية\n\n"
            f"وصف المساق:\n{cl(desc)}"
        ),
        category       = "course_description",
        course_code    = code,
        course_name_ar = name,
        credit_hours   = hours,
        prerequisites  = prereq,
        major_code     = major,
        qs             = 91,
    )

def parse_course_page(html, major, url, existing_codes):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.select("nav,footer,script,style,.navbar"):
        t.decompose()

    results = []
    tables  = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        name = code = hours = prereq = desc = ""
        in_desc = False
        prereq  = "لا يوجد"

        def save():
            nonlocal name, code, hours, prereq, desc, in_desc
            if code and len(desc) > 30 and code not in existing_codes:
                results.append(
                    _build_course_entry(code, name, hours, prereq, desc, major, url))
                existing_codes.add(code)
            name = code = hours = prereq = desc = ""
            in_desc = False
            prereq  = "لا يوجد"

        for row in rows:
            cells  = [cl(td.get_text()) for td in row.find_all(["td", "th"])]
            joined = " ".join(cells)

            if re.search(r'اسم\s+المساق', joined):
                save()
                nm = re.search(
                    r'اسم\s+المساق\s*[:\-]?\s*(.+?)(?:\s*\||\s*رمز|$)', joined)
                if nm:
                    raw  = nm.group(1).strip().rstrip('|').strip()
                    name = re.sub(
                        r'\b(?:CS|CIS|CYS|BIT|DA|VR)\s*\d+\w*\b', '', raw
                    ).strip(' :-')
                cm = CODE_RE.search(joined)
                if cm:
                    code = f"{cm.group(1)} {cm.group(2)}"
                hm = re.search(r'(\d+)\s*ساعات?\s*معتمدة', joined)
                if hm:
                    hours = hm.group(1)
                in_desc = False

            elif not code:
                cm = CODE_RE.search(joined)
                if cm:
                    code = f"{cm.group(1)} {cm.group(2)}"
                hm = re.search(r'(\d+)\s*ساعات?\s*معتمدة', joined)
                if hm and not hours:
                    hours = hm.group(1)

            elif re.search(r'المتطلب\s+(?:السابق|المشترك)', joined):
                pm = re.search(
                    r'المتطلب\s+(?:السابق|المشترك)\s*[:\-]?\s*(.+)', joined)
                if pm:
                    prereq = cl(pm.group(1)).rstrip('|').strip()

            elif re.search(r'وصف\s+المساق', joined):
                in_desc = True
                long_cells = [c for c in cells
                              if len(c) > 40
                              and 'وصف المساق' not in c
                              and 'اسم المساق' not in c]
                if long_cells:
                    desc += " ".join(long_cells) + " "

            elif in_desc:
                long_cells = [c for c in cells if len(c) > 40]
                if long_cells:
                    desc += " ".join(long_cells) + " "

        save()

    # Fallback: plain text
    if not results:
        print("  fallback: plain text parsing")
        main_el = (
            soup.find("div", class_=re.compile(r"item-page|content|article"))
            or soup.body
        )
        text = re.sub(r'\s+', ' ',
                      (main_el or soup).get_text("\n")).strip()
        for chunk in re.split(r'(?=\b(?:CS|CIS|CYS|BIT|DA|VR)\s+\d{3})', text):
            if len(chunk) < 80: continue
            cm = CODE_RE.search(chunk)
            if not cm: continue
            c_code = f"{cm.group(1)} {cm.group(2)}"
            if c_code in existing_codes: continue
            hm  = re.search(r'(\d)\s*ساعات?\s*معتمدة', chunk)
            prm = re.search(
                r'المتطلب\s+السابق\s*[:\-]\s*(.+?)(?:\n|وصف)', chunk)
            results.append(_build_course_entry(
                c_code, "",
                hm.group(1) if hm else "",
                cl(prm.group(1)) if prm else "لا يوجد",
                chunk[:600], major, url,
            ))
            existing_codes.add(c_code)

    print(f"  📚 تم استخراج {len(results)} مساق لـ {major}")
    return results


# ─────────────────────────────────────────────────────────────
#  PDF study plan parser
# ─────────────────────────────────────────────────────────────
def parse_pdf_plan(text, major, year, url):
    if not text: return []
    SEM = re.compile(
        r'(Year\s+\d.*?Semester\s+\d'
        r'|السنة\s+(?:الأولى|الثانية|الثالثة|الرابعة)'
        r'|الفصل\s+(?:الأول|الثاني))', re.I
    )
    has_sem = bool(SEM.search(text))
    body    = "\n".join(l.strip() for l in text.splitlines() if l.strip())
    cat     = "study_plan_semester" if has_sem else "study_plan"
    return [make_entry(
        title      = f"الخطة الدراسية {'الفصلية ' if has_sem else ''}— {major} {year}",
        url        = url,
        content    = (
            f"الخطة الدراسية — {major} {year}\n"
            f"جامعة اليرموك — كلية تكنولوجيا المعلومات\n\n"
            + body[:8000]
        ),
        category   = cat,
        major_code = major,
        plan_year  = year,
        qs         = 85 if has_sem else 70,
    )]


# ─────────────────────────────────────────────────────────────
#  HTML generic page parser
# ─────────────────────────────────────────────────────────────
def parse_html_page(html, t):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("nav,footer,script,style,.navbar"):
        tag.decompose()
    main = (soup.find("div", class_=re.compile(r"item-page|content|article"))
            or soup.body)
    text = cl(main.get_text("\n")) if main else ""
    if len(text) < 100:
        return []
    return [make_entry(
        title    = t["title"],
        url      = t["url"],
        content  = text[:6000],
        category = t.get("category", "general"),
    )]


# ─────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",    default=str(ROOT / "data" / "yarmouk_data_final.json"))
    ap.add_argument("--output",   default=None)
    ap.add_argument("--skip-pdf", action="store_true")
    ap.add_argument("--only",     nargs="+", choices=list(TARGETS),
                    help="process only these keys")
    args = ap.parse_args()

    out  = args.output or args.input
    data = (json.loads(Path(args.input).read_text("utf-8"))
            if Path(args.input).exists() else [])
    print(f"✅  محمّل {len(data)} entries من {args.input}")

    existing_urls  = {e.get("url", "") for e in data}
    existing_codes = {e.get("course_code","") for e in data
                      if e.get("course_code")}

    keys_to_run = args.only or list(TARGETS)
    new_entries = []

    for key in keys_to_run:
        if key not in TARGETS:
            print(f"\n⚠️  مفتاح غير معروف: {key}")
            continue
        t = TARGETS[key]
        print(f"\n{'═'*55}")
        print(f"🔄  {key}: {t['title']}")
        print(f"    {t['url']}")

        entries = []

        # ── Course description pages ──────────────────────────
        if t["type"] == "course_desc_table":
            html = fetch_html(t["url"])
            if html:
                entries = parse_course_page(
                    html, t["major"], t["url"], existing_codes)

        # ── PDF study plans ───────────────────────────────────
        elif t["type"] == "study_plan_pdf":
            if args.skip_pdf:
                print("  ⏭️  تخطي (--skip-pdf)")
                continue
            # تخطى لو موجود بنفس الـ URL
            if t["url"] in existing_urls:
                print("  ⏭️  موجود بالفعل في الداتا — تخطي")
                continue
            # تخطى لو موجودة خطة نفس التخصص ونفس السنة
            yr   = t.get("year","")
            maj  = t.get("major","")
            already = any(
                e.get("plan_year") == yr and e.get("major_code") == maj
                for e in data
            )
            if already:
                print(f"  ⏭️  خطة {maj} {yr} موجودة بالفعل — تخطي")
                continue
            txt = fetch_pdf(t["url"])
            if txt:
                entries = parse_pdf_plan(
                    txt, t["major"], t["year"], t["url"])

        # ── Generic HTML pages ────────────────────────────────
        elif t["type"] == "html_page":
            if t["url"] in existing_urls:
                print("  ⏭️  موجود بالفعل في الداتا — تخطي")
                continue
            html = fetch_html(t["url"])
            if html:
                entries = parse_html_page(html, t)

        if entries:
            new_entries.extend(entries)
            existing_urls.add(t["url"])
            print(f"  ✅ أُضيف {len(entries)} entry")

        time.sleep(DELAY)

    if new_entries:
        data.extend(new_entries)
        Path(out).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        print(f"\n✅ DONE — أُضيف {len(new_entries)} entry، المجموع {len(data)}")
        print("\nالتصنيفات:")
        for c, n in Counter(e.get("category","?") for e in data).most_common():
            print(f"  {c:<35} {n}")
    else:
        print("\n⚠️  لم تُضف أي entries جديدة")
        print("    (كل البيانات المطلوبة موجودة بالفعل، أو فشل الـ fetch)")


if __name__ == "__main__":
    main()