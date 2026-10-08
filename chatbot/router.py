"""A free router: picks one of the answers from the words of a question.

No AI model, no key and no cost. It does what the AI receptionist does, with plain
rules: fix typos, find the role, city, skill, numbers and time words, decide which
answer fits, and hand the function and its values to chatbot.queries.run(), which
checks every value again. It can only point at the functions in chatbot.queries.

When the router is not sure it refuses instead of guessing, and when it answers it
says how it understood the question, so a wrong reading is visible.

The router returns a dict: function, params, understood (a short description),
notes (honest limits that apply to this answer) and hint (shown with a refusal).
"""
import re
from difflib import get_close_matches

from chatbot.queries import MAX_LIMIT

# ---- what the router knows ----------------------------------------------------

ROLE_PHRASES = {
    "data_engineer": ["data engineer", "data engineers", "data engineering", "etl developer",
                      "etl engineer", "pipeline engineer", "analytics engineer"],
    "data_analyst": ["data analyst", "data analysts", "data analytics", "analyst", "analysts",
                     "analytics", "reporting analyst"],
    "data_scientist": ["data scientist", "data scientists", "data science", "scientist", "scientists"],
    "ml_engineer": ["ml engineer", "ml engineers", "machine learning engineer",
                    "machine learning engineers", "machine learning", "ml", "mle"],
    "bi_developer": ["bi developer", "bi developers", "power bi developer", "power bi developers",
                     "bi engineer", "bi engineers", "business intelligence developer",
                     "business intelligence developers"],
    "other": ["other roles", "other jobs", "other role", "business analyst", "business analysts",
              "database administrator", "database administrators", "dba", "data entry",
              "data entry specialist", "analytics manager", "research analyst",
              "research analysts", "reporting specialist"],
}
# Phrases inside "other" that are titles, not the word "other"
OTHER_TITLES = {p for p in ROLE_PHRASES["other"] if not p.startswith("other ")}

CITY_PHRASES = {
    "Cairo": ["cairo", "القاهرة"],
    "Giza": ["giza", "gizeh", "الجيزة"],
    "Alexandria": ["alexandria", "alex", "alexandra", "الإسكندرية",
                   "الاسكندرية"],
    "Remote": ["remote", "remotely", "work from home", "wfh", "work-from-home", "home based"],
}

SKILL_ALIASES = {
    "Power BI": ["powerbi", "power-bi", "pbi"],
    "Scikit-learn": ["scikit learn", "scikitlearn", "sklearn"],
    "Spark": ["apache spark", "pyspark"],
    "Airflow": ["apache airflow"],
    "Kafka": ["apache kafka"],
    "AWS": ["amazon web services"],
    "Azure": ["microsoft azure"],
    "TensorFlow": ["tensor flow"],
    "PyTorch": ["py torch"],
    "dbt": ["data build tool"],
    "Statistics": ["statistical", "stats"],
    "Excel": ["ms excel", "microsoft excel"],
}

INTENT_WORDS = """salary salaries earn earns earning earnings wages compensation income companies
company employers employer skills technologies technology requirements required requires requiring
latest newest recent recently openings vacancies postings positions highest lowest average typical
median location locations together alongside hiring recruiting analyst analysts engineer engineers
scientist scientists developer developers machine learning intelligence business database
administrator research specialist reporting manager alexandria remote remotely cairo
paying cities city""".split()

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10}
_NUM = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"

# Words that may appear before "jobs" or after "in" without being an unknown role or place.
ALLOWED = set("""a an the this that these those it its is are was were be been do does did has have had
what whats which who whose where when how why there here and or of for to in on at by with from as
about any all some many much more most less least few new newest latest recent recently fresh top best
better worst highest lowest high low good great well bad average typical overall total general
available open current currently hot popular common usual entry level junior senior lead principal
graduate fresher freshers intern internship remote onsite hybrid full part time contract egypt egyptian
tech technical data it me my our us we you your yours i people someone anyone everyone one ones other
others paying paid pay pays salary salaries jobs job role roles position positions posting postings
vacancy vacancies opening openings career careers market demand moment database dataset list show
give tell find see get make makes can could would should will may might please first last next
number count compare comparison versus vs per each every between within around near across
company companies city cities skill skills own particular specific main key
need needs needed require required requires learn know knows known use uses used using list lists
listing listed mention mentions mentioned ask asks asked want wants wanted look looking hire hires hiring
offer offers offering pay-wise opportunities opportunity""".split())

# ---- patterns -----------------------------------------------------------------

def _word(alternatives):
    return re.compile(r"(?<![a-z0-9])(?:" + alternatives + r")(?![a-z0-9])")


