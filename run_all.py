"""Run the whole pipeline in order.

    python run_all.py                    # uses LLM_PROVIDER from .env (default: ollama)
    python run_all.py --provider rules   # no AI at all (works anywhere, instantly)
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    print(f"\n=== {script} {' '.join(args)} ===")
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None, help="ollama | groq | gemini | rules")
    ap.add_argument("--limit", default="2000", help="reviews for the AI to label")
    args = ap.parse_args()
    provider = ["--provider", args.provider] if args.provider else []

    run("01_download_data.py")
    run("02_build_database.py")
    run("03_label_reviews.py", "--provider", "rules", "--limit", "0")  # baseline, always
    if args.provider != "rules":
        run("03_label_reviews.py", *provider, "--limit", args.limit)   # the AI labels
    run("04_evaluate.py")
    run("run_sql_analysis.py")
    run("05_export_powerbi.py")
    run("06_excel_kpi_pack.py", *([] if args.provider != "rules" else ["--no-ai"]))
    run("make_readme_charts.py")
    print("\nAll done. Start the app with:  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
