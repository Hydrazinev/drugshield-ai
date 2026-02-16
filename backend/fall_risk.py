# fall_risk.py
from typing import List, Dict, Any

SEDATIVE_KEYWORDS = ["alprazolam","diazepam","lorazepam","zolpidem","zopiclone","temazepam","clonazepam","trazodone","melatonin"]
BP_KEYWORDS = ["lisinopril","losartan","amlodipine","hydrochlorothiazide","metoprolol","propranolol","atenolol","diltiazem","enalapril"]
DIURETIC_KEYWORDS = ["furosemide","hydrochlorothiazide","spironolactone","bumetanide"]

def compute_fall_risk(meds: List[Dict[str, Any]]) -> Dict[str, Any]:
    names = [ (m.get("name") or "").lower() for m in meds ]
    reasons = []
    sedative = any(any(k in name for k in SEDATIVE_KEYWORDS) for name in names)
    bp_agent = any(any(k in name for k in BP_KEYWORDS) for name in names)
    diuretic = any(any(k in name for k in DIURETIC_KEYWORDS) for name in names)

    is_high = False
    if sedative and (bp_agent or diuretic):
        is_high = True
        reasons.append("Sedative combined with blood pressure/diuretic medication increases dizziness and fall risk.")
    if sedative and not (bp_agent or diuretic):
        reasons.append("Sedative medication present which can increase drowsiness or balance problems.")
    if bp_agent or diuretic:
        reasons.append("Medication that lowers blood pressure is present and can increase dizziness especially on standing.")

    return {"is_high_risk": is_high, "reasons": reasons}