SALARY_RE = re.compile(
    r"(?<![a-z])(?:salary|salaries|pay|pays|paid|paying|earn|earns|earned|earning|earnings|wage|"
    r"wages|compensation|remuneration|income|package|packages"
    r"|\u0645\u0631\u062a\u0628|\u0645\u0631\u062a\u0628\u0627\u062a|\u0631\u0627\u062a\u0628|"
    r"\u0631\u0648\u0627\u062a\u0628|\u0645\u0639\u0627\u0634)(?![a-z])"
    r"|how much (?:[a-z]+ ){0,6}(?:make|makes|get|gets|earn|earns)(?![a-z])")
MOST_RE = _word(r"most|highest|best|top|better|higher|largest|biggest|maximum|max|best-paid|"
                r"best-paying|well-paid|lowest|least|worst|cheapest|lower|smallest|minimum|poorest")
LOW_RE = _word(r"lowest|least|worst|cheapest|lower|smallest|minimum|poorest")
COUNT_RE = re.compile(r"(?<![a-z])(?:how many|number of|count of|count|total number|total)(?![a-z])")
SKILL_NOUN_RE = _word(r"skills?|technolog(?:y|ies)|tech|tools?|stack|competenc(?:y|ies)|abilities")
SKILL_NEED_RE = _word(r"need|needs|needed|require|requires|required|requiring|requirements?|learn|use|uses|used|using|"
                      r"know|knowledge|expected|demand|demanded|asked|asks|wanted|wants|want")
OTHERS_RE = _word(r"else|other|also|alongside|together|along with|combined with|pair|pairs|paired|"
                  r"goes with|go with|comes with|come with|frequently|usually|often|commonly")
COMPANY_RE = re.compile(
    r"(?<![a-z])(?:compan(?:y|ies)|employers?|firms?|organi[sz]ations?|businesses|recruiters?|"
    r"who(?:s| is| are)? (?:hiring|recruiting|posting|looking|offering)|who hires|who employs|"
    r"hiring the most)(?![a-z])")
CITY_RE = _word(r"cit(?:y|ies)|locations?|where|areas?|places?|regions?|governorates?")
NEW_RE = _word(r"new|newest|latest|recent|recently|fresh|freshest|just posted|posted|openings?|"
               r"vacanc(?:y|ies)|listings?|list|show|display|find|any|available|current|currently|open")
DOMAIN_RE = _word(r"jobs?|postings?|posts?|roles?|positions?|vacanc(?:y|ies)|openings?|hiring|hire|"
                  r"hires|careers?|work|salary|salaries|pay|pays|paid|paying|earn|earns|earning|"
                  r"wage|wages|skills?|compan(?:y|ies)|employers?|market|listings?")
SENIORITY_RE = _word(r"junior|jr|senior|sr|lead|principal|entry level|entry-level|intern|internship|"
                     r"fresh graduate|graduate|fresher|freshers|staff|head of|manager")
STRICT_NEW_RE = _word(r"new|newest|latest|recent|recently|fresh|freshest|just posted")
VOLUME_RE = _word(r"jobs?|postings?|openings?|vacanc(?:y|ies)|positions?|hiring|listings?|"
                  r"opportunit(?:y|ies)|demand")
ROLE_ASK_RE = _word(r"roles?|titles?|fields?|specializations?|specialisations?|job types?")
TIME_NOTE_RE = _word(r"today|yesterday|tonight|this week|last week|this month|last month|this year|"
                     r"last year|past week|past month|recently")

GROUP_NOUNS = {
    "city": _word(r"cit(?:y|ies)|locations?|where|areas?|regions?"),
    "company": _word(r"compan(?:y|ies)|employers?|firms?|who|organi[sz]ations?"),
    "skill": _word(r"skills?|technolog(?:y|ies)|tech|tools?|stack"),
    "role": _word(r"roles?|jobs?|positions?|titles?|fields?|careers?|specializations?"),
}

AMOUNT_RE = re.compile(
    r"(?:more than|over|above|at least|minimum of|minimum|min|greater than|exceeding|exceeds|"
    r"higher than|upwards of|>=|>)\s*(?:egp|le)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?"
    r"|(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?\s*(?:\+|or more|and above|and up|plus|and over|or higher)")
TIME_RE = re.compile(
    r"(?:in the |in |for the |over the |within the |within )?(?:last|past|previous)\s+" + _NUM +
    r"\s+(day|week|month)s?")
