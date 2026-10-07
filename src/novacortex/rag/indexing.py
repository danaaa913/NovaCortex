"""JSON knowledge base -> Chroma vector store indexing."""

import hashlib
import json
import logging
import os
import re
import shutil

from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from novacortex.config import CHROMA_PATH, DATA_FILE

logger = logging.getLogger(__name__)

# ==================== DATA FILE HASH (Auto-rebuild) ====================
DATA_HASH_FILE = Path("cache") / "data_hash.txt"
def _compute_file_hash(filepath: str) -> str:
    """Compute MD5 hash of a file for change detection."""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()
def _data_has_changed(filepath: str) -> bool:
    """Check if yarmouk_data.json has changed since last index."""
    current_hash = _compute_file_hash(filepath)
    if DATA_HASH_FILE.exists():
        saved_hash = DATA_HASH_FILE.read_text().strip()
        if saved_hash == current_hash:
            return False
    return True
def _save_data_hash(filepath: str):
    """Save current hash after successful indexing."""
    DATA_HASH_FILE.write_text(_compute_file_hash(filepath))
# ==================== DATA LOADING (Auto-rebuild) ====================
# ✅ FIX 1: كشف وتصحيح المحتوى المقلوب (garbled bidi text من PDF)
# السبب: استخراج PDF يقلب كل كلمة عربية — الحل هو قلبها مرة أخرى وليس حذفها
def _is_garbled_content(content: str) -> bool:
    """يكشف النص العربي المقلوب."""
    garbled_markers = [
        'بوساحلا مولع', 'تامولعملا ايجولونكت', 'سويرولاكبلا ةجردل',
        'ةيساردلا ةطخلا', 'كومريلا ةعماج', 'مــــــسق'
    ]
    return any(m in (content or '')[:500] for m in garbled_markers)

def _fix_reversed_arabic(text: str) -> str:
    """يصحح النص المقلوب بقلب كل كلمة عربية مرة أخرى مع الحفاظ على الإنجليزي والأرقام."""
    if not text:
        return text
    tokens = re.split(r'(\s+)', text)
    fixed = []
    for token in tokens:
        if not token.strip():
            fixed.append(token)
        elif re.match(r'^[A-Za-z0-9\(\)/\-\.,:;%+]+$', token):
            fixed.append(token)
        elif re.search(r'[\u0600-\u06FF]', token):
            fixed.append(token[::-1])
        else:
            fixed.append(token)
    return ''.join(fixed)

# ✅ FIX 4: تصحيح عناوين ExternalPlans ليعرفها الـ RAG
EXTERNAL_PLANS_TITLE_MAP = {
    'ExternalPlans': 'خطة بكالوريوس علوم الحاسوب',
    'ExternalPlans — fmd (2)': 'خطة بكالوريوس علم البيانات والذكاء الاصطناعي',
    'ExternalPlans — fmd (3)': 'خطة بكالوريوس نظم المعلومات الحاسوبية',
    'ExternalPlans — fmd (4)': 'خطة بكالوريوس الأمن السيبراني',
    'ExternalPlans — fmd (5)': 'خطة بكالوريوس علوم الحاسوب نسخة 2',
    'ExternalPlans — fmd (6)': 'خطة ماجستير ذكاء الأعمال رسالة',
    'ExternalPlans — fmd (7)': 'خطة بكالوريوس تكنولوجيا معلومات الأعمال',
    'ExternalPlans — fmd (8)': 'خطة ماجستير ذكاء الأعمال امتحان شامل',
    'ExternalPlans — fmd (9)': 'خطة بكالوريوس نظم المعلومات الحاسوبية نسخة 2',
    'ExternalPlans — fmd (10)': 'خطة بكالوريوس علوم الحاسوب نسخة 3',
    'ExternalPlans — fmd (11)': 'خطة ماجستير الذكاء الاصطناعي امتحان شامل',
    'ExternalPlans — fmd (12)': 'خطة بكالوريوس الواقع الرقمي وتطوير الألعاب',
    'ExternalPlans — fmd (13)': 'خطة بكالوريوس نظم المعلومات الحاسوبية نسخة 3',
    'ExternalPlans — fmd (14)': 'خطة بكالوريوس علوم الحاسوب نسخة 4',
}

