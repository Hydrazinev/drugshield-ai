"use client";

import { useEffect, useMemo, useState } from "react";

type MedRow = { name: string; dose: string; frequency: string };

type AnalyzeResponse = {
  api_version: string;
  score_engine_version: string;
  patient_name?: string | null;
  normalized_meds: Array<{
    raw_name: string;
    normalized_name: string;
    rxcui?: string | null;
    note?: string | null;
  }>;
  risk_score_0_to_10: number;
  urgency: "GREEN_MONITOR" | "YELLOW_CALL_SOON" | "RED_URGENT";
  fall_risk: { is_high_risk: boolean; reasons: string[] };
  score_breakdown: {
    interaction_items: Array<{ label: string; points: number }>;
    interaction_points_total: number;
    age_points: number;
    medication_modifiers: Array<{ label: string; points: number }>;
    per_med_impacts: Array<{ label: string; points: number }>;
    medication_points_total: number;
    ddi_score_0_to_10: number;
    dose_score_0_to_10: number;
    vulnerability_score_0_to_10: number;
    weighted_components: Array<{ label: string; points: number }>;
    confidence: "high" | "medium" | "low";
    raw_total: number;
    max_raw: number;
    scaled_score_0_to_10: number;
  };
  llm: {
    patient_summary_simple: string;
    caregiver_summary: string;
    doctor_note: string;
    interaction_explanations: Array<{
      pair: [string, string];
      severity: string;
      simple_explanation: string;
      what_to_watch_for: string[];
      recommended_next_step: string;
    }>;
  };
};

function isValidAnalyzeResponse(data: unknown): data is AnalyzeResponse {
  if (!data || typeof data !== "object") return false;
  const d = data as Record<string, unknown>;
  const sb = d.score_breakdown as Record<string, unknown> | undefined;
  return Boolean(
    typeof d.api_version === "string" &&
      typeof d.score_engine_version === "string" &&
      typeof d.risk_score_0_to_10 === "number" &&
      typeof d.urgency === "string" &&
      sb &&
      typeof sb.ddi_score_0_to_10 === "number" &&
      typeof sb.dose_score_0_to_10 === "number" &&
      typeof sb.vulnerability_score_0_to_10 === "number" &&
      typeof sb.confidence === "string"
  );
}

const COMMON_FREQUENCIES = ["Morning", "Afternoon", "Night"];
const EMPTY_ROW: MedRow = { name: "", dose: "", frequency: "Morning" };

function urgencyLabel(u: AnalyzeResponse["urgency"]) {
  if (u === "RED_URGENT") return "High Risk";
  if (u === "YELLOW_CALL_SOON") return "Moderate Risk";
  return "Low Risk";
}

function urgencyPanelClass(u: AnalyzeResponse["urgency"]) {
  if (u === "RED_URGENT") return "border-red-300 bg-red-50/90 text-red-900";
  if (u === "YELLOW_CALL_SOON") return "border-amber-300 bg-amber-50/90 text-amber-900";
  return "border-emerald-300 bg-emerald-50/90 text-emerald-900";
}

function gaugeClass(u: AnalyzeResponse["urgency"]) {
  if (u === "RED_URGENT") return "from-red-600 to-red-500";
  if (u === "YELLOW_CALL_SOON") return "from-amber-500 to-orange-500";
  return "from-emerald-600 to-emerald-500";
}

function dialStrokeClass(u: AnalyzeResponse["urgency"] | null) {
  if (!u) return "stroke-slate-500";
  if (u === "RED_URGENT") return "stroke-red-600";
  if (u === "YELLOW_CALL_SOON") return "stroke-amber-500";
  return "stroke-emerald-600";
}

function impactTileClass(points: number) {
  if (points >= 50) return "border-red-300 bg-red-100 text-red-900";
  if (points >= 25) return "border-orange-300 bg-orange-100 text-orange-900";
  if (points > 0) return "border-amber-300 bg-amber-100 text-amber-900";
  return "border-emerald-300 bg-emerald-100 text-emerald-900";
}

function medicineImpactTiles(result: AnalyzeResponse) {
  const impacts = result.score_breakdown?.per_med_impacts || [];
  if (impacts.length > 0) {
    const total = impacts.reduce((sum, x) => sum + Number(x.points || 0), 0);
    return impacts.map((x) => {
      const rawPoints = Number(Number(x.points || 0).toFixed(2));
      const contributionPct = total > 0 ? Number(((rawPoints / total) * 100).toFixed(1)) : 0;
      return {
        name: String(x.label || "").toLowerCase(),
        points: rawPoints,
        contributionPct,
      };
    });
  }
  return (result.normalized_meds || []).map((m) => ({
    name: (m.normalized_name || m.raw_name || "").toLowerCase(),
    points: 0,
    contributionPct: 0,
  }));
}

