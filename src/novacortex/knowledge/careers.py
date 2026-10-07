"""CV templates and skill-gap datasets."""


# CV structure by major
CV_TEMPLATES = {
    "CS": {
        "key_skills": ["Python", "Java/C++", "Data Structures & Algorithms", "Git/GitHub",
                       "Databases (SQL/NoSQL)", "Linux", "REST APIs"],
        "certifications": ["AWS Certified Developer", "Google IT Support", "Meta Backend Developer"],
        "project_ideas": ["ML-based web app", "Compiler project", "Distributed system"],
        "linkedin_headline": "CS Student @ Yarmouk University | Python · Backend · Open to Internships",
        "github_tip": "Pin 3-4 projects — عندك مشروع CS 499؟ هاد لازم يكون أول شيء",
    },
    "CYS": {
        "key_skills": ["Network Security", "Ethical Hacking", "Python Scripting", "Wireshark/Nmap",
                       "Linux Admin", "SIEM Tools", "CTF Experience"],
        "certifications": ["CompTIA Security+", "CEH", "TryHackMe profile"],
        "project_ideas": ["Intrusion detection system", "CTF writeups blog", "Vulnerability scanner"],
        "linkedin_headline": "CyberSecurity Student @ Yarmouk | Ethical Hacking · CTF Player | Security+",
        "github_tip": "اعمل repo لـ CTF writeups — الشركات بتحبها أكثر من أي شي ثاني",
    },
    "DA": {
        "key_skills": ["Python (Pandas, NumPy, Scikit-learn)", "SQL", "Power BI/Tableau",
                       "Machine Learning", "Data Visualization", "Statistics"],
        "certifications": ["Google Data Analytics", "IBM Data Science", "Kaggle competitions"],
        "project_ideas": ["End-to-end ML pipeline", "Business dashboard", "NLP project"],
        "linkedin_headline": "Data Science & AI Student @ Yarmouk | Python · ML · Kaggle Contributor",
        "github_tip": "اعمل Kaggle profile وحطّ رابطه بالـ CV — Kaggle أحسن proof للـ DA",
    },
    "CIS": {
        "key_skills": ["Database Design", "Systems Analysis", "ERP (SAP/Odoo)", "SQL",
                       "Business Intelligence", "Project Management", "Python/Java"],
        "certifications": ["PMP / CAPM", "Oracle Database", "SAP Fundamentals"],
        "project_ideas": ["ERP implementation for SMB", "BI dashboard", "Information system prototype"],
        "linkedin_headline": "CIS Student @ Yarmouk | Systems Analysis · ERP · BI Solutions",
        "github_tip": "اعمل projects بتنة عملية — مشروع ERP وصغير أحسن من مشروع نظري كبير",
    },
    "BIT": {
        "key_skills": ["Business Analysis", "Digital Marketing", "ERP Systems", "Power BI",
                       "Project Management", "SQL", "IT Strategy"],
        "certifications": ["Google Digital Marketing", "PMP", "HubSpot CRM"],
        "project_ideas": ["Business process automation", "E-commerce analysis", "CRM system"],
        "linkedin_headline": "BIT Student @ Yarmouk | Business Analysis · Digital Transformation",
        "github_tip": "اعمل Case Studies repo — بيّن كيف حللت مشكلة تجارية بالتقنية",
    },
    "DRG": {
        "key_skills": ["Unity/Unreal Engine", "C#/C++", "3D Modeling (Blender)", "AR/VR Development",
                       "Game Design", "Shader Programming", "Mobile Games"],
        "certifications": ["Unity Certified Developer", "Unreal Blueprint Certification"],
        "project_ideas": ["Playable game demo", "AR education app", "3D portfolio"],
        "linkedin_headline": "Game Dev & XR Student @ Yarmouk | Unity · AR/VR | Portfolio: [link]",
        "github_tip": "الأهم هو demo قابل للتشغيل — حط رابط itch.io أو Google Play",
    },
}

