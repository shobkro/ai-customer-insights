"""Central paths and settings for the project."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
EVAL_DIR = ROOT / "data" / "eval"
DB_PATH = ROOT / "data" / "olist.db"
RESULTS_DIR = ROOT / "results"
POWERBI_DIR = ROOT / "powerbi" / "data"
EXCEL_DIR = ROOT / "excel"

for d in (RAW_DIR, PROCESSED_DIR, EVAL_DIR, RESULTS_DIR, POWERBI_DIR, EXCEL_DIR):
    d.mkdir(parents=True, exist_ok=True)


def load_env(path: Path = ROOT / ".env") -> None:
    """Tiny .env loader so we don't need an extra dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

# Which AI provider to use: "ollama" (free, local), "gemini" (free tier),
# "groq" (free tier) or "rules" (offline keyword baseline, no AI).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
