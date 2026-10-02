"""Build the database automatically if it doesn't exist (used by the app,
so it also works on Streamlit Community Cloud where data/ starts empty)."""
import sqlite3
import subprocess
import sys

import pandas as pd

from src.config import DB_PATH, PROCESSED_DIR, ROOT


def best_labels_file():
    """Prefer real AI labels over the keyword baseline."""
    for provider in ("ollama", "groq", "gemini", "rules"):
        f = PROCESSED_DIR / f"review_labels_{provider}.csv"
        if f.exists():
            return f
    return None


def ensure_database() -> None:
    if DB_PATH.exists():
        return
    for script in ("01_download_data.py", "02_build_database.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)
    labels = best_labels_file()
    if labels is not None:
        con = sqlite3.connect(DB_PATH)
        cols = ["review_id", "order_id", "sentiment", "topic", "urgency", "summary_en", "provider"]
        df = pd.read_csv(labels).drop_duplicates(["review_id", "order_id"])
        df[cols].to_sql("review_ai_labels", con, if_exists="append", index=False)
        con.commit()
        con.close()
