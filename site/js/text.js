// Turns an answer from queries.js into plain English. A port of chatbot/text.py: the wording is
// fixed, so the same data always gives the same sentence, and every number comes from the data.
import { capitalize, money, roundHalfEven } from "./pyfmt.js";

const label = (role) => (role ? role.replace(/_/g, " ") : "all roles");

function salaryRange(low, high) {
  return low === null ? "salary not listed" : `${money(low)}-${money(high)} EGP/month`;
}

function filters(r) {
  let text = "";
  if (r.city) text += ` in ${r.city}`;
  if (r.skill) text += ` that list ${r.skill}`;
  if (r.min_salary !== undefined && r.min_salary !== null) text += ` paying at least ${money(r.min_salary)} EGP/month`;
  return text;
}

const postings = (r) => (r.role ? `${label(r.role)} postings` : "postings") + filters(r);
const percent = (share) => roundHalfEven(share * 100);

function newPostings(r) {
  if (r.total === 0) return `No new ${postings(r)} in the last ${r.days} days.`;
  let head = `${r.total} new ${postings(r)} in the last ${r.days} days (up to ${r.latest_date})`;
  if (r.total > r.postings.length) head += `, showing ${r.postings.length}`;
  const lines = [`${head}:`];
  for (const p of r.postings) {
    lines.push(`- ${p.title} at ${p.company || "company not listed"}, ${p.city || "city not listed"}, ` +
      `${salaryRange(p.salary_min, p.salary_max)} (posted ${p.posted_date})`);
  }
  return lines.join("\n");
}

function salary(r) {
  const where = label(r.role) + filters(r);
  if (r.postings === 0) return `No ${postings(r)} found.`;
  if (r.with_salary === 0) return `No salary data for ${where}: none of the ${r.postings} postings list a salary.`;
  return `${where}: typical ${money(r.typical)} EGP/month (median of the range midpoints), ` +
    `lowest listed ${money(r.lowest)}, highest listed ${money(r.highest)}. ` +
    `Based on ${r.with_salary} of ${r.postings} postings that list a salary.`;
}

function skills(r) {
  const where = label(r.role) + filters(r);
  if (!r.skills.length) return `No skills listed for ${postings(r)}.`;
  const lines = [`Top skills for ${where} (share of the ${r.postings_with_skills} postings that list skills):`];
  for (const s of r.skills) lines.push(`- ${s.skill}: ${percent(s.share)}% (${s.postings} postings)`);
  return lines.join("\n");
}

function skillsWith(r) {
  const scope = (r.role ? `${label(r.role)} postings` : "postings") + filters(r);
  if (r.postings_with_skill === 0) return `No ${scope} list ${r.skill}.`;
  if (!r.skills.length) return `The ${r.postings_with_skill} ${scope} that list ${r.skill} name no other skills.`;
  const lines = [`Skills that appear with ${r.skill} in ${scope} ` +
    `(share of the ${r.postings_with_skill} postings that list ${r.skill}):`];
  for (const s of r.skills) lines.push(`- ${s.skill}: ${percent(s.share)}% (${s.postings} postings)`);
  return lines.join("\n");
}

function companies(r) {
  if (!r.companies.length) return `No companies found for ${postings(r)}.`;
  return [`Companies with the most ${postings(r)}:`, ...r.companies.map((c) => `- ${c.company}: ${c.postings}`)].join("\n");
}

function cities(r) {
  if (!r.cities.length) return `No postings found for ${postings(r)}.`;
  const noun = r.role ? `${capitalize(label(r.role))} postings` : "Postings";
  const lines = [`${noun}${filters(r)} by city:`, ...r.cities.map((c) => `- ${c.city}: ${c.postings}`)];
  if (r.no_city) lines.push(`- city not listed: ${r.no_city}`);
  return lines.join("\n");
}

function roles(r) {
  if (!r.roles.length) return `No postings found${filters(r)}.`;
  return [`Postings by role${filters(r)}:`, ...r.roles.map((x) => `- ${label(x.role)}: ${x.postings}`)].join("\n");
}

const countText = (r) => `${r.total} postings for ${label(r.role) + filters(r)}.`;

export function createFormatter(minGroup) {
  function paying(r) {
    const word = r.order === "highest" ? "Highest" : "Lowest";
    const scope = label(r.role) + filters(r);
    if (!r.groups.length) {
      return `Not enough salary data to rank by ${r.group_by} for ${scope}: ` +
        `each ${r.group_by} needs at least ${minGroup} postings that list a salary.`;
    }
    const lines = [`${word} typical monthly salary by ${r.group_by} for ${scope} ` +
      `(median of the range midpoints, at least ${minGroup} listed salaries each):`];
    for (const g of r.groups) {
      const name = r.group_by === "role" ? g.group.replace(/_/g, " ") : g.group;
      lines.push(`- ${name}: ${money(g.typical)} EGP/month (${g.with_salary} postings with a salary)`);
    }
    return lines.join("\n");
  }

  const formatters = {
    new_postings: newPostings, salary_for_role: salary, top_skills: skills, skills_with: skillsWith,
    top_companies: companies, jobs_by_city: cities, jobs_by_role: roles, count_postings: countText,
    top_paying: paying,
  };

  return function toText(answer) {
    return answer.ok ? formatters[answer.function](answer.result) : answer.message;
  };
}
