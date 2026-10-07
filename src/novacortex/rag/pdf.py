"""PDF document fetching / extraction."""

import io
import logging

from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

# ==================== PDF EXTRACTOR ====================
class PDFExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.cache = {}
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    def fetch_and_extract(self, url: str, max_pages: int = 10) -> Dict[str, Any]:
        if not url.lower().endswith('.pdf'):
            return {"text": "", "success": False, "error": "Not a PDF file", "is_garbled": False, "pages_extracted": 0}
        if url in self.cache:
            return self.cache[url]
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            pdf_bytes = response.content
            import pdfplumber  # lazy: only needed when a PDF is fetched
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                all_text = []
                pages_to_process = min(len(pdf.pages), max_pages)
                for page in pdf.pages[:pages_to_process]:
                    text = page.extract_text()
                    if text:
                        all_text.append(text.strip())
            combined_text = "\n\n".join(all_text)
            is_garbled = self._detect_garbled_text(combined_text)
            success = len(combined_text) > 100 and not is_garbled
            result = {"text": combined_text, "success": success, "is_garbled": is_garbled, "pages_extracted": pages_to_process}
            self.cache[url] = result
            return result
        except Exception as e:
            logger.error(f"PDF error: {e}")
            return {"text": "", "success": False, "error": str(e), "is_garbled": False, "pages_extracted": 0}
    def _detect_garbled_text(self, text: str) -> bool:
        if not text or len(text) < 50:
            return True
        words = text.split()
        if not words:
            return True
        short_word_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
        return short_word_ratio > 0.7 or len(text) < 300