PERIOD_RE = re.compile(r"(?<![a-z])(?:this|last|past|previous|current)\s+(week|month)(?![a-z])")
DAY_WORD_RE = re.compile(r"(?<![a-z])(today|yesterday)(?![a-z])")
LIMIT_RES = [
    re.compile(r"(?<![a-z])(?:top|first|best|biggest|leading|highest)\s+" + _NUM + r"(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])" + _NUM + r"\s+(?:most|top|best|biggest|leading)(?![a-z])"),
    re.compile(r"(?<![a-z])(?:list|show|give|name|tell)(?:\s+me)?(?:\s+the)?\s+" + _NUM + r"(?![a-z0-9])"),
    re.compile(r"(?<![a-z0-9])" + _NUM + r"\s+(?:skills?|compan(?:y|ies)|cities|postings|jobs|results?)"),
]

SUBJECT_RES = [
    re.compile(r"(?<![a-z])(?:a|an|the)\s+([a-z]+(?:\s+[a-z]+)?)\s+"
               r"(?:earn|earns|make|makes|get paid|gets paid|salary|salaries|jobs?|positions?|roles?|"
               r"postings?|vacancies)(?![a-z])"),
    re.compile(r"(?<![a-z])([a-z]+(?:\s+[a-z]+)?)\s+"
               r"(?:salary|salaries|jobs?|positions?|roles?|postings?|vacancies)(?![a-z])"),
]
PLACE_RE = re.compile(r"(?<![a-z])(?:in|at|near|around)\s+([a-z]+(?:\s+[a-z]+)?)(?![a-z])")

ROLE_HINT = ("I only have data roles: data engineer, data analyst, data scientist, ML engineer, "
             "BI developer and other.")
PLACE_HINT = "I only have postings in Cairo, Giza, Alexandria and Remote."

TITLE_NOTE = ("Titles such as business analyst, database administrator and data entry specialist "
              "are grouped under 'other'.")
SENIORITY_NOTE = "Seniority is not tracked, so this covers all levels."
AMBIGUOUS_HINT = ("Do you mean the most postings or the highest pay? Try: which city has the most "
                  "postings, or which city pays the most.")
NO_QUESTION_HINT = "I could not tell what you want to know about it."
AMOUNT_HINT = "A minimum salary only works when counting postings, for example: how many jobs pay over 30k?"
AMOUNT_NOTE = "I can count postings above that salary but not list them."
MULTI_ROLE_NOTE = "I show all roles because I cannot filter to just the ones you named."
TIME_NOTE = "This answer does not filter by date; it covers all collected postings."

LABELS = {
    "new_postings": "newest postings",
    "salary_for_role": "salary",
    "top_skills": "top skills",
    "skills_with": "skills that appear with another skill",
    "top_companies": "top companies",
    "jobs_by_city": "postings by city",
    "jobs_by_role": "postings by role",
    "count_postings": "number of postings",
    "top_paying": "typical salary ranking",
}


def _number(token):
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


