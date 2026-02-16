from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class MedicationIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dose: Optional[str] = Field(default=None, max_length=50)
    frequency: Optional[str] = Field(default=None, max_length=50)


class AnalyzeRequest(BaseModel):
    patient_name: Optional[str] = Field(default=None, max_length=60)
    age: int = Field(ge=1, le=120)
    meds: List[MedicationIn] = Field(min_length=1, max_length=100)


class NormalizedMed(BaseModel):
    raw_name: str
    normalized_name: str
    rxcui: Optional[str] = None
    note: Optional[str] = None


class InteractionFact(BaseModel):
    drug_a: str
    drug_b: str
    severity: Literal["high", "moderate", "low", "unknown"]
    source_text: str

class FallRiskOut(BaseModel):
    is_high_risk: bool
    reasons: List[str]

class ScoreLineItem(BaseModel):
    label: str
    points: float

class ScoreBreakdownOut(BaseModel):
    interaction_items: List[ScoreLineItem]
    interaction_points_total: float
    age_points: float
    medication_modifiers: List[ScoreLineItem]
    per_med_impacts: List[ScoreLineItem]
    medication_points_total: float
    ddi_score_0_to_10: float
    dose_score_0_to_10: float
    vulnerability_score_0_to_10: float
    weighted_components: List[ScoreLineItem]
    confidence: Literal["high", "medium", "low"]
    raw_total: float
    max_raw: float
    scaled_score_0_to_10: float


class AnalyzeResponse(BaseModel):
    api_version: str
    score_engine_version: str
    patient_name: Optional[str] = None
    normalized_meds: List[NormalizedMed]
    interactions: List[InteractionFact]
    risk_score_0_to_10: float
    urgency: Literal["GREEN_MONITOR", "YELLOW_CALL_SOON", "RED_URGENT"]
    fall_risk: FallRiskOut
    score_breakdown: ScoreBreakdownOut
    llm: dict
    disclaimer: str
