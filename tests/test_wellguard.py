"""Unit tests on small synthetic frames. Run: .venv/bin/python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import wellguard as wg  # noqa: E402


def daily(uwi: str, oil: list[float], start: str = "2025-06-01") -> pd.DataFrame:
    return pd.DataFrame({"uwi": uwi,
                         "production_date": pd.date_range(start, periods=len(oil)).astype("datetime64[ns]"),
                         "oil_produced_m3": oil})


def fails(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame({"uwi": [u for u, _ in rows],
                         "failure_date": pd.to_datetime([d for _, d in rows]).astype("datetime64[ns]")})


class NormalizeFailureType(unittest.TestCase):
    def test_variants(self):
        cases = {"Rods": "Rods", "Pared rod": "Rods", "|Rod": "Rods", "PCP": "Pump", "Pump": "Pump",
                 "Parted tbg": "Tubing", "TUBING": "Tubing", "Casing": "Other", None: "Other", "": "Other"}
        for raw, want in cases.items():
            self.assertEqual(wg.normalize_failure_type(raw), want, raw)


class SafeRatio(unittest.TestCase):
    def test_zero_and_cap(self):
        r = wg.safe_ratio(pd.Series([1.0, 1.0, 100.0]), pd.Series([2.0, 0.0, 1.0]))
        self.assertEqual(r.iloc[0], 0.5)
        self.assertTrue(np.isnan(r.iloc[1]))
        self.assertEqual(r.iloc[2], 5)


class Baseline(unittest.TestCase):
    def test_lagged_median_ignores_recent_drop(self):
        d = daily("A", [10.0] * 40 + [0.0] * 5)
        base = wg.add_baseline(d)
        self.assertTrue(np.isnan(base.iloc[5]))     # not enough history yet
        self.assertEqual(base.iloc[44], 10.0)      # the 5-day drop is inside the 8-day lag


class DaysToNextFailure(unittest.TestCase):
    def test_strictly_after_and_per_well(self):
        d = pd.concat([daily("A", [1.0] * 5), daily("B", [1.0] * 5)], ignore_index=True)
        out = wg.days_to_next_failure(d, fails([("A", "2025-06-04")]))
        self.assertEqual(out.iloc[:3].tolist(), [3, 2, 1])
        self.assertTrue(out.iloc[3:].isna().all())  # failure day itself and after: none ahead on A
        self.assertTrue(out.iloc[5:].isna().all())  # well B has no failure


class Threshold(unittest.TestCase):
    def test_flags_requested_share(self):
        s = np.arange(1000, dtype=float)
        self.assertEqual((s >= wg.threshold_for_rate(s, 0.02)).sum(), 20)


class FailureShortfall(unittest.TestCase):
    def test_shortfall_and_lead(self):
        oil = [10.0] * 60 + [2.0] * 4  # last 4 days at 20% of normal, failure on the last day
        d = daily("A", oil)
        d["oil_base"] = wg.add_baseline(d)
        d["oil_ratio_3d"] = wg.safe_ratio(d["oil_produced_m3"].rolling(3, min_periods=1).mean(), d["oil_base"])
        d["lost_oil_m3"] = 0.0
        f = fails([("A", str(d["production_date"].iloc[-1].date()))]).assign(
            component="Rods", cause="Fatigue", field_operating_area="X")
        out = wg.failure_shortfall(d, f)
        self.assertAlmostEqual(out.loc[0, "shortfall_m3"], 4 * 8.0)
        # 3-day mean on the 1st low day is (10+10+2)/3 = 7.3 < 8, so all 4 low days count: 3 days before failure
        self.assertEqual(out.loc[0, "lead_days_low"], 3)


class EventMetrics(unittest.TestCase):
    def test_recall_lead_precision(self):
        d = pd.concat([daily("A", [1.0] * 10), daily("B", [1.0] * 10)], ignore_index=True)
        f = fails([("A", "2025-06-09"), ("B", "2025-06-09")])
        d["label"] = wg.days_to_next_failure(d, f).between(1, wg.HORIZON_DAYS).astype(int)
        flag = pd.Series(False, index=d.index)
        flag.iloc[4] = True   # A, 2025-06-05: 4 days before its failure
        flag.iloc[10] = True  # B, 2025-06-01: 8 days before, outside the horizon (false alert)
        m = wg.event_metrics(d, flag, f)
        self.assertEqual(m["failures_in_test"], 2)
        self.assertEqual(m["failures_caught"], 1)
        self.assertEqual(m["median_warning_days"], 4)
        self.assertEqual(m["alert_precision"], 0.5)


if __name__ == "__main__":
    unittest.main()
