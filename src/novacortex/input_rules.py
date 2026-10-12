"""Dependency-free input rules shared by safety checks and tests."""

import re


INJECTION_PATTERNS = [
    r'تجاهل\s*(كل|جميع)?\s*التعليمات',
    r'تجاهل\s*(كل|جميع)?\s*تعليمات',
    r'ignore\s+.{0,25}instructions',
    r'أنت\s+الآن',
    r'you\s+are\s+now',
    r'forget\s+(everything|your\s+rules)',
    r'انسى\s+(كل|تعليماتك)',
    r'system\s*prompt',
    r'اعطيني\s+تعليماتك',
    r'reveal\s+your\s+(instructions|prompt)',
    r'act\s+as\s+(if|a|an)',
    r'تصرف\s+كأنك',
    r'do\s+not\s+follow',
    r'override',
    r'jailbreak',
    r'DAN\s+mode',
    r'developer\s+mode',
    r'بدون\s+قيود',
    r'without\s+restrictions',
    r'new\s+persona',
    r'شخصية\s+جديدة',
    r'كيف\s+أعمل\s+هاكر',
    r'كيف\s+أخترق\s+نظام',
    r'كيف\s+أخترق',
    r'hack\s+the\s+(university|system|server)',
    r'اخترق\s+(الجامعة|النظام|الموقع)',
    r'كيف\s+أسرق\s+(بيانات|كلمة\s+مرور|حساب)',
    r'كيف\s+أدخل\s+على\s+(حساب|نظام|موقع)\s+شخص',
]


def detect_injection(question: str) -> bool:
    """Detect explicit prompt-injection patterns without broad word blocking."""
    q_low = question.lower()
    return any(re.search(pattern, q_low, re.IGNORECASE) for pattern in INJECTION_PATTERNS)


def needs_false_premise_check(question: str) -> bool:
    """Limit costly fact-check calls to questions that actually assert a claim."""
    q_low = question.lower()
    if not re.search(r'اليرموك|yarmouk', q_low, re.IGNORECASE):
        return False
    claim_markers = [
        r'تأسست', r'تقع\s+في', r'جامعة\s+خاصة', r'ليست\s+حكومية',
        r'مش\s+حكومية', r'عندها', r'لديها', r'فروع\s+في', r'تقدم\s+برنامج',
        r'founded', r'established', r'located\s+in', r'private\s+university',
        r'has\s+(?:a|an|campus|program)', r'offers?\s+',
    ]
    return any(re.search(pattern, q_low, re.IGNORECASE) for pattern in claim_markers)