def load_data_from_json():
    # Imported lazily so that the package can be imported (and the pure
    # helpers below unit tested) without loading the RAG stack.
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    json_file = DATA_FILE
    if not json_file.exists():
        logger.error("yarmouk_data.json not found!")
        return False
    needs_rebuild = not os.path.exists(CHROMA_PATH) or not os.listdir(CHROMA_PATH)
    # Auto-rebuild: check if data has changed
    if not needs_rebuild and _data_has_changed(str(json_file)):
        logger.info("[AUTO-REBUILD] Data file changed! Rebuilding vector store...")
        shutil.rmtree(CHROMA_PATH, ignore_errors=True)
        needs_rebuild = True
    if needs_rebuild:
        logger.info("Building vector store from JSON...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Enhanced chunking: larger chunks + more separators for Arabic
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, chunk_overlap=200,
            separators=[
                "\n\n\n", "\n\n", "\n",
                ". ", "؟ ", "! ", "؛ ", "، ",
                "• ", "- ", "\t",
                " "
            ]
        )
        # ✅ FIX 2: حد أقصى للـ chunks من كل وثيقة لمنع هيمنة الوثائق الضخمة
        MAX_CHUNKS_PER_DOC = 12
        # الوثائق ذات الأولوية العالية تأخذ حداً أعلى
        HIGH_PRIORITY_MAX_CHUNKS = 20

        all_docs = []
        garbled_count = 0
        skipped_stub = 0
        for item in tqdm(data, desc="Processing documents"):
            content_parts = []
            original_title = item.get('title', 'No Title')
            # ✅ FIX 4: تصحيح العنوان عند الـ indexing
            fixed_title = EXTERNAL_PLANS_TITLE_MAP.get(original_title, original_title)

            if fixed_title:
                content_parts.append(f"# {fixed_title}")
            if item.get('description'):
                content_parts.append(item['description'])
            if item.get('content'):
                content_parts.append(item['content'])
            content = "\n\n".join(filter(None, content_parts))

            if not content.strip():
                continue

            # ✅ FIX 1: تصحيح المحتوى المقلوب بدلاً من حذفه — لا نخسر أي بيانات
            if _is_garbled_content(content):
                content = _fix_reversed_arabic(content)
                logger.info(f"[FIX-GARBLED] Fixed reversed text: {original_title}")
                garbled_count += 1

            # تخطي العناصر الصغيرة جداً (stub pages)
            if len(content.strip()) < 100:
                skipped_stub += 1
                continue

            # تحديد الأولوية
            item_priority = item.get('priority', 2)
            is_news = any(kw in original_title.lower() for kw in ['اخبار', 'خبر', 'news'])
            is_monster = len(content) > 20000
            if is_news:
                item_priority = 3
            elif is_monster and item_priority == 2:
                item_priority = 3

            chunks = splitter.create_documents([content.strip()])

            # ✅ FIX 2: تطبيق الحد الأقصى للـ chunks مع الاحتفاظ بالأهم
            max_chunks = HIGH_PRIORITY_MAX_CHUNKS if item_priority == 1 else MAX_CHUNKS_PER_DOC
            if len(chunks) > max_chunks:
                # خذ أول نصف وآخر نصف لتغطية بداية ونهاية الوثيقة
                half = max_chunks // 2
                chunks = chunks[:half] + chunks[-(max_chunks - half):]
                logger.info(f"[TRIM] Trimmed '{fixed_title[:40]}' from {len(chunks)+max_chunks} to {max_chunks} chunks")

            for chunk in chunks:
                chunk.metadata = {
                    "source": item.get("url", "manual"),
                    "title": fixed_title,  # ✅ استخدم العنوان المصحح
                    "category": item.get("category", "General"),
                    "description": item.get("description", "")[:100],
                    "priority": item_priority,  # ✅ أضف الأولوية للـ metadata
                    "indexed_at": datetime.now().isoformat()
                }
                all_docs.append(chunk)

        logger.info(f"[BUILD] Fixed garbled: {garbled_count}, Skipped stubs: {skipped_stub}")
        if all_docs:
            embeddings = HuggingFaceEmbeddings(
                model_name="intfloat/multilingual-e5-large-instruct",
                model_kwargs={'device': 'cpu'}
            )
            Chroma.from_documents(documents=all_docs, embedding=embeddings, persist_directory=CHROMA_PATH)
            _save_data_hash(str(json_file))
            logger.info(f"Vector store created with {len(all_docs)} chunks")
            return True
        else:
            logger.error("No documents to index!")
            return False
    else:
        logger.info("Vector store already exists (data unchanged)")
        return True
