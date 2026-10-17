"""The RAG route: answer from the five reports when the question is about them.

Order in chatbot.ai.answer_question: fixed answers -> this route -> local-AI SQL fallback -> refusal.
Retrieval comes first and needs no language model. Only when the best passage scores at least
rag.retrieve.THRESHOLD is the model asked to write an answer, and if it says the documents do not
cover the question, or Ollama is not running, the chatbot moves on to the next route (so a question that merely
scores close to the threshold, such as a jobs-table question, still reaches the SQL fallback or the usual refusal). Skipped quietly when the documents were
never indexed (rag/index/ is not in the repository). Everything stays on this computer.
"""
from chatbot.local_ai import BLOCKED
from rag import answer as rag_answer
from rag import retrieve


class RagRoute:
    """Callable like LocalAI: RagRoute()(question) -> a result dict, or None to try the next route."""

    def __init__(self, ask_model=None, search=None, threshold=None, on_token=None):
        self.ask_model = ask_model
        self.on_token = on_token
        self.search = search or retrieve.search
        self.threshold = retrieve.THRESHOLD if threshold is None else threshold
        self.enabled = search is not None or retrieve.index_available()

    def __call__(self, question):
        if not self.enabled or BLOCKED.search(question):  # instruction-like text never reaches the model
            return None
        try:
            hits = self.search(question)
        except ImportError:  # sentence-transformers is an optional extra
            return None
        if not hits or hits[0]["best_score"] < self.threshold:
            return None
        result = rag_answer.answer(question, hits, ask_model=self.ask_model, on_token=self.on_token)
        if result["mode"] in ("not_covered", "quotes_offline"):  # no model, or the reports do not cover it
            return None
        return {"ok": True, "text": rag_answer.format_answer(result), "function": "rag", "params": {},
                "data": {"mode": result["mode"], "model": result.get("model"), "sources": result["sources"], "best_score": hits[0]["best_score"]}}
