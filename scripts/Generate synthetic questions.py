"""
Synthetic Questions Generator v2.0
معالج: منع الهلوسة، تحقق جودة، تصنيف تلقائي، variations كاملة
"""

import json
import os
import re
import time
import random
from openai import OpenAI
import httpx
from tqdm import tqdm
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ==================== CONFIG ====================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    http_client=httpx.Client(follow_redirects=True, timeout=60.0)
)

INPUT_FILE = str(ROOT / "data" / "yarmouk_data.json")
OUTPUT_FILE = str(ROOT / "synthetic_questions.json")
PROGRESS_FILE = str(ROOT / "progress.json")
BATCH_SIZE = 2

# ==================== الموديل السريع والمستقر ====================
MODEL_NAME = "llama-3.1-8b-instant"
MAX_RETRIES = 5

# ==================== دالة retry محسنة ====================
def call_llm_with_retry(prompt, response_format=None, temperature=0.7, max_tokens=1000):
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format=response_format,
                temperature=temperature,
                max_tokens=max_tokens
            )
            content = response.choices[0].message.content.strip()
            return json.loads(content)
        except json.JSONDecodeError:
            print("  ⚠️ JSON decode error، محاولة تاني...")
            temperature = max(0.3, temperature - 0.15)
        except Exception as e:
            error_str = str(e)
            print(f"  ⚠️ محاولة {attempt+1}/{MAX_RETRIES} فشلت: {error_str[:200]}")
            
            if "429" in error_str or "rate limit" in error_str.lower():
                match = re.search(r'try again in (\d+m?\d*\.?\d*s?)', error_str)
                if match:
                    wait_str = match.group(1)
                    if 'm' in wait_str:
                        minutes = float(re.findall(r'\d+', wait_str)[0])
                        wait = minutes * 60 + 10
                    else:
                        wait = float(re.findall(r'\d+\.?\d*', wait_str)[0]) + 10
                else:
                    wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                
                print(f"  ⏳ Rate limit، انتظر {wait:.1f} ثانية...")
                time.sleep(wait)
                
            elif "400" in error_str or "json" in error_str.lower():
                print("  → مشكلة JSON، محاولة مع temperature أقل...")
                temperature = max(0.3, temperature - 0.15)
                
            else:
                time.sleep(5)
    
    print("  ❌ فشل بعد كل المحاولات")
    return {}

# ==================== QUALITY VALIDATION ====================
def _is_valid_question(q: str) -> bool:
    """Validate a question meets quality standards."""
    if not isinstance(q, str):
        return False
    q = q.strip()
    if len(q.split()) < 4:
        return False
    if not any(c in q for c in ['؟', '?']):
        return False
    # Reject if it's clearly not a question (just a phrase)
    if len(q) < 15:
        return False
    return True

# ==================== AUTO CATEGORY DETECTION ====================
CATEGORY_KEYWORDS = {
    'fees': ['رسوم', 'رسم', 'تكلفة', 'تكاليف', 'مصاريف', 'fees', 'tuition', 'cost'],
    'admission': ['قبول', 'تسجيل', 'شروط', 'التحاق', 'admission', 'registration', 'requirements'],
    'programs': ['تخصص', 'برنامج', 'كلية', 'قسم', 'program', 'faculty', 'major', 'department'],
    'services': ['خدم', 'مكتبة', 'سكن', 'تأمين', 'service', 'library', 'housing', 'insurance'],
    'academic': ['ساعات', 'خطة', 'أكاديمي', 'فصل', 'credit', 'academic', 'semester', 'exam'],
    'staff': ['عميد', 'دكتور', 'رئيس', 'أستاذ', 'dean', 'professor', 'president', 'head'],
}
def auto_detect_category(content: str, fallback: str = 'General') -> str:
    """Auto-detect category from content keywords."""
    content_lower = content.lower()
    best_cat = fallback
    best_count = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in content_lower)
        if count > best_count:
            best_count = count
            best_cat = cat
    return best_cat

