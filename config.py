"""The one place that lists roles, cities, skills, limits and example questions.

The generator, the cleaner, the router, the chatbot service, the web pages and the static
site export all read these lists, so adding a role means editing this file only.
All numbers here (weights, salary bands, skill shares) are invented for the synthetic data.
"""

# ---- limits shared by the chatbot answers and the browser version ----------------------
MAX_LIMIT = 20
MAX_DAYS = 90
MAX_SALARY = 1_000_000
MIN_GROUP = 3  # a group needs this many listed salaries before it can be ranked
MAX_QUESTION_CHARS = 300

# A monthly salary outside this range is treated as a typo or a different unit and ignored.
SALARY_MONTHLY_RANGE = (1_000, 500_000)

# ---- cities -----------------------------------------------------------------------------
CITIES = ["Cairo", "Giza", "Alexandria", "Remote"]

# Ways a visitor may write each city in a question (the Arabic names are unicode escapes).
CITY_PHRASES = {
    "Cairo": ["cairo", "القاهرة", "القاهره", "kahera"],
    "Giza": ["giza", "gizeh", "الجيزة", "الجيزه"],
    "Alexandria": ["alexandria", "alex", "alexandra", "الإسكندرية",
                   "الاسكندرية", "إسكندرية", "اسكندرية",
                   "الأسكندرية", "اسكندريه"],
    "Remote": ["remote", "remotely", "work from home", "wfh", "work-from-home", "home based"],
}

# ---- roles ------------------------------------------------------------------------------
# Order matters: the cleaner tries each role's title pattern in this order, so a specific
# role (such as "big data engineer") must come before a general one ("data engineer").
#   label     how a sentence names the role        plural   used in follow-up questions
#   pattern   regex on a lower-case job title      phrases  how a visitor may write it
#   titles    how a job board writes it            weight   share of postings
#   seniority share per level (a missing level is never generated)
#   salary    invented monthly EGP band (low, high) per level
#   skills    chance that each skill is listed in a posting for the role
_SENIORITY = {"junior": 0.30, "mid": 0.45, "senior": 0.25}
_AI_SENIORITY = {"junior": 0.15, "mid": 0.45, "senior": 0.40}   # newer, more senior-heavy fields
_ARCHITECT_SENIORITY = {"mid": 0.30, "senior": 0.70}             # nobody is hired as a junior architect

