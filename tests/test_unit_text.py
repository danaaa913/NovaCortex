"""Unit tests for the Arabic text helpers (stdlib + nltk only)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

nltk = pytest.importorskip("nltk", reason="nltk unavailable in this environment")

from novacortex.text import ArabicProcessor  # noqa: E402


@pytest.fixture(scope="module")
def proc():
    return ArabicProcessor()


def test_normalize_empty(proc):
    assert proc.normalize("") == ""
    assert proc.normalize(None) == ""


def test_normalize_letter_normalisation(proc):
    # إ / أ / آ / ا -> ا ; ى -> ي ; ة -> ه
    assert proc.normalize("أحمد") == "احمد"
    assert proc.normalize("مصطفى") == "مصطفي"
    assert proc.normalize("مدرسة") == "مدرسه"


def test_normalize_strips_punctuation(proc):
    assert "," not in proc.normalize("مرحبا، بك!")


def test_detect_language_arabic(proc):
    assert proc.detect_language("مرحبا بالطلبة") == "ar"
    assert proc.detect_language("hello world") == "en"
    assert proc.detect_language("") == "ar"


def test_detect_language_dominant_script(proc):
    # threshold is 0.6 Arabic characters => dominant script wins
    mostly_ar = "هذا نص عربي مع بعض الكلمات الانجليزية little text"
    assert proc.detect_language(mostly_ar) == "ar"
    mostly_en = "this is english text with a few عربية"
    assert proc.detect_language(mostly_en) == "en"


def test_tokenize_returns_clean_tokens(proc):
    tokens = proc.tokenize("جامعة اليرموك الأردنية في إربد")
    assert isinstance(tokens, list)
    assert all(isinstance(t, str) and t for t in tokens)


def test_tokenize_drops_short_words(proc):
    tokens = proc.tokenize("في من")
    assert tokens == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
