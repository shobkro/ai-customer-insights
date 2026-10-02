"""Make the PNG charts used in the README (docs/images/)."""
import sqlite3
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DB_PATH, ROOT  # noqa: E402

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)
BLUE, SURFACE, INK, MUTED, GRID = "#2a78d6", "#fcfcfb", "#1f1f1e", "#6b6b68", "#e6e5e1"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.axisbelow": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "font.size": 11, "axes.titlesize": 14, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def lateness_chart(con):
    df = pd.read_sql_query("""
        SELECT CASE WHEN days_late<=-7 THEN '7+ days\nearly' WHEN days_late<=0 THEN '0-7 days\nearly'
               WHEN days_late<=3 THEN '1-3 days\nlate' WHEN days_late<=7 THEN '4-7 days\nlate'
               ELSE '8+ days\nlate' END bucket, AVG(r.review_score) score, MIN(days_late) o
        FROM fact_reviews r JOIN fact_orders o ON o.order_id = r.order_id
        WHERE o.order_status='delivered' AND days_late IS NOT NULL GROUP BY bucket ORDER BY o""", con)
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    bars = ax.bar(df.bucket, df.score, color=BLUE, width=0.55)
    for b, v in zip(bars, df.score):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.08, f"{v:.2f}", ha="center", color=INK, fontsize=10)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review score (stars)")
    ax.set_title("Reviews collapse once an order is late")
    ax.tick_params(axis="x", length=0)
    fig.tight_layout()
    fig.savefig(OUT / "rating_vs_lateness.png")
    plt.close(fig)


def topics_chart(con):
    df = pd.read_sql_query("""SELECT topic, COUNT(*) n FROM review_ai_labels
                              WHERE sentiment='negative' GROUP BY topic ORDER BY n""", con)
    provider = pd.read_sql_query("SELECT provider FROM review_ai_labels LIMIT 1", con).provider[0]
    df["topic"] = df.topic.str.replace("_", " ")
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=150)
    ax.barh(df.topic, df.n, color=BLUE, height=0.55)
    for y, v in enumerate(df.n):
        ax.text(v + df.n.max() * 0.01, y, f"{v:,}", va="center", color=INK, fontsize=10)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel("Negative reviews")
    ax.set_title(f"What customers complain about (labels: {provider})")
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    fig.savefig(OUT / "complaint_topics.png")
    plt.close(fig)


if __name__ == "__main__":
    con = sqlite3.connect(DB_PATH)
    lateness_chart(con)
    topics_chart(con)
    con.close()
    print(f"Charts saved to {OUT}")