ROLES = {
    "data_analyst": {
        "label": "data analyst", "plural": "data analysts",
        "pattern": r"\bdata\s+analyst\b",
        "phrases": ["data analyst", "data analysts", "data analytics", "analyst", "analysts",
                    "analytics", "reporting analyst"],
        "titles": ["Data Analyst"], "weight": 0.14, "seniority": _SENIORITY,
        "salary": {"junior": (8000, 15000), "mid": (15000, 25000), "senior": (25000, 40000)},
        "skills": {"SQL": 0.85, "Excel": 0.80, "Power BI": 0.55, "Python": 0.40,
                   "Tableau": 0.30, "Statistics": 0.30},
    },
    "bi_developer": {
        "label": "BI developer", "plural": "bi developers",
        "pattern": r"\b(?:power\s*bi|bi|business\s+intelligence)\s+developer\b",
        "phrases": ["bi developer", "bi developers", "power bi developer", "power bi developers",
                    "bi engineer", "bi engineers", "bi job", "bi jobs", "bi role", "bi roles", "bi position",
                    "bi positions", "bi postings", "bi dev", "bi devs", "power bi dev",
                    "business intelligence developer", "business intelligence developers"],
        "titles": ["BI Developer", "Power BI Developer", "Business Intelligence Developer"],
        "weight": 0.08, "seniority": _SENIORITY,
        "salary": {"junior": (9000, 16000), "mid": (16000, 28000), "senior": (28000, 45000)},
        "skills": {"Power BI": 0.85, "SQL": 0.80, "Excel": 0.50, "Tableau": 0.30, "Azure": 0.20,
                   "Looker": 0.10},
    },
    "business_analyst": {
        "label": "business analyst", "plural": "business analysts",
        "pattern": r"\bbusiness\s+(?:data\s+)?analyst\b",
        "phrases": ["business analyst", "business analysts", "business data analyst",
                    "business data analysts"],
        "titles": ["Business Analyst", "Business Analyst (Data)", "Business Data Analyst"],
        "weight": 0.08, "seniority": _SENIORITY,
        "salary": {"junior": (9000, 16000), "mid": (16000, 27000), "senior": (27000, 42000)},
        "skills": {"Excel": 0.75, "SQL": 0.70, "Power BI": 0.40, "Tableau": 0.20, "Statistics": 0.20,
                   "Python": 0.15},
    },
    "data_engineer": {
        "label": "data engineer", "plural": "data engineers",
        "pattern": r"\bdata\s+engineer\b",
        "phrases": ["data engineer", "data engineers", "data engineering", "data eng", "data engs", "de",
                    "etl developer", "etl engineer", "pipeline engineer"],
        "titles": ["Data Engineer"], "weight": 0.17, "seniority": _SENIORITY,
        "salary": {"junior": (12000, 20000), "mid": (20000, 35000), "senior": (35000, 60000)},
        "skills": {"Python": 0.90, "SQL": 0.90, "Airflow": 0.50, "Spark": 0.50, "AWS": 0.40,
                   "Git": 0.30, "Docker": 0.30, "Kafka": 0.20, "Azure": 0.20, "dbt": 0.15,
                   "Snowflake": 0.15},
    },
    "analytics_engineer": {
        "label": "analytics engineer", "plural": "analytics engineers",
        "pattern": r"\banalytics\s+engineer\b",
        "phrases": ["analytics engineer", "analytics engineers", "analytics eng", "analytics engs"],
        "titles": ["Analytics Engineer"], "weight": 0.05, "seniority": _SENIORITY,
        "salary": {"junior": (13000, 22000), "mid": (22000, 37000), "senior": (37000, 58000)},
        "skills": {"SQL": 0.95, "dbt": 0.85, "Python": 0.50, "Git": 0.50, "Snowflake": 0.35,
                   "Looker": 0.30, "Airflow": 0.25, "Tableau": 0.15},
    },
    "data_scientist": {
        "label": "data scientist", "plural": "data scientists",
        "pattern": r"\bdata\s+scientist\b",
        "phrases": ["data scientist", "data scientists", "data science", "ds", "scientist", "scientists"],
        "titles": ["Data Scientist"], "weight": 0.10, "seniority": _SENIORITY,
        "salary": {"junior": (12000, 20000), "mid": (20000, 35000), "senior": (35000, 55000)},
        "skills": {"Python": 0.95, "SQL": 0.60, "Pandas": 0.60, "Scikit-learn": 0.60,
                   "Statistics": 0.50, "TensorFlow": 0.25, "PyTorch": 0.25},
    },
    "ml_engineer": {
        "label": "ML engineer", "plural": "ml engineers",
        "pattern": r"\b(?:machine\s+learning|ml)\s+engineer\b",
        "phrases": ["ml engineer", "ml engineers", "ml eng", "ml engs", "machine learning engineer",
                    "machine learning engineers", "machine learning", "ml", "mle"],
        "titles": ["Machine Learning Engineer", "ML Engineer"], "weight": 0.07, "seniority": _SENIORITY,
        "salary": {"junior": (15000, 25000), "mid": (25000, 40000), "senior": (40000, 65000)},
        "skills": {"Python": 0.95, "PyTorch": 0.50, "Docker": 0.50, "TensorFlow": 0.40,
                   "AWS": 0.40, "Scikit-learn": 0.40, "SQL": 0.30, "Git": 0.30, "MLflow": 0.20},
    },
    "ai_engineer": {
        "label": "AI engineer", "plural": "ai engineers",
        "pattern": r"\b(?:ai|artificial\s+intelligence)\s+engineer\b",
        "phrases": ["ai engineer", "ai engineers", "ai eng", "ai engs", "ai developer", "ai developers",
                    "ai job", "ai jobs", "ai role", "ai roles", "artificial intelligence engineer",
                    "artificial intelligence engineers", "artificial intelligence"],
        "titles": ["AI Engineer", "Artificial Intelligence Engineer"], "weight": 0.06,
        "seniority": _AI_SENIORITY,
        "salary": {"junior": (16000, 26000), "mid": (26000, 42000), "senior": (42000, 68000)},
        "skills": {"Python": 0.95, "PyTorch": 0.50, "Docker": 0.40, "TensorFlow": 0.35, "Hugging Face": 0.35,
                   "AWS": 0.35, "Git": 0.30, "SQL": 0.25, "LangChain": 0.20},
    },
    "mlops_engineer": {
        "label": "MLOps engineer", "plural": "mlops engineers",
        "pattern": r"\bml\s*ops\b",
        "phrases": ["mlops engineer", "mlops engineers", "mlops eng", "mlops engs", "mlops", "ml ops",
                    "ml-ops", "ml ops engineer", "ml ops engineers"],
        "titles": ["MLOps Engineer", "ML Ops Engineer"], "weight": 0.04, "seniority": _AI_SENIORITY,
        "salary": {"junior": (15000, 25000), "mid": (25000, 40000), "senior": (40000, 62000)},
        "skills": {"Python": 0.90, "Docker": 0.85, "Kubernetes": 0.70, "CI/CD": 0.60, "MLflow": 0.55,
                   "Git": 0.50, "AWS": 0.45, "Terraform": 0.35, "Azure": 0.25, "Airflow": 0.25},
    },
    "nlp_engineer": {
        "label": "NLP engineer", "plural": "nlp engineers",
        "pattern": r"\b(?:nlp|natural\s+language\s+processing)\b",
        "phrases": ["nlp engineer", "nlp engineers", "nlp eng", "nlp engs", "nlp",
                    "natural language processing engineer", "natural language processing engineers",
                    "natural language processing", "natural language"],
        "titles": ["NLP Engineer", "Natural Language Processing Engineer"], "weight": 0.03,
        "seniority": _AI_SENIORITY,
        "salary": {"junior": (16000, 26000), "mid": (26000, 42000), "senior": (42000, 66000)},
        "skills": {"Python": 0.97, "Hugging Face": 0.55, "PyTorch": 0.55, "spaCy": 0.45, "Scikit-learn": 0.30,
                   "TensorFlow": 0.25, "Docker": 0.25, "Git": 0.25, "SQL": 0.20},
    },
    "computer_vision_engineer": {
        "label": "computer vision engineer", "plural": "computer vision engineers",
        "pattern": r"\b(?:computer\s+vision|cv)\s+engineer\b",
        "phrases": ["computer vision engineer", "computer vision engineers", "computer vision",
                    "cv engineer", "cv engineers", "cv eng", "cv engs", "vision engineer", "vision engineers"],
        "titles": ["Computer Vision Engineer", "CV Engineer"], "weight": 0.03, "seniority": _AI_SENIORITY,
        "salary": {"junior": (15000, 25000), "mid": (25000, 41000), "senior": (41000, 65000)},
        "skills": {"Python": 0.95, "OpenCV": 0.80, "PyTorch": 0.60, "TensorFlow": 0.40, "CUDA": 0.30,
                   "Docker": 0.30, "Git": 0.25, "AWS": 0.20},
    },
    "data_architect": {
        "label": "data architect", "plural": "data architects",
        "pattern": r"\bdata\s+architect\b",
        "phrases": ["data architect", "data architects", "data architecture", "architect", "architects"],
        "titles": ["Data Architect"], "weight": 0.03, "seniority": _ARCHITECT_SENIORITY,
        "salary": {"mid": (35000, 50000), "senior": (50000, 85000)},
        "skills": {"SQL": 0.85, "Data Modeling": 0.85, "AWS": 0.50, "Azure": 0.45, "Python": 0.40,
                   "Snowflake": 0.30, "Spark": 0.30, "Databricks": 0.25, "Kafka": 0.20, "Terraform": 0.20},
    },
    "big_data_engineer": {
        "label": "big data engineer", "plural": "big data engineers",
        "pattern": r"\bbig\s+data\s+(?:engineer|developer)\b",
        "phrases": ["big data engineer", "big data engineers", "big data eng", "big data engs",
                    "big data developer", "big data developers", "big data", "bigdata engineer"],
        "titles": ["Big Data Engineer", "Big Data Developer"], "weight": 0.04, "seniority": _SENIORITY,
        "salary": {"junior": (13000, 21000), "mid": (21000, 36000), "senior": (36000, 60000)},
        "skills": {"Spark": 0.85, "SQL": 0.70, "Hadoop": 0.60, "Python": 0.60, "Kafka": 0.50, "Hive": 0.40,
                   "AWS": 0.35, "Java": 0.35, "Airflow": 0.30, "Docker": 0.20},
    },
    "genai_engineer": {
        "label": "GenAI engineer", "plural": "genai engineers",
        "pattern": r"\b(?:gen\s*ai|generative\s+ai|llm)\b",
        "phrases": ["genai engineer", "genai engineers", "genai eng", "genai engs", "genai developer",
                    "genai developers", "genai", "gen ai engineer", "gen ai engineers", "gen ai",
                    "generative ai engineer", "generative ai engineers", "generative ai", "llm engineer",
                    "llm engineers", "llm eng", "llm engs", "llm developer", "llm developers", "llm", "llms"],
        "titles": ["GenAI Engineer", "Generative AI Engineer", "LLM Engineer"], "weight": 0.05,
        "seniority": _AI_SENIORITY,
        "salary": {"junior": (17000, 28000), "mid": (28000, 45000), "senior": (45000, 75000)},
        "skills": {"Python": 0.95, "LangChain": 0.65, "Prompt Engineering": 0.60, "RAG": 0.55,
                   "Vector Databases": 0.45, "Hugging Face": 0.40, "PyTorch": 0.30, "AWS": 0.30,
                   "Azure": 0.30, "Docker": 0.30, "SQL": 0.15},
    },
    # Titles that match none of the patterns above end up here on purpose.
    "other": {
        "label": "other roles", "plural": "other roles", "pattern": None,
        "phrases": ["other roles", "other jobs", "other role", "database administrator",
                    "database administrators", "dba", "data entry", "data entry specialist",
                    "analytics manager", "research analyst", "research analysts", "reporting specialist"],
        "titles": ["Database Administrator", "Data Entry Specialist", "Analytics Manager",
                   "Research Analyst", "Reporting Specialist"],
        "weight": 0.03, "seniority": _SENIORITY,
        "salary": {"junior": (8000, 15000), "mid": (15000, 25000), "senior": (25000, 40000)},
        "skills": {"Excel": 0.70, "SQL": 0.60, "Power BI": 0.30, "Python": 0.20, "Tableau": 0.15},
    },
}

