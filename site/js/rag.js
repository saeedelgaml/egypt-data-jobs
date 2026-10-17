// The "Reports" page: search-only. The question is embedded in the browser with the same model as the
// Python index (all-MiniLM-L6-v2, mean pooling, normalised vectors) and compared with the exported vectors.
// Nothing you type is sent anywhere; the only downloads are the library and the model (once, then cached).
import { NOT_COVERED, pagesText, search, THRESHOLD } from "./ragsearch.js";
import { h } from "./render.js";

const LIBRARY = "https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2/dist/transformers.min.js";
const MODEL = "Xenova/all-MiniLM-L6-v2";
const $ = (id) => document.getElementById(id);
let index = null;
let extractor = null;

const EXAMPLES = [
  "How many jobs will be created and displaced by 2030?",
  "What degree do Egyptian job ads ask for?",
  "What is youth unemployment in Egypt?",
  "Why can't young Egyptians get formal jobs?",
  "How concentrated are job ads in Cairo and Giza?",
];

function setStatus(text, busy = false) {
  const el = $("model-status");
  el.textContent = text;
  el.hidden = !text;
  el.setAttribute("aria-busy", String(busy));
}

async function loadModel() {
  setStatus("Loading the search model (a one-time download of about 25 MB, then it is cached in your browser)...", true);
  const { pipeline, env } = await import(LIBRARY);
  env.allowLocalModels = false;
  const files = new Map();
  extractor = await pipeline("feature-extraction", MODEL, {
    quantized: true,
    progress_callback: (p) => {
      if (p.status === "progress" && p.file) {
        files.set(p.file, p.progress);
        const mean = [...files.values()].reduce((a, b) => a + b, 0) / files.size;
        setStatus(`Loading the search model, one-time download: ${Math.round(mean)}%`, true);
      }
    },
  });
  extractor.tokenizer.model_max_length = index.max_seq_length; // the same limit as the Python index
  setStatus("");
}

async function embed(text) {
  const out = await extractor(text, { pooling: "mean", normalize: true });
  return Array.from(out.data);
}

function passage(hit) {
  const c = hit.chunk;
  const title = c.url ? h("a", { href: c.url, rel: "noopener" }, c.title) : c.title;
  return h("li", { class: "passage" },
    h("div", { class: "t" }, title),
    h("div", { class: "m" }, `${c.short} · ${c.year} · ${pagesText(c)}${c.url ? "" : " · no link recorded"} · similarity ${hit.score.toFixed(2)}`),
    h("p", {}, `“${c.snippet}”`));
}

function show(result, question) {
  const out = $("answer");
  out.replaceChildren();
  if (!result.covered) {
    out.append(h("article", { class: "card refuse" }, h("h2", {}, NOT_COVERED),
      h("p", { class: "muted" }, "Try a question about jobs, skills or education in Egypt, or the future of work."),
      h("div", { class: "chips" }, EXAMPLES.map((q) => h("button", { class: "chip", type: "button", onclick: () => ask(q) }, q)))));
    $("status").textContent = "The documents don't cover that.";
    return;
  }
  out.append(h("article", { class: "card" },
    h("p", { class: "read-as" }, "From the reports ", h("b", {}, "top 3 passages")),
    h("ol", { class: "passages" }, result.hits.map(passage)),
    h("p", { class: "muted" }, "Search-only demo. The full cited-answer version runs locally.")));
  $("status").textContent = `${result.hits.length} passages found for: ${question}`;
}

export async function ask(question) {
  $("q").value = question;
  if (!question.trim() || !extractor) return null;
  const result = search(await embed(question), index.chunks, THRESHOLD);
  show(result, question);
  return result;
}

async function start() {
  try {
    const response = await fetch("rag/index.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`The index answered with status ${response.status}.`);
    index = await response.json();
    $("examples").replaceChildren(...EXAMPLES.map((q) => h("button", { class: "chip", type: "button", onclick: () => ask(q) }, q)));
    $("ask").addEventListener("submit", (event) => { event.preventDefault(); ask($("q").value); });
    await loadModel();
    $("ask").querySelector("button").disabled = false;
    window.ragSearch = async (q) => search(await embed(q), index.chunks, 0); // for the test page: raw scores
    window.ragReady = true;
    document.body.dataset.ragReady = "true"; // lets a browser test wait without evaluating strings (the page forbids eval)
  } catch (problem) {
    setStatus("");
    $("answer").replaceChildren(h("article", { class: "card error", role: "alert" }, h("h2", {}, "The search could not start"),
      h("p", {}, String(problem.message || problem)), h("button", { class: "btn-ghost", type: "button", onclick: () => location.reload() }, "Try again")));
  }
}

start();
