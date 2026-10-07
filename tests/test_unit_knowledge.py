"""Sanity checks for the static knowledge modules and central config."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from novacortex import config  # noqa: E402
from novacortex.knowledge.careers import CV_TEMPLATES, SKILL_GAP_DATA  # noqa: E402
from novacortex.knowledge.facts import VERIFIED_FACTS  # noqa: E402
from novacortex.knowledge.faculty import COLLOQUIAL_FACULTY_TERMS  # noqa: E402
from novacortex.knowledge.keywords import (  # noqa: E402
    COST_SPECIFIC_KEYWORDS,
    UNIVERSITY_CONTEXT_KEYWORDS,
)
from novacortex.knowledge.localization import INTERNATIONAL_DATA, LANGUAGE_BRIDGE  # noqa: E402


def test_verified_facts_present():
    assert VERIFIED_FACTS, "VERIFIED_FACTS must not be empty"
    assert isinstance(VERIFIED_FACTS, dict)
    assert "ar" in VERIFIED_FACTS and "en" in VERIFIED_FACTS


def test_faculty_terms_present():
    assert COLLOQUIAL_FACULTY_TERMS
    assert isinstance(COLLOQUIAL_FACULTY_TERMS, dict)


def test_keywords_present():
    assert UNIVERSITY_CONTEXT_KEYWORDS
    assert COST_SPECIFIC_KEYWORDS


def test_localization_data_present():
    assert INTERNATIONAL_DATA
    assert LANGUAGE_BRIDGE


def test_careers_data_present():
    assert CV_TEMPLATES
    assert SKILL_GAP_DATA


def test_paths_resolve_under_project_root():
    assert str(config.DATA_FILE).endswith(os.path.join("data", "yarmouk_data.json"))
    assert config.DATA_FILE.exists(), "data/yarmouk_data.json must exist"
    assert config.CHROMA_PATH == "chroma_ultra"
    assert config.DB_PATH.name == "novacortex_v12.db"


def test_missing_secrets_is_consistent():
    """missing_secrets() must agree with the configured values (env-dependent)."""
    expected = [n for n in config._SECRETS if not getattr(config, n)]
    assert config.missing_secrets() == expected


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
