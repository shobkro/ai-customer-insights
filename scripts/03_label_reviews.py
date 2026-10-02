"""Step 3 - Use AI to turn free-text reviews into structured data.

    python scripts/03_label_reviews.py                     # Ollama, 2,000 reviews
    python scripts/03_label_reviews.py --provider rules    # offline baseline, no AI
    python scripts/03_label_reviews.py --provider groq --limit 500

* Always includes the 150 hand-labelled reviews in data/eval/gold_labels.csv,
  so the result can be evaluated (scripts/04_evaluate.py).
* Results are cached in data/processed/, so if it stops (rate limit, laptop
  sleeps) just run it again and it resumes where it left off.
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.config import DB_PATH, EVAL_DIR, PROCESSED_DIR
from src.labels import SYSTEM_PROMPT, build_batch_prompt, parse_batch_response
from src.llm import LLMError, ask_llm
from src.rules_classifier import classify

COLUMNS = ["review_id", "order_id", "sentiment", "topic", "urgency", "summary_en", "provider"]


def pick_reviews(limit: int, seed: int = 42) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    reviews = pd.read_sql_query(
        """SELECT review_id, order_id, review_score, comment_message
           FROM fact_reviews
           WHERE comment_message IS NOT NULL AND length(comment_message) >= 5""",
        con,
    )
    con.close()
    gold = pd.read_csv(EVAL_DIR / "gold_labels.csv")[["review_id", "order_id"]]
    is_gold = reviews.set_index(["review_id", "order_id"]).index.isin(
        gold.set_index(["review_id", "order_id"]).index)
    gold_rows = reviews[is_gold]
    rest = reviews[~is_gold]
    if limit and limit < len(rest):
        rest = rest.sample(limit, random_state=seed)
    return pd.concat([gold_rows, rest]).reset_index(drop=True)


def label_with_llm(batch: pd.DataFrame, provider: str) -> list[dict]:
    keys = [f"r{i}" for i in range(len(batch))]  # short ids are easier for small models
    pairs = list(zip(keys, batch["comment_message"]))
    try:
        reply = ask_llm(SYSTEM_PROMPT, build_batch_prompt(pairs), provider=provider)
        labels = parse_batch_response(reply, keys)
    except (ValueError, KeyError) as exc:  # bad JSON -> fall back to one-by-one
        print(f"  batch parse failed ({exc}); retrying one at a time")
        labels = {}
    rows = []
    for key, (_, row) in zip(keys, batch.iterrows()):
        label = labels.get(key)
        if label is None:  # retry single review
            try:
                reply = ask_llm(SYSTEM_PROMPT, build_batch_prompt([(key, row.comment_message)]),
                                provider=provider)
                label = parse_batch_response(reply, [key]).get(key)
            except (ValueError, KeyError):
                label = None
        if label is None:
            continue  # skip; it will be retried on the next run
        rows.append({"review_id": row.review_id, "order_id": row.order_id, **label,
                     "provider": provider})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=config.LLM_PROVIDER,
                    choices=["ollama", "gemini", "groq", "rules"])
    ap.add_argument("--limit", type=int, default=2000, help="random reviews to label (0 = all ~41k)")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls (free-tier limits)")
    args = ap.parse_args()

    cache = PROCESSED_DIR / f"review_labels_{args.provider}.csv"
    done = pd.read_csv(cache) if cache.exists() else pd.DataFrame(columns=COLUMNS)
    todo = pick_reviews(args.limit)
    todo = todo[~todo.review_id.isin(done.review_id)]
    print(f"provider={args.provider}  already labelled={len(done)}  to do={len(todo)}")

    if args.provider == "rules":
        rows = [{"review_id": r.review_id, "order_id": r.order_id, **classify(r.comment_message),
                 "provider": "rules"} for r in todo.itertuples()]
        done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
        done.to_csv(cache, index=False)
    else:
        start = time.time()
        for i in range(0, len(todo), args.batch_size):
            batch = todo.iloc[i:i + args.batch_size]
            try:
                rows = label_with_llm(batch, args.provider)
            except LLMError as exc:
                print(f"\nStopped: {exc}\nProgress is saved - run the same command again to resume.")
                break
            done = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
            done.to_csv(cache, index=False)  # save after every batch
            n = min(i + args.batch_size, len(todo))
            rate = n / max(time.time() - start, 1e-6)
            print(f"  {n}/{len(todo)} labelled  (~{(len(todo) - n) / rate / 60:.0f} min left)", end="\r")
            if args.sleep:
                time.sleep(args.sleep)
        print()

    # Load into the database so SQL, the app and Power BI can use it
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM review_ai_labels")
    done.drop_duplicates(["review_id", "order_id"])[COLUMNS].to_sql(
        "review_ai_labels", con, if_exists="append", index=False)
    con.commit()
    con.close()
    print(f"Saved {len(done)} labels to {cache.name} and table review_ai_labels")


if __name__ == "__main__":
    main()
