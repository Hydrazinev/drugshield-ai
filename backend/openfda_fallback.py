from __future__ import annotations

import copy
import re
import time
from typing import Any, Dict, List, Tuple

import httpx

OPENFDA_LABEL_ENDPOINT = "https://api.fda.gov/drug/label.json"
OPENFDA_CACHE_TTL_SECONDS = 12 * 60 * 60

_label_cache: Dict[str, Tuple[float, List[str]]] = {}


def _cache_get(name_key: str) -> List[str] | None:
    hit = _label_cache.get(name_key)
    if not hit:
        return None
    exp, value = hit
    if exp <= time.monotonic():
        _label_cache.pop(name_key, None)
        return None
    return copy.deepcopy(value)


def _cache_set(name_key: str, value: List[str]) -> None:
    _label_cache[name_key] = (time.monotonic() + OPENFDA_CACHE_TTL_SECONDS, copy.deepcopy(value))


def _norm(name: str) -> str:
    return str(name or "").strip().lower()


def _severity_from_text(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["contraindicated", "avoid concomitant", "life-threatening", "fatal", "major"]):
        return "high"
    if any(k in t for k in ["serious", "severe", "significant", "clinically important"]):
        return "moderate"
    if any(k in t for k in ["minor", "monitor", "caution"]):
        return "low"
    return "unknown"


def _first_sentence_with_term(texts: List[str], term: str) -> str | None:
    needle = _norm(term)
    if not needle:
        return None
    for text in texts:
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(text)):
            s = sentence.strip()
            if not s:
                continue
            if re.search(rf"\b{re.escape(needle)}\b", s.lower()):
                return s[:300]
    return None


def _extract_interaction_texts(label_result: Dict[str, Any]) -> List[str]:
    keys = [
        "drug_interactions",
        "warnings_and_cautions",
        "warnings",
        "boxed_warning",
        "contraindications",
    ]
    texts: List[str] = []
    for key in keys:
        val = label_result.get(key)
        if isinstance(val, list):
            for item in val:
                s = str(item).strip()
                if s:
                    texts.append(s)
        elif isinstance(val, str) and val.strip():
            texts.append(val.strip())
    return texts


async def _fetch_label_texts_for_name(client: httpx.AsyncClient, med_name: str) -> List[str]:
    name = _norm(med_name)
    if not name:
        return []

    cached = _cache_get(name)
    if cached is not None:
        return cached

    search_variants = [
        f'openfda.generic_name:"{name}"',
        f'openfda.brand_name:"{name}"',
        f'openfda.substance_name:"{name}"',
    ]

    for search in search_variants:
        try:
            r = await client.get(
                OPENFDA_LABEL_ENDPOINT,
                params={"search": search, "limit": 3},
                timeout=20,
            )
        except Exception:
            continue
        if r.status_code != 200:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        results = data.get("results", [])
        if not isinstance(results, list) or not results:
            continue
        texts: List[str] = []
        for item in results:
            if isinstance(item, dict):
                texts.extend(_extract_interaction_texts(item))
        if texts:
            _cache_set(name, texts)
            return texts

    _cache_set(name, [])
    return []


async def infer_interactions_from_openfda(
    client: httpx.AsyncClient, names: List[str]
) -> List[Dict[str, Any]]:
    cleaned = [_norm(n) for n in names if _norm(n)]
    if len(cleaned) < 2:
        return []

    unique_names = list(dict.fromkeys(cleaned))
    label_texts_by_name: Dict[str, List[str]] = {}
    for name in unique_names:
        label_texts_by_name[name] = await _fetch_label_texts_for_name(client, name)

    out: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()

    for i in range(len(unique_names)):
        for j in range(i + 1, len(unique_names)):
            a = unique_names[i]
            b = unique_names[j]
            pair_key = tuple(sorted([a, b]))
            if pair_key in seen:
                continue

            a_texts = label_texts_by_name.get(a, [])
            b_texts = label_texts_by_name.get(b, [])

            a_mentions_b = _first_sentence_with_term(a_texts, b)
            b_mentions_a = _first_sentence_with_term(b_texts, a)
            if not a_mentions_b and not b_mentions_a:
                continue

            seen.add(pair_key)
            evidence = a_mentions_b or b_mentions_a or ""
            severity = _severity_from_text(evidence)
            source_text = f"{evidence} (openFDA label fallback)".strip()
            out.append(
                {
                    "drug_a": a,
                    "drug_b": b,
                    "severity": severity,
                    "source_text": source_text[:400],
                }
            )

    return out