# The cleaner tries these patterns in this order, so a specific title ("big data engineer",
# "genai engineer") is matched before a general one ("data engineer", "ai engineer").
PATTERN_ORDER = ["mlops_engineer", "genai_engineer", "nlp_engineer", "computer_vision_engineer",
                 "ml_engineer", "ai_engineer", "big_data_engineer", "data_engineer", "analytics_engineer",
                 "data_architect", "data_scientist", "business_analyst", "data_analyst", "bi_developer"]

# ---- skills -----------------------------------------------------------------------------
# canonical name -> other ways a job board writes it (the cleaner maps them back).
SKILL_VARIANTS = {
    "Python": ["python", "Python3"],
    "SQL": ["Sql"],
    "Spark": ["Apache Spark", "PySpark"],
    "Airflow": ["Apache Airflow"],
    "AWS": ["Amazon Web Services"],
    "Azure": [], "Docker": [], "Kafka": [], "dbt": [], "Git": [], "Java": [],
    "Excel": ["MS Excel"],
    "Power BI": ["PowerBI", "power bi"],
    "Tableau": [], "Pandas": [], "Statistics": [],
    "Scikit-learn": ["sklearn"],
    "TensorFlow": [], "PyTorch": [],
    "Snowflake": [], "Databricks": [], "Looker": [], "Terraform": [], "Hadoop": [], "Hive": [],
    "Kubernetes": ["K8s"],
    "MLflow": ["ML Flow"],
    "LangChain": ["Lang Chain"],
    "Hugging Face": ["HuggingFace"],
    "spaCy": ["SpaCy"],
    "OpenCV": ["Open CV"],
    "CUDA": [],
    "CI/CD": ["CICD"],
    "RAG": ["Retrieval-Augmented Generation"],
    "Prompt Engineering": ["Prompting"],
    "Vector Databases": ["Vector DB", "Vector DBs"],
    "Data Modeling": ["Data Modelling"],
}

