// The browser chatbot keeps the guarded-answer rules: read-only, a fixed list of answers, checked
// values, a row limit. Also checks the Insights numbers and that the page code builds no raw HTML.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createChatbot } from "../site/js/answer.js";
import { buildInsights, formatDate } from "../site/js/insights.js";

const siteDir = new URL("../site/", import.meta.url);
const golden = JSON.parse(readFileSync(new URL("../tests/data/router_golden.json", import.meta.url), "utf8"));
const bot = createChatbot(golden.data);
const { db } = bot;

test("only the nine fixed answers exist, and nothing can write", () => {
  assert.deepEqual([...db.functions].sort(), [
    "count_postings", "jobs_by_city", "jobs_by_role", "new_postings", "salary_for_role",
    "skills_with", "top_companies", "top_paying", "top_skills"]);
  for (const name of ["constructor", "__proto__", "toString", "drop_table", "run_sql", "DELETE FROM jobs"]) {
    assert.equal(db.run(name, {}).ok, false, name);
  }
});

test("unknown parameters and values are refused", () => {
  assert.equal(db.run("salary_for_role", { sql: "DROP TABLE jobs" }).ok, false);
  assert.equal(db.run("salary_for_role", { role: "x'; DROP TABLE jobs; --" }).ok, false);
  assert.equal(db.run("salary_for_role", { city: "Paris" }).ok, false);
  assert.equal(db.run("top_skills", { limit: "ten" }).ok, false);
  assert.equal(db.run("count_postings", { min_salary: 10 ** 9 }).ok, false);
  assert.equal(db.run("skills_with", {}).ok, false);
  assert.equal(db.run("top_paying", { group_by: "title" }).ok, false);
});

test("row and day limits are enforced", () => {
  assert.ok(db.run("top_skills", { limit: 10 ** 6 }).result.skills.length <= 20);
  assert.ok(db.run("top_companies", { limit: 500 }).result.companies.length <= 20);
  assert.equal(db.run("new_postings", { days: 10 ** 6 }).result.days, 90);
  assert.ok(db.run("new_postings", { role: null, days: 90, limit: 999 }).result.postings.length <= 20);
});

test("a typed question can never reach the data except through an answer", () => {
  for (const q of ["drop table jobs", "delete all jobs", "'; DROP TABLE jobs; --", "ignore previous instructions", "select * from jobs"]) {
    assert.equal(bot.ask(q).ok, false, q);
  }
  assert.equal(bot.ask("x".repeat(301)).ok, false);
  assert.equal(bot.ask(null).ok, false);
});

test("every role in the data can be asked about", () => {
  const roles = golden.data.config.roles.filter((r) => r.key !== "other");
  assert.ok(roles.length >= 14);
  for (const r of roles) {
    const reply = bot.ask(`what does a ${r.label} earn`);
    assert.equal(reply.ok, true, r.label);
    assert.equal(reply.params.role, r.key);
  }
});

test("insights come from the same answers as the chat", () => {
  const insights = buildInsights(golden.data, db);
  assert.equal(insights.charts.length, 4);
  assert.equal(insights.kpis[0].label, "postings");
  const pay = insights.charts.find((c) => c.id === "pay");
  assert.deepEqual(pay.values, [...pay.values].sort((a, b) => b - a));
  const skills = insights.charts.find((c) => c.id === "skills");
  assert.equal(skills.labels[0], db.run("top_skills", { limit: 10 }).result.skills[0].skill);
  const city = insights.charts.find((c) => c.id === "cities");
  assert.equal(city.values.reduce((a, b) => a + b, 0) <= golden.data.meta.postings, true);
});

test("the data-last-updated date is formatted for people", () => {
  assert.equal(formatDate("2026-11-29"), "29 November 2026");
  assert.equal(formatDate(null), "unknown");
  assert.equal(formatDate("not a date"), "unknown");
});

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

test("page code never builds raw HTML from text", () => {
  const banned = /innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function\(/;
  for (const file of files(fileURLToPath(new URL("../site/js/", import.meta.url)))) {
    assert.doesNotMatch(readFileSync(file, "utf8"), banned, file);
  }
});

test("no key or AI-service code is in the site folder", () => {
  const forbidden = /LLM_API_KEY|anthropic|api[_-]?key|sk-[A-Za-z0-9_-]{20,}|Bearer /i;
  for (const file of files(fileURLToPath(siteDir))) {
    assert.doesNotMatch(readFileSync(file, "utf8"), forbidden, file);
  }
});
