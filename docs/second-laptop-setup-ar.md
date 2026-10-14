# تجهيز لابتوب جديد لنسخة المسابقة

هذا الدليل خاص بمساعد الوثائق المحلي الموجود على فرع
`codex/hackathon-local-rag`. لا يحتاج مفاتيح Groq أو Telegram أو أي خدمة
سحابية.

## المتطلبات

- ذاكرة RAM بسعة 16GB موصى بها لتشغيل `qwen2.5:7b` براحة.
- مساحة فارغة لا تقل عن 12GB للموديلات، المكتبات والفهرس التجريبي.
- Git.
- Python 3.11 موصى به. يدعم المشروع Python 3.10 أو أحدث، لكن 3.11 هو الخيار
  الأكثر أمانًا لتوافق المكتبات في المسابقة.
- Ollama، مع الموديلين:
  - `qwen2.5:7b` للإجابة.
  - `embeddinggemma` لإنشاء الـembeddings.

تحقق من Ollama:

```bash
ollama list
ollama pull qwen2.5:7b
ollama pull embeddinggemma
```

## تنزيل المشروع

```bash
git clone --branch codex/hackathon-local-rag --single-branch https://github.com/danaaa913/NovaCortex.git
cd NovaCortex
```

إذا كان المشروع موجودًا مسبقًا:

```bash
git switch codex/hackathon-local-rag
git pull --ff-only origin codex/hackathon-local-rag
```

## إنشاء البيئة وتثبيت المكتبات

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r hackathon_requirements.txt
Copy-Item hackathon.env.example hackathon.env
```

### Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r hackathon_requirements.txt
cp hackathon.env.example hackathon.env
```

ملف `hackathon_requirements.txt` يثبت Chroma، قارئات PDF وWord وPowerPoint
وExcel، FastAPI، Uvicorn، Streamlit، LangGraph وMCP وجميع مكتبات نسخة المسابقة.

## تجربة البيانات الحكومية الصغيرة

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force hackathon_workspace\documents
Copy-Item examples\government_services_ar\documents\* hackathon_workspace\documents -Force
```

### Linux

```bash
mkdir -p hackathon_workspace/documents
cp examples/government_services_ar/documents/* hackathon_workspace/documents/
```

ثم نفذ على النظامين:

```bash
python hackathon.py doctor
python hackathon.py preview --output hackathon_workspace/government-preview.json
python hackathon.py ingest
python hackathon.py evaluate examples/government_services_ar/evaluation.json
python hackathon_api.py
```

افتح `http://127.0.0.1:8000` في المتصفح.

## فحوص سريعة عند حدوث مشكلة

```bash
python --version
python -m pip --version
ollama list
python hackathon.py doctor
```

يجب أن يكون Ollama قيد التشغيل، وأن يظهر `qwen2.5:7b` و`embeddinggemma` في
`ollama list`. الفهرس ومجلد `hackathon_workspace` لا يرفعان إلى GitHub؛ يعاد
بناؤهما محليًا من الوثائق على كل جهاز.
