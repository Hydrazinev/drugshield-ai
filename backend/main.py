import os
import sys
import asyncio

# Ensure local backend modules are imported even if uvicorn is started from another cwd.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import httpx
from fall_risk import compute_fall_risk
import scoring as scoring_module


from models import AnalyzeRequest, AnalyzeResponse, NormalizedMed, InteractionFact
from rxnav import get_rxcui_for_name, get_interactions_for_rxcuis, infer_interactions_from_names
from openfda_fallback import infer_interactions_from_openfda
from scoring import compute_score_breakdown, urgency_from_score
from llm_explain import build_facts_bundle, explain_with_llm
from pdf_report import render_report_bytes

app = FastAPI(title="DrugShield AI")
API_VERSION = "2026.02.16.2"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for hackathon. lock down later.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DISCLAIMER = (
    "Decision support only. Not medical advice. "
    "Always confirm medication changes with a licensed clinician."
)

SEVERITY_RANK = {"unknown": 0, "low": 1, "moderate": 2, "high": 3}


def _build_llm_pair_fallback_cards(meds: list[dict], max_pairs: int = 6) -> list[dict]:
    """
    Build synthetic pair cards for LLM explanation only when no confirmed DDI pairs exist.
    These cards do not affect score calculation.
    """
    names: list[str] = []
    seen_lower: set[str] = set()
    for m in meds:
        nm = str(m.get("normalized_name") or m.get("raw_name") or "").strip()
        if not nm:
            continue
        nm_lower = nm.lower()
        if nm_lower in seen_lower:
            continue
        seen_lower.add(nm_lower)
        names.append(nm)

    out: list[dict] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out.append(
                {
                    "drug_a": names[i],
                    "drug_b": names[j],
                    "severity": "unknown",
                    "source_text": "No confirmed interaction pair was returned in the checked data source.",
                }
            )
            if len(out) >= max_pairs:
                return out
    return out

@app.get("/health")
def health():
    return {
        "ok": True,
        "api_version": API_VERSION,
        "score_engine_version": getattr(scoring_module, "SCORE_ENGINE_VERSION", "unknown"),
    }


