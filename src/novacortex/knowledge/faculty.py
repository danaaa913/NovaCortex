"""Faculties, deans, contacts, counselling and study-plan constants."""

COLLOQUIAL_FACULTY_TERMS = {
    'الايتي': 'كلية تكنولوجيا المعلومات وعلوم الحاسوب',
    'ايتي': 'كلية تكنولوجيا المعلومات وعلوم الحاسوب',
    'it faculty': 'Faculty of Information Technology',
    'الحجاوي': 'كلية الحجاوي للهندسة التكنولوجية',
    'الهندسه': 'كلية الحجاوي للهندسة التكنولوجية',
    'الهندسة': 'كلية الحجاوي للهندسة التكنولوجية',
    'كلية الطب': 'كلية الطب',
    'الصيدليه': 'كلية الصيدلة',
    'التمريض': 'كلية التمريض',
    'الاداب': 'كلية الآداب',
    'الآداب': 'كلية الآداب',
    'الاعمال': 'كلية الأعمال',
    'التربية': 'كلية العلوم التربوية',
    'الشريعه': 'كلية الشريعة والدراسات الإسلامية',
    'الشريعة': 'كلية الشريعة والدراسات الإسلامية',
    'القانون': 'كلية القانون',
    'الاعلام': 'كلية الإعلام',
    'السياحه': 'كلية السياحة والفنادق',
    'السياحة': 'كلية السياحة والفنادق',
    'الفنون': 'كلية الفنون الجميلة',
    'الاثار': 'كلية الآثار والأنثروبولوجيا',
    'الآثار': 'كلية الآثار والأنثروبولوجيا',
    'الرياضة': 'كلية التربية البدنية وعلوم الرياضة',
    'رياضة': 'كلية التربية البدنية وعلوم الرياضة',
}

# ==================== COUNSELING CONTACTS — عمادة شؤون الطلبة ====================
COUNSELING_CONTACTS = {
    "ar": {
        "primary": {
            "name": "د. قصي الزعبي",
            "title": "مساعد العميد لشؤون الطلبة — كلية IT",
            "email": "q.zoubi@yu.edu.jo",
            "phone": "02-7211111 | فرعي: 2526",
            "office": "مبنى المقدسي، الطابق الرابع",
            "hours": "8:00 صباحاً – 3:00 مساءً",
        },
        "student_affairs": {
            "name": "عمادة شؤون الطلبة",
            "email": "studentaffairs@yu.edu.jo",
            "phone": "02-7211111 | فرعي: 2303",
            "website": "https://www.yu.edu.jo/students",
        },
        "crisis_line": {
            "name": "خط نجدة الطفل / الدعم النفسي الأردني",
            "number": "110",
            "note": "مجاني وسري — 24/7",
        },
        "mental_health_center": {
            "name": "مركز الإرشاد النفسي — جامعة اليرموك",
            "email": "counseling@yu.edu.jo",
            "phone": "02-7211111 | فرعي: 2540",
        },
    },
    "en": {
        "primary": {
            "name": "Dr. Qusai Al-Zoubi",
            "title": "Assistant Dean for Student Affairs — IT Faculty",
            "email": "q.zoubi@yu.edu.jo",
            "phone": "02-7211111 ext. 2526",
            "office": "Muqadasi Building, 4th Floor",
            "hours": "8:00 AM – 3:00 PM",
        },
        "crisis_line": {
            "name": "Jordan Crisis Line",
            "number": "110",
            "note": "Free, confidential — 24/7",
        },
    }
}

