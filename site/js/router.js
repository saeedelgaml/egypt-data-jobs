// The free, rule-based router, running in the browser. A port of chatbot/router.py: the word
// lists, regular expressions and fixed sentences are read from the data file (they are exported
// from the Python file, so the two cannot drift apart); only the logic is written here.
// It can only point at the nine answers in queries.js. No AI model, no key, nothing is sent anywhere.
import { closestWord } from "./difflib.js";
import { floatMoney, money } from "./pyfmt.js";

const NUMERIC = /^\d+$/;
const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&");

export function normalize(text) {
  let out = text.toLowerCase().replace(/'/g, "").replace(/’/g, "");
  out = out.replace(/[^a-z0-9؀-ۿ\s\-.,+#<>=]/g, " ");
  out = out.replace(/(?<![0-9])[.,]|[.,](?![0-9])/g, " ");
  return out.replace(/\s+/g, " ").trim();
}

const squeeze = (text) => text.replace(/ +/g, " ");
const mask = (text, start, end) => squeeze(`${text.slice(0, start)} ${text.slice(end)}`);

export function createRouter(cfg, skills) {
  const R = cfg.router;
  const T = R.text;
  const MAX_LIMIT = cfg.max_limit, MAX_DAYS = cfg.max_days;
  const rx = Object.fromEntries(Object.entries(R.patterns).map(([k, v]) => [k, new RegExp(v)]));
  const globalOf = (source, flags = "g") => new RegExp(source, flags);
  const limitSources = R.limit_patterns, subjectSources = R.subject_patterns;
  const groupNouns = Object.entries(R.group_nouns).map(([name, src]) => [name, new RegExp(src)]);
  const allowed = new Set(R.allowed);
  const intentWords = R.intent_words;
  const intentSet = new Set(intentWords);
  const numberWords = R.number_words;
  const otherTitles = new Set(R.other_titles);
  const labels = R.labels;
  const numeric = (token) => (NUMERIC.test(token) ? Number.parseInt(token, 10) : numberWords[token]);

  function table(phrasesByName) {
    const mapping = new Map();
    for (const [name, phrases] of phrasesByName) for (const phrase of phrases) mapping.set(phrase, name);
    const ordered = [...mapping.keys()].sort((a, b) => b.length - a.length);
    const source = `(?<![a-z0-9])(?:${ordered.map(escapeRegExp).join("|")})(?![a-z0-9])`;
    return { source, map: mapping };
  }

  const roleTable = table(Object.entries(R.role_phrases));
  const cityTable = table(Object.entries(R.city_phrases));
  const skillPhrases = new Map();
  const byLower = new Map(skills.map((s) => [s.toLowerCase(), s]));
  for (const name of skills) {
    const lower = name.toLowerCase();
    skillPhrases.set(name, new Set([lower, lower.replace(/-/g, " "), lower.replace(/-/g, "").replace(/ /g, "")]));
  }
  for (const [canonical, aliases] of Object.entries(R.skill_aliases)) {
    if (byLower.has(canonical.toLowerCase())) aliases.forEach((a) => skillPhrases.get(byLower.get(canonical.toLowerCase())).add(a));
  }
  const rolePhrases = new Set(Object.values(R.role_phrases).flat());
  const roleWords = new Set([...rolePhrases].flatMap((p) => p.split(" ")));
  const skillTable = table([...skillPhrases].map(([name, set]) => [name, [...set].filter((p) => !rolePhrases.has(p)).sort()]));

  const minLength = R.typo.min_length;
  const wordsLong = (text) => text.match(new RegExp(`[a-z]{${minLength},}`, "g")) || [];
  const vocabulary = new Set(intentWords);
  for (const phrases of [...Object.values(R.role_phrases), ...Object.values(R.city_phrases)]) {
    phrases.forEach((p) => wordsLong(p).forEach((w) => vocabulary.add(w)));
  }
  skills.forEach((s) => wordsLong(s.toLowerCase()).forEach((w) => vocabulary.add(w)));
  const vocabularyList = [...vocabulary].sort();
  const vocabularySet = new Set(vocabulary);
  for (const phrases of [...[...skillPhrases.values()].map((s) => [...s]), ...Object.values(R.role_phrases),
                         ...Object.values(R.city_phrases)]) {
    phrases.forEach((p) => wordsLong(p).forEach((w) => vocabularySet.add(w)));
  }

  function fixTypos(text) {
    return text.replace(new RegExp(`[a-z]{${minLength},}`, "g"), (word) => {
      if (vocabularySet.has(word) || allowed.has(word)) return word;
      return closestWord(word, vocabularyList, R.typo.cutoff) ?? word;
    });
  }

  function find(tbl, text) {
    const found = [];
    let masked = text;
    for (const m of text.matchAll(globalOf(tbl.source))) {
      found.push([tbl.map.get(m[0]), m[0]]);
      masked = masked.slice(0, m.index) + " ".repeat(m[0].length) + masked.slice(m.index + m[0].length);
    }
    return [found, squeeze(masked)];
  }

  function amount(text) {
    const m = rx.AMOUNT.exec(text);
    if (!m) return [null, text, false];
    const number = (m[1] || m[3]).replace(/,/g, "");
    const factor = m[2] || m[4] ? 1000 : 1;
    const isFloat = number.includes(".");
    const value = isFloat ? Number.parseFloat(number) * factor : Number.parseInt(number, 10) * factor;
    return [value, mask(text, m.index, m.index + m[0].length), isFloat];
  }

  function days(text) {
    let m = rx.TIME.exec(text);
    if (m) {
      const unit = { day: 1, week: 7, month: 30 }[m[2]];
      return [numeric(m[1]) * unit, mask(text, m.index, m.index + m[0].length)];
    }
    m = rx.PERIOD.exec(text);
    if (m) return [m[1] === "week" ? 7 : 30, mask(text, m.index, m.index + m[0].length)];
    m = rx.DAY_WORD.exec(text);
    if (m) return [m[1] === "today" ? 1 : 2, mask(text, m.index, m.index + m[0].length)];
    return [null, text];
  }

  function limit(text) {
    for (const source of limitSources) {
      const m = globalOf(source, "d").exec(text);
      if (m) return [numeric(m[1]), mask(text, m.indices[1][0], m.indices[1][1])];
    }
    return [null, text];
  }

  function unknown(sources, text, lastWordOnly = false) {
    for (const source of sources) {
      for (const m of text.matchAll(globalOf(source))) {
        const parts = m[1].split(/\s+/).filter(Boolean);
        const last = parts[parts.length - 1];
        if (lastWordOnly && (allowed.has(last) || Object.hasOwn(numberWords, last) || NUMERIC.test(last) || last.startsWith("zz"))) continue;
        const rest = parts.filter((w) => !allowed.has(w) && !NUMERIC.test(w) && !w.startsWith("zz"));
        if (rest.length) return rest.join(" ");
      }
    }
    return null;
  }

  const askedGroup = (text) =>
    ["city", "company", "skill"].some((name) => groupNouns.find(([n]) => n === name)[1].test(text)) || rx.STRONG_ROLE.test(text);

  function mark(text) {
    for (const [tbl, name] of [[roleTable, "zzrole"], [skillTable, "zzskill"], [cityTable, "zzcity"]]) {
      text = text.replace(globalOf(tbl.source), ` ${name} `);
    }
    return squeeze(text);
  }

  function unknownFilter(text) {
    for (const m of text.matchAll(globalOf(rx.FILTER_WORD.source))) {
      const word = m[1].replace(/^[.-]+|[.-]+$/g, "");
      if (!word || /^\d/.test(word) || allowed.has(word) || intentSet.has(word) || roleWords.has(word) || Object.hasOwn(numberWords, word) ||
          word.startsWith("zz") || /[^\x00-\x7F]/.test(word)) continue;
      return word;
    }
    return null;
  }

  function group(text, role, skill) {
    let best = null, bestAt = null;
    for (const [name, pattern] of groupNouns) {
      if (name === "role") continue;
      const m = pattern.exec(text);
      if (m && (bestAt === null || m.index < bestAt)) { best = name; bestAt = m.index; }
    }
    if (best === null && groupNouns.find(([n]) => n === "role")[1].test(text)) best = "role";
    if (best === "role" && role) best = "city";
    if (best === null) best = role ? "city" : "role";
    return best;
  }

  function notes(question, text, roles, fn) {
    const out = [];
    if (roles.some(([, phrase]) => otherTitles.has(phrase))) out.push(T.TITLE_NOTE);
    if (rx.SENIORITY.test(text)) out.push(T.SENIORITY_NOTE);
    if (fn !== "new_postings" && rx.TIME_NOTE.test(normalize(question))) out.push(T.TIME_NOTE);
    return out;
  }

  function describe(fn, params, amountIsFloat) {
    const bits = [];
    const role = params.role;
    if (fn === "new_postings" || role) bits.push(role ? role.replace(/_/g, " ") : "all roles");
    if (params.city) bits.push(`in ${params.city}`);
    if (params.skill) bits.push(fn !== "skills_with" ? `listing ${params.skill}` : params.skill);
    if (params.min_salary !== undefined && params.min_salary !== null) {
      const shown = amountIsFloat ? floatMoney(params.min_salary) : money(params.min_salary);
      bits.push(`paying at least ${shown} EGP/month`);
    }
    if (fn === "top_paying") bits.unshift(`${params.order} first, by ${params.group_by}`);
    if (params.days !== undefined && params.days !== null) bits.push(`last ${params.days} days`);
    if (params.limit !== undefined && params.limit !== null) bits.push(`top ${params.limit}`);
    return labels[fn] + (bits.length ? `: ${bits.join(", ")}` : "");
  }

  const refusal = (hint = null) => ({ function: null, params: {}, hint });
  const uniqueNames = (found) => [...new Set(found.map(([name]) => name))];

  function route(question) {
    const base = fixTypos(normalize(question));
    const marked = mark(base);
    let text = base;
    let roles, foundSkills, cities;
    [roles, text] = find(roleTable, text);
    [foundSkills, text] = find(skillTable, text);
    [cities, text] = find(cityTable, text);
    const roleNames = uniqueNames(roles), skillNames = uniqueNames(foundSkills), cityNames = uniqueNames(cities);

    let amountValue, amountIsFloat, daysValue, limitValue;
    [amountValue, text, amountIsFloat] = amount(text);
    [daysValue, text] = days(text);
    [limitValue, text] = limit(text);
    const extra = [];
    if (limitValue !== null && !(limitValue >= 1 && limitValue <= MAX_LIMIT)) {
      extra.push(limitValue > MAX_LIMIT ? `I show at most ${MAX_LIMIT} results, so I used ${MAX_LIMIT}.`
                                        : "I show at least 1 result, so I used 1.");
      limitValue = Math.max(1, Math.min(MAX_LIMIT, limitValue));
    }

    const has = {
      salary: rx.SALARY.test(text), most: rx.MOST.test(text), count: rx.COUNT.test(text),
      noun: rx.SKILL_NOUN.test(text), need: rx.SKILL_NEED.test(text), others: rx.OTHERS.test(text),
      company: rx.COMPANY.test(text), city: rx.CITY.test(text), new: rx.NEW.test(text),
      strict_new: rx.STRICT_NEW.test(text),
    };
    const intent = ["salary", "most", "count", "noun", "need", "others", "company", "city", "new"].some((k) => has[k])
      || daysValue !== null || limitValue !== null;
    if (!(intent || rx.DOMAIN.test(text) || roleNames.length || cityNames.length)) {
      return refusal(skillNames.length ? T.NO_QUESTION_HINT : null);
    }
    const subject = unknown(subjectSources, text, true);
    if (subject) return refusal(`I do not have data about ${pyReprShort(subject)}. ${T.ROLE_HINT}`);
    const place = unknown([rx.PLACE.source], marked);
    if (place && !cityNames.length) return refusal(`I do not have postings in ${pyReprShort(place)}. ${T.PLACE_HINT}`);
    if (rx.INJECTION.test(text)) return refusal(T.INJECTION_HINT);
    if (rx.MUTATE.test(text)) return refusal(T.MUTATE_HINT);
    if (rx.CONTACT.test(text)) return refusal(T.CONTACT_HINT);
    if (rx.TREND.test(text)) return refusal(T.TREND_HINT);
    if (rx.ADVICE.test(text) && !((has.noun || has.need) && /(?<![a-z])(?:what|which)(?![a-z])/.test(text))) {
      return refusal(T.ADVICE_HINT);
    }
    if (daysValue !== null && daysValue > MAX_DAYS) return refusal(`I can only look back ${MAX_DAYS} days.`);
    const bad = unknownFilter(marked);
    if (bad) return refusal(`I do not recognize ${pyReprShort(bad)}. ${T.SKILL_HINT.replace("{}", skills.join(", "))} ${T.PLACE_HINT}`);
    const whereQuestion = cityNames.length > 1 && has.city && !has.salary;
    if (whereQuestion) extra.push("Showing all cities.");
    for (const [names, kind] of [[skillNames, "skill"], [cityNames, "city"]]) {
      if (names.length > 1 && !(kind === "city" && whereQuestion)) return refusal(`Please ask about one ${kind} at a time.`);
    }

    const role = roleNames.length === 1 ? roleNames[0] : null;
    const city = cityNames.length === 1 ? cityNames[0] : null;
    const skill = skillNames.length ? skillNames[0] : null;
    if (roleNames.length > 1 && !has.salary) return refusal("Please ask about one role at a time.");

    const multiRole = roleNames.length > 1;
    if (amountValue !== null) {
      if (has.noun || has.company || has.others || has.most || has.city) return refusal(T.AMOUNT_HINT);
      if (has.new && !has.count) extra.push(T.AMOUNT_NOTE);
    }
    let fn, params, lastResort = false;
    if (amountValue !== null) {
      fn = "count_postings"; params = { role, city, skill, min_salary: amountValue };
    } else if (skill && skillNames.length === 1 && (has.noun || has.others) && !has.count && !has.salary) {
      fn = "skills_with"; params = { skill, role, city, limit: limitValue };
    } else if (has.salary && (multiRole || (has.most && (askedGroup(text) || !(role || city || skill))))) {
      fn = "top_paying";
      params = { group_by: multiRole ? "role" : group(text, role, skill), role, city, skill,
                 order: rx.LOW.test(text) ? "lowest" : "highest", limit: limitValue };
    } else if (has.salary) {
      fn = "salary_for_role"; params = { role, city, skill };
    } else if (has.company) {
      fn = "top_companies"; params = { role, city, skill, limit: limitValue };
    } else if (has.noun || (has.need && role && !skill)) {
      fn = "top_skills"; params = { role, city, limit: limitValue };
    } else if (has.city && !city && has.most && !rx.VOLUME.test(text)) {
      return refusal(T.AMBIGUOUS_HINT);
    } else if (has.city && !city) {
      fn = "jobs_by_city"; params = { role, skill };
    } else if ((rx.ROLE_ASK.test(text) || (has.most && rx.ROLE_MOST.test(text) && rx.VOLUME.test(text))) && !roleNames.length) {
      fn = "jobs_by_role"; params = { city, skill };
    } else if (has.count && daysValue === null && !has.strict_new) {
      fn = "count_postings"; params = { role, city, skill };
    } else if (has.new || daysValue !== null || role || city || skill) {
      // The last resort: only for a question about jobs, or a bare role/city phrase (same rule as the Python router).
      const bare = base.split(" ").filter(Boolean).length <= R.bare_phrase_words
        && text.split(" ").filter(Boolean).every((w) => allowed.has(w));
      if (!(rx.JOB_INTENT.test(base) || bare)) return refusal();
      lastResort = true;
      fn = "new_postings"; params = { role, city, skill };
      if (daysValue !== null) params.days = daysValue;
      if (limitValue !== null) params.limit = limitValue;
      else if (has.count) params.limit = 3;
    } else {
      return refusal();
    }

    const keep = fn === "new_postings" ? ([k, v]) => v !== null || k === "role" : ([, v]) => v !== null;
    params = Object.fromEntries(Object.entries(params).filter(keep));
    if (multiRole && fn === "top_paying") extra.push(T.MULTI_ROLE_NOTE);
    return {
      function: fn, params, understood: describe(fn, params, amountIsFloat),
      notes: [...notes(question, text, roles, fn), ...extra],
      ...(lastResort ? { last_resort: true } : {}),
    };
  }

  route.fixTypos = fixTypos;
  return route;
}

// Python shows a word in quotes the way repr() does; plain words always get single quotes.
function pyReprShort(text) {
  return text.includes("'") && !text.includes('"') ? `"${text}"` : `'${text.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}
