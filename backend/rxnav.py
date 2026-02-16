from __future__ import annotations
import httpx
import time
import copy
from typing import Optional, List, Dict, Any, Tuple

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNORM_RXCUI_BY_NAME_ENDPOINT = f"{RXNORM_BASE}/rxcui.json"
RXNAV_INTERACTION_ENDPOINTS = [
    f"{RXNORM_BASE}/interaction/interaction.json",
    f"{RXNORM_BASE}/interaction.json",
    f"{RXNORM_BASE}/interaction/list.json",
]
RXNORM_APPROX_ENDPOINT = f"{RXNORM_BASE}/approximateTerm.json"
RXNORM_RXCUI_PROP_ENDPOINT = f"{RXNORM_BASE}/rxcui/{{rxcui}}/property.json"
MIN_APPROX_SCORE = 50.0
RXCUI_CACHE_TTL_SECONDS = 60 * 60
INTERACTIONS_CACHE_TTL_SECONDS = 10 * 60

_rxcui_cache: Dict[str, Tuple[float, Tuple[Optional[str], Optional[str], Optional[str]]]] = {}
_interactions_cache: Dict[Tuple[str, ...], Tuple[float, List[Dict[str, Any]]]] = {}


def _cache_get_rxcui(name_key: str) -> Optional[Tuple[Optional[str], Optional[str], Optional[str]]]:
    hit = _rxcui_cache.get(name_key)
    if not hit:
        return None
    exp, value = hit
    if exp <= time.monotonic():
        _rxcui_cache.pop(name_key, None)
        return None
    return value


def _cache_set_rxcui(name_key: str, value: Tuple[Optional[str], Optional[str], Optional[str]]) -> None:
    _rxcui_cache[name_key] = (time.monotonic() + RXCUI_CACHE_TTL_SECONDS, value)


def _cache_get_interactions(key: Tuple[str, ...]) -> Optional[List[Dict[str, Any]]]:
    hit = _interactions_cache.get(key)
    if not hit:
        return None
    exp, value = hit
    if exp <= time.monotonic():
        _interactions_cache.pop(key, None)
        return None
    return copy.deepcopy(value)


def _cache_set_interactions(key: Tuple[str, ...], value: List[Dict[str, Any]]) -> None:
    _interactions_cache[key] = (time.monotonic() + INTERACTIONS_CACHE_TTL_SECONDS, copy.deepcopy(value))