def _normalize(text):
    text = text.lower().replace("'", "").replace("\u2019", "")
    text = re.sub(r"[^a-z0-9؀-ۿ\s\-.,+#<>=]", " ", text)
    text = re.sub(r"(?<![0-9])[.,]|[.,](?![0-9])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _mask(text, span):
    """Blank out a span (and tidy the spaces) so later rules do not match it again."""
    return re.sub(r" +", " ", text[:span[0]] + " " + text[span[1]:])


class RuleRouter:
    """Callable that maps a question to {"function", "params", ...}. Needs the open
    database only to learn which skills exist."""

    def __init__(self, con):
        self.skills = [r[0] for r in con.execute("SELECT skill FROM skills ORDER BY skill").fetchall()]
        self._role_re, self._role_map = self._table(ROLE_PHRASES)
        self._city_re, self._city_map = self._table(CITY_PHRASES)
        skill_phrases = {}
        by_lower = {s.lower(): s for s in self.skills}
        for name in self.skills:
            lower = name.lower()
            skill_phrases[name] = {lower, lower.replace("-", " "), lower.replace("-", "").replace(" ", "")}
        for canonical, aliases in SKILL_ALIASES.items():
            if canonical.lower() in by_lower:
                skill_phrases[by_lower[canonical.lower()]].update(aliases)
        self._skill_re, self._skill_map = self._table({k: sorted(v) for k, v in skill_phrases.items()})
        vocabulary = set(INTENT_WORDS)
        for phrases in (*ROLE_PHRASES.values(), *CITY_PHRASES.values()):
            vocabulary.update(w for p in phrases for w in re.findall(r"[a-z]{5,}", p))
        vocabulary.update(w for s in self.skills for w in re.findall(r"[a-z]{5,}", s.lower()))
        self._vocabulary = sorted(vocabulary)
        self._vocabulary_set = set(vocabulary)

    @staticmethod
    def _table(phrases_by_name):
        mapping = {}
        for name, phrases in phrases_by_name.items():
            for phrase in phrases:
                mapping[phrase] = name
        ordered = sorted(mapping, key=len, reverse=True)
        pattern = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(p) for p in ordered) + r")(?![a-z0-9])")
        return pattern, mapping

    def _fix_typos(self, text):
        def repair(match):
            word = match.group(0)
            if word in self._vocabulary_set:
                return word
            close = get_close_matches(word, self._vocabulary, n=1, cutoff=0.84)
            return close[0] if close else word
        return re.sub(r"[a-z]{5,}", repair, text)

    @staticmethod
    def _find(pattern, mapping, text):
        found, masked = [], text
        for match in pattern.finditer(text):
            found.append((mapping[match.group(0)], match.group(0)))
            masked = masked[:match.start()] + " " * (match.end() - match.start()) + masked[match.end():]
        return found, re.sub(r" +", " ", masked)

    # ---- the routing -------------------------------------------------------------

    def __call__(self, question):
        text = self._fix_typos(_normalize(question))
        roles, text = self._find(self._role_re, self._role_map, text)
        skills, text = self._find(self._skill_re, self._skill_map, text)
        cities, text = self._find(self._city_re, self._city_map, text)
        role_names = list(dict.fromkeys(name for name, _ in roles))
        skill_names = list(dict.fromkeys(name for name, _ in skills))
        city_names = list(dict.fromkeys(name for name, _ in cities))

        amount, text = self._amount(text)
        days, text = self._days(text)
        limit, text = self._limit(text)
        extra = []
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            extra.append(f"I show at most {MAX_LIMIT} results, so I used {MAX_LIMIT}." if limit > MAX_LIMIT
                         else "I show at least 1 result, so I used 1.")
            limit = max(1, min(MAX_LIMIT, limit))

        refusal = lambda hint=None: {"function": None, "params": {}, "hint": hint}
        has = {name: bool(rx.search(text)) for name, rx in (
            ("salary", SALARY_RE), ("most", MOST_RE), ("count", COUNT_RE), ("noun", SKILL_NOUN_RE),
            ("need", SKILL_NEED_RE), ("others", OTHERS_RE), ("company", COMPANY_RE),
            ("city", CITY_RE), ("new", NEW_RE), ("strict_new", STRICT_NEW_RE))}
        intent = any(has[k] for k in ("salary", "most", "count", "noun", "need", "others", "company",
                                      "city", "new")) or days is not None or limit is not None
        if not (intent or DOMAIN_RE.search(text) or role_names or city_names):
            return refusal(NO_QUESTION_HINT if skill_names else None)
        subject = self._unknown(SUBJECT_RES, text, 1)
        if subject:
            return refusal(f"I do not have data about {subject!r}. " + ROLE_HINT)
        place = self._unknown(PLACE_RE, text, 0)
        if place and not city_names:
            return refusal(f"I do not have postings in {place!r}. " + PLACE_HINT)
        for names, kind in ((skill_names, "skill"), (city_names, "city")):
            if len(names) > 1:
                return refusal(f"Please ask about one {kind} at a time.")

        role = role_names[0] if len(role_names) == 1 else None
        city = city_names[0] if city_names else None
        skill = skill_names[0] if skill_names else None
        if len(role_names) > 1 and not has["salary"]:
            return refusal("Please ask about one role at a time.")

        multi_role = len(role_names) > 1
        if amount is not None:
            if has["noun"] or has["company"] or has["others"] or has["most"] or has["city"]:
                return refusal(AMOUNT_HINT)
            if has["new"] and not has["count"]:
                extra.append(AMOUNT_NOTE)
        if amount is not None:
            choice = ("count_postings", {"role": role, "city": city, "skill": skill,
                                         "min_salary": amount})
        elif skill and len(skill_names) == 1 and (has["noun"] or has["others"]) \
                and not has["count"] and not has["salary"]:
            choice = ("skills_with", {"skill": skill, "role": role, "city": city, "limit": limit})
        elif has["salary"] and (has["most"] or multi_role):
            group = "role" if multi_role else self._group(text, role, skill)
            order = "lowest" if LOW_RE.search(text) else "highest"
            choice = ("top_paying", {"group_by": group, "role": role, "city": city, "skill": skill,
                                     "order": order, "limit": limit})
        elif has["salary"]:
            choice = ("salary_for_role", {"role": role, "city": city, "skill": skill})
        elif has["company"]:
            choice = ("top_companies", {"role": role, "city": city, "skill": skill, "limit": limit})
        elif has["noun"] or (has["need"] and role and not skill):
            choice = ("top_skills", {"role": role, "city": city, "limit": limit})
        elif has["city"] and not city and has["most"] and not VOLUME_RE.search(text):
            return refusal(AMBIGUOUS_HINT)
        elif has["city"] and not city:
            choice = ("jobs_by_city", {"role": role, "skill": skill})
        elif ROLE_ASK_RE.search(text) and not role_names and (has["most"] or has["count"]):
            choice = ("jobs_by_role", {"city": city, "skill": skill})
        elif has["count"] and days is None and not has["strict_new"]:
            choice = ("count_postings", {"role": role, "city": city, "skill": skill})
        elif has["new"] or days is not None or role or city or skill:
            params = {"role": role, "city": city, "skill": skill}
            if days is not None:
                params["days"] = days
            if limit is not None:
                params["limit"] = limit
            elif has["count"]:
                params["limit"] = 3
            choice = ("new_postings", params)
        else:
            return refusal()

        function, params = choice
        if function != "new_postings":
            params = {k: v for k, v in params.items() if v is not None}
        else:
            params = {k: v for k, v in params.items() if v is not None or k == "role"}
        if multi_role and function == "top_paying":
            extra.append(MULTI_ROLE_NOTE)
        notes = self._notes(question, text, roles, function) + extra
        return {"function": function, "params": params,
                "understood": self._describe(function, params), "notes": notes}

    # ---- pieces ------------------------------------------------------------------

    @staticmethod
    def _amount(text):
        match = AMOUNT_RE.search(text)
        if not match:
            return None, text
        number = (match.group(1) or match.group(3)).replace(",", "")
        factor = 1000 if (match.group(2) or match.group(4)) else 1
        return float(number) * factor if "." in number else int(number) * factor, _mask(text, match.span())

    @staticmethod
    def _days(text):
        match = TIME_RE.search(text)
        if match:
            unit = {"day": 1, "week": 7, "month": 30}[match.group(2)]
            return _number(match.group(1)) * unit, _mask(text, match.span())
        match = PERIOD_RE.search(text)
        if match:
            return (7 if match.group(1) == "week" else 30), _mask(text, match.span())
        match = DAY_WORD_RE.search(text)
        if match:
            return (1 if match.group(1) == "today" else 2), _mask(text, match.span())
        return None, text

    @staticmethod
    def _limit(text):
        for pattern in LIMIT_RES:
            match = pattern.search(text)
            if match:
                return _number(match.group(1)), _mask(text, match.span())
        return None, text

    @staticmethod
    def _unknown(patterns, text, group_index):
        patterns = patterns if isinstance(patterns, list) else [patterns]
        for pattern in patterns:
            for match in pattern.finditer(text):
                words = [w for w in match.group(1).split() if w not in ALLOWED]
                if words:
                    return " ".join(words)
        return None

    @staticmethod
    def _group(text, role, skill):
        best, best_at = None, None
        for name, pattern in GROUP_NOUNS.items():
            match = pattern.search(text)
            if match and (best_at is None or match.start() < best_at):
                best, best_at = name, match.start()
        if best == "role" and role:
            best = "city"
        if best is None:
            best = "city" if role else "role"
        return best

    @staticmethod
    def _notes(question, text, roles, function):
        notes = []
        if any(phrase in OTHER_TITLES for _, phrase in roles):
            notes.append(TITLE_NOTE)
        if SENIORITY_RE.search(text):
            notes.append(SENIORITY_NOTE)
        if function != "new_postings" and TIME_NOTE_RE.search(_normalize(question)):
            notes.append(TIME_NOTE)
        return notes

    @staticmethod
    def _describe(function, params):
        bits = []
        role = params.get("role")
        if function == "new_postings" or role:
            bits.append(role.replace("_", " ") if role else "all roles")
        if params.get("city"):
            bits.append(f"in {params['city']}")
        if params.get("skill"):
            bits.append(f"listing {params['skill']}" if function != "skills_with" else params["skill"])
        if params.get("min_salary") is not None:
            bits.append(f"paying at least {params['min_salary']:,} EGP/month")
        if function == "top_paying":
            bits.insert(0, f"{params['order']} first, by {params['group_by']}")
        if params.get("days") is not None:
            bits.append(f"last {params['days']} days")
        if params.get("limit") is not None:
            bits.append(f"top {params['limit']}")
        return LABELS[function] + (": " + ", ".join(bits) if bits else "")
