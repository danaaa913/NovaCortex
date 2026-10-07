"""Verified facts about Yarmouk University (LLM grounding source)."""

# ==================== VERIFIED FACTS ====================
VERIFIED_FACTS = {
    "ar": {
        "university_brief": "جامعة اليرموك هي جامعة حكومية أردنية رائدة تقع في مدينة إربد، تأسست عام 1976. التعليم فيها وجاهي بالكامل.",
        "president": "أ.د. مالك الشرايري",
        "president_full": "الأستاذ الدكتور مالك أحمد الشرايري",
        "president_title": "رئيس جامعة اليرموك",
        "deans": {
            "hijjawi": {"name": "د. عوض سميران الزبن", "title": "عميد كلية الحجاوي للهندسة التكنولوجية", "match": ["حجاوي", "هندسة", "هندسه", "engineering", "technology"]},
            "it": {"name": "د. قاسم الردايدة", "title": "عميد كلية تكنولوجيا المعلومات وعلوم الحاسوب", "match": ["معلومات", "المعلومات", "المعلومان", "تكنولوجيا", "حاسوب", "it", "computer", "ايتي", "الايتي", "information technology"]},
            "medicine": {"name": "د. جمانة السليمان", "title": "قائم بأعمال عميد كلية الطب", "match": ["طب", "medicine", "medical"]},
            "pharmacy": {"name": "د. غيث الطعاني", "title": "عميد كلية الصيدلة", "match": ["صيدلة", "صيدليه", "pharmacy"]},
            "science": {"name": "د. مهيب محمد عواودة", "title": "عميد كلية العلوم", "match": ["علوم", "science"]},
            "arts": {"name": "د. خالد محمد أمين الهزايمة", "title": "عميد كلية الآداب", "match": ["آداب", "اداب", "arts"]},
            "business": {"name": "د. يحيى سليم بني ملحم", "title": "عميد كلية الأعمال", "match": ["أعمال", "اعمال", "business"]},
            "education": {"name": "د. هاني حتمل عبيدات", "title": "عميد كلية العلوم التربوية", "match": ["تربية", "تعليم", "education"]},
            "nursing": {"name": "د. رسمية مصطفى الأعمر", "title": "قائم بأعمال عميد كلية التمريض", "match": ["تمريض", "nursing"]},
            "law": {"name": "د. مها خصاونة", "title": "قائم بأعمال عميد كلية القانون", "match": ["قانون", "law"]}
        },
        "it_admin": {
            "dean": {"name": "د. قاسم الردايدة", "title": "عميد كلية تكنولوجيا المعلومات وعلوم الحاسوب"},
            "vice_deans": [
                {"name": "د. عماد الشواقفة", "title": "نائب العميد"},
                {"name": "د. خالد النهار", "title": "نائب العميد لشؤون الاعتماد الأكاديمي والجودة"}
            ],
            "assistant_dean": {"name": "د. قصي الزعبي", "title": "مساعد العميد لشؤون الطلبة"},
            "department_heads": {
                "cs": {"name": "د. بلال عبدالغني", "dept": "قسم علوم الحاسوب"},
                "cis": {"name": "د. ايناس خشاشنة", "dept": "قسم نظم المعلومات"},
                "it": {"name": "د. علاء حمود", "dept": "قسم تكنولوجيا المعلومات"}
            }
        },
        "it_credit_hours": {
            "علوم الحاسوب": "134",
            "نظم المعلومات الحاسوبية": "134",
            "تكنولوجيا معلومات الأعمال": "134",
            "علم البيانات والذكاء الاصطناعي": "134",
            "الأمن السيبراني": "134",
            "الواقع الرقمي وتطوير الألعاب": "134",
            "default": "134",
            "note": "جميع تخصصات كلية IT تتطلب 134 ساعة معتمدة للتخرج (15 جامعة إجبارية + 119 ساعة قسم)"
        },
        "gpa_scale": {
            "system": "مئوي (من 100)",
            "passing": "60",
            "warning": "نزل تحت 60 → إنذار أكاديمي",
            "details": (
                "📊 نظام المعدل في جامعة اليرموك:\n"
                "• المعدل يُحسب من 100 (ليس من 4 كما في بعض الجامعات)\n"
                "• الحد الأدنى للنجاح في المادة: 50/100\n"
                "• الحد الأدنى للتخرج: معدل 60/100 تراكمي\n"
                "• تحت 60 → إنذار أكاديمي أول\n"
                "• تحت 60 فصلين متتاليين → إنذار ثاني\n"
                "• التحويل لجامعة نظام 4.0: اضرب معدلك بـ 0.04\n"
                "  (مثال: معدل 75/100 ≈ 3.0/4.0)"
            ),
        },
        "psychological_counselors": {
            "title": "أخصائيون نفسيون — عمادة شؤون الطلبة — جامعة اليرموك",
            "emails": [
                "muayyad@yu.edu.jo",
                "ahmad.talahmeh@yu.edu.jo",
                "sujoud.aljedaya@yu.edu.jo",
                "ptl_mohammad.hamouri@yu.edu.jo",
            ],
            "details": (
                "💙 للتواصل المباشر مع الأخصائيين النفسيين — عمادة شؤون الطلبة:\n\n"
                "📧 muayyad@yu.edu.jo\n"
                "📧 ahmad.talahmeh@yu.edu.jo\n"
                "📧 sujoud.aljedaya@yu.edu.jo\n"
                "📧 ptl_mohammad.hamouri@yu.edu.jo\n\n"
                "🆘 خط الأزمات الأردني: 110 (مجاني — 24/7)\n"
                "🏢 مكتب عمادة شؤون الطلبة: الطابق الأرضي، المبنى الرئيسي"
            ),
        },
        "it_dept_structure": {
            "CS": "قسم علوم الحاسوب — رئيسه: أ. بلال عبد الغني — تخصصاته: CS و VR",
            "VR": "قسم علوم الحاسوب — رئيسه: أ. بلال عبد الغني — تخصصاته: CS و VR",
            "CIS": "قسم نظم المعلومات — رئيسته: د. إيناس خشاشنة — تخصصاته: CIS و DA",
            "DA": "قسم نظم المعلومات — رئيسته: د. إيناس خشاشنة — تخصصاته: CIS و DA",
            "BIT": "قسم تكنولوجيا المعلومات — رئيسه: د. علاء الحمود — تخصصاته: BIT و CYS",
            "CYS": "قسم تكنولوجيا المعلومات — رئيسه: د. علاء الحمود — تخصصاته: BIT و CYS",
        },
        "num_faculties": "16",
        "faculties_list": [
            "كلية الطب", "كلية الصيدلة", "كلية التمريض", "كلية العلوم",
            "كلية الحجاوي للهندسة التكنولوجية", "كلية تكنولوجيا المعلومات وعلوم الحاسوب",
            "كلية الآداب", "كلية الأعمال", "كلية الشريعة والدراسات الإسلامية",
            "كلية العلوم التربوية", "كلية القانون", "كلية الإعلام",
            "كلية التربية البدنية وعلوم الرياضة", "كلية الآثار والأنثروبولوجيا",
            "كلية السياحة والفنادق", "كلية الفنون الجميلة"
        ],
        "hijjawi_programs": [
            "هندسة الإلكترونيات",
            "هندسة الاتصالات",
            "هندسة الحاسوب",
            "هندسة القوى الكهربائية",
            "هندسة النظم والمعلوماتية الطبية الحيوية",
            "الهندسة المدنية",
            "هندسة العمارة",
            "الهندسة الصناعية",
            "الهندسة الميكانيكية",
        ],
        "hijjawi_note": "كلية الحجاوي للهندسة التكنولوجية تضم 9 أقسام أكاديمية. بعض المساقات النظرية تُدرَّس بشكل هجين (وجاهي + أونلاين)، أما المساقات العملية واللابات فهي وجاهية بالكامل.",
        "gates": {
            "count": "5",
            "main": "البوابة الشرقية — وهي البوابة الرئيسية للجامعة",
            "details": (
                "لجامعة اليرموك 5 بوابات رئيسية:\n"
                "1. 🔑 البوابة الشرقية (الرئيسية) — الدخول الرئيسي من الشارع الرئيسي\n"
                "2. البوابة الغربية\n"
                "3. البوابة الشمالية\n"
                "4. البوابة الجنوبية\n"
                "5. البوابة الخلفية (الداخلية)\n\n"
                "📍 البوابة الشرقية هي المدخل الرئيسي وتُستخدم للدخول والخروج الرئيسي."
            )
        },
        "it_programs": [
            "علوم الحاسوب",
            "نظم المعلومات الحاسوبية",
            "تكنولوجيا معلومات الأعمال",
            "علم البيانات والذكاء الاصطناعي",
            "الأمن السيبراني",
            "الواقع الرقمي وتطوير الألعاب"
        ],
        "student_housing": {
            "available": True,
            "details": "نعم، يتوفر سكن جامعي للطالبات داخل الحرم بتكلفة 15 دينارًا في الليلة (حوالي 250-450 دينارًا شهريًا). وللطلاب الذكور يتوفر سكن خارجي بأسعار متفاوتة. للاستفسار: عمادة شؤون الطلبة - مكتب رقم (110).",
            "brief": "تكلفة السكن الجامعي 15 دينار/ليلة (≈ 250-450 دينار/شهر) للطالبات داخل الحرم."
        },
        "health_insurance": {
            "available": True,
            "details": "نعم، التأمين الصحي إلزامي لجميع طلبة البكالوريوس في جامعة اليرموك."
        },
        "online_policy": "جامعة اليرموك تعتمد بشكل أساسي على التعليم الوجاهي. بعض المساقات النظرية تُدرَّس بشكل هجين (وجاهي + أونلاين حسب قرار الدكتور)، أما المساقات العملية ولابات الحاسوب فهي وجاهية إلزامية بالكامل. لا يوجد برامج دراسية عن بُعد بشكل كامل.",
        "university_info_answer": "جامعة اليرموك جامعة حكومية أردنية في إربد، تأسست عام 1976. تضم 16 كلية وتقدم برامج البكالوريوس والماجستير والدكتوراه. التعليم فيها وجاهي بالكامل.",
        "admission_requirements": """شروط القبول في كلية IT — جامعة اليرموك:
✅ الحصول على شهادة الثانوية العامة (التوجيهي) الأردنية أو ما يعادلها
✅ التقديم عبر نظام القبول الموحد في وزارة التعليم العالي
✅ الحد الأدنى للمعدل (تقريبي، يتفاوت سنوياً):
   CS: ~85% | CIS: ~80% | CYS: ~83%
   DA: ~82% | BIT: ~78% | DRG: ~78%
📅 موعد التقديم: أغسطس–سبتمبر من كل عام
🌐 التقديم الإلكتروني: admreg.yu.edu.jo
📞 للاستفسار: دائرة القبول والتسجيل — جامعة اليرموك""",
        "hackathon_achievements": """إنجازات الكلية في المسابقات والهاكاثونات:
🏆 المركز الأول — هاكثون DataDrip لتحليل البيانات (10 دول عربية) بتنظيم فريق NOVA AI
🥈 المركز الرابع — هاكاثون Tech Arabi 2025 من بين 35+ فريق
🚀 المشاركة في تحدي تطبيقات NASA الدولي
🛡️ ثلاثة مراكز أولى في مسابقة هيئة النزاهة (أمن سيبراني + ذكاء اصطناعي)
💻 مسابقة YUCPC-2025 لحل المسائل البرمجية (Problem Solving)
🔐 مسابقة CTF@YU2025 للأمن السيبراني والاختراق الأخلاقي
📊 فعالية NOVA BRAINLYTICS لتحليل البيانات — برعاية رئيس الجامعة
🎓 معرض مشاريع التخرج الفصلي — مفتوح للشركات والمجتمع
الكلية تشارك في: قمة QS 2026 بالهند، اجتماعات ABET الدولية، أسبوع ريادة الأعمال مع نادي DEVIT""",
        "graduation_projects_info": """مشاريع التخرج في كلية IT — جامعة اليرموك:
تُنجز في الفصل الأخير تحت إشراف عضو هيئة تدريس متخصص.

أمثلة حقيقية من فصول سابقة:
• منصة ذكاء اصطناعي لتشخيص الأمراض
• نظام كشف اختراق بالتعلم العميق
• تطبيق واقع معزز للتعليم
• لعبة فيديو 3D كاملة بمحرك Unity
• منصة ERP للشركات الصغيرة
• نظام توصية بالمقررات بالذكاء الاصطناعي

✨ ضمن مبادرة TechForward: مشاريع حقيقية بالتعاون مع شركات تقنية!
📅 يوم العرض: نهاية كل فصل — مفتوح للشركات والجمهور والأهالي""",
        "companies_and_training": """شركات تقنية تستقبل متدربين من كلية IT — جامعة اليرموك:
🟠 Orange Jordan — اتصالات وتقنية معلومات | التخصصات: CS, CIS, CYS, BIT | برنامج التدريب: صيفي عبر موقعهم
🔵 Zain Jordan — اتصالات وتحول رقمي | التخصصات: CS, CIS, DA, CYS | LinkedIn: linkedin.com/company/zain-jordan
🟣 Umniah — خدمات رقمية واتصالات | LinkedIn: linkedin.com/company/umniah
🟢 Makeen Technology — برمجيات وحلول حكومية | التخصصات: CS, CIS, BIT | LinkedIn: linkedin.com/company/makeen-technology
🔒 ScopeX (Scope X) — أمن سيبراني وتدريب | شريك رسمي مع كلية IT اليرموك | LinkedIn: linkedin.com/company/scopex
💼 Estarta Solutions — خدمات IT وتطوير برمجيات | LinkedIn: linkedin.com/company/estarta
🤖 Mawdoo3.com — محتوى رقمي وذكاء اصطناعي | التخصصات: DA, CS | LinkedIn: linkedin.com/company/mawdoo3
🌐 جمعية إنتاج — مبادرة TechForward (شراكة رسمية مع اليرموك)
🏦 Jordan Ahli Bank (قسم التقنية) — تقنية مالية FinTech | التخصصات: CS, CIS, CYS
💡 نصيحة: ابحث على LinkedIn: "IT internship Jordan" | تواصل مع د. قصي الزعبي (مساعد العميد للطلبة) | احضر Job Fair الكلية السنوي""",
        "career_paths": """مسارات التوظيف لخريجي كلية IT — جامعة اليرموك:
💻 CS  → Backend Developer, ML Engineer, DevOps Engineer, Game Developer, Compiler Developer
📊 CIS → Business Analyst, ERP Consultant, Database Admin, Systems Analyst, IT Project Manager
🔐 CYS → Security Engineer, Ethical Hacker, SOC Analyst, Penetration Tester, Cloud Security Specialist
🤖 DA  → Data Scientist, AI Engineer, NLP Specialist, Business Intelligence Developer, MLOps Engineer
💼 BIT → IT Manager, Digital Transformation Lead, Product Owner, ERP Implementation Consultant
🎮 DRG → Game Developer (Unity/Unreal), XR Developer, 3D Artist, Technical Artist, Indie Game Developer
📌 متوسط الراتب المبدئي في الأردن: 600-1000 JD/شهر
🌍 فرص دولية: أوروبا وكندا والخليج لخريجي CYS وDA وCS""",
        "university_type": "حكومية",
        "university_type_full": "جامعة اليرموك هي جامعة حكومية أردنية.",
        "founded_year": "1976",
        "location": "إربد، الأردن",
        "website": "yu.edu.jo",
        "elearning_url": "https://elearning.yu.edu.jo",
        "registration_url": "https://admreg.yu.edu.jo",
        "faculty_directory": "fmd.yu.edu.jo",
    },
    "en": {
        "university_brief": "Yarmouk University is a leading Jordanian public university located in Irbid, founded in 1976. Education is entirely in-person.",
        "president": "Prof. Malik Al-Shariri",
        "president_full": "Professor Dr. Malik Ahmed Al-Shariri",
        "president_title": "President of Yarmouk University",
        "deans": {
            "hijjawi": {"name": "Dr. Awad Smiran Al-Zabn", "title": "Dean of Hijjawi Faculty for Engineering Technology", "match": ["hijjawi", "engineering", "technology"]},
            "it": {"name": "Dr. Qasem Al-Radaideh", "title": "Dean of Faculty of Information Technology and Computer Science", "match": ["it", "information", "computer", "technology"]},
            "medicine": {"name": "Dr. Jumana Al-Sulaiman", "title": "Acting Dean of Faculty of Medicine", "match": ["medicine", "medical"]},
            "pharmacy": {"name": "Dr. Ghaith Al-Taani", "title": "Dean of Faculty of Pharmacy", "match": ["pharmacy"]},
            "science": {"name": "Dr. Muheeb Mohammed Awawdeh", "title": "Dean of Faculty of Science", "match": ["science"]},
            "arts": {"name": "Dr. Khaled Mohammed Ameen Al-Hazyameh", "title": "Dean of Faculty of Arts", "match": ["arts"]},
            "business": {"name": "Dr. Yahya Salim Bani Melhem", "title": "Dean of Faculty of Business", "match": ["business"]},
            "education": {"name": "Dr. Hani Hatmel Obeidat", "title": "Dean of Faculty of Education", "match": ["education"]},
            "nursing": {"name": "Dr. Rasmiya Mustafa Al-A'mar", "title": "Acting Dean of Faculty of Nursing", "match": ["nursing"]},
            "law": {"name": "Dr. Maha Khasawneh", "title": "Acting Dean of Faculty of Law", "match": ["law"]}
        },
        "it_admin": {
            "dean": {"name": "Dr. Qasem Al-Radaideh", "title": "Dean of Faculty of IT and Computer Science"},
            "vice_deans": [
                {"name": "Dr. Emad Al-Shawaqfeh", "title": "Vice Dean"},
                {"name": "Dr. Khaled Al-Nahar", "title": "Vice Dean for Academic Accreditation and Quality"}
            ],
            "assistant_dean": {"name": "Dr. Qusay Al-Zaabi", "title": "Assistant Dean for Student Affairs"},
            "department_heads": {
                "cs": {"name": "Dr. Bilal Abdul-Ghani", "dept": "Department of Computer Science"},
                "cis": {"name": "Dr. Inas Khashashna", "dept": "Department of Information Systems"},
                "it": {"name": "Dr. Alaa Hammoud", "dept": "Department of Information Technology"}
            }
        },
        "num_faculties": "16",
        "faculties_list": [
            "Faculty of Medicine", "Faculty of Pharmacy", "Faculty of Nursing", "Faculty of Science",
            "Hijjawi Faculty for Engineering Technology", "Faculty of Information Technology and Computer Science",
            "Faculty of Arts", "Faculty of Business", "Faculty of Sharia and Islamic Studies",
            "Faculty of Education", "Faculty of Law", "Faculty of Mass Communication",
            "Faculty of Physical Education", "Faculty of Archaeology and Anthropology",
            "Faculty of Tourism and Hotel Management", "Faculty of Fine Arts"
        ],
        "online_policy": "Yarmouk University primarily uses in-person teaching. Some theoretical courses may be taught in a hybrid format (in-person + online depending on the instructor), while all practical courses and computer labs are fully in-person. There are no fully online degree programs.",
        "it_programs": [
            "Computer Science",
            "Computer Information Systems",
            "Business Information Technology",
            "Data Science and Artificial Intelligence",
            "Cybersecurity",
            "Digital Reality and Game Development"
        ],
        "student_housing": {
            "available": True,
            "details": "Yes, on-campus housing is available for female students at 15 JD per night (approximately 250-450 JD/month). Male students have off-campus housing options at varying rates. Contact: Student Affairs Office, Room 110.",
            "brief": "On-campus housing costs 15 JD/night (≈ 250-450 JD/month) for female students."
        },
        "health_insurance": {
            "available": True,
            "details": "Yes, health insurance is mandatory for all undergraduate students at Yarmouk University."
        },
        "university_info_answer": "Yarmouk University is a leading Jordanian public university in Irbid, Jordan, founded in 1976. It has 16 faculties offering Bachelor's, Master's and PhD programs. Education is entirely in-person.",
        "admission_requirements": """Admission Requirements for IT Faculty — Yarmouk University:
✅ Jordanian Tawjihi (Secondary School Certificate) or equivalent
✅ Apply via the Unified Admission System (Ministry of Higher Education)
✅ Minimum GPA thresholds (approximate, vary annually):
   CS: ~85% | CIS: ~80% | CYS: ~83%
   DA: ~82% | BIT: ~78% | DRG: ~78%
📅 Application period: August–September each year
🌐 Online application: admreg.yu.edu.jo
📞 Contact: Admissions & Registration Office, Yarmouk University""",
        "companies_and_training": """IT companies that accept interns from Yarmouk University — IT Faculty:
🟠 Orange Jordan — Telecom & IT | Majors: CS, CIS, CYS, BIT | Summer internship program
🔵 Zain Jordan — Telecom & Digital Transformation | Majors: CS, CIS, DA, CYS
🟣 Umniah — Digital services and telecom
🟢 Makeen Technology — Software & Government Solutions | Majors: CS, CIS, BIT
🔒 ScopeX — Cybersecurity & Training | Official partner with IT Faculty
💼 Estarta Solutions — IT Services & Software Development
🤖 Mawdoo3.com — Digital content & AI | Majors: DA, CS
🌐 INTAJ Association — TechForward initiative (official Yarmouk partnership)
💡 Tip: Search "IT internship Jordan" on LinkedIn | Contact Dr. Qusai Al-Zoubi (Student Affairs) | Attend the annual Job Fair""",
        "career_paths": """Career paths for Yarmouk IT Faculty graduates:
💻 CS  → Backend Developer, ML Engineer, DevOps Engineer, Game Developer
📊 CIS → Business Analyst, ERP Consultant, Database Admin, Systems Analyst
🔐 CYS → Security Engineer, Ethical Hacker, SOC Analyst, Penetration Tester
🤖 DA  → Data Scientist, AI Engineer, NLP Specialist, MLOps Engineer
💼 BIT → IT Manager, Digital Transformation Lead, ERP Implementation Consultant
🎮 DRG → Game Developer (Unity/Unreal), XR Developer, 3D Artist
📌 Starting salary in Jordan: 600-1000 JD/month
🌍 International opportunities in Europe, Canada, Gulf for CYS, DA, CS graduates""",
        "university_type": "public",
        "university_type_full": "Yarmouk University is a public university.",
        "founded_year": "1976",
        "location": "Irbid, Jordan",
        "website": "yu.edu.jo",
        "elearning_url": "https://elearning.yu.edu.jo",
        "registration_url": "https://admreg.yu.edu.jo",
        "faculty_directory": "fmd.yu.edu.jo",
        "it_dept_structure": {
            "CS":  "CS Department (Computer Science) — Head: Dr. Bilal Abdul-Ghani — Programs: CS & VR",
            "VR":  "CS Department (Computer Science) — Head: Dr. Bilal Abdul-Ghani — Programs: CS & VR",
            "CIS": "CIS Department (Information Systems) — Head: Dr. Inas Khashashna — Programs: CIS & DA",
            "DA":  "CIS Department (Information Systems) — Head: Dr. Inas Khashashna — Programs: CIS & DA",
            "BIT": "IT Department (Information Technology) — Head: Dr. Alaa Hammoud — Programs: BIT & CYS",
            "CYS": "IT Department (Information Technology) — Head: Dr. Alaa Hammoud — Programs: BIT & CYS",
        },
    }
}
