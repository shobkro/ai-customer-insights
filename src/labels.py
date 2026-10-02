"""Label definitions, the AI prompt, and strict validation of AI output.

Keeping the taxonomy in ONE place means the AI, the rule baseline,
the evaluation and the dashboard all use exactly the same categories.
"""
from __future__ import annotations

import json
import re

SENTIMENTS = ["positive", "neutral", "negative"]
URGENCY = ["low", "medium", "high"]

# topic -> description shown to the AI (and documented in the README)
TOPICS = {
    "late_delivery": "arrived later than promised, or customer complains about slow delivery",
    "not_received": "customer says the order has not arrived / was never delivered",
    "wrong_or_missing_item": "wrong product sent, or only part of the order arrived",
    "damaged_or_defective": "product arrived broken, damaged, or does not work",
    "quality_not_as_described": "poor quality, different from the photo/description, counterfeit",
    "seller_service": "communication, customer service, refund or return problems",
    "praise": "positive comment about the product, delivery or seller",
    "other": "anything else, or too vague to classify",
}

SYSTEM_PROMPT = f"""You are a customer-insights analyst for a Brazilian e-commerce marketplace.
You classify customer reviews written in Portuguese. Reply with JSON only.

For each review return:
- "sentiment": one of {SENTIMENTS}
- "topic": the MAIN topic, one of {list(TOPICS)}
- "urgency": one of {URGENCY} (high = customer has no product / wants money back; medium = problem but product received; low = no action needed)
- "summary_en": a short English summary, max 12 words

Topic definitions:
""" + "\n".join(f"- {k}: {v}" for k, v in TOPICS.items())


def build_batch_prompt(reviews: list[tuple[str, str]]) -> str:
    """reviews = [(id, text), ...] -> user prompt asking for a JSON list."""
    lines = [f'{i + 1}. [id={rid}] {text.strip()[:600]}' for i, (rid, text) in enumerate(reviews)]
    return (
        "Classify each review below. Return a JSON object of the form "
        '{"results": [{"id": "...", "sentiment": "...", "topic": "...", '
        '"urgency": "...", "summary_en": "..."}]} with one entry per review, '
        "in the same order.\n\n" + "\n".join(lines)
    )


def extract_json(text: str):
    """LLMs sometimes wrap JSON in ``` fences or add chatter. Pull out the JSON."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(1))


def clean_label(raw: dict) -> dict:
    """Guardrail: force every field into the allowed set (never trust raw AI output)."""
    sentiment = str(raw.get("sentiment", "")).lower().strip()
    topic = str(raw.get("topic", "")).lower().strip()
    urgency = str(raw.get("urgency", "")).lower().strip()
    return {
        "sentiment": sentiment if sentiment in SENTIMENTS else "neutral",
        "topic": topic if topic in TOPICS else "other",
        "urgency": urgency if urgency in URGENCY else "low",
        "summary_en": str(raw.get("summary_en", ""))[:120],
    }


def parse_batch_response(text: str, ids: list[str]) -> dict[str, dict]:
    """Return {review_id: cleaned_label}. Missing ids are simply absent."""
    data = extract_json(text)
    items = data.get("results", data) if isinstance(data, dict) else data
    if isinstance(items, dict):  # single object
        items = [items]
    out: dict[str, dict] = {}
    for pos, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id", "")).strip()
        if rid not in ids and pos < len(ids):  # model dropped/mangled the id -> use position
            rid = ids[pos]
        if rid in ids:
            out[rid] = clean_label(item)
    return out


def stars_to_sentiment(score: int) -> str:
    """Star rating used as free 'ground truth' for sentiment."""
    return "negative" if score <= 2 else ("neutral" if score == 3 else "positive")
