"""A fake Ollama server for testing the pipeline without downloading a model.

It speaks Ollama's /api/chat format and answers using the keyword baseline,
so tests can check the HTTP + JSON-parsing + caching code end to end.

    python tests/mock_ollama.py   # then OLLAMA_URL=http://localhost:11999
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.rules_classifier import classify

PORT = 11999


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        user = body["messages"][-1]["content"]
        if "Classify each review" in user:
            results = [{"id": rid, **classify(text), "summary_en": "mock summary"}
                       for rid, text in re.findall(r"^\d+\. \[id=([^\]]+)\] (.*)$", user, flags=re.M)]
            # Wrap in a code fence like real models sometimes do, to test the parser
            content = "```json\n" + json.dumps({"results": results}) + "\n```"
        else:  # text-to-SQL request
            content = "```sql\nSELECT COUNT(*) AS orders FROM fact_orders\n```"
        payload = json.dumps({"message": {"role": "assistant", "content": content}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)


def serve(port: int = PORT) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    print(f"mock Ollama on http://localhost:{PORT}")
    serve().serve_forever()
