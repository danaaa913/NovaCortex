import json
import re
from pathlib import Path

def clean_text(text):
    if not text:
        return ""
    
    # 1. إزالة نصوص القوائم الملاحية والروابط المكررة الشائعة في موقع جامعة اليرموك
    noise_patterns = [
        r"روابط سريعة.*?(?=الدوائر|الكليات|العمادات|$)",
        r"اتصل بنا.*?(\+962\d+|yarmouk@yu\.edu\.jo)",
        r"عن الجامعة.*?الخطة الاستراتيجية",
        r"مشاهدة جميع (الاخبار|الاعلانات)",
        r"Follow Us",
        r"مركز الاعتماد|مركز الملكة رانيا|المدرسة النموذجية",
        r"شكاوى الطلاب|شكاوى العاملين|شكاوى المتعاملين",
        r"الانظمة والقوانين|التعليمات|الاسس",
        r"البريد الإلكتروني للتواصل هو:.*",
        r"رقم الهاتف للتواصل هو:.*",
        r"اربد- الاردن, ص\. ب 566 الرمز البريدي 21163",
        r"Irbid - Jordan, P\. O Box 566 ZipCode 21163",
        r"حقائق سريعة.*?برنامج دراسات عليا",
        r"خرائط الجامعة|جولة افتراضية|خريطة الجامعة",
        r"المنصات الإلكترونية.*?المكتبة",
        r"المرافق والخدمات العامة.*?قسم دعم الأقليات"
    ]
    
    cleaned = text
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. إزالة المسافات الزائدة والأسطر الفارغة
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # 3. إزالة التكرار المتتالي للجمل (إذا وجدت نفس الجملة مكررة أكثر من مرتين)
    sentences = cleaned.split('. ')
    unique_sentences = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent: continue
        # إضافة الجملة فقط إذا لم تكن مكررة مباشرة
        if i == 0 or sent != sentences[i-1].strip():
            unique_sentences.append(sent)
    
    return ". ".join(unique_sentences).strip()

def process_json(input_path, output_path):
    print(f"🚀 Starting cleaning process for: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    cleaned_data = []
    for item in data:
        # تنظيف المحتوى الرئيسي
        original_content = item.get('content', '')
        cleaned_content = clean_text(original_content)
        
        # تنظيف الوصف إذا وجد
        original_desc = item.get('description', '')
        cleaned_desc = clean_text(original_desc)
        
        # الحفاظ على البيانات المهمة الأخرى
        new_item = item.copy()
        new_item['content'] = cleaned_content
        new_item['description'] = cleaned_desc
        
        # إضافة وسم لبيان أن البيانات تم تنظيفها
        new_item['is_refined'] = True
        
        # إضافة العنصر فقط إذا كان المحتوى بعد التنظيف لا يزال مفيداً
        if len(cleaned_content) > 50:
            cleaned_data.append(new_item)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Cleaning complete! Saved to: {output_path}")
    print(f"📊 Original items: {len(data)} | Cleaned items: {len(cleaned_data)}")

if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[1]
    input_file = ROOT / "data" / "yarmouk_data_cleaned.json"
    output_file = ROOT / "data" / "yarmouk_data.json"
    process_json(input_file, output_file)