"""Data-integrity checks (rewritten from the original root-level test.py).

Runs with plain pytest:      python -m pytest tests/test_data_integrity.py
Or standalone (no pytest):   python tests/test_data_integrity.py
"""
import ast
import io
import json
import os
import re
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA_FILE = os.path.join(ROOT, "data", "yarmouk_data.json")
SRC_DIR = os.path.join(ROOT, "src", "novacortex")
SHIM = os.path.join(ROOT, "NovaCortexbot.py")

GARBLED_MARKERS = ['بوساحلا مولع', 'تامولعملا ايجولونكت', 'سويرولاكبلا ةجردل']
REQUIRED_PROGRAMS = [
    'علم البيانات والذكاء الاصطناعي',
    'علوم الحاسوب',
    'الأمن السيبراني',
]
# Every marker must appear somewhere in the refactored sources.
SOURCE_MARKERS = {
    "FIX 1 - _fix_reversed_arabic": "_fix_reversed_arabic",
    "FIX 2 - MAX_CHUNKS_PER_DOC": "MAX_CHUNKS_PER_DOC",
    "FIX 2 - priority boost": "priority == 1",
    "FIX 4 - EXTERNAL_PLANS_TITLE_MAP": "EXTERNAL_PLANS_TITLE_MAP",
    "FIX 5 - _found_in_facts": "_found_in_facts",
    "FIX 6 - threshold 0.88": "SIMILARITY_THRESHOLD = 0.88",
    "FIX 6 - _is_incompatible": "_is_incompatible_cache",
    "FIX 2 - _last_was_count": "_last_was_count",
}


def _load_data():
    with io.open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_json_valid_and_complete():
    data = _load_data()
    assert len(data) >= 280, "عدد العناصر أقل من المتوقع: %d" % len(data)


def test_no_garbled_content():
    data = _load_data()
    garbled = [
        item.get('title', '') for item in data
        if any(m in (item.get('content', '') or '')[:300] for m in GARBLED_MARKERS)
    ]
    assert not garbled, "لا يزال يوجد محتوى مقلوب: %s" % garbled


def test_external_plan_titles_fixed():
    data = _load_data()
    old = [
        x.get('title', '') for x in data
        if (x.get('title', '') or '').startswith('ExternalPlans')
    ]
    assert not old, "عناوين لم تُصحَّح: %s" % old


def test_required_program_pages_exist():
    data = _load_data()
    for prog in REQUIRED_PROGRAMS:
        assert any(prog in (x.get('title', '') or '') for x in data), \
            "صفحة مستقلة مفقودة: %s" % prog


def test_priority_field_reported():
    """Non-fatal (matches the original test): report items without priority."""
    data = _load_data()
    missing = [x.get('title', '')[:40] for x in data if 'priority' not in x]
    if missing:
        warnings.warn("%d عناصر بدون priority: %s" % (len(missing), missing))


def test_fix_reversed_arabic():
    from novacortex.rag.indexing import _fix_reversed_arabic
    garbled = 'بوساحلا مولع Computer Science كومريلا ةعماج'
    expected = 'الحاسوب علوم Computer Science اليرموك جامعة'
    assert _fix_reversed_arabic(garbled) == expected
    assert _fix_reversed_arabic("") == ""


def _all_sources():
    chunks = []
    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                with io.open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                    chunks.append(f.read())
    with io.open(SHIM, encoding="utf-8") as f:
        chunks.append(f.read())
    return "\n".join(chunks)


def test_sources_parse_and_contain_fixes():
    source = _all_sources()
    # syntax check every module
    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                with io.open(path, encoding="utf-8") as f:
                    ast.parse(f.read(), filename=path)
    with io.open(SHIM, encoding="utf-8") as f:
        ast.parse(f.read(), filename=SHIM)
    # regression markers must survive the refactor
    missing = [name for name, token in SOURCE_MARKERS.items() if token not in source]
    assert not missing, "تعديل مفقود في الكود: %s" % missing


if __name__ == "__main__":
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print("  PASS %s" % name)
        except AssertionError as exc:
            failures += 1
            print("  FAIL %s: %s" % (name, exc))
    print("=" * 55)
    print("OK" if not failures else "%d FAILED" % failures)
    sys.exit(1 if failures else 0)
