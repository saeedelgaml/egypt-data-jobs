// The page: loads jobs.json, builds the chatbot and wires up the search box, answers, insights and theme.
// Nothing is sent anywhere: the chatbot runs on the rows in the JSON file (see answer.js).
import { createChatbot } from "./answer.js";
import { buildInsights, formatDate, roleLabels } from "./insights.js";
import { answerView, chartCard, chips, errorView, h, kpiView, loadingView, refusalView, tipCard } from "./render.js";

const $ = (id) => document.getElementById(id);
const DATA_URL = "data/jobs.json";
let chatbot = null;
let payload = null;
let charts = [];
let insights = null;

// ---- theme (remembered in this browser only; the page works without storage) -----------
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("theme", theme); } catch { /* private mode: fine */ }
  drawCharts();
}
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch { /* ignore */ }
  if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
  $("theme").addEventListener("click", () => {
    const shown = document.documentElement.dataset.theme
      || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    applyTheme(shown === "dark" ? "light" : "dark");
  });
}

// ---- asking -----------------------------------------------------------------------------
function ask(question) {
  $("q").value = question;
  const reply = chatbot.ask(question);
  const label = roleLabels(payload);
  const out = $("answer");
  out.replaceChildren();
  if (reply.ok) {
    out.append(answerView(reply, { label, onAsk: ask }));
    $("status").textContent = `Answer: ${reply.understood || "done"}`;
  } else {
    const near = question.trim() ? (reply.did_you_mean.length ? reply.did_you_mean : chatbot.suggest(question)) : [];
    out.append(refusalView(reply, { asked: question, near, onAsk: ask }));
    $("status").textContent = "No answer for that question. Suggestions are shown.";
  }
  $("suggest").replaceChildren();
  out.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
}

function initSearch() {
  const input = $("q");
  $("ask").addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
  input.addEventListener("input", () => {
    const typed = input.value.trim();
    $("suggest").replaceChildren(...(typed.length >= 2 ? [chips(chatbot.suggest(typed, 4), ask)] : []));
  });
}

// ---- insights ----------------------------------------------------------------------------
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function drawCharts() {
  charts.forEach((c) => c.destroy());
  charts = [];
  if (!insights || typeof window.Chart === "undefined") return; // the tables below each chart still work
  const colors = ["--brand", "--pink", "--teal", "--amber"].map(cssVar);
  insights.charts.forEach((chart, i) => {
    const canvas = $(`chart-${chart.id}`);
    if (!canvas) return;
    charts.push(new window.Chart(canvas, {
      type: "bar",
      data: { labels: chart.labels, datasets: [{ data: chart.values, backgroundColor: colors[i % colors.length], borderRadius: 8, maxBarThickness: 22 }] },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => ` ${c.parsed.x.toLocaleString("en-US")} ${chart.unit}` } } },
        scales: {
          x: { beginAtZero: true, grid: { color: cssVar("--line") }, ticks: { color: cssVar("--muted") } },
          y: { grid: { display: false }, ticks: { color: cssVar("--ink") } },
        },
      },
    }));
  });
}

function renderInsights() {
  insights = buildInsights(payload, chatbot.db);
  $("kpis").replaceChildren(...kpiView(insights.kpis));
  $("charts").replaceChildren(...insights.charts.map(chartCard));
  $("insights").hidden = false;
  drawCharts();
  window.addEventListener("load", drawCharts, { once: true }); // Chart.js may finish loading after this runs
}

// ---- start -------------------------------------------------------------------------------
function renderStatic() {
  const examples = $("examples");
  examples.replaceChildren(...Object.entries(payload.config.examples).map(([group, questions]) =>
    h("div", {}, h("p", { class: "group-label" }, group), chips(questions, ask))));
  $("tips").replaceChildren(...payload.config.how_to_ask.map((tip) => tipCard(tip, ask)));
  $("updated").replaceChildren(h("strong", {}, "Data last updated: "), h("span", {}, formatDate(payload.meta.data_last_updated)),
    h("span", { class: "muted" }, ` · ${payload.meta.postings.toLocaleString("en-US")} synthetic postings`));
  const all = Object.values(payload.config.examples).flat();
  $("q").placeholder = all[Math.floor(Math.random() * all.length)];
}

async function load() {
  $("answer").replaceChildren(loadingView());
  try {
    const response = await fetch(DATA_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`The data file answered with status ${response.status}.`);
    payload = await response.json();
    chatbot = createChatbot(payload);
  } catch (problem) {
    const old = /lookbehind|Invalid regular expression|Invalid regex/i.test(String(problem));
    $("answer").replaceChildren(errorView(old ? "This browser is too old to run the chatbot. Please update it." : String(problem.message || problem), load));
    $("updated").replaceChildren(h("strong", {}, "Data last updated: "), h("span", {}, "unavailable"));
    return;
  }
  $("answer").replaceChildren();
  renderStatic();
  initSearch();
  renderInsights();
}

initTheme();
load();
