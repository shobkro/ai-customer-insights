"""End-to-end test of the AI code path using the fake Ollama server (no model needed)."""
import threading

import pytest

from src import config
from src.config import DB_PATH


@pytest.fixture(scope="module")
def mock_ollama():
    from tests.mock_ollama import PORT, serve
    server = serve(PORT)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    old = config.OLLAMA_URL
    config.OLLAMA_URL = f"http://127.0.0.1:{PORT}"
    yield
    config.OLLAMA_URL = old
    server.shutdown()


@pytest.mark.skipif(not DB_PATH.exists(), reason="build the database first")
def test_ask_data_end_to_end(mock_ollama):
    from src.text_to_sql import ask_data
    ans = ask_data("How many orders are there?", provider="ollama", explain=False)
    assert ans.error == ""
    assert ans.columns == ["orders"]
    assert ans.rows[0][0] == 99441


def test_llm_batch_labelling(mock_ollama):
    from src.labels import SYSTEM_PROMPT, build_batch_prompt, parse_batch_response
    from src.llm import ask_llm
    reply = ask_llm(SYSTEM_PROMPT, build_batch_prompt([("r0", "Não recebi o produto"),
                                                        ("r1", "Adorei, recomendo")]),
                    provider="ollama")
    out = parse_batch_response(reply, ["r0", "r1"])
    assert out["r0"]["topic"] == "not_received"
    assert out["r1"]["sentiment"] == "positive"
