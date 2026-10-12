// The nine fixed answers, run on the rows in jobs.json. This is a port of chatbot/queries.py.
//
// Safety rules, the same as the Python version:
//  - the data is read-only: nothing here writes to it, and no free-form SQL exists at all;
//  - only the nine functions in FUNCTIONS can be called, with only the parameters listed in SIGNATURES;
//  - role, city and skill are checked against the known values, numbers are clamped
//    (at most MAX_LIMIT rows, at most MAX_DAYS days, a minimum salary up to MAX_SALARY).
import { pyRepr, round2, roundHalfEven } from "./pyfmt.js";

export class BadQuestion extends Error {}

// name -> [parameters it accepts, parameters it requires]
const SIGNATURES = {
  new_postings: [["role", "city", "skill", "days", "limit"], []],
  salary_for_role: [["role", "city", "skill"], []],
  top_skills: [["role", "city", "limit"], []],
  skills_with: [["skill", "role", "city", "limit"], ["skill"]],
  top_companies: [["role", "city", "skill", "limit"], []],
  jobs_by_city: [["role", "skill"], []],
  jobs_by_role: [["city", "skill"], []],
  count_postings: [["role", "city", "skill", "min_salary"], []],
  top_paying: [["group_by", "role", "city", "skill", "order", "limit"], []],
};

const mid = (job) => (job.salary_min + job.salary_max) / 2.0;
const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const half = sorted.length >> 1;
  return sorted.length % 2 ? sorted[half] : (sorted[half - 1] + sorted[half]) / 2;
}

function minusDays(isoDate, days) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

