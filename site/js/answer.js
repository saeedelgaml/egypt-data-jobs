// The one door the page uses (a port of chatbot/ai.py answer_question and chatbot/service.py):
// ask(question) returns the answer text, the numbers behind it, follow-up questions and tips.
// Everything runs in the browser on the rows in jobs.json.
import { createRouter, normalize } from "./router.js";
import { ratio } from "./difflib.js";
import { createDatabase } from "./queries.js";
import { createFormatter } from "./text.js";

const article = (noun) => (/^(ml|a|e|i|o|u)/i.test(noun) ? "an " : "a ") + noun;

export function createChatbot(payload) {
  const cfg = payload.config;
  const db = createDatabase(payload);
  const route = createRouter(cfg, db.skills);
  const toText = createFormatter(cfg.min_group);
  const { plural: PLURAL, examples: EXAMPLES, how_to_ask: HOW_TO_ASK, help: HELP, max_question_chars: MAX } = cfg;

  function answerQuestion(question) {
    const text = typeof question === "string" ? question.trim() : "";
    if (!text) return { text: "Please type a question.", function: null, params: {}, ok: false };
    if (text.length > MAX) {
      return { text: `Please keep the question under ${MAX} characters.`, function: null, params: {}, ok: false };
    }
    const choice = route(text);
    if (choice.function === null) {
      const hint = choice.hint ?? null;
      return { text: (hint ? `${hint}\n\n` : "") + HELP, function: null, params: {}, ok: false,
               data: null, understood: null, notes: [], hint };
    }
    const answer = db.run(choice.function, choice.params);
    let out;
    if (!answer.ok) {
      out = `${answer.message}\n\n${HELP}`;
    } else {
      out = toText(answer);
      if (choice.understood) out = `Understood as: ${choice.understood}\n${out}`;
      for (const note of choice.notes || []) out += `\nNote: ${note}`;
    }
    return { text: out, function: choice.function, params: choice.params, ok: answer.ok,
             data: answer.result ?? null, understood: choice.understood, notes: [...(choice.notes || [])] };
  }

  function followUps(fn, params) {
    const role = params.role;
    const plural = PLURAL[role];
    const { skill, city } = params;
    const out = [];
    if (fn === "salary_for_role") {
      if (plural) out.push(`Which city pays ${plural} the most?`, `What skills do ${plural} need?`, `Who is hiring ${plural}?`);
      else out.push("Which role pays the most?", "Which city pays the most?", "What skills are most in demand?");
    } else if (fn === "top_skills") {
      if (plural) out.push(`What is the salary for ${plural}?`, `Who is hiring ${plural}?`);
      out.push("What skills go with Python?");
    } else if (fn === "skills_with") {
      out.push(`How many postings list ${skill}?`, "Which skill pays the most?", "Which role has the most openings?");
    } else if (fn === "top_companies") {
      out.push(plural ? `What is the salary for ${plural}?` : "Which role pays the most?",
        "Which city has the most postings?", "What skills are most in demand?");
    } else if (fn === "jobs_by_city") {
      out.push("Which city pays the most?", "Which role has the most openings?", "Who is hiring the most?");
    } else if (fn === "jobs_by_role") {
      out.push("Which role pays the most?", "What skills are most in demand?", "Which city has the most postings?");
    } else if (fn === "count_postings") {
      out.push("Which city has the most postings?", "Which role has the most openings?", "Show the newest postings");
    } else if (fn === "top_paying") {
      out.push("What skills are most in demand?", "Who is hiring the most?", "Which city has the most postings?");
    } else if (fn === "new_postings") {
      out.push(plural ? `What is the salary for ${plural}?` : "Which role pays the most?",
        plural ? `What skills do ${plural} need?` : "What skills are most in demand?", "Who is hiring the most?");
    }
    if (city && (fn === "salary_for_role" || fn === "top_skills") && plural) {
      out.unshift(`Show new ${role.replace(/_/g, " ")} jobs in ${city}`);
    }
    const seen = new Set(), unique = [];
    for (const q of out) {
      if (!seen.has(q.toLowerCase())) { seen.add(q.toLowerCase()); unique.push(q); }
    }
    return unique.slice(0, 3);
  }

  function ask(question) {
    const reply = (ok, text, tips = false, extra = {}) => ({
      ok, text, function: null, params: {}, data: null, understood: null, notes: [], follow_ups: [],
      hint: null, did_you_mean: [], tips: tips ? HOW_TO_ASK : [], examples: tips ? EXAMPLES : {}, ...extra,
    });
    if (typeof question !== "string" || !question.trim()) {
      return reply(false, "Type a question, or click one of the examples.", true);
    }
    if (question.length > MAX) return reply(false, `Please keep the question under ${MAX} characters.`, true);
    let result;
    try {
      result = answerQuestion(question);
    } catch (problem) {
      return reply(false, `Something went wrong (${problem?.name || "Error"}). Please try again.`);
    }
    if (!result.ok) return reply(false, result.text, true, { hint: result.hint ?? null, did_you_mean: didYouMean(question) });
    return reply(true, result.text, false, {
      function: result.function, params: result.params, data: result.data, understood: result.understood,
      notes: result.notes, follow_ups: followUps(result.function, result.params),
    });
  }

  const allowedWords = new Set(cfg.router.allowed);

  function pool() {
    const plurals = Object.values(PLURAL);
    const out = [...Object.values(EXAMPLES).flat(), ...HOW_TO_ASK.map((t) => t.example)];
    out.push(...db.skills.map((s) => `What skills go with ${s}?`), ...db.skills.map((s) => `How many postings list ${s}?`));
    out.push(...plurals.map((r) => `What does ${article(r.slice(0, -1))} earn?`));
    out.push(...plurals.map((r) => `Who is hiring ${r}?`), ...plurals.map((r) => `What skills do ${r} need?`));
    for (const r of plurals) for (const c of cfg.cities) out.push(`${r.charAt(0).toUpperCase() + r.slice(1)} jobs in ${c}`);
    out.push(...cfg.generic);
    return [...new Set(out)];
  }

  /** One or two known-good questions that look like a question we could not answer (same rule as service.py). */
  function didYouMean(question, limit = 2, cutoff = 0.5) {
    const text = route.fixTypos(normalize(String(question ?? "")));
    const words = new Set(text.split(" ").filter((w) => w && !allowedWords.has(w)));
    const scored = [];
    for (const q of pool()) {
      const candidate = normalize(q);
      let score = ratio(candidate, text);
      const cwords = new Set(candidate.split(" "));
      const hits = words.size ? [...words].filter((w) => cwords.has(w)).length / words.size : 0;
      score = Math.max(score, hits >= 0.5 ? 0.9 * hits : 0);
      if (score >= cutoff) scored.push([-score, q.length, q]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0));
    return scored.slice(0, limit).map((s) => s[2]);
  }

  function suggest(typed, limit = 6) {
    const words = String(typed || "").toLowerCase().slice(0, 100).split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    const scored = [];
    for (const q of pool()) {
      const low = q.toLowerCase();
      if (words.every((w) => low.includes(w))) scored.push([low.startsWith(words[0]) ? 0 : 1, q.length, q]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0));
    return scored.slice(0, limit).map((s) => s[2]);
  }

  return { ask, suggest, db, route, followUps, answerQuestion };
}
