# DrugShield AI

Medication risk intelligence for patients, caregivers, and clinicians.

DrugShield AI analyzes a patient medication list and returns:
- a risk score (`0.0` to `10.0`)
- an urgency signal (`GREEN_MONITOR`, `YELLOW_CALL_SOON`, `RED_URGENT`)
- interaction and dose-aware scoring breakdown
- fall-risk flags
- plain-language summaries for patient/caregiver/doctor
- downloadable PDF report

## Why This Exists

Medication lists are hard to reason about quickly, especially for older adults, polypharmacy, and high-risk classes.  
DrugShield AI gives a fast, structured safety snapshot to support better conversations with licensed clinicians.

## Core Features

- RxNorm normalization using RxNav APIs
- Drug-drug interaction scoring
- Dose sanity checks with conservative limits
- Vulnerability scoring (age, polypharmacy, risk classes)
- Confidence label (`high`, `medium`, `low`)
- Fall-risk heuristic detection
- LLM-generated explanations with deterministic local fallback
- One-click PDF export for clinician handoff

## Project Structure

```text
drugshield-ai/
  backend/        # FastAPI risk engine + scoring + report generation
  frontend/       # Next.js app (patient/caregiver facing UI)
  RAILWAY_DEPLOY.md
```

## Architecture

1. User submits age + medicines from frontend.
2. Backend normalizes medicine names via RxNav (`RxCUI`).
3. Backend fetches interaction data from RxNav.
4. Scoring engine computes:
   - DDI subscore
   - Dose subscore
   - Vulnerability subscore
   - weighted final score and urgency
5. Explanation layer returns patient/caregiver/doctor text.
6. Frontend renders results + allows PDF download.

## Tech Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: FastAPI, Pydantic, httpx, ReportLab
- Data source: RxNav (RxNorm + interactions)
- LLM: OpenAI Responses API (with local fallback)

## Local Development

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

Health check:

```text
http://127.0.0.1:8010/health
```

### 2. Frontend

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_BACKEND_URL="http://127.0.0.1:8010"
npm run dev -- -p 3000
```

Open:

```text
http://127.0.0.1:3000
```

## Environment Variables

### Backend

- `OPENAI_API_KEY` (optional but recommended)
- `OPENAI_MODEL` (optional, default is `gpt-5.2`)
- `LLM_TIMEOUT_SECONDS` (optional, default `6.0`)

### Frontend

- `NEXT_PUBLIC_BACKEND_URL` (required in deployment)

## API Endpoints

- `GET /health`
- `GET /debug/scoring-source`
- `POST /analyze`
- `POST /report`

Example `POST /analyze` request body:

```json
{
  "patient_name": "Demo",
  "age": 82,
  "meds": [
    { "name": "warfarin", "dose": "5 mg", "frequency": "Morning" },
    { "name": "ibuprofen", "dose": "400 mg", "frequency": "Afternoon" }
  ]
}
```

## Testing

Run backend regression tests:

```powershell
python -m unittest backend/tests/test_scoring_regression.py
```

## Deployment (Railway)

This repo is preconfigured for Railway with:
- `backend/railway.json`
- `frontend/railway.json`

Full steps:

```text
RAILWAY_DEPLOY.md
```

## Safety Disclaimer

DrugShield AI is decision support only.  
It is **not medical advice** and does not replace clinical judgment.  
Always confirm medication decisions with a licensed clinician.

---

If you are a recruiter, judge, or collaborator: start from `frontend`, run one sample analysis, then inspect `backend/scoring.py` for the scoring engine logic.
