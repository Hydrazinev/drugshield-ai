# llm_explain.py
import os
import json
from typing import Any, Dict, List

GENERIC_WATCH = ["Dizziness", "Sleepiness", "Stomach upset", "Any unusual symptoms"]


def _is_not_specified(value: Any) -> bool:
    txt = str(value or "").strip().lower()
    return txt in {"", "not specified in the data", "not specified", "n/a", "na", "none", "null"}


def _default_explanation_card(med_names: List[str], interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    if interactions:
        it = interactions[0]
        a = it.get("drug_a") or it.get("drugA") or "Medicine A"
        b = it.get("drug_b") or it.get("drugB") or "Medicine B"
        sev = str(it.get("severity") or "unknown").lower()
        src = str(it.get("source_text") or "").strip()
        simple = src if src else f"When taken together, {a} and {b} may increase side effects."
        return {
            "pair": [a, b],
            "severity": sev,
            "simple_explanation": simple,
            "what_to_watch_for": GENERIC_WATCH,
            "recommended_next_step": "Report symptoms and ask your clinician or pharmacist to review this combination.",
        }
    if len(med_names) >= 2:
        return {
            "pair": [med_names[0], med_names[1]],
            "severity": "unknown",
            "simple_explanation": f"No confirmed interaction pair was returned for {med_names[0]} and {med_names[1]} in the checked data source.",
            "what_to_watch_for": GENERIC_WATCH,
            "recommended_next_step": "Ask your clinician or pharmacist to verify this pair, especially if symptoms are present.",
        }
    if med_names:
        return {
            "pair": [med_names[0], "your body"],
            "severity": "low",
            "simple_explanation": f"{med_names[0]} can still cause side effects by itself, even without a detected pair interaction.",
            "what_to_watch_for": GENERIC_WATCH,
            "recommended_next_step": "If symptoms appear or worsen, contact your clinician or pharmacist.",
        }
    return {
        "pair": ["None", "None"],
        "severity": "low",
        "simple_explanation": "No medication details were provided.",
        "what_to_watch_for": [],
        "recommended_next_step": "Provide at least one valid medication name.",
    }

# Local fallback builder (keeps demo resilient)
def _build_local_explanation(bundle: Dict[str, Any]) -> Dict[str, Any]:
    patient_age = bundle.get("patient", {}).get("age", "Not specified")
    meds = bundle.get("medications", [])
    interactions = bundle.get("interactions", [])
    score_block = bundle.get("score", {}) if isinstance(bundle.get("score", {}), dict) else {}
    final_score = score_block.get("final_score")
    breakdown = score_block.get("breakdown", {}) if isinstance(score_block.get("breakdown", {}), dict) else {}
    med_mods = breakdown.get("medication_modifiers", []) if isinstance(breakdown.get("medication_modifiers", []), list) else []
    extreme_dose_flags = [m for m in med_mods if "Extreme dose concern" in str(m.get("label", ""))]

    med_names = [m.get("raw_name") or m.get("name") or m.get("normalized_name") or "Unknown" for m in meds]
    meds_text = ", ".join(med_names) if med_names else "No medications provided."

    patient_summary_simple = f"🙂 You are {patient_age} and these medicines were listed: {meds_text}. "
    if extreme_dose_flags:
        patient_summary_simple += "⚠ A dose in this list looks very high for at least one medicine, so please contact a clinician or pharmacist urgently to verify it."
    elif isinstance(final_score, (int, float)) and float(final_score) >= 7.5:
        patient_summary_simple += "⚠ This report suggests high overall risk, so please seek clinical advice soon."
    else:
        patient_summary_simple += "Quick note: some combinations can cause extra side effects, so keep an eye on how you feel and check with your clinician."

    caregiver_summary = (
        f"Age {patient_age}. Meds: {meds_text}. Some combinations may increase bleeding, dizziness, or sleepiness. "
        "Bring this report to the clinician."
    )

    doctor_note = (
        f"Automated DrugShield AI report for patient age {patient_age}.\n"
        f"Medications: {meds_text}.\nInteractions detected: {len(interactions)}. See details."
    )

    interaction_explanations = []
    for it in interactions:
        a = it.get("drug_a") or it.get("drugA") or it.get("a") or it.get("name_a") or "Unknown"
        b = it.get("drug_b") or it.get("drugB") or it.get("b") or it.get("name_b") or "Unknown"
        severity = it.get("severity") or "unknown"
        source_text = str(it.get("source_text") or "").strip()
        if source_text:
            simple_ex = f"When taken together, {a} and {b} can cause this: {source_text}"
        else:
            simple_ex = f"When taken together, {a} and {b} may increase side effects in the body."
        interaction_explanations.append({
            "pair": [a, b],
            "severity": severity,
            "simple_explanation": simple_ex,
            "what_to_watch_for": ["Dizziness", "Bleeding", "Excessive sleepiness"],
            "recommended_next_step": "Contact clinician to review medications."
        })

    if not interaction_explanations:
        if len(med_names) >= 2:
            interaction_explanations.append({
                "pair": [med_names[0], med_names[1]],
                "severity": "unknown",
                "simple_explanation": f"No confirmed interaction pair was returned for {med_names[0]} and {med_names[1]} in the checked data source.",
                "what_to_watch_for": ["Dizziness", "Sleepiness", "Stomach upset", "Any unusual symptoms"],
                "recommended_next_step": "Ask your clinician or pharmacist to verify this pair, especially if symptoms are present."
            })
        elif med_names:
            interaction_explanations.append({
                "pair": [med_names[0], "your body"],
                "severity": "low",
                "simple_explanation": f"{med_names[0]} can still cause side effects on its own, even without drug-drug interactions.",
                "what_to_watch_for": ["Dizziness", "Sleepiness", "Stomach upset", "Any unusual symptoms"],
                "recommended_next_step": "Use as prescribed and report new or worsening symptoms to a clinician."
            })
        else:
            interaction_explanations.append({
                "pair": ["None", "None"],
                "severity": "low",
                "simple_explanation": "No interactions were found in the checked datasets for the provided medications.",
                "what_to_watch_for": [],
                "recommended_next_step": "Continue monitoring and consult clinician if symptoms develop."
            })

    return {
        "patient_summary_simple": patient_summary_simple,
        "caregiver_summary": caregiver_summary,
        "doctor_note": doctor_note,
        "interaction_explanations": interaction_explanations,
        "disclaimer": "Decision support only. Not medical advice."
    }

def _ensure_explanation_shape(bundle: Dict[str, Any], out: Dict[str, Any]) -> Dict[str, Any]:
    meds = bundle.get("medications", []) or []
    interactions = bundle.get("interactions", []) or []
    med_names = [
        m.get("raw_name") or m.get("name") or m.get("normalized_name") or "Unknown"
        for m in meds
    ]
    exps = out.get("interaction_explanations")
    if not isinstance(exps, list):
        exps = []

    cleaned: List[Dict[str, Any]] = []
    for e in exps:
        if not isinstance(e, dict):
            continue

        pair = e.get("pair")
        if not isinstance(pair, list) or len(pair) < 2:
            pair = ["Not specified in the data", "Not specified in the data"]
        a = pair[0]
        b = pair[1]
        sev = e.get("severity") or "unknown"
        simple = e.get("simple_explanation")
        watch = e.get("what_to_watch_for")
        step = e.get("recommended_next_step")

        whole_placeholder = (
            _is_not_specified(a)
            and _is_not_specified(b)
            and _is_not_specified(sev)
            and _is_not_specified(simple)
            and _is_not_specified(step)
        )
        if whole_placeholder:
            cleaned.append(_default_explanation_card(med_names, interactions))
            continue

        if _is_not_specified(simple):
            simple = _default_explanation_card(med_names, interactions)["simple_explanation"]
        if not isinstance(watch, list) or len(watch) == 0:
            watch = _default_explanation_card(med_names, interactions)["what_to_watch_for"]
        if _is_not_specified(step):
            step = _default_explanation_card(med_names, interactions)["recommended_next_step"]

        cleaned.append(
            {
                "pair": [a or "Not specified in the data", b or "Not specified in the data"],
                "severity": str(sev or "unknown"),
                "simple_explanation": str(simple),
                "what_to_watch_for": watch,
                "recommended_next_step": str(step),
            }
        )

    if not cleaned:
        cleaned = [_default_explanation_card(med_names, interactions)]

    out["interaction_explanations"] = cleaned
    return out

# Compatibility build_facts_bundle used by main.py
def build_facts_bundle(*args, **kwargs):
    if args and isinstance(args[0], dict) and len(args) == 1:
        return args[0]
    age = kwargs.get("age") if "age" in kwargs else (args[0] if len(args) > 0 else None)
    meds = kwargs.get("meds") if "meds" in kwargs else (args[1] if len(args) > 1 else [])
    interactions = kwargs.get("interactions") if "interactions" in kwargs else (args[2] if len(args) > 2 else [])
    score = kwargs.get("score") if "score" in kwargs else (args[3] if len(args) > 3 else {})
    if meds is None:
        meds = []
    if interactions is None:
        interactions = []
    if score is None:
        score = {}
    return {"patient": {"age": age}, "medications": meds, "interactions": interactions, "score": score}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "6.0"))

