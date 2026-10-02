from src.labels import clean_label, extract_json, parse_batch_response, stars_to_sentiment
from src.rules_classifier import classify


def test_extract_json_with_fences_and_chatter():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('blah {"a": [1, 2]} blah') == {"a": [1, 2]}


def test_clean_label_forces_allowed_values():
    out = clean_label({"sentiment": "VERY ANGRY", "topic": "aliens", "urgency": "HIGH"})
    assert out == {"sentiment": "neutral", "topic": "other", "urgency": "high", "summary_en": ""}


def test_parse_batch_uses_position_when_id_is_mangled():
    reply = '{"results": [{"id": "1", "sentiment": "negative", "topic": "not_received", "urgency": "high"}]}'
    out = parse_batch_response(reply, ["r0"])
    assert out["r0"]["topic"] == "not_received"


def test_stars_to_sentiment():
    assert [stars_to_sentiment(s) for s in (1, 2, 3, 4, 5)] == \
        ["negative", "negative", "neutral", "positive", "positive"]


def test_rules_baseline_examples():
    assert classify("Ainda não recebi o produto")["topic"] == "not_received"
    assert classify("Produto chegou quebrado")["topic"] == "damaged_or_defective"
    assert classify("Ótimo produto, chegou antes do prazo, recomendo!")["sentiment"] == "positive"
