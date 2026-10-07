"""
Constants and static content for NovaCortex Bot
Contains roadmaps, messages, and other static data
"""

# Conversation states for registration flow
ROLE, INTL, ASK_UNI_ID, ASK_EMAIL = range(4)

# IT Roadmaps
ROADMAPS = {
    "web": """
🌐 **خارطة طريق: تطوير الويب (Web Development)**

**المستوى الأساسي (3-4 أشهر):**
• HTML5 & CSS3 - بناء صفحات الويب
• JavaScript الأساسيات - البرمجة التفاعلية
• Git & GitHub - إدارة الكود
• Responsive Design - التصميم المتجاوب
📚 مصادر: freeCodeCamp, MDN Web Docs

**المستوى المتوسط (4-6 أشهر):**
• Frontend Framework: React أو Vue.js
• Backend: Node.js + Express أو Django/Python
• REST APIs - التواصل بين Frontend/Backend
• قواعد البيانات: PostgreSQL أو MongoDB
📚 مصادر: The Odin Project, Full Stack Open

**المستوى المتقدم (6+ أشهر):**
• TypeScript - تطوير آمن وقوي
• Next.js أو Nuxt.js - Server Side Rendering
• Docker & Deployment - النشر والتوزيع
• Authentication & Security - الحماية والأمان
• GraphQL (اختياري)
📚 مصادر: Udemy, Pluralsight

**مشروع تخرج مقترح:**
نظام إدارة خدمات طلابية لجامعة اليرموك:
- تسجيل المواد
- حجز السكن الجامعي
- تتبع الحضور والغياب
- نظام تقييم المدرسين

💡 **نصيحة:** ابني مشاريع صغيرة باستمرار، وانشرها على GitHub!
""",

    "ml": """
🤖 **خارطة طريق: الذكاء الاصطناعي وتعلم الآلة (ML/AI)**

**المستوى الأساسي (3-4 أشهر):**
• Python - اللغة الأساسية
• NumPy & Pandas - معالجة البيانات
• Matplotlib & Seaborn - تصوير البيانات
• رياضيات: جبر خطي + إحصاء + حساب التفاضل
📚 مصادر: Kaggle Learn, DataCamp

**المستوى المتوسط (6-8 أشهر):**
• Scikit-learn - خوارزميات ML الكلاسيكية
• Feature Engineering - هندسة الميزات
• Model Evaluation - تقييم النماذج
• مشاريع عملية على Kaggle
• مشاريع: Regression, Classification, Clustering
📚 مصادر: Andrew Ng's ML Course (Coursera)

**المستوى المتقدم (8+ أشهر):**
• Deep Learning: PyTorch أو TensorFlow
• Computer Vision (CV) أو NLP حسب الاهتمام
• Transformers & Large Language Models
• MLOps - نشر النماذج في الإنتاج
• Cloud Platforms (AWS/GCP/Azure)
📚 مصادر: Fast.ai, DeepLearning.AI

**تخصصات فرعية:**
1. **Computer Vision:** تحليل الصور والفيديو
2. **NLP:** معالجة اللغة الطبيعية
3. **Time Series:** تحليل البيانات الزمنية
4. **Recommender Systems:** أنظمة التوصية

**مشروع تخرج مقترح:**
نظام ذكي لجامعة اليرموك:
- نظام تنبؤ بأداء الطلاب
- chatbot ذكي للإجابة على أسئلة الطلاب (مثلي! 😊)
- نظام توصية للمواد الدراسية
- تحليل آراء الطلاب من تقييمات المدرسين

💡 **نصيحة:** المشاريع العملية أهم من الشهادات - ابني portfolio قوي!
""",

    "mobile": """
📱 **خارطة طريق: تطوير تطبيقات الموبايل**

**المستوى الأساسي (3-4 أشهر):**
• أساسيات البرمجة (Python أو Java)
• مفاهيم OOP
• Git & Version Control
• UI/UX Basics

**المستوى المتوسط (4-6 أشهر):**
اختر مسار:

**1. Native Development:**
• Android: Kotlin + Jetpack Compose
• iOS: Swift + SwiftUI

**2. Cross-Platform (أسهل للبداية):**
• Flutter (Dart) - موصى به للمبتدئين
• React Native (JavaScript)

**المستوى المتقدم (6+ أشهر):**
• State Management (Provider, Bloc, Redux)
• REST APIs & Firebase
• Local Storage & SQLite
• Push Notifications
• App Store & Google Play Publishing

**مشروع مقترح:**
تطبيق خدمات طلاب جامعة اليرموك:
- الجدول الدراسي
- حساب المعدل
- أخبار الجامعة
- خريطة الكليات
- نظام حجز المواصلات

💡 **نصيحة:** Flutter أفضل للبداية - تطبيق واحد يشتغل على Android و iOS!
""",

    "data": """
📊 **خارطة طريق: علم البيانات (Data Science)**

**المستوى الأساسي (3-4 أشهر):**
• Python - لغة علم البيانات
• SQL - قواعد البيانات
• Excel المتقدم
• إحصاء أساسي
• NumPy & Pandas

**المستوى المتوسط (6-8 أشهر):**
• Data Cleaning & Preprocessing
• Exploratory Data Analysis (EDA)
• Data Visualization: Matplotlib, Seaborn, Plotly
• Statistical Analysis
• BI Tools: Tableau أو Power BI

**المستوى المتقدم (8+ أشهر):**
• Machine Learning Basics
• Big Data: Spark, Hadoop
• Cloud: AWS, GCP, Azure
• A/B Testing
• Dashboard Development

**مشروع مقترح:**
تحليل بيانات جامعة اليرموك:
- تحليل معدلات النجاح حسب التخصص
- التنبؤ بأعداد الطلاب المسجلين
- dashboard تفاعلي لإحصائيات الجامعة
- تحليل رضا الطلاب

💡 **نصيحة:** ابدأ بمشاريع حقيقية من Kaggle أو بيانات محلية!
"""
}

