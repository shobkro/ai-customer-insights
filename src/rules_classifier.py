"""Offline keyword baseline (no AI).

Why have this? 1) The project runs end-to-end with zero setup.
2) It is the BASELINE the AI must beat - comparing the two is the most
convincing part of the project ("the LLM improved topic accuracy from X% to Y%").
"""
from __future__ import annotations

import re
import unicodedata


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


# Checked in order: the first matching topic wins.
TOPIC_PATTERNS = [
    ("not_received", r"nao (foi )?(recebi|chegou|entregue|entregaram|veio)|ainda nao (recebi|chegou)"
                     r"|nunca chegou|aguardando (o )?(produto|entrega)|nao recebemos|cade (o )?(meu )?produto"),
    ("wrong_or_missing_item", r"(produto|item|cor|modelo|tamanho) (errad|diferente)|veio (errad|outro|so )"
                              r"|faltando|falt(ou|a) (um|uma|o|a|\d)|apenas (um|uma|\d)|so (recebi|veio|chegou) (um|uma|\d|parte)"
                              r"|recebi (apenas|somente|so) |incomplet|nao veio (o|a|um|uma)"),
    ("damaged_or_defective", r"quebrad|danificad|amassad|defeito|nao funciona|parou de funcionar|rachad"
                             r"|estragad|com problema|nao liga|avariad"),
    ("late_delivery", r"atras|demor|fora do prazo|depois do prazo|prazo (nao|excedido|vencido)|ainda nao"
                      r"|nao (chegou|entregue) no prazo"),
    ("quality_not_as_described", r"qualidade (ruim|pessima|baixa|inferior)|pessima qualidade|nao (e|eh) original"
                                 r"|falsificad|diferente da (foto|imagem|descricao|anuncio)|nao corresponde"
                                 r"|frac|mal acabad|material ruim|nao gostei|piratead|paraguai"),
    ("seller_service", r"devolu|reembols|estorno|dinheiro de volta|atendimento|nao respond|sem resposta"
                       r"|contato|cancel|troca"),
]

POSITIVE = r"otim|excelent|perfeit|amei|adorei|recomendo|parabens|satisfeit|muito bom|tudo certo|gostei" \
           r"|chegou (antes|rapido|no prazo)|super rapid|maravilh|top|bom produto|show|lindo|obrigad|nota 10|ok\b"
NEGATIVE = r"pessim|horrivel|ruim|nao recomendo|decepcion|insatisfeit|pior|lament|absurd|vergonha" \
           r"|nao gostei|nunca mais|enganad|descaso|problema"


def classify(text: str) -> dict:
    t = normalise(text or "")
    topic = next((name for name, pattern in TOPIC_PATTERNS if re.search(pattern, t)), None)

    pos = len(re.findall(POSITIVE, t))
    neg = len(re.findall(NEGATIVE, t)) + (2 if topic else 0)
    if "nao recomendo" in t:
        pos = max(0, pos - 1)
    sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"

    if topic is None:
        topic = "praise" if sentiment == "positive" else "other"
    if sentiment == "positive" and topic not in ("praise", "other"):
        sentiment = "neutral"  # mixed review: praise + a problem

    urgency = ("high" if topic in ("not_received", "wrong_or_missing_item") or "reembols" in t or "devolu" in t
               else "medium" if sentiment == "negative" else "low")
    return {"sentiment": sentiment, "topic": topic, "urgency": urgency, "summary_en": ""}
