# scoring.py
import re
from typing import Any, Dict, List, Tuple

SCORE_ENGINE_VERSION = "2026.02.16.2"


SEVERITY_POINTS = {"low": 1.0, "moderate": 3.0, "high": 7.0, "unknown": 2.0}

HIGH_RISK_SUBSTANCE_POINTS = {
    "cocaine": 8.0,
    "heroin": 8.0,
    "methamphetamine": 8.0,
    "fentanyl": 6.0,
}

SEDATIVE_KEYWORDS = {
    "alprazolam",
    "diazepam",
    "lorazepam",
    "clonazepam",
    "zolpidem",
    "temazepam",
}

RISK_CLASS_POINTS = {
    "anticoagulant": 2.5,
    "opioid": 2.5,
    "sedative": 2.0,
    "antipsychotic": 1.8,
    "insulin": 1.8,
    "hypoglycemic": 1.2,
    "antiplatelet": 1.6,
}

RISK_CLASS_KEYWORDS = {
    "anticoagulant": {"warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "heparin", "enoxaparin"},
    "opioid": {"morphine", "oxycodone", "hydrocodone", "codeine", "tramadol", "methadone", "buprenorphine", "fentanyl"},
    "sedative": SEDATIVE_KEYWORDS,
    "antipsychotic": {"quetiapine", "olanzapine", "risperidone", "haloperidol", "clozapine"},
    "insulin": {"insulin"},
    "hypoglycemic": {"glipizide", "glyburide", "glimepiride"},
    "antiplatelet": {"clopidogrel", "prasugrel", "ticagrelor", "aspirin"},
}

DOSE_LIMITS_MG_PER_DAY = {
    # Conservative maximum daily dose references for common medicines.
    "acetaminophen": 4000.0,
    "ibuprofen": 3200.0,
    "naproxen": 1000.0,
    "aspirin": 4000.0,
    "diclofenac": 150.0,
    "meloxicam": 15.0,
    "celecoxib": 400.0,
    "prednisone": 80.0,
    "methylprednisolone": 48.0,
    "dexamethasone": 10.0,
    "warfarin": 15.0,
    "apixaban": 20.0,
    "rivaroxaban": 20.0,
    "dabigatran": 300.0,
    "edoxaban": 60.0,
    "enoxaparin": 200.0,
    "clopidogrel": 75.0,
    "prasugrel": 10.0,
    "ticagrelor": 180.0,
    "lisinopril": 80.0,
    "losartan": 100.0,
    "valsartan": 320.0,
    "olmesartan": 40.0,
    "amlodipine": 10.0,
    "nifedipine": 120.0,
    "diltiazem": 480.0,
    "verapamil": 480.0,
    "metoprolol": 400.0,
    "atenolol": 100.0,
    "carvedilol": 100.0,
    "propranolol": 320.0,
    "hydrochlorothiazide": 50.0,
    "furosemide": 600.0,
    "spironolactone": 200.0,
    "chlorthalidone": 100.0,
    "atorvastatin": 80.0,
    "rosuvastatin": 40.0,
    "simvastatin": 40.0,
    "pravastatin": 80.0,
    "ezetimibe": 10.0,
    "metformin": 2550.0,
    "glipizide": 40.0,
    "glyburide": 20.0,
    "glimepiride": 8.0,
    "empagliflozin": 25.0,
    "dapagliflozin": 10.0,
    "canagliflozin": 300.0,
    "sitagliptin": 100.0,
    "linagliptin": 5.0,
    "levothyroxine": 0.3,
    "omeprazole": 40.0,
    "esomeprazole": 40.0,
    "pantoprazole": 80.0,
    "famotidine": 40.0,
    "ondansetron": 24.0,
    "metoclopramide": 40.0,
    "loperamide": 16.0,
    "docusate": 400.0,
    "senna": 34.4,
    "sertraline": 200.0,
    "fluoxetine": 80.0,
    "escitalopram": 20.0,
    "citalopram": 40.0,
    "paroxetine": 60.0,
    "venlafaxine": 375.0,
    "duloxetine": 120.0,
    "bupropion": 450.0,
    "mirtazapine": 45.0,
    "trazodone": 400.0,
    "quetiapine": 800.0,
    "olanzapine": 20.0,
    "risperidone": 16.0,
    "haloperidol": 20.0,
    "clozapine": 900.0,
    "aripiprazole": 30.0,
    "alprazolam": 10.0,
    "diazepam": 40.0,
    "lorazepam": 10.0,
    "clonazepam": 20.0,
    "zolpidem": 10.0,
    "temazepam": 30.0,
    "eszopiclone": 3.0,
    "ramelteon": 8.0,
    "gabapentin": 3600.0,
    "pregabalin": 600.0,
    "carbamazepine": 1600.0,
    "lamotrigine": 500.0,
    "valproate": 3000.0,
    "levetiracetam": 3000.0,
    "topiramate": 400.0,
    "phenytoin": 600.0,
    "baclofen": 80.0,
    "cyclobenzaprine": 30.0,
    "tizanidine": 36.0,
    "methocarbamol": 6000.0,
    "hydroxyzine": 400.0,
    "diphenhydramine": 300.0,
    "cetirizine": 10.0,
    "loratadine": 10.0,
    "fexofenadine": 180.0,
    "montelukast": 10.0,
    "morphine": 200.0,
    "oxycodone": 160.0,
    "hydrocodone": 120.0,
    "codeine": 360.0,
    "tramadol": 400.0,
    "methadone": 120.0,
    "buprenorphine": 32.0,
    "amoxicillin": 3000.0,
    "azithromycin": 500.0,
    "doxycycline": 200.0,
    "ciprofloxacin": 1500.0,
    "levofloxacin": 750.0,
    "cephalexin": 4000.0,
    "nitrofurantoin": 400.0,
    "acyclovir": 4000.0,
    "valacyclovir": 3000.0,
    "oseltamivir": 150.0,
    "allopurinol": 800.0,
    "colchicine": 1.8,
    "tamsulosin": 0.8,
    "finasteride": 5.0,
    "sildenafil": 100.0,
    "tadalafil": 20.0,
    "donepezil": 10.0,
    "memantine": 20.0,
    "sumatriptan": 200.0,
}

NAME_ALIASES = {
    "valium": "diazepam",
    "xanax": "alprazolam",
    "ativan": "lorazepam",
    "klonopin": "clonazepam",
    "coumadin": "warfarin",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "tylenol": "acetaminophen",
    "norvasc": "amlodipine",
    "lipitor": "atorvastatin",
    "zocor": "simvastatin",
    "crestor": "rosuvastatin",
    "glucophage": "metformin",
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "lexapro": "escitalopram",
    "celexa": "citalopram",
    "wellbutrin": "bupropion",
    "seroquel": "quetiapine",
    "abilify": "aripiprazole",
    "neurontin": "gabapentin",
    "lyrica": "pregabalin",
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "pepcid": "famotidine",
    "lasix": "furosemide",
    "zestril": "lisinopril",
    "cozaar": "losartan",
    "diovan": "valsartan",
    "eliquis": "apixaban",
    "xarelto": "rivaroxaban",
    "plavix": "clopidogrel",
    "brilinta": "ticagrelor",
    "baby aspirin": "aspirin",
}


def _norm_sev(s: str) -> str:
    if not s:
        return "unknown"
    s = s.lower()
    if "high" in s or "major" in s or "contra" in s:
        return "high"
    if "moderate" in s or "significant" in s:
        return "moderate"
    if "low" in s or "minor" in s:
        return "low"
    return "unknown"


def _age_points(age: int) -> float:
    if age >= 85:
        return 3.0
    if age >= 75:
        return 2.0
    if age >= 65:
        return 1.0
    return 0.0


def _polypharmacy_points(med_count: int) -> float:
    if med_count <= 1:
        return 0.0
    if med_count <= 4:
        return (med_count - 1) * 0.5
    if med_count <= 10:
        return 1.5 + (med_count - 4) * 0.8
    return 6.3 + (med_count - 10) * 0.5


def _normalize_name(name: str) -> str:
    n = str(name or "").strip().lower()
    for alias, canonical in NAME_ALIASES.items():
        if alias in n:
            return canonical
    return n


def _dose_to_mg(dose_text: str) -> float | None:
    if not dose_text:
        return None
    t = str(dose_text).lower().strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(mcg|ug|mg|g)\b", t)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    if unit in {"mcg", "ug"}:
        return val / 1000.0
    if unit == "g":
        return val * 1000.0
    return val


def _frequency_multiplier(freq_text: str) -> float:
    if not freq_text:
        return 1.0
    f = str(freq_text).lower()
    if "three times" in f or "tid" in f:
        return 3.0
    if "twice" in f or "bid" in f:
        return 2.0
    if "every 6" in f:
        return 4.0
    if "every 8" in f:
        return 3.0
    if "every 12" in f:
        return 2.0
    if "weekly" in f:
        return 1.0 / 7.0
    return 1.0


def _find_limit_for_name(name: str) -> float | None:
    for drug, lim in DOSE_LIMITS_MG_PER_DAY.items():
        if drug in name:
            return lim
    return None


def _compute_ddi_subscore(
    interactions: List[Dict[str, Any]], per_med_points: Dict[str, float]
) -> Tuple[float, float, List[Dict[str, Any]], int]:
    raw = 0.0
    interaction_items: List[Dict[str, Any]] = []
    high_count = 0

    for it in interactions:
        sev = _norm_sev(it.get("severity", "unknown"))
        pts = SEVERITY_POINTS.get(sev, 2.0)
        raw += pts
        if sev == "high":
            high_count += 1

        a_name = str(it.get("drug_a", "")).lower().strip()
        b_name = str(it.get("drug_b", "")).lower().strip()
        share = pts / 2.0
        if a_name:
            per_med_points[a_name] = per_med_points.get(a_name, 0.0) + share
        if b_name:
            per_med_points[b_name] = per_med_points.get(b_name, 0.0) + share

        interaction_items.append(
            {
                "label": f"{it.get('drug_a', 'Unknown')} + {it.get('drug_b', 'Unknown')} ({sev})",
                "points": round(pts, 2),
            }
        )

    # Interaction burden bonus to scale for many pairs.
    density_bonus = min(8.0, (len(interactions) * 0.6) + (high_count * 1.2))
    if density_bonus > 0:
        raw += density_bonus
        interaction_items.append(
            {"label": f"Interaction burden ({len(interactions)} pairs)", "points": round(density_bonus, 2)}
        )
        interaction_meds = set()
        for it in interactions:
            a_name = str(it.get("drug_a", "")).lower().strip()
            b_name = str(it.get("drug_b", "")).lower().strip()
            if a_name:
                interaction_meds.add(a_name)
            if b_name:
                interaction_meds.add(b_name)
        if interaction_meds:
            share = density_bonus / len(interaction_meds)
            for n in interaction_meds:
                per_med_points[n] = per_med_points.get(n, 0.0) + share

    ddi_score = min(10.0, round((raw / 12.0) * 10.0, 2))
    return ddi_score, raw, interaction_items, high_count


def _compute_dose_subscore(
    meds: List[Dict[str, Any]], per_med_points: Dict[str, float]
) -> Tuple[float, float, List[Dict[str, Any]], bool, int, int, int]:
    raw = 0.0
    modifiers: List[Dict[str, Any]] = []
    extreme_dose_present = False
    known_dose_refs = 0
    parsed_dose_count = 0
    unknown_dose_ref_count = 0

    for m in meds:
        name = _normalize_name(str(m.get("normalized_name") or m.get("raw_name") or ""))
        if not name:
            continue

        per_dose_mg = _dose_to_mg(str(m.get("dose") or ""))
        if per_dose_mg is not None:
            parsed_dose_count += 1

        limit = _find_limit_for_name(name)
        if limit is None:
            if per_dose_mg is not None:
                unknown_dose_ref_count += 1
                daily_mg = per_dose_mg * _frequency_multiplier(str(m.get("frequency") or ""))
                p = 3.0 if daily_mg >= 2000 else 1.5
                raw += p
                modifiers.append(
                    {
                        "label": f"Dose entered but no reference found: {name} ({round(daily_mg, 2)} mg/day)",
                        "points": p,
                    }
                )
                per_med_points[name] = per_med_points.get(name, 0.0) + p
            continue
        known_dose_refs += 1

        if per_dose_mg is None:
            continue
        daily_mg = per_dose_mg * _frequency_multiplier(str(m.get("frequency") or ""))
        ratio = daily_mg / limit if limit > 0 else 0.0

        if ratio >= 3.0:
            p = 10.0
            extreme_dose_present = True
            modifiers.append({"label": f"Extreme dose concern: {name} ({round(daily_mg, 2)} mg/day)", "points": p})
        elif ratio >= 1.5:
            p = 6.0
            modifiers.append({"label": f"High dose concern: {name} ({round(daily_mg, 2)} mg/day)", "points": p})
        elif ratio >= 1.0:
            p = 3.0
            modifiers.append({"label": f"Upper-range dose: {name} ({round(daily_mg, 2)} mg/day)", "points": p})
        else:
            p = 0.0

        raw += p
        if p > 0:
            per_med_points[name] = per_med_points.get(name, 0.0) + p

    dose_score = min(10.0, round((raw / 10.0) * 10.0, 2))
    return dose_score, raw, modifiers, extreme_dose_present, known_dose_refs, parsed_dose_count, unknown_dose_ref_count


def _compute_vulnerability_subscore(
    age: int, meds: List[Dict[str, Any]], per_med_points: Dict[str, float]
) -> Tuple[float, float, List[Dict[str, Any]], bool, bool]:
    raw = 0.0
    modifiers: List[Dict[str, Any]] = []
    high_risk_substance_present = False
    blood_thinner_present = False

    names = [str(m.get("normalized_name") or m.get("raw_name") or "").lower().strip() for m in meds]
    names = [n for n in names if n]
    med_count = len(names)

    age_pts = _age_points(age)
    if age_pts > 0:
        raw += age_pts
        modifiers.append({"label": f"Age modifier ({age})", "points": age_pts})

    unmatched_names = [
        str(m.get("normalized_name") or m.get("raw_name") or "").lower().strip()
        for m in meds
        if not m.get("rxcui")
    ]
    unmatched = len([n for n in unmatched_names if n])
    unmatched_pts = min(5.0, float(unmatched) * 0.8)
    if unmatched_pts > 0:
        raw += unmatched_pts
        modifiers.append({"label": f"Unmatched medication names ({unmatched})", "points": unmatched_pts})
        share = unmatched_pts / unmatched if unmatched > 0 else 0.0
        for n in unmatched_names:
            if n:
                per_med_points[n] = per_med_points.get(n, 0.0) + share

    poly_pts = _polypharmacy_points(med_count)
    if poly_pts > 0:
        raw += poly_pts
        modifiers.append({"label": f"Polypharmacy ({med_count} medicines)", "points": round(poly_pts, 2)})
        share = poly_pts / med_count if med_count > 0 else 0.0
        for n in names:
            per_med_points[n] = per_med_points.get(n, 0.0) + share

    for name in names:
        for substance, pts in HIGH_RISK_SUBSTANCE_POINTS.items():
            if substance in name:
                raw += pts
                high_risk_substance_present = True
                modifiers.append({"label": f"High-risk substance: {substance}", "points": pts})
                per_med_points[name] = per_med_points.get(name, 0.0) + pts
        for risk_class, keywords in RISK_CLASS_KEYWORDS.items():
            if any(k in name for k in keywords):
                pts = RISK_CLASS_POINTS[risk_class]
                raw += pts
                modifiers.append({"label": f"Medicine class risk: {risk_class}", "points": pts})
                per_med_points[name] = per_med_points.get(name, 0.0) + pts
                if risk_class in {"anticoagulant", "antiplatelet"}:
                    blood_thinner_present = True
                break

    sedative_names = [n for n in names if any(k in n for k in SEDATIVE_KEYWORDS)]
    if age >= 65 and sedative_names:
        raw += 1.5
        modifiers.append({"label": "Age 65+ with sedative present", "points": 1.5})
        share = 1.5 / len(sedative_names)
        for n in sedative_names:
            per_med_points[n] = per_med_points.get(n, 0.0) + share

    vuln_score = min(10.0, round((raw / 10.0) * 10.0, 2))
    return vuln_score, raw, modifiers, high_risk_substance_present, blood_thinner_present


def _confidence_label(
    med_count: int,
    matched_count: int,
    known_dose_refs: int,
    parsed_dose_count: int,
    interactions_count: int,
    approx_match_count: int,
    unmatched_count: int,
    unknown_dose_ref_count: int,
) -> str:
    if med_count <= 0:
        return "low"

    match_ratio = matched_count / med_count
    dose_ref_ratio = known_dose_refs / med_count
    dose_parse_ratio = parsed_dose_count / med_count
    approx_ratio = approx_match_count / med_count

    if match_ratio < 0.6:
        return "low"
    if approx_ratio > 0.4:
        return "low"
    if unmatched_count > 0 and match_ratio < 0.8:
        return "low"
    if unknown_dose_ref_count > 0 and dose_ref_ratio < 0.5:
        return "low"

    if med_count == 1:
        if unknown_dose_ref_count > 0:
            return "low"
        if match_ratio == 1.0 and approx_match_count == 0 and dose_ref_ratio >= 1.0 and dose_parse_ratio >= 1.0:
            return "high"
        if match_ratio >= 0.8 and (dose_ref_ratio >= 1.0 or interactions_count > 0):
            return "medium"
        return "low"

    evidence_points = 0
    if interactions_count > 0:
        evidence_points += 2
    if dose_ref_ratio >= 0.6:
        evidence_points += 1
    if dose_parse_ratio >= 0.5:
        evidence_points += 1
    if unmatched_count == 0:
        evidence_points += 1
    if approx_match_count == 0:
        evidence_points += 1

    if match_ratio >= 0.95 and evidence_points >= 4:
        return "high"
    if match_ratio >= 0.75 and evidence_points >= 2:
        return "medium"
    return "low"


def compute_score_breakdown(
    age: int,
    interactions: List[Dict[str, Any]],
    meds: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    meds = meds or []
    med_names = [str(m.get("normalized_name") or m.get("raw_name") or "").lower().strip() for m in meds]
    per_med_points: Dict[str, float] = {n: 0.0 for n in med_names if n}

    ddi_score, ddi_raw, interaction_items, high_interaction_count = _compute_ddi_subscore(interactions, per_med_points)
    dose_score, dose_raw, dose_modifiers, extreme_dose_present, known_dose_refs, parsed_dose_count, unknown_dose_ref_count = _compute_dose_subscore(
        meds, per_med_points
    )
    vuln_score, vuln_raw, vulnerability_modifiers, high_risk_substance_present, blood_thinner_present = _compute_vulnerability_subscore(
        age, meds, per_med_points
    )

    # Weighted blended score.
    weighted_components = [
        {"label": "DDI Risk x 0.50", "points": round(ddi_score * 0.50, 2)},
        {"label": "Dose Safety x 0.30", "points": round(dose_score * 0.30, 2)},
        {"label": "Patient Vulnerability x 0.20", "points": round(vuln_score * 0.20, 2)},
    ]
    blended = sum(x["points"] for x in weighted_components)

    med_count = len([m for m in meds if str(m.get("raw_name") or m.get("normalized_name") or "").strip()])

    # Hard safety floors.
    if high_risk_substance_present:
        blended = max(blended, 7.5)
    if age >= 75 and blood_thinner_present:
        blended = max(blended, 4.2)
    if vuln_score >= 6.0:
        blended = max(blended, 4.0)
    if vuln_score >= 8.0:
        blended = max(blended, 6.0)
    if high_interaction_count >= 1:
        blended = max(blended, 7.0)
    if high_interaction_count >= 2:
        blended = max(blended, 8.5)
    if extreme_dose_present:
        blended = max(blended, 8.8)
    if med_count >= 10:
        blended = max(blended, 6.5)
    if med_count >= 20:
        blended = max(blended, 8.0)
    if med_count >= 50:
        blended = max(blended, 9.0)

    final_score = round(min(10.0, blended), 2)

    matched_count = len([m for m in meds if m.get("rxcui")])
    approx_match_count = len([m for m in meds if "approximate rxnorm match" in str(m.get("note") or "").lower()])
    unmatched_count = med_count - matched_count
    confidence = _confidence_label(
        med_count=med_count,
        matched_count=matched_count,
        known_dose_refs=known_dose_refs,
        parsed_dose_count=parsed_dose_count,
        interactions_count=len(interactions),
        approx_match_count=approx_match_count,
        unmatched_count=unmatched_count,
        unknown_dose_ref_count=unknown_dose_ref_count,
    )

    per_med_impacts = [
        {"label": med, "points": round(pts, 2)}
        for med, pts in sorted(per_med_points.items(), key=lambda kv: kv[1], reverse=True)
    ]

    medication_modifiers = []
    medication_modifiers.extend(vulnerability_modifiers)
    medication_modifiers.extend(dose_modifiers)

    return {
        "interaction_items": interaction_items,
        "interaction_points_total": round(ddi_raw, 2),
        "age_points": round(_age_points(age), 2),
        "medication_modifiers": medication_modifiers,
        "per_med_impacts": per_med_impacts,
        "medication_points_total": round(vuln_raw + dose_raw, 2),
        "ddi_score_0_to_10": round(ddi_score, 2),
        "dose_score_0_to_10": round(dose_score, 2),
        "vulnerability_score_0_to_10": round(vuln_score, 2),
        "weighted_components": weighted_components,
        "confidence": confidence,
        "raw_total": round(ddi_raw + dose_raw + vuln_raw, 2),
        "max_raw": 30.0,
        "scaled_score_0_to_10": final_score,
    }


def compute_score(age: int, interactions: List[Dict[str, Any]], meds: List[Dict[str, Any]] | None = None) -> float:
    breakdown = compute_score_breakdown(age, interactions, meds=meds)
    return breakdown["scaled_score_0_to_10"]


def urgency_from_score(score: float) -> str:
    if score >= 7.5:
        return "RED_URGENT"
    if score >= 4.0:
        return "YELLOW_CALL_SOON"
    return "GREEN_MONITOR"
