import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring import compute_score_breakdown, urgency_from_score


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "risk_scenarios.json"


class ScoringRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_count(self):
        self.assertGreaterEqual(len(self.scenarios), 30)
        self.assertLessEqual(len(self.scenarios), 50)

    def test_regression_scenarios(self):
        for s in self.scenarios:
            with self.subTest(scenario=s["id"]):
                breakdown = compute_score_breakdown(
                    age=s["age"],
                    interactions=s["interactions"],
                    meds=s["meds"],
                )
                expected = s["expected"]

                self.assertAlmostEqual(
                    breakdown["scaled_score_0_to_10"],
                    expected["score"],
                    places=2,
                    msg=f"Score mismatch for {s['id']}",
                )
                self.assertEqual(
                    urgency_from_score(breakdown["scaled_score_0_to_10"]),
                    expected["urgency"],
                    msg=f"Urgency mismatch for {s['id']}",
                )
                self.assertEqual(
                    breakdown["confidence"],
                    expected["confidence"],
                    msg=f"Confidence mismatch for {s['id']}",
                )
                self.assertAlmostEqual(
                    breakdown["ddi_score_0_to_10"],
                    expected["ddi"],
                    places=2,
                    msg=f"DDI subscore mismatch for {s['id']}",
                )
                self.assertAlmostEqual(
                    breakdown["dose_score_0_to_10"],
                    expected["dose"],
                    places=2,
                    msg=f"Dose subscore mismatch for {s['id']}",
                )
                self.assertAlmostEqual(
                    breakdown["vulnerability_score_0_to_10"],
                    expected["vulnerability"],
                    places=2,
                    msg=f"Vulnerability subscore mismatch for {s['id']}",
                )

    def test_lexapro_extreme_dose_is_high(self):
        breakdown = compute_score_breakdown(
            age=35,
            interactions=[],
            meds=[
                {
                    "raw_name": "Lexapro",
                    "normalized_name": "Lexapro",
                    "rxcui": "352741",
                    "dose": "10000 mg",
                    "frequency": "Morning",
                    "note": None,
                }
            ],
        )
        self.assertGreaterEqual(breakdown["dose_score_0_to_10"], 9.0)
        self.assertGreaterEqual(breakdown["scaled_score_0_to_10"], 8.0)


if __name__ == "__main__":
    unittest.main()