export function createDatabase(payload) {
  const cfg = payload.config;
  const jobs = payload.jobs.map((row) => Object.fromEntries(payload.columns.map((c, i) => [c, row[i]])));
  const skills = [...payload.skills];
  const roleKeys = cfg.roles.map((r) => r.key);
  const cities = [...new Set(jobs.map((j) => j.city).filter((c) => c !== null))].sort(byText);
  const { max_limit: MAX_LIMIT, max_days: MAX_DAYS, max_salary: MAX_SALARY, min_group: MIN_GROUP } = cfg;

  // ---- checks on values that come from a visitor --------------------------------------
  function checkRole(role) {
    if (role === null || role === undefined) return null;
    const cleaned = String(role).trim().toLowerCase().replace(/ /g, "_").replace(/-/g, "_");
    if (!roleKeys.includes(cleaned)) {
      throw new BadQuestion(`I do not know the role ${pyRepr(role)}. Roles: ${roleKeys.join(", ")}`);
    }
    return cleaned;
  }

  function checkCity(city) {
    if (city === null || city === undefined) return null;
    const found = cities.find((name) => name.toLowerCase() === String(city).trim().toLowerCase());
    if (found) return found;
    throw new BadQuestion(`I have no postings in ${pyRepr(city)}. Cities: ${cities.join(", ") || "none yet"}`);
  }

  function checkSkill(skill, required = false) {
    if (skill === null || skill === undefined) {
      if (required) throw new BadQuestion("This answer needs a skill, such as Python or SQL.");
      return null;
    }
    const found = skills.find((name) => name.toLowerCase() === String(skill).trim().toLowerCase());
    if (found) return found;
    throw new BadQuestion(`I have no postings that list ${pyRepr(skill)}. Skills: ${skills.join(", ") || "none yet"}`);
  }

  function checkInt(value, name, low, high) {
    const number = typeof value === "number" ? Math.trunc(value) : Number.parseInt(value, 10);
    if (!Number.isFinite(number) || (typeof value === "string" && !/^\s*[+-]?\d+\s*$/.test(value))) {
      throw new BadQuestion(`${name} must be a whole number.`);
    }
    return Math.max(low, Math.min(high, number));
  }

  function checkAmount(value) {
    if (value === null || value === undefined) return null;
    const amount = Number(value);
    if (typeof value === "boolean" || Number.isNaN(amount)) throw new BadQuestion("min_salary must be a number.");
    if (!(amount >= 0 && amount <= MAX_SALARY)) {
      throw new BadQuestion(`min_salary must be between 0 and ${MAX_SALARY.toLocaleString("en-US")}.`);
    }
    return amount;
  }

  function scope({ role = null, city = null, skill = null, minSalary = null } = {}) {
    return jobs.filter((j) =>
      (role === null || j.role === role) &&
      (city === null || j.city === city) &&
      (skill === null || j.skills.includes(skill)) &&
      (minSalary === null || (j.salary_min !== null && mid(j) >= minSalary)));
  }

  const ranked = (counts, limit) =>
    [...counts.entries()].sort((a, b) => b[1] - a[1] || byText(a[0], b[0])).slice(0, limit);

  function count(map, key) { map.set(key, (map.get(key) || 0) + 1); }

  // ---- the nine answers ---------------------------------------------------------------
  const FUNCTIONS = {
    new_postings(p) {
      const role = checkRole("role" in p ? p.role : "data_engineer");
      const city = checkCity(p.city);
      const skill = checkSkill(p.skill);
      const days = checkInt("days" in p ? p.days : 7, "days", 1, MAX_DAYS);
      const limit = checkInt("limit" in p ? p.limit : 10, "limit", 1, MAX_LIMIT);
      const latest = jobs.reduce((m, j) => (m === null || j.first_seen_date > m ? j.first_seen_date : m), null);
      let rows = [];
      if (latest !== null) {
        const since = minusDays(latest, days);
        rows = scope({ role, city, skill }).filter((j) => j.first_seen_date > since).sort((a, b) =>
          byText(b.first_seen_date, a.first_seen_date) || byText(b.posted_date, a.posted_date) ||
          byText(a.job_id, b.job_id));
      }
      const keep = ["job_id", "title", "company", "city", "salary_min", "salary_max", "posted_date", "first_seen_date"];
      return {
        role, city, skill, days, latest_date: latest, total: rows.length,
        postings: rows.slice(0, limit).map((j) => Object.fromEntries(keep.map((k) => [k, j[k]]))),
      };
    },

    salary_for_role(p) {
      const role = checkRole(p.role), city = checkCity(p.city), skill = checkSkill(p.skill);
      const rows = scope({ role, city, skill });
      const priced = rows.filter((j) => j.salary_min !== null);
      const typical = median(priced.map(mid));
      return {
        role, city, skill, postings: rows.length, with_salary: priced.length,
        typical: typical === null ? null : roundHalfEven(typical),
        lowest: priced.length ? Math.min(...priced.map((j) => j.salary_min)) : null,
        highest: priced.length ? Math.max(...priced.map((j) => j.salary_max)) : null,
      };
    },

    top_skills(p) {
      const role = checkRole(p.role), city = checkCity(p.city);
      const limit = checkInt("limit" in p ? p.limit : 5, "limit", 1, MAX_LIMIT);
      const rows = scope({ role, city }).filter((j) => j.skills.length);
      const counts = new Map();
      rows.forEach((j) => j.skills.forEach((s) => count(counts, s)));
      return {
        role, city, postings_with_skills: rows.length,
        skills: ranked(counts, limit).map(([skill, n]) => ({ skill, postings: n, share: round2(n / rows.length) })),
      };
    },

    skills_with(p) {
      const skill = checkSkill(p.skill, true);
      const role = checkRole(p.role), city = checkCity(p.city);
      const limit = checkInt("limit" in p ? p.limit : 5, "limit", 1, MAX_LIMIT);
      const rows = scope({ role, city, skill });
      const counts = new Map();
      rows.forEach((j) => j.skills.forEach((s) => { if (s !== skill) count(counts, s); }));
      return {
        skill, role, city, postings_with_skill: rows.length,
        skills: ranked(counts, limit).map(([name, n]) => ({ skill: name, postings: n, share: round2(n / rows.length) })),
      };
    },

    top_companies(p) {
      const role = checkRole(p.role), city = checkCity(p.city), skill = checkSkill(p.skill);
      const limit = checkInt("limit" in p ? p.limit : 5, "limit", 1, MAX_LIMIT);
      const counts = new Map();
      scope({ role, city, skill }).forEach((j) => { if (j.company !== null) count(counts, j.company); });
      return { role, city, skill, companies: ranked(counts, limit).map(([company, n]) => ({ company, postings: n })) };
    },

    jobs_by_city(p) {
      const role = checkRole(p.role), skill = checkSkill(p.skill);
      const rows = scope({ role, skill });
      const counts = new Map();
      rows.forEach((j) => { if (j.city !== null) count(counts, j.city); });
      return {
        role, skill, cities: ranked(counts, Infinity).map(([city, n]) => ({ city, postings: n })),
        no_city: rows.filter((j) => j.city === null).length,
      };
    },

    jobs_by_role(p) {
      const city = checkCity(p.city), skill = checkSkill(p.skill);
      const counts = new Map();
      scope({ city, skill }).forEach((j) => { if (j.role !== null) count(counts, j.role); });
      return { city, skill, roles: ranked(counts, Infinity).map(([role, n]) => ({ role, postings: n })) };
    },

    count_postings(p) {
      const role = checkRole(p.role), city = checkCity(p.city), skill = checkSkill(p.skill);
      const minSalary = checkAmount(p.min_salary);
      return { role, city, skill, min_salary: minSalary, total: scope({ role, city, skill, minSalary }).length };
    },

    top_paying(p) {
      const groupBy = "group_by" in p ? p.group_by : "role";
      const order = "order" in p ? p.order : "highest";
      if (!["role", "city", "company", "skill"].includes(groupBy)) {
        throw new BadQuestion("I can rank by: role, city, company, skill.");
      }
      if (!["highest", "lowest"].includes(order)) throw new BadQuestion("order must be highest or lowest.");
      const role = checkRole(p.role), city = checkCity(p.city), skill = checkSkill(p.skill);
      const limit = checkInt("limit" in p ? p.limit : 5, "limit", 1, MAX_LIMIT);
      const groups = new Map();
      for (const j of scope({ role, city, skill })) {
        if (j.salary_min === null) continue;
        const keys = groupBy === "skill" ? j.skills : [j[groupBy]];
        for (const key of keys) {
          if (key === null || key === undefined) continue;
          if (!groups.has(key)) groups.set(key, []);
          groups.get(key).push(mid(j));
        }
      }
      const rows = [...groups.entries()].filter(([, v]) => v.length >= MIN_GROUP)
        .map(([group, v]) => ({ group, typical: median(v), n: v.length }));
      const sign = order === "highest" ? -1 : 1;
      rows.sort((a, b) => sign * (a.typical - b.typical) || byText(a.group, b.group));
      return {
        group_by: groupBy, order, role, city, skill,
        groups: rows.slice(0, limit).map((r) => ({ group: r.group, typical: roundHalfEven(r.typical), with_salary: r.n })),
      };
    },
  };

  /** Call one answer by name. Never throws: a problem comes back as {ok: false, message}. */
  function run(name, params = {}) {
    if (!Object.hasOwn(FUNCTIONS, name)) {
      return { ok: false, message: `I have no answer called ${pyRepr(name)}. I can answer: ${Object.keys(FUNCTIONS).join(", ")}` };
    }
    const [allowed, required] = SIGNATURES[name];
    const given = { ...params };
    const unknown = Object.keys(given).filter((k) => !allowed.includes(k)).sort();
    if (unknown.length) {
      return { ok: false, message: `${name} does not take ${unknown.join(", ")}. It takes: ${allowed.join(", ")}` };
    }
    const missing = required.filter((k) => !(k in given));
    if (missing.length) return { ok: false, message: `${name} needs: ${missing.join(", ")}` };
    try {
      return { ok: true, function: name, params: given, result: FUNCTIONS[name](given) };
    } catch (problem) {
      if (problem instanceof BadQuestion) return { ok: false, message: problem.message };
      throw problem;
    }
  }

  return { run, skills, cities, jobs, functions: Object.keys(FUNCTIONS) };
}
