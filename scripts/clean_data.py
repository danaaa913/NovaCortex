import json
import re
import logging
from tqdm import tqdm

# إعداد اللوجر لمتابعة عملية التنظيف
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clean_html_and_whitespace(text):
    """إزالة بقايا HTML والمسافات الزائدة."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_meaningful_sentences(text, min_words=4):
    """استخلاص الجمل التي تحتوي على عدد كافٍ من الكلمات."""
    # تقسيم النص إلى جمل باستخدام علامات الترقيم الشائعة ونوازل الأسطر
    sentences = re.split(r'[.!?؟\n\r]+', text)
    meaningful_sentences = []
    for sentence in sentences:
        cleaned_sentence = sentence.strip()
        # التأكد من أن الجملة تحتوي على عدد كافٍ من الكلمات وليست مجرد روابط أو كلمات متفرقة
        if len(cleaned_sentence.split()) >= min_words and 'http' not in cleaned_sentence and '|' not in cleaned_sentence:
            meaningful_sentences.append(cleaned_sentence )
    return ". ".join(meaningful_sentences)

def extract_contact_info(text):
    """استخلاص الإيميلات وأرقام الهواتف من النص."""
    emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    # نمط أكثر شمولاً لأرقام الهواتف
    phones = re.findall(r'\(?\+?\d{1,4}?\)?[-\s\.\d]{7,}', text)
    
    # تنظيف أرقام الهواتف من أي حروف أو رموز غير مرغوبة
    cleaned_phones = []
    for phone in phones:
        # إزالة أي شيء ليس رقماً أو + أو - أو ()
        p = re.sub(r'[^\d\+\-\(\)]', '', phone).strip()
        # التأكد من أن الرقم يحتوي على 5 أرقام على الأقل ليكون رقم هاتف صالح
        if len(re.sub(r'\D', '', p)) >= 5:
            cleaned_phones.append(p)
            
    return list(set(emails)), list(set(cleaned_phones))

def process_generic_page(item):
    """المعالجة العامة لأي صفحة."""
    content = item.get('content', '')
    
    # 1. استخلاص معلومات الاتصال أولاً
    emails, phones = extract_contact_info(content)
    
    # 2. تنظيف المحتوى الرئيسي
    cleaned_content = clean_html_and_whitespace(content)
    meaningful_text = extract_meaningful_sentences(cleaned_content)
    
    # 3. بناء المحتوى النهائي
    final_content_parts = []
    if meaningful_text:
        final_content_parts.append(meaningful_text)
        
    # 4. إضافة معلومات الاتصال في جمل واضحة إذا وجدت
    contact_sentences = []
    if emails:
        contact_sentences.append(f"البريد الإلكتروني للتواصل هو: {', '.join(emails)}")
    if phones:
        contact_sentences.append(f"رقم الهاتف للتواصل هو: {', '.join(phones)}")
    
    if contact_sentences:
        final_content_parts.append(" ".join(contact_sentences))
        
    item['content'] = ". ".join(final_content_parts)
    return item

def clean_data(input_file, output_file):
    """
    الدالة الرئيسية التي تقرأ الملف الخام، تنظفه، وتحفظه في ملف جديد.
    """
    logging.info(f"بدء عملية تنظيف الملف: {input_file}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logging.error(f"خطأ: لم يتم العثور على الملف {input_file}. تأكد من أنه في نفس المجلد.")
        return
    except json.JSONDecodeError:
        logging.error(f"خطأ: الملف {input_file} ليس ملف JSON صالح.")
        return

    cleaned_data = []
    
    # كلمات مفتاحية لتحديد الصفحات التي يجب تجاهلها بالكامل
    discard_titles = [
        'مجلس الامناء', 'العمداء السابقون', 'فريق الدعم الفني', 
        'الموظفون الاداريون', 'رؤساء القسم السابقون', 'هيكل الكلية'
    ]

    for item in tqdm(data, desc="جاري تنظيف المستندات"):
        title = item.get('title', '').strip()
        
        # 1. تجاهل الصفحات غير المرغوب فيها
        if any(keyword in title for keyword in discard_titles):
            logging.info(f"تجاهل صفحة قائمة: {title}")
            continue
            
        # 2. تطبيق التنظيف العام على جميع الصفحات المتبقية
        cleaned_item = process_generic_page(item)
        
        # 3. التأكد من أن المحتوى النهائي ليس فارغاً
        if len(cleaned_item.get('content', '')) < 50:
            logging.info(f"تجاهل صفحة ذات محتوى قليل بعد التنظيف: {title}")
            continue

        cleaned_data.append(cleaned_item)

    logging.info(f"اكتمل التنظيف. عدد المستندات الأصلية: {len(data)}, عدد المستندات النظيفة: {len(cleaned_data)}")

    # 4. حفظ البيانات النظيفة في ملف جديد
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        logging.info(f"تم حفظ البيانات النظيفة بنجاح في الملف: {output_file}")
    except Exception as e:
        logging.error(f"حدث خطأ أثناء حفظ الملف الجديد: {e}")

if __name__ == "__main__":
    from pathlib import Path as _Path
    ROOT = _Path(__file__).resolve().parents[1]
    INPUT_JSON_FILE = str(ROOT / "data" / "yarmouk_scraped_it_focused.json")
    OUTPUT_JSON_FILE = str(ROOT / "data" / "yarmouk_data_cleaned.json")
    
    clean_data(INPUT_JSON_FILE, OUTPUT_JSON_FILE)

    print("\n" + "="*50)
    print("العملية اكتملت بنجاح!")
    print("1. تم إنشاء ملف 'yarmouk_data_cleaned.json' بالبيانات النظيفة.")
    print("2. في الكود الرئيسي للبوت، غيّر اسم الملف في دالة `load_data_from_json` إلى 'yarmouk_data_cleaned.json'.")
    print("3. **مهم جداً:** احذف مجلد 'chroma_ultra' القديم.")
    print("4. قم بتشغيل البوت الرئيسي. سيقوم ببناء قاعدة بيانات جديدة تماماً من البيانات النظيفة.")
    print("="*50)