# Try to import OpenAI SDK
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False


def _call_responses_api_interactions_only(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Dedicated GPT call for 'What Happens When Taken Together' cards.
    Returns only interaction_explanations list.
    """
    client = OpenAI(api_key=OPENAI_API_KEY, timeout=LLM_TIMEOUT_SECONDS, max_retries=0)
    system = (
        "You are DrugShield AI. Use only facts in provided JSON. "
        "Return only a JSON array. Each item must contain keys: "
        "pair (two-item array), severity, simple_explanation, what_to_watch_for, recommended_next_step. "
        "For each pair, explain what happens when both medicines are taken together in plain language. "
        "Do not output markdown or extra text. "
        "If interaction evidence is missing, still provide a conservative practical explanation and monitoring guidance. "
        "Do not provide advice to start/stop medicines."
    )
    user = f"Facts:\n{json.dumps(bundle, ensure_ascii=False)}"
    resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text={"format": {"type": "text"}},
    )

    text_output = None
    if hasattr(resp, "output_text") and resp.output_text:
        text_output = resp.output_text
    else:
        try:
            j = resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)
        except Exception:
            j = dict(resp)
        if "output" in j and isinstance(j["output"], list) and j["output"]:
            out_item = j["output"][0]
            if isinstance(out_item, dict):
                for c in out_item.get("content", []):
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        text_output = c.get("text")
                        break
                    if isinstance(c, dict) and "text" in c:
                        text_output = c.get("text")
                        break

    if not text_output:
        raise RuntimeError("No interaction explanations returned from Responses API")

    parsed = json.loads(text_output)
    if not isinstance(parsed, list):
        raise RuntimeError("Interaction explanations response was not a JSON array")
    return parsed

def _call_responses_api(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try the Responses API (modern SDK). Request plain JSON output from model.
    If the SDK expects 'text.format.name' or similar, we still try and fall back.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, timeout=LLM_TIMEOUT_SECONDS, max_retries=0)
        system = (
            "You are DrugShield AI. You MUST ONLY use the facts in the provided JSON. "
            "Return a single JSON object and nothing else with the keys: "
            "patient_summary_simple, caregiver_summary, doctor_note, interaction_explanations, disclaimer. "
            "interaction_explanations must be a list of objects with pair (two item array), severity, simple_explanation, what_to_watch_for, recommended_next_step. "
            "All text must be short and simple for patients and caregivers. "
            "For patient_summary_simple only, use a calm and reassuring tone with 1-2 friendly emojis and a lightly funny style that reduces anxiety. "
            "Do not joke about harm, death, or emergencies. Keep it respectful and safe. "
            "For each simple_explanation, clearly explain what is happening in the body in plain language, without jargon. "
            "Example style: 'These two medicines can make you more sleepy and dizzy.' "
            "If score.breakdown.medication_modifiers includes an 'Extreme dose concern' item, clearly mention that as urgent safety context in patient_summary_simple and caregiver_summary. "
            "If a fact is missing, use 'Not specified in the data' only for that field. "
            "Never return an interaction card where pair, severity, simple_explanation, what_to_watch_for, and recommended_next_step are all 'Not specified in the data'. "
            "If exact evidence is limited, still provide a safe generic explanation and practical watch-for symptoms. "
            "Do not provide clinical advice to start/stop medicines. Use conservative language."
        )
        user = f"Facts:\n{json.dumps(bundle, ensure_ascii=False)}"

        # Attempt Responses API call
        resp = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            # ask for text output; SDKs vary so we avoid complex format settings
            text={"format": {"type": "text"}}
        )

        # Try multiple ways to extract output text
        text_output = None
        if hasattr(resp, "output_text") and resp.output_text:
            text_output = resp.output_text
        else:
            try:
                j = resp.to_dict() if hasattr(resp, "to_dict") else dict(resp)
            except Exception:
                j = dict(resp)
            # Look inside common fields
            if "output" in j and isinstance(j["output"], list) and j["output"]:
                # each item may contain 'content' which is a list
                out_item = j["output"][0]
                if isinstance(out_item, dict):
                    # iterate content list
                    for c in out_item.get("content", []):
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            text_output = c.get("text")
                            break
                        if isinstance(c, dict) and "text" in c:
                            text_output = c.get("text")
                            break
            if not text_output and "choices" in j and isinstance(j["choices"], list) and j["choices"]:
                ch = j["choices"][0]
                if isinstance(ch, dict) and "message" in ch:
                    msg = ch["message"]
                    if isinstance(msg, dict) and "content" in msg:
                        if isinstance(msg["content"], str):
                            text_output = msg["content"]
                        else:
                            # content could be list
                            try:
                                text_output = json.dumps(msg["content"], ensure_ascii=False)
                            except Exception:
                                pass

        if text_output:
            # Try to parse JSON
            try:
                parsed = json.loads(text_output)
                return parsed
            except Exception:
                # If not JSON, give up and fall back
                pass

    except Exception as e:
        print("Responses API call failed:", str(e))

    raise RuntimeError("Responses API call did not return valid JSON")

def _call_chat_completion(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback to classic ChatCompletion API for broader compatibility."""
    try:
        import openai
        openai.api_key = OPENAI_API_KEY
        system = (
            "You are DrugShield AI. Only use the facts in the JSON. Return a single JSON object only with the keys: "
            "patient_summary_simple, caregiver_summary, doctor_note, interaction_explanations, disclaimer. "
            "interaction_explanations must be a list of objects with pair (two item array), severity, simple_explanation, what_to_watch_for, recommended_next_step."
            "For patient_summary_simple only, use a calm and reassuring tone with 1-2 friendly emojis and a lightly funny style that reduces anxiety. "
            "Do not joke about harm, death, or emergencies. Keep it respectful and safe. "
            "Keep language simple and short. Explain what is happening in the body in plain language and avoid jargon."
            "If score.breakdown.medication_modifiers includes an 'Extreme dose concern' item, clearly mention that as urgent safety context in patient_summary_simple and caregiver_summary. "
            "If a fact is missing, use 'Not specified in the data' only for that field. "
            "Never return an interaction card where all fields are 'Not specified in the data'. "
            "If exact evidence is limited, still provide a safe generic explanation and practical watch-for symptoms."
        )
        user = f"Facts:\n{json.dumps(bundle, ensure_ascii=False)}"
        # Compose message
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
        # Call with the chat endpoint
        resp = openai.ChatCompletion.create(model=MODEL, messages=messages, temperature=0.0, max_tokens=800)
        # Extract text
        text = resp["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        return parsed
    except Exception as e:
        print("ChatCompletion call failed:", str(e))
        raise RuntimeError("ChatCompletion did not return valid JSON")

def explain_with_llm(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Public function. Tries: Responses API -> local fallback
    Always returns a dict matching expected schema.
    """
    # Quick local fallback if no key or SDK
    if not OPENAI_API_KEY:
        return _ensure_explanation_shape(bundle, _build_local_explanation(bundle))

    # Try Responses API if SDK is present
    out: Dict[str, Any] = _build_local_explanation(bundle)
    if _OPENAI_AVAILABLE:
        try:
            out = _call_responses_api(bundle)
        except Exception:
            # If the API is slow/unreachable, fail fast to local fallback.
            pass

    # Always try a dedicated GPT pass for pair explanations when key+SDK are available.
    # If this fails, keep whichever explanations already exist in `out`.
    if _OPENAI_AVAILABLE:
        try:
            out["interaction_explanations"] = _call_responses_api_interactions_only(bundle)
        except Exception:
            pass

    return _ensure_explanation_shape(bundle, out)