@app.get("/debug/scoring-source")
def debug_scoring_source():
    return {
        "api_version": API_VERSION,
        "scoring_file": getattr(scoring_module, "__file__", "unknown"),
        "has_lexapro_alias": bool(getattr(scoring_module, "NAME_ALIASES", {}).get("lexapro")),
        "has_escitalopram_limit": bool(getattr(scoring_module, "DOSE_LIMITS_MG_PER_DAY", {}).get("escitalopram")),
        "score_engine_version": getattr(scoring_module, "SCORE_ENGINE_VERSION", "unknown"),
    }

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    patient_name = (req.patient_name or "").strip() or None
    normalized = []
    rxcuis = []
    meds_lower_for_fall = []

    invalid_names = []

    async with httpx.AsyncClient() as client:
        lookup_tasks = [get_rxcui_for_name(client, m.name.strip()) for m in req.meds]
        lookup_results = await asyncio.gather(*lookup_tasks)

        for m, (rxcui, best_name, note) in zip(req.meds, lookup_results):
            raw_name = m.name.strip()
            nm = NormalizedMed(
                raw_name=raw_name,
                normalized_name=best_name or raw_name,
                rxcui=rxcui,
                note=note
            )
            normalized.append(nm)
            if rxcui:
                rxcuis.append(rxcui)
            else:
                invalid_names.append(raw_name)

        if not rxcuis:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "No valid medication names were recognized. Please check spelling and try generic names.",
                    "invalid_meds": invalid_names,
                },
            )

        valid_normalized = [m for m in normalized if m.rxcui]
        meds_lower_for_fall = [{"name": m.normalized_name.lower()} for m in valid_normalized]

        interactions_raw = await get_interactions_for_rxcuis(client, rxcuis)
        if not interactions_raw:
            openfda_interactions = await infer_interactions_from_openfda(
                client, [m.normalized_name for m in normalized]
            )
            local_interactions = infer_interactions_from_names(
                [m.normalized_name for m in normalized]
            )

            merged: dict[tuple[str, str], dict] = {}
            for item in openfda_interactions + local_interactions:
                a = str(item.get("drug_a", "")).lower().strip()
                b = str(item.get("drug_b", "")).lower().strip()
                if not a or not b:
                    continue
                pair_key = tuple(sorted([a, b]))
                sev = str(item.get("severity", "unknown")).lower()
                if sev not in SEVERITY_RANK:
                    sev = "unknown"

                if pair_key not in merged:
                    merged[pair_key] = {
                        "drug_a": a,
                        "drug_b": b,
                        "severity": sev,
                        "source_text": str(item.get("source_text", "")),
                    }
                    continue

                prev = merged[pair_key]
                prev_rank = SEVERITY_RANK.get(str(prev.get("severity", "unknown")).lower(), 0)
                cur_rank = SEVERITY_RANK.get(sev, 0)
                if cur_rank > prev_rank:
                    prev["severity"] = sev
                    prev["source_text"] = str(item.get("source_text", "")) or str(prev.get("source_text", ""))
                elif not str(prev.get("source_text", "")).strip():
                    prev["source_text"] = str(item.get("source_text", ""))

            interactions_raw = list(merged.values())

    interactions = [
        InteractionFact(
            drug_a=i["drug_a"],
            drug_b=i["drug_b"],
            severity=i["severity"],
            source_text=i["source_text"]
        )
        for i in interactions_raw
    ]

    meds_for_scoring = []
    for m_in, m_norm in zip(req.meds, normalized):
        if not m_norm.rxcui:
            continue
        meds_for_scoring.append(
            {
                "raw_name": m_norm.raw_name,
                "normalized_name": m_norm.normalized_name,
                "rxcui": m_norm.rxcui,
                "dose": m_in.dose,
                "frequency": m_in.frequency,
                "note": m_norm.note,
            }
        )
    score_breakdown = compute_score_breakdown(
        req.age, [i.model_dump() for i in interactions], meds=meds_for_scoring
    )
    score = score_breakdown["scaled_score_0_to_10"]
    urgency = urgency_from_score(score)
    fall_risk = compute_fall_risk(meds_lower_for_fall)

    meds_for_bundle = []
    for m_in, m_norm in zip(req.meds, normalized):
        meds_for_bundle.append(
            {
                "raw_name": m_norm.raw_name,
                "normalized_name": m_norm.normalized_name,
                "rxcui": m_norm.rxcui,
                "dose": m_in.dose,
                "frequency": m_in.frequency,
                "note": m_norm.note,
            }
        )

    interactions_for_bundle = [i.model_dump() for i in interactions]
    if not interactions_for_bundle and len(meds_for_bundle) >= 2:
        interactions_for_bundle = _build_llm_pair_fallback_cards(meds_for_bundle)
    facts = build_facts_bundle(
        age=req.age,
        meds=meds_for_bundle,
        interactions=interactions_for_bundle,
        score={
            "final_score": score,
            "urgency": urgency,
            "breakdown": score_breakdown,
        },
    )
    facts.setdefault("patient", {})
    facts["patient"]["name"] = patient_name

    llm_out = explain_with_llm(facts)

    return AnalyzeResponse(
        api_version=API_VERSION,
        score_engine_version=getattr(scoring_module, "SCORE_ENGINE_VERSION", "unknown"),
        patient_name=patient_name,
        normalized_meds=normalized,
        interactions=interactions,
        risk_score_0_to_10=score,
        urgency=urgency,
        fall_risk=fall_risk,
        score_breakdown=score_breakdown,
        llm=llm_out,
        disclaimer=DISCLAIMER,
    )

@app.post("/report")
def report(payload: dict):
    patient_name = str(payload.get("patient_name", "")).strip() if isinstance(payload, dict) else ""
    safe_name = "".join(ch.lower() for ch in patient_name if ch.isalnum() or ch in {"-", "_", " "}).strip().replace(" ", "-")
    filename = f"{safe_name}-drugshield-report.pdf" if safe_name else "drugshield-report.pdf"

    llm = payload.get("llm", {}) if isinstance(payload, dict) else {}
    bundle = {
        "patient_name": payload.get("patient_name", ""),
        "patient_summary_simple": llm.get("patient_summary_simple", ""),
        "caregiver_summary": llm.get("caregiver_summary", ""),
        "doctor_note": llm.get("doctor_note", ""),
        "interaction_explanations": llm.get("interaction_explanations", []),
        "score": {
            "final_score": payload.get("risk_score_0_to_10", "N/A"),
            "urgency": payload.get("urgency", "GREEN_MONITOR"),
        },
    }

    pdf_bytes = render_report_bytes(bundle)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