# Welcome message
WELCOME_MESSAGE = """
🎓 **أهلاً وسهلاً في NovaCortex!**

أنا مساعدك الذكي الخاص بجامعة اليرموك 🏛️

**يمكنني مساعدتك في:**
• 📚 معلومات عن الكليات والتخصصات
• 📝 القبول والتسجيل والرسوم
• 🏠 السكن الجامعي والخدمات
• 🌍 دعم الطلاب الدوليين
• 💼 الحياة الطلابية والأنشطة
• 🎯 المسارات الوظيفية في IT

**الأوامر المتاحة:**
/help - عرض المساعدة والأوامر
/history - آخر محادثاتك
/roadmap - خارطة طريق تعلم IT
/clear - مسح الذاكرة الحالية
/register - تحديث بياناتك

**💬 جرب الآن:** اسألني أي سؤال عن الجامعة!
"""

# Help message
HELP_MESSAGE = """
❓ **كيف تستخدم NovaCortex؟**

**📝 للأسئلة:**
• اكتب سؤالك مباشرة بدون أي أوامر
• لو بدك توضيح أكثر قول "قصدي..." أو "يعني..."
• أنا بفهم اللهجة الأردنية والعربية الفصحى

**🎯 أمثلة على الأسئلة:**
• "شو الكليات المتاحة في الجامعة؟"
• "كيف بسجل مواد؟"
• "كم رسوم كلية الهندسة؟"
• "في سكن جامعي؟"
• "شو الأوراق المطلوبة للتسجيل؟"

**⚙️ الأوامر المتاحة:**
/start - البداية والترحيب
/register - تسجيل أو تحديث بياناتك
/history - عرض آخر محادثاتك
/roadmap <مجال> - خارطة طريق تعلم:
  • /roadmap web - تطوير الويب
  • /roadmap ml - الذكاء الاصطناعي
  • /roadmap mobile - تطوير التطبيقات
  • /roadmap data - علم البيانات
/clear - مسح الذاكرة الحالية
/stats - إحصائيات استخدامك (قريباً)

**💡 نصائح:**
• كون محدد في سؤالك عشان الإجابة تكون أدق
• لو الإجابة مش واضحة، اسأل مرة ثانية بطريقة مختلفة
• استخدم زر 👍 أو 👎 عشان تساعدني أتحسن!

**🆘 محتاج مساعدة؟**
تواصل مع الجامعة:
📞 الهاتف: 027211111
🌐 الموقع: https://www.yu.edu.jo
📧 البريد: info@yu.edu.jo
"""

