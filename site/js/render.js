// Builds the page's elements. Every piece of text goes in as a text node (never as HTML), so
// nothing from a question or from the data can inject markup.
import { money } from "./pyfmt.js";

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name === "class") el.className = value;
    else if (name.startsWith("on")) el.addEventListener(name.slice(2), value);
    else if (name.startsWith("--")) el.style.setProperty(name, value);
    else el.setAttribute(name, value === true ? "" : String(value));
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}

export function chips(questions, onAsk, extraClass = "") {
  return h("div", { class: `chips ${extraClass}`.trim() },
    questions.map((q) => h("button", { class: "chip", type: "button", onclick: () => onAsk(q) }, q)));
}

function bars(rows, unit) {
  const top = Math.max(...rows.map((r) => r.value), 1);
  return h("ul", { class: "bars" }, rows.map((r) => h("li", {},
    h("span", { class: "name" }, r.name),
    h("span", { class: "track", "aria-hidden": "true" }, h("span", { class: "fill", "--w": `${Math.max(2, (100 * r.value) / top)}%` })),
    h("span", { class: "val" }, r.text ?? `${money(r.value)}${unit ? ` ${unit}` : ""}`))));
}

function bodyLines(reply) {
  return reply.text.split("\n").filter((l) => !l.startsWith("Understood as:") && !l.startsWith("Note: "));
}

function visual(reply, label) {
  const d = reply.data;
  switch (reply.function) {
    case "salary_for_role": {
      if (!d.postings || !d.with_salary) return null;
      const span = Math.max(1, d.highest - d.lowest);
      return h("div", {},
        h("div", { class: "big" }, money(d.typical), h("small", {}, "EGP / month, typical")),
        h("div", { class: "range", role: "img", "aria-label": `Listed salaries run from ${money(d.lowest)} to ${money(d.highest)} EGP` },
          h("i", { style: `left:${Math.min(96, Math.max(0, (100 * (d.typical - d.lowest)) / span - 2))}%;width:4%;background:var(--ink)` }),
          h("i", { style: "left:0;right:0;opacity:.35" })),
        h("div", { class: "range-labels" }, h("span", {}, `lowest ${money(d.lowest)}`), h("span", {}, `highest ${money(d.highest)}`)),
        h("p", { class: "muted" }, `Based on ${d.with_salary} of ${d.postings} postings that list a salary.`));
    }
    case "count_postings":
      return h("div", { class: "big" }, money(d.total), h("small", {}, d.total === 1 ? "posting" : "postings"));
    case "top_skills": case "skills_with":
      return d.skills.length ? bars(d.skills.map((s) => ({ name: s.skill, value: s.share * 100, text: `${Math.round(s.share * 100)}% · ${s.postings}` }))) : null;
    case "top_companies":
      return d.companies.length ? bars(d.companies.map((c) => ({ name: c.company, value: c.postings, text: String(c.postings) }))) : null;
    case "jobs_by_city":
      return d.cities.length ? bars(d.cities.map((c) => ({ name: c.city, value: c.postings, text: String(c.postings) }))) : null;
    case "jobs_by_role":
      return d.roles.length ? bars(d.roles.map((r) => ({ name: label(r.role), value: r.postings, text: String(r.postings) }))) : null;
    case "top_paying":
      return d.groups.length ? bars(d.groups.map((g) => ({
        name: d.group_by === "role" ? label(g.group) : g.group, value: g.typical, text: `${money(g.typical)} EGP`,
      }))) : null;
    case "new_postings":
      return d.postings.length ? h("ul", { class: "postings" }, d.postings.map((p) => h("li", {},
        h("div", { class: "t" }, p.title),
        h("div", { class: "m" }, [p.company || "company not listed", p.city || "city not listed",
          p.salary_min === null ? "salary not listed" : `${money(p.salary_min)}–${money(p.salary_max)} EGP/month`,
          `posted ${p.posted_date}`].join(" · ")))) ) : null;
    default:
      return null;
  }
}