# ==================== FACULTY DATABASE — كلية IT اليرموك ====================
# مصدر: fmd.yu.edu.jo + it.yu.edu.jo
# رابط البحث المباشر: https://fmd.yu.edu.jo/AcademicsListByName.aspx
FACULTY_DB = {
    # إدارة الكلية
    "قاسم الردايدة": {
        "name_ar": "أ.د. قاسم أحمد الردايدة",
        "name_en": "Prof. Qasem Al-Radaideh",
        "role": "عميد الكلية",
        "dept": "قسم نظم المعلومات",
        "rank": "أستاذ",
        "specialty": "ذكاء اصطناعي، علم البيانات",
        "email": "qasemr@yu.edu.jo",
        "office": "مبنى المقدسي، الطابق الرابع، مكتب 408",
        "phone": "02-7211111 | فرعي: 2526",
        "fmd_url": "https://fmd.yu.edu.jo/AcademicsCard.aspx?Card=qLI44d4hGJU%3D",
        "research": ["Data Mining", "AI", "Machine Learning"],
        "keys": ["عميد", "الردايدة", "radaideh", "قاسم"],
    },
    "محمد حمدان": {
        "name_ar": "أ.د. محمد حمدان",
        "name_en": "Prof. Mohammad Hamdan",
        "role": "عضو هيئة تدريس",
        "dept": "قسم علوم الحاسوب",
        "rank": "أستاذ",
        "specialty": "خوارزميات، برمجة تنافسية",
        "email": "mhamdan@yu.edu.jo",
        "office": "مبنى المقدسي",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["حمدان", "hamdan", "خوارزميات"],
    },
    "جعفر شهابات": {
        "name_ar": "د. جعفر شهابات",
        "name_en": "Dr. Jafar Shahabat",
        "role": "مدير مبادرة TechForward",
        "dept": "كلية IT",
        "rank": "دكتور",
        "specialty": "تكنولوجيا المعلومات، ريادة الأعمال",
        "email": "j.shahabat@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["شهابات", "shahabat", "techforward", "جعفر"],
    },
    "عماد الشواقفة": {
        "name_ar": "د. عماد الشواقفة",
        "name_en": "Dr. Imad Al-Shawaqfeh",
        "role": "ضابط ارتباط TechForward",
        "dept": "كلية IT",
        "rank": "دكتور",
        "specialty": "أمن المعلومات",
        "email": "i.shawaqfeh@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["الشواقفة", "shawaqfeh"],
    },
    "قصي الزعبي": {
        "name_ar": "د. قصي الزعبي",
        "name_en": "Dr. Qusai Al-Zoubi",
        "role": "مساعد العميد لشؤون الطلبة",
        "dept": "إدارة الكلية",
        "rank": "دكتور",
        "specialty": "شؤون طلبة، إرشاد أكاديمي",
        "email": "q.zoubi@yu.edu.jo",
        "office": "مبنى المقدسي، الطابق الرابع",
        "phone": "02-7211111 | فرعي: 2526",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["الزعبي", "zoubi", "شؤون الطلبة", "مساعد العميد"],
    },
    "رعد الخطيب": {
        "name_ar": "د. رعد الخطيب",
        "name_en": "Dr. Raad Al-Khatib",
        "role": "رئيس قسم علوم الحاسوب",
        "dept": "قسم علوم الحاسوب",
        "rank": "دكتور",
        "specialty": "علوم الحاسوب",
        "email": "r.khatib@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["الخطيب", "khatib", "رئيس قسم", "علوم الحاسوب"],
    },
    "رامي مهاوش": {
        "name_ar": "د. رامي مهاوش",
        "name_en": "Dr. Rami Mhawish",
        "role": "عضو هيئة تدريس",
        "dept": "قسم نظم المعلومات",
        "rank": "دكتور",
        "specialty": "نظم المعلومات، ذكاء اصطناعي، كشف التقييمات الكاذبة",
        "email": "r.mhawish@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["مهاوش", "mhawish"],
    },
    "خالد نواصرة": {
        "name_ar": "أ.د. خالد نواصرة",
        "name_en": "Prof. Khalid Nawasreh",
        "role": "عضو هيئة تدريس",
        "dept": "قسم علوم الحاسوب",
        "rank": "أستاذ",
        "specialty": "علوم الحاسوب",
        "email": "k.nawasreh@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["نواصرة", "nawasreh"],
    },
    "أمجد الناصر": {
        "name_ar": "د. أمجد الناصر",
        "name_en": "Dr. Amjad Al-Nasser",
        "role": "ممثل الجامعة في مبادرة TechForward",
        "dept": "إدارة الجامعة",
        "rank": "دكتور",
        "specialty": "تطوير الشراكات",
        "email": "a.nasser@yu.edu.jo",
        "fmd_url": "https://fmd.yu.edu.jo/",
        "keys": ["الناصر", "nasser"],
    },
}

FMD_SEARCH_URL = "https://fmd.yu.edu.jo/AcademicsListByName.aspx"
FMD_BASE_URL   = "https://fmd.yu.edu.jo/"


GRADUATION_HOURS = {
    'CS': 134, 'علوم الحاسوب': 134,
    'CIS': 134, 'نظم المعلومات': 134, 'نظم المعلومات الحاسوبية': 134,
    'CYS': 134, 'الأمن السيبراني': 134, 'أمن سيبراني': 134,
    'BIT': 134, 'تكنولوجيا معلومات الأعمال': 134, 'bit': 134,
    'DA': 134, 'علم البيانات': 134, 'ذكاء اصطناعي': 134,
    'VR': 134, 'DRG': 134, 'الواقع الرقمي': 134, 'تطوير الألعاب': 134,
    'default': 134,
}

HARD_COURSES_BY_MAJOR = {
    'CS':  ['CS 253 (تراكيب البيانات)', 'CS 310 (الخوارزميات)', 'CS 411 (هندسة البرمجيات)', 'CS 342 (أنظمة التشغيل)', 'CS 499A/B (مشروع التخرج)'],
    'CIS': ['CIS 260 (قواعد البيانات)', 'CIS 340 (تحليل النظم)', 'CIS 464 (أمن المعلومات)', 'CIS 499 (مشروع التخرج)'],
    'CYS': ['CYS 321 (أمن الشبكات)', 'CYS 440 (التشفير)', 'CYS 332 (الجرائم الرقمية)', 'CYS 499 (مشروع التخرج)', 'CS 253 (تراكيب البيانات)'],
    'BIT': ['BIT 381 (تحليل الأعمال)', 'BIT 480 (نظم المعلومات الإدارية)', 'BIT 364 (إدارة قواعد البيانات)', 'BIT 499 (مشروع التخرج)'],
    'DA':  ['DA 312 (التعلم الآلي)', 'DA 360 (التعمق في البيانات)', 'DA 480 (مشروع)', 'CS 253 (تراكيب البيانات)', 'DA 370 (معالجة البيانات الكبيرة)'],
    'VR':  ['DRG 310 (برمجة ألعاب متقدمة)', 'DRG 420 (رسوميات الحاسوب)', 'DRG 499A/B (مشروع التخرج)', 'CS 253 (تراكيب البيانات)'],
    'DRG': ['DRG 310 (برمجة ألعاب متقدمة)', 'DRG 420 (رسوميات الحاسوب)', 'DRG 499A/B (مشروع التخرج)', 'CS 253 (تراكيب البيانات)'],
}
