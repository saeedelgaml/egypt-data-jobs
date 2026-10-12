// The numbers behind the Insights section. They come from the same nine answers the chatbot uses,
// so the charts and the chat can never disagree. No DOM here, so it is easy to test.
import { money } from "./pyfmt.js";

export function roleLabels(payload) {
  const labels = Object.fromEntries(payload.config.roles.map((r) => [r.key, r.label]));
  const pretty = (key) => {
    const label = labels[key] ?? String(key).replace(/_/g, " ");
    return key === "other" ? "Other roles" : label.charAt(0).toUpperCase() + label.slice(1);
  };
  return pretty;
}

export function formatDate(iso) {
  if (!iso) return "unknown";
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return "unknown";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

export function buildInsights(payload, db) {
  const label = roleLabels(payload);
  const result = (name, params) => {
    const answer = db.run(name, params);
    if (!answer.ok) throw new Error(answer.message);
    return answer.result;
  };
  const roles = result("jobs_by_role", {}).roles.slice(0, 8);
  const skills = result("top_skills", { limit: 10 });
  const cities = result("jobs_by_city", {}).cities;
  const pay = result("top_paying", { group_by: "role", limit: 15 }).groups;
  const meta = payload.meta;
  const rolesPresent = new Set(db.jobs.map((j) => j.role)).size;

  return {
    kpis: [
      { value: money(meta.postings), label: "postings" },
      { value: `${Math.round((100 * meta.with_salary) / Math.max(1, meta.postings))}%`, label: "list a salary" },
      { value: String(rolesPresent), label: "roles" },
      { value: String(db.skills.length), label: "skills tracked" },
    ],
    charts: [
      {
        id: "roles", title: "Top roles", sub: "Number of postings per role",
        labels: roles.map((r) => label(r.role)), values: roles.map((r) => r.postings), unit: "postings",
      },
      {
        id: "skills", title: "Top skills", sub: "Postings that list each skill",
        labels: skills.skills.map((s) => s.skill), values: skills.skills.map((s) => s.postings), unit: "postings",
        extra: skills.skills.map((s) => `${Math.round(s.share * 100)}% of postings with skills`),
      },
      {
        id: "cities", title: "Jobs by city", sub: "Number of postings per city",
        labels: cities.map((c) => c.city), values: cities.map((c) => c.postings), unit: "postings",
      },
      {
        id: "pay", title: "Salary by role", sub: "Typical monthly salary in EGP (median of the listed ranges)",
        labels: pay.map((g) => label(g.group)), values: pay.map((g) => g.typical), unit: "EGP/month",
        extra: pay.map((g) => `${g.with_salary} postings with a salary`),
      },
    ],
  };
}