async def get_rxcui_for_name(client: httpx.AsyncClient, name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (rxcui, best_name, note)
    Strategy:
    - Try exact RxNorm name lookup first.
    - Fall back to approximate term matching.
    """
    cache_key = str(name or "").strip().lower()
    if cache_key:
        cached = _cache_get_rxcui(cache_key)
        if cached is not None:
            return cached

    # Prefer exact name resolution for common generic/brand names.
    exact = await client.get(RXNORM_RXCUI_BY_NAME_ENDPOINT, params={"name": name}, timeout=20)
    if exact.status_code == 200:
        ex = exact.json()
        exact_ids = ex.get("idGroup", {}).get("rxnormId", [])
        if exact_ids:
            rxcui = str(exact_ids[0])
            best_name = None
            pr = await client.get(
                RXNORM_RXCUI_PROP_ENDPOINT.format(rxcui=rxcui),
                params={"propName": "RxNorm Name"},
                timeout=20,
            )
            if pr.status_code == 200:
                pj = pr.json()
                best_name = pj.get("propConceptGroup", {}).get("propConcept", [None])[0]
                if isinstance(best_name, dict):
                    best_name = best_name.get("propValue")
            out = (rxcui, best_name or name, None)
            if cache_key:
                _cache_set_rxcui(cache_key, out)
            return out

    params = {
        "term": name,
        "maxEntries": 1,
        "option": 1,  # approximate matching
    }
    r = await client.get(RXNORM_APPROX_ENDPOINT, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    candidates = data.get("approximateGroup", {}).get("candidate", [])
    if not candidates:
        out = (None, None, "No RxNorm match found. Check spelling or use generic name.")
        if cache_key:
            _cache_set_rxcui(cache_key, out)
        return out

    c = candidates[0]
    rxcui = c.get("rxcui")
    score = c.get("score")
    # Reject weak approximate matches so random text does not pass as medication.
    note = None
    if score is not None:
        try:
            sc = float(score)
            if sc < MIN_APPROX_SCORE:
                out = (None, None, "No confident RxNorm match found. Check spelling or use a generic medicine name.")
                if cache_key:
                    _cache_set_rxcui(cache_key, out)
                return out
            if sc < 70:
                note = "Approximate RxNorm match. Double check medication name."
        except Exception:
            pass
    else:
        out = (None, None, "No confident RxNorm match found. Check spelling or use a generic medicine name.")
        if cache_key:
            _cache_set_rxcui(cache_key, out)
        return out

    best_name = None
    if rxcui:
        pr = await client.get(RXNORM_RXCUI_PROP_ENDPOINT.format(rxcui=rxcui), params={"propName": "RxNorm Name"}, timeout=20)
        if pr.status_code == 200:
            pj = pr.json()
            best_name = pj.get("propConceptGroup", {}).get("propConcept", [None])[0]
            if isinstance(best_name, dict):
                best_name = best_name.get("propValue")

    out = (rxcui, best_name, note)
    if cache_key:
        _cache_set_rxcui(cache_key, out)
    return out


def _extract_interactions(payload: Dict[str, Any], rxcui_to_name: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    RxNav interaction responses include an interactionTypeGroup with pairs and descriptions.
    This parser is defensive and extracts the most useful text available.
    """
    out: List[Dict[str, Any]] = []
    groups = payload.get("interactionTypeGroup", [])
    if not groups:
        full_groups = payload.get("fullInteractionTypeGroup", [])
        for fg in full_groups:
            groups.extend(fg.get("interactionTypeGroup", []))
    for g in groups:
        for itype in g.get("interactionType", []):
            pairs = itype.get("interactionPair", [])
            for p in pairs:
                desc = p.get("description") or ""
                sev = (p.get("severity") or "").lower().strip()
                if sev not in {"high", "moderate", "low"}:
                    sev = "unknown"

                concepts = p.get("interactionConcept", [])
                if len(concepts) >= 2:
                    a = concepts[0].get("minConceptItem", {}).get("rxcui")
                    b = concepts[1].get("minConceptItem", {}).get("rxcui")
                    if a and b:
                        out.append(
                            {
                                "drug_a": rxcui_to_name.get(a, a),
                                "drug_b": rxcui_to_name.get(b, b),
                                "severity": sev,
                                "source_text": desc if desc else "Interaction detected (no description provided by source).",
                            }
                        )
    return out


async def get_interactions_for_rxcuis(
    client: httpx.AsyncClient,
    rxcuis: List[str],
) -> List[Dict[str, Any]]:
    """
    Strategy:
    - Call interaction endpoint per RxCUI
    - Merge unique pairs
    This keeps it simple and reliable for a hackathon demo.
    """
    rxcuis = [x for x in rxcuis if x]
    if not rxcuis:
        return []
    key = tuple(sorted(set(rxcuis)))
    cached = _cache_get_interactions(key)
    if cached is not None:
        return cached

    # Map RxCUI to display name if possible later
    rxcui_to_name = {x: x for x in rxcuis}

    all_pairs: List[Dict[str, Any]] = []
    seen = set()

    for rx in rxcuis:
        extracted = []
        for endpoint in RXNAV_INTERACTION_ENDPOINTS:
            r = await client.get(endpoint, params={"rxcui": rx}, timeout=25)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            extracted = _extract_interactions(data, rxcui_to_name)
            if extracted:
                break

        for item in extracted:
            a = item["drug_a"]
            b = item["drug_b"]
            key = tuple(sorted([a, b]))
            if key in seen:
                continue
            seen.add(key)
            all_pairs.append(item)

    _cache_set_interactions(key, all_pairs)
    return all_pairs