# ==================== PHASE 1 ====================
def generate_base_questions(text: str, title: str, category: str) -> list:
    prompt = f"""أنت خبير في توليد أسئلة طلابية عن جامعة اليرموك.

العنوان: {title}
الفئة: {category}
المحتوى:
{text[:1500]}

ولّد 8 أسئلة متنوعة يمكن الإجابة عليها من المحتوى أعلاه:
- 3 فصحى رسمية
- 3 عامية أردنية طبيعية
- 2 إنجليزي

❗ قواعد صارمة:
1. كل سؤال يجب أن تكون إجابته موجودة في المحتوى أعلاه — لا تفبرك معلومات
2. لا تذكر تواريخ أو أرقام غير موجودة في المحتوى
3. كل سؤال لازم ينتهي بعلامة استفهام (؟ أو ?)
4. كل سؤال لازم يكون جملة كاملة (مش كلمتين)
5. تنوع في الأسلوب: سؤال بعضها يبدأ بـ "ما هي"، "كيف"، "هل"، "كم"

الرد JSON فقط:
{{"أسئلة": ["سؤال1", "سؤال2", ...]}}"""

    result = call_llm_with_retry(prompt, {"type": "json_object"}, temperature=0.6, max_tokens=800)

    # Support both Arabic and English key names
    questions = result.get("أسئلة", result.get("questions", []))
    if not isinstance(questions, list):
        print("  ⚠️ النتيجة مش list، تخطي...")
        return []

    # Quality validation
    valid_questions = [q.strip() for q in questions if _is_valid_question(q)]
    rejected = len(questions) - len(valid_questions)
    if rejected > 0:
        print(f"  🔍 رفض {rejected} سؤال (لا يستوفي الجودة)")

    if len(valid_questions) < 3:
        print(f"  ⚠️ أسئلة صالحة قليلة ({len(valid_questions)} فقط)، تخطي...")
        return []

    return valid_questions

# ==================== PHASE 2 ====================
def generate_variations(original_question: str, count: int = 3) -> list:
    prompt = f"""لديك سؤال عن جامعة اليرموك: "{original_question}"

ولّد {count} صيغ بديلة بنفس المعنى بالضبط.

❗ قواعد صارمة:
1. كل صيغة لازم تكون جملة كاملة ومفهومة لوحدها
2. كل صيغة تنتهي بعلامة استفهام (؟ أو ?)
3. المعنى يبقى نفسه — فقط غيّر الكلمات والأسلوب
4. لا تضف معلومات جديدة مش موجودة في السؤال الأصلي
5. ممنوع الصيغ القصيرة (كلمتين أو 3) — 4 كلمات على الأقل

الرد JSON فقط:
{{"variations": ["صيغة1", "صيغة2", "صيغة3"]}}"""

    result = call_llm_with_retry(prompt, {"type": "json_object"}, temperature=0.65, max_tokens=400)

    variations = result.get("variations", [])
    if not isinstance(variations, list):
        return []

    # Quality filter: full sentences with question marks only
    valid = [v.strip() for v in variations
             if _is_valid_question(v) and v.strip() != original_question.strip()]
    return valid[:count]