# Other ways a visitor may write a skill in a question (canonical name -> aliases).
SKILL_QUERY_ALIASES = {
    "Power BI": ["powerbi", "power-bi", "pbi"],
    "Scikit-learn": ["scikit learn", "scikitlearn", "sklearn"],
    "Spark": ["apache spark", "pyspark"],
    "Airflow": ["apache airflow"],
    "Kafka": ["apache kafka"],
    "AWS": ["amazon web services"],
    "Azure": ["microsoft azure"],
    "TensorFlow": ["tensor flow", "tf"],
    "PyTorch": ["py torch", "torch"],
    "dbt": ["data build tool"],
    "Statistics": ["statistical", "stats"],
    "Excel": ["ms excel", "microsoft excel"],
    "Kubernetes": ["k8s", "kube"],
    "MLflow": ["ml flow"],
    "LangChain": ["lang chain"],
    "Hugging Face": ["huggingface", "hugging-face", "hf"],
    "OpenCV": ["open cv", "cv2"],
    "CI/CD": ["cicd", "ci cd", "ci-cd"],
    "RAG": ["retrieval augmented generation"],
    "Prompt Engineering": ["prompting", "prompt eng"],
    "Vector Databases": ["vector database", "vector db", "vector dbs"],
    "Data Modeling": ["data modelling", "data model"],
}

