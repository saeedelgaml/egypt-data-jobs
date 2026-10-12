import os

# Tests never talk to a real Ollama: point the local-AI fallback at a closed port.
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"
