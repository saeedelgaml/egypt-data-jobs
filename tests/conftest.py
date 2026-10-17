import os

import pytest

# Tests never talk to a real Ollama: point the local-AI fallback at a closed port.
# (Tests marked slow restore the real address themselves, and only run with --runslow.)
REAL_OLLAMA_URL = os.environ.get("OLLAMA_URL")
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="also run tests that need a real Ollama model")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="needs a real Ollama model: run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def real_ollama(monkeypatch):
    """Point the code at the real local Ollama for one test."""
    if REAL_OLLAMA_URL:
        monkeypatch.setenv("OLLAMA_URL", REAL_OLLAMA_URL)
    else:
        monkeypatch.delenv("OLLAMA_URL")