# ---- derived views (everything below is computed, do not edit) ---------------------------
SEED_ROLES = list(ROLES)
PLURAL = {key: r["plural"] for key, r in ROLES.items() if key != "other"}
ROLE_LABEL = {key: r["label"] for key, r in ROLES.items()}
ROLE_PATTERNS = [(key, ROLES[key]["pattern"]) for key in PATTERN_ORDER]
ROLE_PHRASES = {key: list(r["phrases"]) for key, r in ROLES.items()}
ROLE_WEIGHTS = {key: r["weight"] for key, r in ROLES.items()}
ROLE_TITLES = {key: list(r["titles"]) for key, r in ROLES.items()}
SALARY_BANDS = {key: dict(r["salary"]) for key, r in ROLES.items()}
SENIORITY_BY_ROLE = {key: dict(r["seniority"]) for key, r in ROLES.items()}
ROLE_SKILL_PROBS = {key: dict(r["skills"]) for key, r in ROLES.items()}

# ---- content for the pages ---------------------------------------------------------------
# Click-to-ask questions, grouped for the page. Tests check that every one is answered.
EXAMPLES = {
    "Pay": [
        "What does a data analyst earn in Cairo?",
        "Which city pays data engineers the most?",
        "Lowest paying role",
        "How many jobs pay over 30k?",
        "What does an AI engineer earn?",
    ],
    "Skills": [
        "What skills do ml engineers need?",
        "What skills go with Airflow?",
        "Top 5 skills in Giza",
        "What skills do MLOps engineers need?",
    ],
    "Hiring": [
        "Who is hiring data scientists?",
        "Top 5 companies hiring data engineers",
        "Which city has the most postings?",
        "Who is hiring GenAI engineers?",
    ],
    "New": [
        "New data engineer jobs in the last 7 days",
        "Remote data analyst jobs",
        "Which role has the most openings?",
        "New NLP engineer jobs in the last 7 days",
    ],
}

# Advice on how to ask. Each tip has an example that a test checks.
HOW_TO_ASK = [
    {"title": "Name a role", "tip": "Data analyst, BI developer, business analyst, data engineer, analytics engineer, data scientist, ML engineer, AI engineer, MLOps, NLP, computer vision, data architect, big data or GenAI/LLM engineer.",
     "example": "What does a data engineer earn?"},
    {"title": "Add a city", "tip": "Cairo, Giza, Alexandria or Remote.",
     "example": "Data scientist jobs in Alexandria"},
    {"title": "Add a skill", "tip": "Python, SQL, Airflow, Power BI, Spark, Docker and more.",
     "example": "How many postings list Spark?"},
    {"title": "Use numbers", "tip": "Try top 5, over 30k, or the last 7 days.",
     "example": "Top 3 skills for data analysts"},
    {"title": "Ask for a ranking", "tip": "Start with which and end with the most or the lowest.",
     "example": "Which skill pays the most?"},
    {"title": "One thing at a time", "tip": "One city and one skill per question works best.",
     "example": "Companies hiring in Giza"},
]