function UrgencyLegendStrip() {
  return (
    <div className="rounded-2xl border border-[var(--line)] bg-white/85 p-2.5">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div className="rounded-xl border border-emerald-300 bg-emerald-100 px-3 py-2 text-sm text-emerald-900">
          <p className="font-semibold">Green</p>
          <p>Monitor</p>
        </div>
        <div className="rounded-xl border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-900">
          <p className="font-semibold">Yellow</p>
          <p>Call doctor soon</p>
        </div>
        <div className="rounded-xl border border-red-300 bg-red-100 px-3 py-2 text-sm text-red-900">
          <p className="font-semibold">Red</p>
          <p>Seek immediate medical advice</p>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const configuredBackend = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [patientNameInput, setPatientNameInput] = useState<string>("");
  const [ageInput, setAgeInput] = useState<string>("82");
  const [rows, setRows] = useState<MedRow[]>([
    { name: "warfarin", dose: "5 mg", frequency: "Morning" },
    { name: "ibuprofen", dose: "4 mg", frequency: "Afternoon" },
    { name: "alprazolam", dose: "0.5 mg", frequency: "Night" },
    { name: "lisinopril", dose: "10 mg", frequency: "Morning" },
  ]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errorText, setErrorText] = useState("");
  const [dialScore, setDialScore] = useState(0);
  const [backend, setBackend] = useState<string>(configuredBackend || "http://127.0.0.1:8000");

  const age = useMemo(() => {
    if (ageInput.trim() === "") return null;
    const parsed = Number(ageInput);
    if (!Number.isFinite(parsed)) return null;
    const normalized = Math.trunc(parsed);
    if (normalized < 1 || normalized > 120) return null;
    return normalized;
  }, [ageInput]);

  const canAnalyze = useMemo(
    () => rows.some((r) => r.name.trim().length > 0) && age !== null,
    [rows, age]
  );
  const scorePct = result ? Math.max(2, Math.min(100, (result.risk_score_0_to_10 / 10) * 100)) : 0;
  const impactTiles = result ? medicineImpactTiles(result) : [];

  useEffect(() => {
    const target = result ? result.risk_score_0_to_10 : 0;
    setDialScore(0);
    const id = window.setTimeout(() => setDialScore(target), 120);
    return () => window.clearTimeout(id);
  }, [result]);

  useEffect(() => {
    const saved = window.localStorage.getItem("drugshield-theme");
    if (saved === "dark" || saved === "light") {
      setTheme(saved);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("drugshield-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (configuredBackend) return;
    let alive = true;
    const candidates = ["http://127.0.0.1:8000", "http://127.0.0.1:8010"];
    (async () => {
      for (const candidate of candidates) {
        try {
          const r = await fetch(`${candidate}/health`);
          if (!r.ok) continue;
          const j = (await r.json()) as Record<string, unknown>;
          if (typeof j.api_version === "string" && typeof j.score_engine_version === "string") {
            if (alive) setBackend(candidate);
            return;
          }
        } catch {
          // continue probing other candidates
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [configuredBackend]);

  function addMedicineRow() {
    setRows([...rows, { ...EMPTY_ROW }]);
  }

  function removeMedicineRow(index: number) {
    if (rows.length <= 1) return;
    setRows(rows.filter((_, i) => i !== index));
  }

  async function analyze() {
    setLoading(true);
    setErrorText("");
    setResult(null);
    if (age === null) {
      setErrorText("Please enter a valid age between 1 and 120.");
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${backend}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_name: patientNameInput.trim() || null, age, meds: rows }),
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = data?.detail;
        if (typeof detail === "string") {
          setErrorText(detail);
        } else if (detail?.message) {
          const bad = Array.isArray(detail.invalid_meds) ? detail.invalid_meds.join(", ") : "";
          setErrorText(bad ? `${detail.message} Invalid: ${bad}` : detail.message);
        } else {
          setErrorText("Could not analyze medications. Please check your entries.");
        }
        return;
      }
      if (!isValidAnalyzeResponse(data)) {
        setErrorText("Backend response is outdated or invalid. Restart backend and try again.");
        return;
      }
      setResult(data);
    } catch {
      setErrorText("Server error while analyzing. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadPdf() {
    if (!result) return;
    setDownloading(true);
    try {
      const nameBase = (result.patient_name || patientNameInput || "")
        .toLowerCase()
        .replace(/[^a-z0-9 _-]/g, "")
        .trim()
        .replace(/\s+/g, "-");
      const fileName = nameBase ? `${nameBase}-drugshield-report.pdf` : "drugshield-report.pdf";

      const payload = {
        ...result,
        patient_name: (result.patient_name || patientNameInput || "").trim() || null,
      };
      const res = await fetch(`${backend}/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to generate PDF");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const dialOffset = circumference - (Math.max(0, Math.min(10, dialScore)) / 10) * circumference;

  return (
    <main className={`app-bg min-h-screen px-4 py-6 md:px-8 md:py-10 ${theme === "dark" ? "theme-dark" : ""}`}>
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rise-in overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--surface)]/95 p-6 shadow-[0_16px_52px_rgba(13,33,41,0.12)] md:p-8">
          <div className="relative">
            <div className="absolute -right-14 -top-16 h-44 w-44 rounded-full bg-[var(--brand-warm)]/25 blur-2xl" />
            <div className="absolute -left-10 bottom-0 h-36 w-36 rounded-full bg-[var(--brand-leaf)]/30 blur-2xl" />
            <p className="relative font-mono text-xs uppercase tracking-[0.18em] text-[var(--brand-ink)]">Hackathon Showcase</p>
            <div className="relative mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className="text-4xl font-bold leading-tight text-[var(--brand-ink)] md:text-5xl">DrugShield AI</h1>
                <p className="mt-3 max-w-3xl text-sm text-slate-700 md:text-base">
                  Live medication risk intelligence with patient-first explanations, caregiver guidance, and clinician handoff report.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
                className="rounded-2xl border border-slate-300 bg-white/90 px-4 py-2 text-sm font-semibold text-slate-800 transition hover:border-slate-500"
              >
                Theme: {theme === "dark" ? "Dark" : "Light"}
              </button>
            </div>
          </div>
          <div className="mt-4">
            <UrgencyLegendStrip />
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="panel-glass rise-in rounded-3xl p-5 lg:col-span-2 lg:p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-[var(--brand-ink)]">Medication Input</h2>
              <button
                type="button"
                onClick={addMedicineRow}
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-500"
              >
                Add medicine
              </button>
            </div>

            <label className="text-sm font-medium text-slate-700">Patient name</label>
            <input
              type="text"
              placeholder="e.g., Vaidik"
              value={patientNameInput}
              onChange={(e) => setPatientNameInput(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2"
            />

            <label className="text-sm font-medium text-slate-700">Patient age</label>
            <input
              type="number"
              min={1}
              max={120}
              value={ageInput}
              onChange={(e) => setAgeInput(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2"
            />

            <div className="mt-4 space-y-3">
              {rows.map((r, i) => (
                <div key={i} className="rounded-2xl border border-slate-200 bg-white p-3">
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                    <input
                      placeholder="Medication"
                      value={r.name}
                      onChange={(e) =>
                        setRows(rows.map((x, idx) => (idx === i ? { ...x, name: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-300 px-3 py-2"
                    />
                    <input
                      placeholder="Dose (e.g., 5 mg)"
                      value={r.dose}
                      onChange={(e) =>
                        setRows(rows.map((x, idx) => (idx === i ? { ...x, dose: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-300 px-3 py-2"
                    />
                    <select
                      value={r.frequency}
                      onChange={(e) =>
                        setRows(rows.map((x, idx) => (idx === i ? { ...x, frequency: e.target.value } : x)))
                      }
                      className="rounded-xl border border-slate-300 bg-white px-3 py-2"
                    >
                      {COMMON_FREQUENCIES.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeMedicineRow(i)}
                    disabled={rows.length <= 1}
                    className="mt-2 rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 disabled:opacity-40"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <button
              onClick={analyze}
              disabled={!canAnalyze || loading}
              className="mt-5 w-full rounded-2xl bg-[linear-gradient(95deg,var(--brand-ink),#1c5d73)] px-4 py-3 font-semibold text-white transition hover:brightness-110 disabled:opacity-60"
            >
              {loading ? "Analyzing..." : "Analyze medication safety"}
            </button>

            {errorText && (
              <div className="mt-4 rounded-2xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{errorText}</div>
            )}
          </div>

          <div className="panel-glass rise-in rounded-3xl p-5 lg:col-span-3 lg:p-6">
            {!result && (
              <div className="flex h-full min-h-[320px] items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 p-6 text-center text-slate-600">
                <div>
                  <p className="text-lg font-semibold text-[var(--brand-ink)]">Ready for analysis</p>
                  <p className="mt-2 text-sm">
                    Enter medications to generate patient-safe guidance.
                  </p>
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-5">
                <div className="rounded-2xl border border-[var(--line)] bg-white/80 px-4 py-3">
                  <p className="text-3xl font-bold text-[var(--brand-ink)] md:text-4xl">
                    {`Hi ${result.patient_name?.trim() || patientNameInput.trim() || "there"}!`}
                  </p>
                  <p className="mt-2 text-xs text-slate-500">
                    API {result.api_version} | Score Engine {result.score_engine_version}
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-[190px_1fr]">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="mx-auto h-[130px] w-[130px]">
                      <svg viewBox="0 0 140 140" className="h-full w-full -rotate-90">
                        <circle cx="70" cy="70" r={radius} className="stroke-slate-200" strokeWidth="12" fill="none" />
                        <circle
                          cx="70"
                          cy="70"
                          r={radius}
                          className={`${dialStrokeClass(result.urgency)} transition-all duration-1000 ease-out`}
                          strokeWidth="12"
                          strokeLinecap="round"
                          fill="none"
                          strokeDasharray={circumference}
                          strokeDashoffset={dialOffset}
                        />
                      </svg>
                    </div>
                    <p className="-mt-20 text-center text-2xl font-bold text-[var(--brand-ink)]">{result.risk_score_0_to_10}</p>
                    <p className="mt-10 text-center text-xs uppercase tracking-[0.16em] text-slate-600">Risk Dial</p>
                  </div>

                  <div className={`rounded-2xl border p-4 ${urgencyPanelClass(result.urgency)}`}>
                    <p className="font-mono text-xs uppercase tracking-[0.16em]">{urgencyLabel(result.urgency)}</p>
                    <p className="mt-2 text-2xl font-bold">Overall Medication Risk: {result.risk_score_0_to_10} / 10</p>
                    <div className="mt-3 h-3 overflow-hidden rounded-full bg-white/80">
                      <div
                        className={`h-3 rounded-full bg-gradient-to-r ${gaugeClass(result.urgency)} transition-all duration-700`}
                        style={{ width: `${scorePct}%` }}
                      />
                    </div>
                    <p className="mt-3 text-sm">Urgency signal for quick triage in patient and caregiver conversations.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Medicine Mix Risk</p>
                    <p className="mt-1 text-xl font-bold text-[var(--brand-ink)]">{result.score_breakdown.ddi_score_0_to_10}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Dose Danger</p>
                    <p className="mt-1 text-xl font-bold text-[var(--brand-ink)]">{result.score_breakdown.dose_score_0_to_10}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Body Sensitivity</p>
                    <p className="mt-1 text-xl font-bold text-[var(--brand-ink)]">{result.score_breakdown.vulnerability_score_0_to_10}</p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-slate-500">How Sure This Is</p>
                    <p className="mt-1 text-xl font-bold capitalize text-[var(--brand-ink)]">{result.score_breakdown.confidence}</p>
                  </div>
                </div>

                {impactTiles.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-[var(--brand-ink)]">Medicine Impact Tiles</h3>
                    <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                      {impactTiles.map((t) => (
                        <div key={t.name} className={`rounded-xl border p-3 ${impactTileClass(t.contributionPct)}`}>
                          <p className="font-semibold capitalize">{t.name}</p>
                          <p className="text-sm">Risk contribution: {t.contributionPct}%</p>
                          <p className="text-xs opacity-80">Raw points: {t.points}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {result.fall_risk?.is_high_risk && (
                  <div className="rounded-2xl border border-orange-300 bg-orange-50 p-4 text-sm text-orange-950">
                    <p className="font-semibold">Increased fall risk detected</p>
                    <ul className="mt-2 list-disc pl-5">
                      {result.fall_risk.reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <h3 className="font-semibold text-[var(--brand-ink)]">Patient View</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{result.llm?.patient_summary_simple}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <h3 className="font-semibold text-[var(--brand-ink)]">Caregiver View</h3>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{result.llm?.caregiver_summary}</p>
                  </div>
                </div>

                {result.llm?.interaction_explanations?.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-lg font-semibold text-[var(--brand-ink)]">What Happens When Taken Together</h3>
                    {result.llm.interaction_explanations.map((item, idx) => {
                      const watch = Array.isArray(item.what_to_watch_for)
                        ? item.what_to_watch_for.join(", ")
                        : String(item.what_to_watch_for || "");
                      return (
                        <div key={idx} className="rounded-2xl border border-slate-200 bg-white p-4 text-sm">
                          <p className="font-semibold text-[var(--brand-ink)]">
                            {item.pair?.[0]} + {item.pair?.[1]} ({item.severity})
                          </p>
                          <p className="mt-2 text-slate-700">{item.simple_explanation}</p>
                          {watch && (
                            <p className="mt-2 text-slate-700">
                              <strong>Watch for:</strong> {watch}
                            </p>
                          )}
                          {item.recommended_next_step && (
                            <p className="mt-1 text-slate-700">
                              <strong>Next step:</strong> {item.recommended_next_step}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="pt-1">
                  <button
                    onClick={downloadPdf}
                    disabled={downloading}
                    className="rounded-2xl border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-800 transition hover:border-slate-600 disabled:opacity-60"
                  >
                    {downloading ? "Preparing PDF..." : "Download PDF Report"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
