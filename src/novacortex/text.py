"""Arabic text normalisation / tokenisation helpers."""

import re

from typing import List

import nltk

from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

try:
    nltk.data.find('corpora/stopwords')
except:
    nltk.download('stopwords', quiet=True)
# ==================== ARABIC PROCESSOR ====================
class ArabicProcessor:
    def __init__(self):
        self.stemmer = SnowballStemmer("arabic")
        self.stopwords = set(stopwords.words("arabic"))
        self.space_pattern = re.compile(r'\s+')
    def normalize(self, text: str) -> str:
        if not text: return ""
        text = text.strip()
        text = re.sub(r"[إأآا]", "ا", text)
        text = re.sub(r"ى", "ي", text)
        text = re.sub(r"ة", "ه", text)
        text = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)
        text = self.space_pattern.sub(' ', text)
        return text.strip()
    def tokenize(self, text: str) -> List[str]:
        text = self.normalize(text)
        words = text.split()
        tokens = []
        for word in words:
            if len(word) > 2 and word not in self.stopwords:
                try:
                    tokens.append(self.stemmer.stem(word))
                except:
                    tokens.append(word)
        return tokens
    def detect_language(self, text: str) -> str:
        if not text:
            return "ar"
        clean_text = re.sub(r'[0-9\s\.,!?;:\-()]+', '', text)
        if not clean_text:
            return "ar"
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', clean_text))
        latin_chars = len(re.findall(r'[a-zA-Z]', clean_text))
        total_chars = arabic_chars + latin_chars
        if arabic_chars == 0 and latin_chars > 0:
            return "en"
        if latin_chars == 0 and arabic_chars > 0:
            return "ar"
        if total_chars > 0:
            return "ar" if arabic_chars / total_chars >= 0.6 else "en"
        return "ar"
arabic_processor = ArabicProcessor()