export function answerView(reply, { label, onAsk }) {
  const lines = bodyLines(reply);
  const card = h("article", { class: "card", "aria-label": "Answer" });
  if (reply.understood) {
    card.append(h("p", { class: "read-as" }, "Read as ", h("b", {}, reply.understood)));
  }
  const picture = visual(reply, label);
  if (picture) card.append(picture);
  else card.append(...lines.map((l) => h("p", {}, l)));
  if (reply.notes.length) card.append(h("ul", { class: "notes" }, reply.notes.map((n) => h("li", {}, `Note: ${n}`))));
  if (reply.follow_ups.length) {
    card.append(h("div", { class: "next" }, h("p", { class: "group-label" }, "Ask next"), chips(reply.follow_ups, onAsk)));
  }
  card.append(h("details", {}, h("summary", {}, "Answer as plain text"), h("pre", { class: "plain" }, reply.text)));
  return card;
}

export function refusalView(reply, { asked, near, onAsk }) {
  const card = h("article", { class: "card refuse", "aria-label": "No answer" });
  if (!asked.trim()) {
    card.append(h("p", {}, reply.text));
  } else {
    card.append(h("h2", {}, "That one I can’t answer"));
    card.append(h("p", {}, reply.hint || reply.text.split("\n\n")[0]));
  }
  if (near.length) card.append(h("p", { class: "group-label" }, "Did you mean"), chips(near, onAsk));
  if (reply.tips.length && asked.trim()) {
    card.append(h("p", { class: "group-label" }, "What works"),
      h("ul", { class: "tip-list" }, reply.tips.map((t) => h("li", {}, h("b", {}, `${t.title}. `), t.tip))));
  }
  const tryThese = Object.values(reply.examples).map((group) => group[0]).filter(Boolean);
  if (tryThese.length) card.append(h("p", { class: "group-label" }, "Try one of these"), chips(tryThese, onAsk));
  return card;
}

export function errorView(message, onRetry) {
  return h("article", { class: "card error", role: "alert" },
    h("h2", {}, "The data did not load"),
    h("p", {}, message),
    h("button", { class: "btn-ghost", type: "button", onclick: onRetry }, "Try again"));
}

export function loadingView() {
  return h("div", { class: "card", "aria-busy": "true", "aria-label": "Loading the data" },
    h("div", { class: "skeleton", style: "width:60%" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton", style: "width:80%" }));
}

export function kpiView(kpis) {
  return kpis.map((k) => h("div", { class: "kpi" }, h("b", {}, k.value), h("span", {}, k.label)));
}

export function chartCard(chart) {
  const rows = chart.labels.map((name, i) => h("tr", {},
    h("td", {}, name), h("td", {}, `${money(chart.values[i])}${chart.extra ? ` (${chart.extra[i]})` : ""}`)));
  const height = Math.max(200, 34 * chart.labels.length + 40);
  const canvas = h("canvas", { id: `chart-${chart.id}`, role: "img",
    "aria-label": `${chart.title}: highest is ${chart.labels[0]} with ${money(chart.values[0] ?? 0)} ${chart.unit}. A table follows.` });
  return h("section", { class: "chart-card", "aria-labelledby": `h-${chart.id}` },
    h("h3", { id: `h-${chart.id}` }, chart.title), h("p", {}, chart.sub),
    h("div", { class: "chart-box", "--h": `${height}px` }, canvas),
    h("details", {}, h("summary", {}, "View as table"),
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, h("th", {}, chart.title), h("th", {}, chart.unit))), h("tbody", {}, rows))));
}

export function tipCard(tip, onAsk) {
  return h("div", { class: "tip" }, h("h3", {}, tip.title), h("p", {}, tip.tip),
    h("button", { class: "chip", type: "button", onclick: () => onAsk(tip.example) }, tip.example));
}