# Registration messages
REGISTRATION_MESSAGES = {
    "choose_role": "مرحباً! 🎓\n\nعشان أقدر أساعدك بشكل أفضل، حدد نوع حسابك:",
    "ask_international": "هل أنت طالب دولي (من خارج الأردن)؟",
    "ask_uni_id": "ممتاز! 👍\n\nاكتب رقمك الجامعي (7-10 أرقام):",
    "invalid_uni_id": "⚠️ الرقم الجامعي لازم يكون أرقام فقط ويتكون من 7-10 أرقام\n\nجرب مرة ثانية:",
    "ask_email": "اكتب بريدك الإلكتروني:",
    "invalid_email": "⚠️ البريد الإلكتروني مش صحيح\n\nجرب مرة ثانية:",
    "registration_complete": "✅ تم تسجيلك بنجاح!\n\nدلوقتي اسألني أي سؤال عن جامعة اليرموك 🎓",
    "registration_updated": "✅ تم تحديث بياناتك بنجاح!"
}

# Feedback messages
FEEDBACK_MESSAGES = {
    "request": "شو رأيك بالإجابة؟ 🤔",
    "thanks": "شكراً على رأيك! 🙏\n\nملاحظاتك بتساعدني أتحسن أكثر",
    "thanks_positive": "يسلموو! 😊 سعيد إني قدرت أساعدك",
    "thanks_negative": "آسف إذا الإجابة ما كانت مفيدة 😔\n\nراح أحاول أتحسن أكثر!"
}

# Error messages
ERROR_MESSAGES = {
    "rate_limit": "⏱️ رجاءً انتظر شوية قبل ما ترسل رسالة جديدة\n\n"
                 "وصلت للحد الأقصى من الرسائل المسموح فيها بالدقيقة.",
    "agent_not_ready": "⚠️ النظام مش جاهز حالياً\n\nجرب /start أو انتظر شوية",
    "general_error": "❌ آسف، صار خطأ مؤقت\n\nجرب مرة ثانية بعد شوي",
    "no_history": "📭 ما عندك محادثات سابقة بعد\n\nابدأ بسؤال أول سؤال!",
    "invalid_roadmap": "❓ المجال مش موجود\n\n"
                      "المجالات المتاحة:\n"
                      "• /roadmap web\n"
                      "• /roadmap ml\n"
                      "• /roadmap mobile\n"
                      "• /roadmap data"
}

# Success messages
SUCCESS_MESSAGES = {
    "memory_cleared": "✅ تم مسح الذاكرة الحالية\n\nبتقدر تبدأ محادثة جديدة الآن",
    "feedback_saved": "✅ تم حفظ ملاحظاتك بنجاح"
}

# Contact info
CONTACT_INFO = """
📞 **معلومات التواصل - جامعة اليرموك:**

**القبول والتسجيل:**
📞 الهاتف: 027211111
📧 البريد: admission@yu.edu.jo

**الموقع الرسمي:**
🌐 https://www.yu.edu.jo

**دوام مكتب القبول:**
🕐 الأحد - الخميس: 8:00 صباحاً - 3:00 مساءً

**العنوان:**
📍 جامعة اليرموك، إربد، الأردن
"""