# ==================== SKILL GAP DATA (LinkedIn 2026) ====================
SKILL_GAP_DATA = {
    'CS': {
        'covered': ['تراكيب البيانات والخوارزميات', 'قواعد البيانات SQL', 'OOP (البرمجة الكائنية)', 'أنظمة التشغيل', 'الذكاء الاصطناعي (أساسي)'],
        'missing': {
            'Web Dev':      ['React / Vue.js', 'Node.js / Express', 'Docker & Kubernetes', 'REST APIs', 'Git & CI/CD'],
            'Mobile Dev':   ['Flutter أو React Native', 'Android (Kotlin)', 'iOS (Swift)', 'Firebase', 'App Store Deployment'],
            'AI/ML':        ['PyTorch / TensorFlow', 'Hugging Face', 'MLOps', 'Vector Databases', 'LLM Fine-tuning'],
            'DevOps':       ['Docker & Kubernetes', 'Linux Admin', 'CI/CD (GitHub Actions)', 'AWS / Azure Basics', 'Terraform'],
            'Backend':      ['Spring Boot أو Django', 'Microservices', 'Message Queues (Kafka)', 'Redis', 'GraphQL'],
            'Security':     ['Penetration Testing', 'OWASP Top 10', 'Burp Suite', 'Network Forensics', 'CTF Skills'],
        }
    },
    'CIS': {
        'covered': ['قواعد البيانات (SQL/NoSQL)', 'تحليل النظم', 'ERP Systems', 'Business Analysis', 'Project Management Basics'],
        'missing': {
            'Data Analytics':  ['Power BI / Tableau', 'Python للتحليل', 'Excel Advanced', 'DAX & M Query', 'Data Storytelling'],
            'Web Dev':         ['React.js', 'Node.js', 'REST APIs', 'Docker', 'Git Advanced'],
            'ERP/SAP':         ['SAP Basics', 'Oracle ERP', 'Odoo', 'Business Process Modeling', 'BPMN'],
            'Project Mgmt':    ['PMP / Scrum', 'Jira / Confluence', 'Agile Methodology', 'Risk Management', 'Stakeholder Communication'],
        }
    },
    'CYS': {
        'covered': ['أمن الشبكات', 'التشفير', 'الجرائم الرقمية', 'أنظمة التشغيل', 'البرمجة (أساسي)'],
        'missing': {
            'Cybersecurity':   ['Penetration Testing (CEH/OSCP)', 'Burp Suite & Metasploit', 'Cloud Security (AWS/Azure)', 'DevSecOps', 'SIEM Tools (Splunk)'],
            'SOC Analyst':     ['SIEM & Log Analysis', 'Incident Response', 'Threat Hunting', 'Malware Analysis', 'MITRE ATT&CK Framework'],
            'Cloud Security':  ['AWS Security Specialty', 'Zero Trust Architecture', 'IAM Advanced', 'Container Security', 'CASB Tools'],
        }
    },
    'BIT': {
        'covered': ['Business Analysis', 'ERP Basics', 'قواعد البيانات', 'إدارة المشاريع', 'نظم المعلومات الإدارية'],
        'missing': {
            'Data Analytics':  ['Power BI', 'Python Pandas', 'SQL Advanced', 'Tableau', 'Statistics for Business'],
            'Digital Marketing': ['Google Analytics', 'SEO/SEM', 'Meta Ads', 'CRM Systems (HubSpot)', 'Content Strategy'],
            'Business Dev':    ['Agile / Scrum', 'Jira', 'Financial Modeling', 'Business Canvas', 'Pitch Deck Design'],
        }
    },
    'DA': {
        'covered': ['Machine Learning (أساسي)', 'Python للبيانات', 'إحصاء', 'قواعد البيانات', 'تصوير البيانات'],
        'missing': {
            'Data Science':    ['MLOps (ML Pipeline)', 'Hugging Face / LLMs', 'Vector Databases', 'PySpark (Big Data)', 'Feature Engineering'],
            'AI Engineer':     ['PyTorch Advanced', 'LLM Fine-tuning', 'Prompt Engineering', 'LangChain', 'Model Deployment (FastAPI)'],
            'Data Engineering':['Apache Spark', 'Airflow (Orchestration)', 'dbt', 'Kafka', 'Cloud Data Warehouses (BigQuery/Snowflake)'],
        }
    },
    'VR': {
        'covered': ['برمجة الألعاب (Unity/Unreal)', 'رسوميات الحاسوب', 'OOP', 'فيزياء الألعاب'],
        'missing': {
            'Game Dev':        ['Unreal Engine Blueprints', 'C++ Advanced للألعاب', 'Shader Programming', 'Multiplayer Networking', 'Game Publishing (Steam/App Store)'],
            'XR Dev':          ['AR Foundation', 'Meta Quest SDK', 'WebXR', 'Spatial Computing (Apple Vision Pro)', '3D Modeling (Blender)'],
            'Mobile Games':    ['Unity Mobile Optimization', 'Addressables', 'In-App Purchases', 'Firebase Analytics', 'Ad Monetization'],
        }
    },
    'DRG': {
        'covered': ['برمجة الألعاب (Unity/Unreal)', 'رسوميات الحاسوب', 'OOP', 'فيزياء الألعاب'],
        'missing': {
            'Game Dev':        ['Unreal Engine Blueprints', 'C++ Advanced للألعاب', 'Shader Programming', 'Multiplayer Networking', 'Game Publishing (Steam/App Store)'],
            'XR Dev':          ['AR Foundation', 'Meta Quest SDK', 'WebXR', 'Spatial Computing', '3D Modeling (Blender)'],
        }
    },
}