# ==================== PHASE 3 ====================
def process_item(item: dict, existing_questions_set: set, progress: dict, global_idx: int) -> list:
    synthetic_questions = []

    content = item.get('content', '') or item.get('description', '')
    title = item.get('title', 'معلومات عامة')
    raw_category = item.get('category', 'General')
    url = item.get('url', '')

    if len(content.strip()) < 100:
        return []

    # Auto-detect category from content
    category = auto_detect_category(content, raw_category)

    item_key = str(global_idx)

    # ✅ التحقق: هل العنصر مكتمل من قبل؟
    if item_key in progress:
        item_progress = progress[item_key]

        # تحويل الصيغة القديمة إلى الجديدة
        if isinstance(item_progress, int):
            item_progress = {"total": item_progress, "completed": True}
            progress[item_key] = item_progress

        # ✅ لو مكتمل، تخطيه تماماً
        if item_progress.get("completed", False):
            total = item_progress.get("total", 0)
            print(f"  ⏭️ تخطي عنصر {global_idx} (مكتمل: {total} سؤال)")
            return []

    # ✅ توليد الأسئلة
    base_questions = generate_base_questions(content, title, category)
    if not base_questions:
        progress[item_key] = {"total": 0, "completed": True}
        return []

    print(f"  ✅ ولّد {len(base_questions)} سؤال أساسي [تصنيف: {category}] من: {title[:50]}...")

    for base_q in base_questions:
        if not isinstance(base_q, str) or base_q in existing_questions_set:
            continue

        synthetic_questions.append({
            "question": base_q,
            "answer_source": title,
            "category": category,
            "url": url,
            "original_content": content[:800],
            "is_variation": False,
            "source_id": global_idx
        })
        existing_questions_set.add(base_q)

        # Generate 3 variations (down from 4 to improve quality)
        variations = generate_variations(base_q, count=3)

        for var_q in variations:
            if not isinstance(var_q, str) or var_q in existing_questions_set:
                continue
            synthetic_questions.append({
                "question": var_q,
                "answer_source": title,
                "category": category,
                "url": url,
                "original_content": content[:800],
                "is_variation": True,
                "base_question": base_q,
                "source_id": global_idx
            })
            existing_questions_set.add(var_q)

        time.sleep(0.5)

    # ✅ تسجيل العنصر كمكتمل
    progress[item_key] = {
        "total": len(synthetic_questions),
        "completed": True
    }

    return synthetic_questions

# ==================== دالة حفظ ====================
def save_progress_and_questions(all_synthetic, progress):
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_synthetic, f, ensure_ascii=False, indent=2)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

# ==================== MAIN ====================
def main():
    print("🚀 بدء/استكمال توليد الأسئلة")
    print("=" * 60)
    
    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} غير موجود!")
        return
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📊 تحميل {len(data)} عنصر")
    
    rich_items = [item for item in data if len(item.get('content', '') or item.get('description', '')) >= 100]
    
    print(f"🎯 {len(rich_items)} عنصر غني")
    print(f"📈 متوقع: {len(rich_items) * 50} سؤال تقريبًا")
    print("-" * 60)
    
    all_synthetic = []
    progress = {}
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            all_synthetic = json.load(f)
        print(f"  📂 تحميل {len(all_synthetic)} سؤال سابق")
    
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        
        # تحويل الصيغة القديمة للجديدة
        converted = False
        for key in progress:
            if isinstance(progress[key], int):
                progress[key] = {"total": progress[key], "completed": True}
                converted = True
        if converted:
            print("  🔄 تم تحويل التقدم القديم إلى الصيغة الجديدة")
    
    completed = sum(1 for v in progress.values() if isinstance(v, dict) and v.get("completed", False))
    print(f"  📊 تقدم: {completed}/{len(rich_items)} عنصر مكتمل")
    
    existing_questions_set = set(q["question"] for q in all_synthetic if isinstance(q.get("question"), str))
    
    for i in range(0, len(rich_items), BATCH_SIZE):
        batch = rich_items[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(rich_items) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n📦 Batch {batch_num}/{total_batches} ({len(batch)} items)")
        
        for idx, item in enumerate(tqdm(batch, desc=f"  Processing Batch {batch_num}")):
            global_idx = i + idx
            questions = process_item(item, existing_questions_set, progress, global_idx)
            all_synthetic.extend(questions)
            
            save_progress_and_questions(all_synthetic, progress)
        
        print(f"  💾 حفظ تلقائي بعد Batch {batch_num}: {len(all_synthetic)} سؤال")
        
        if i + BATCH_SIZE < len(rich_items):
            time.sleep(5)
    
    save_progress_and_questions(all_synthetic, progress)
    
    print("\n" + "=" * 60)
    print("✅ انتهى التوليد!")
    print(f"📊 إجمالي الأسئلة: {len(all_synthetic)}")
    print(f"📁 الملفات: {OUTPUT_FILE} | {PROGRESS_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()