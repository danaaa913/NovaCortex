"""Conservative privacy screening for a local government-service assistant.

The scanner intentionally reports categories and counts without copying detected
values into diagnostics. It is a safety net, not a legal data classifier.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

from .models import SourceUnit


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

LABELED_IDENTIFIER = re.compile(
    r"(?:"
    r"(?:الرقم|رقمي)\s+(?:الوطني|الشخصي)|رقم\s+(?:الهوية|هويتي|جواز\s*السفر)|"
    r"national\s+(?:id|number)|identity\s+(?:id|number)|passport\s+(?:id|number|no\.?)"
    r")\s*[:：#-]?\s*([A-Z0-9][A-Z0-9 -]{5,22})",
    re.I,
)
IBAN = re.compile(r"\bJO\d{2}[A-Z0-9]{26}\b", re.I)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?962|00962|0)\s*[- ]?7\d(?:[ -]?\d){7}(?!\d)")
SECRET = re.compile(
    r"(?:password|passwd|api[_ -]?key|secret[_ -]?key|كلمة\s*المرور|مفتاح\s*(?:سري|واجهة))"
    r"\s*[:=]\s*([^\s,;]{6,})",
    re.I,
)
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
FILENAME_IDENTIFIER = re.compile(r"(?<!\d)\d{8,14}(?!\d)")


def _luhn(value: str) -> bool:
    digits = [int(char) for char in value if char.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def scan_personal_data(text: str) -> List[Dict[str, object]]:
    """Find likely identifiers without returning their raw values."""
    normalized = text.translate(ARABIC_DIGITS)
    findings: List[Dict[str, object]] = []
    patterns = (
        ("labeled_identity_number", "high", LABELED_IDENTIFIER),
        ("jordan_iban", "high", IBAN),
        ("credential_or_secret", "high", SECRET),
        ("email_address", "medium", EMAIL),
        ("jordan_mobile_number", "medium", PHONE),
    )
    for code, severity, pattern in patterns:
        count = len(pattern.findall(normalized))
        if count:
            findings.append({"code": code, "severity": severity, "count": count})
    cards = [match.group(0) for match in CARD_CANDIDATE.finditer(normalized)]
    valid_cards = sum(_luhn(candidate.replace(" ", "").replace("-", "")) for candidate in cards)
    if valid_cards:
        findings.append({"code": "payment_card_number", "severity": "high", "count": valid_cards})
    return findings


def scan_units_privacy(units: Iterable[SourceUnit]) -> Dict[str, object]:
    findings: List[Dict[str, object]] = []
    for unit in units:
        for finding in scan_personal_data(unit.text):
            enriched = dict(finding)
            enriched["page"] = unit.page
            enriched["section"] = unit.section
            findings.append(enriched)
    high = sum(item["severity"] == "high" for item in findings)
    medium = sum(item["severity"] == "medium" for item in findings)
    return {
        "classification": "restricted" if high else ("personal_data_review" if medium else "public_or_unclassified"),
        "high_findings": high,
        "medium_findings": medium,
        "findings": findings,
    }


def filename_privacy_findings(filename: str) -> List[Dict[str, object]]:
    """Flag identifier-like filenames because provenance metadata is also displayed."""
    findings = scan_personal_data(filename)
    normalized = filename.translate(ARABIC_DIGITS)
    count = len(FILENAME_IDENTIFIER.findall(normalized))
    if count:
        findings.append({"code": "identifier_in_filename", "severity": "high", "count": count})
    return findings


def question_privacy_findings(question: str) -> List[Dict[str, object]]:
    """Return personal-data categories that should not be sent to the model."""
    return scan_personal_data(question)
