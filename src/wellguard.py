"""WellGuard: pre-failure production loss and 7-day failure-risk backtest.

Run: .venv/bin/python src/wellguard.py   (reads data/*.parquet, writes outputs/)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs"

M3_TO_BBL = 6.2898
HORIZON_DAYS = 7          # predict a failure in (d, d + 7]
BASELINE_LAG_DAYS = 8     # baseline window ends 8 days before d, so the decline itself is not in it
BASELINE_WINDOW_DAYS = 30
PRE_FAILURE_DAYS = 14     # shortfall window before a failure
LOW_RATIO = 0.8           # "below 80% of baseline"
STUDY_START = pd.Timestamp("2025-05-01")  # failure log is near-empty before Q2 2025
TEST_START = pd.Timestamp("2026-03-01")   # time split: train before, test from here
ALERT_RATE = 0.02         # share of producing well-days the model is allowed to flag

DAILY_COLS = [
    "uwi", "well_name", "field_operating_area", "surface_latitude", "surface_longitude",
    "on_production_date", "well_daily_status", "production_date", "hours_on_prod", "hours_down",
    "lost_oil_m3", "oil_produced_m3", "gas_produced_e3m3", "water_produced_m3",
    "tubing_pressure_kpa", "casing_pressure_kpa", "pump_efficiency_pct", "pcp_pump_make",
    "pcp_pump_rpm", "pcp_pump_electric_current_a", "pcp_pump_rod_torque_ftlb",
    "pcp_pump_displacement_m3d100rpm",
]


def normalize_failure_type(raw: object) -> str:
    """Collapse the free-typed failure_type column into Rods / Pump / Tubing / Other."""
    if not isinstance(raw, str) or not raw.strip():
        return "Other"
    s = raw.lower()
    if "rod" in s or "corod" in s:
        return "Rods"
    if "pump" in s or "pcp" in s:
        return "Pump"
    if "tub" in s or "tbg" in s:
        return "Tubing"
    return "Other"


def load_failures(path: Path = DATA / "production_failures.parquet") -> pd.DataFrame:
    f = pd.read_parquet(path)
    f["failure_date"] = pd.to_datetime(f["failure_start_date"]).astype("datetime64[ns]")
    f["component"] = f["failure_type"].map(normalize_failure_type)
    f = f.drop_duplicates(["uwi", "failure_date", "component"])
    return f.sort_values(["uwi", "failure_date"]).reset_index(drop=True)


def load_jobs(path: Path = DATA / "well_jobs.parquet") -> pd.DataFrame:
    j = pd.read_parquet(path, columns=["uwi", "job_category", "start_date", "end_date",
                                       "job_duration_days", "field_est_total"])
    j["start_date"] = pd.to_datetime(j["start_date"]).astype("datetime64[ns]")
    return j


def load_daily(fields: list[str], path: Path = DATA / "daily_production.parquet") -> pd.DataFrame:
    """Producing-well days in the failure-reporting fields, from 45 days before STUDY_START."""
    d = pd.read_parquet(path, columns=DAILY_COLS,
                        filters=[("field_operating_area", "in", fields)])
    d["production_date"] = pd.to_datetime(d["production_date"]).astype("datetime64[ns]")
    for col in DAILY_COLS[8:]:
        if col != "pcp_pump_make":  # some numeric columns are stored as decimal
            d[col] = pd.to_numeric(d[col], errors="coerce").astype(float)
    d = d[d["production_date"] >= STUDY_START - pd.Timedelta(days=45)]
    d = d[d["well_daily_status"] == "Producing"].drop_duplicates(["uwi", "production_date"]).copy()
    # tubing pressure has placeholder values such as 999999 (handbook)
    d.loc[d["tubing_pressure_kpa"] > 50_000, "tubing_pressure_kpa"] = np.nan
    return d.sort_values(["uwi", "production_date"]).reset_index(drop=True)


def add_baseline(d: pd.DataFrame, col: str = "oil_produced_m3") -> pd.Series:
    """Per-well median of `col` over days [d-38, d-8]: the well's normal rate before any recent decline."""
    return (d.groupby("uwi")[col]
             .transform(lambda s: s.shift(BASELINE_LAG_DAYS)
                        .rolling(BASELINE_WINDOW_DAYS, min_periods=10).median()))


def safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den.where(den > 0)).clip(upper=5)


def build_features(d: pd.DataFrame, failures: pd.DataFrame, jobs: pd.DataFrame) -> pd.DataFrame:
    """One row per producing well-day; every feature uses only data up to and including that day."""
    g = d.groupby("uwi")
    d["oil_base"] = add_baseline(d)
    d["oil_ratio_1d"] = safe_ratio(d["oil_produced_m3"], d["oil_base"])
    for w in (3, 7):
        d[f"oil_ratio_{w}d"] = safe_ratio(
            g["oil_produced_m3"].transform(lambda s: s.rolling(w, min_periods=1).mean()), d["oil_base"])
        d[f"hours_on_{w}d"] = g["hours_on_prod"].transform(lambda s: s.rolling(w, min_periods=1).mean())
    liquid = d["oil_produced_m3"] + d["water_produced_m3"]
    d["water_cut"] = d["water_produced_m3"] / liquid.where(liquid > 0)
    d["water_cut_delta_7d"] = d["water_cut"] - g["water_cut"].transform(lambda s: s.shift(7))
    for col, name in [("gas_produced_e3m3", "gas"), ("pcp_pump_rod_torque_ftlb", "torque"),
                      ("pcp_pump_electric_current_a", "current"), ("pump_efficiency_pct", "eff"),
                      ("pcp_pump_rpm", "rpm")]:
        d[f"{name}_ratio"] = safe_ratio(d[col], add_baseline(d, col))
    d["well_age_years"] = (d["production_date"] - pd.to_datetime(d["on_production_date"])).dt.days / 365.25
    d["field_code"] = d["field_operating_area"].astype("category").cat.codes
    d["pump_make_code"] = d["pcp_pump_make"].astype("category").cat.codes

    d = add_event_history(d, failures, jobs)
    d["label"] = days_to_next_failure(d, failures).between(1, HORIZON_DAYS).astype(int)
    return d


def _days_since_last(d: pd.DataFrame, events: pd.DataFrame, date_col: str) -> pd.Series:
    """Days since the most recent event on the same well, on or before each row's date."""
    left = d[["uwi", "production_date"]].reset_index()
    right = (events[["uwi", date_col]].dropna().rename(columns={date_col: "event_date"})
             .sort_values("event_date"))
    m = pd.merge_asof(left.sort_values("production_date"), right, left_on="production_date",
                      right_on="event_date", by="uwi", direction="backward")
    return m.set_index("index")["production_date"].sub(m.set_index("index")["event_date"]).dt.days.reindex(d.index)


def days_to_next_failure(d: pd.DataFrame, failures: pd.DataFrame) -> pd.Series:
    """Days from each row's date to the next failure on the same well, strictly after it (NaN if none)."""
    left = d[["uwi", "production_date"]].reset_index()
    left["probe"] = left["production_date"] + pd.Timedelta(days=1)
    right = failures[["uwi", "failure_date"]].sort_values("failure_date")
    m = pd.merge_asof(left.sort_values("probe"), right, left_on="probe", right_on="failure_date",
                      by="uwi", direction="forward")
    return m.set_index("index")["failure_date"].sub(m.set_index("index")["production_date"]).dt.days.reindex(d.index)


def add_event_history(d: pd.DataFrame, failures: pd.DataFrame, jobs: pd.DataFrame) -> pd.DataFrame:
    d["days_since_failure"] = _days_since_last(d, failures, "failure_date")
    d["days_since_rod_job"] = _days_since_last(d, jobs[jobs["job_category"] == "Rod Truck"], "start_date")
    # failures on this well in the prior 365 days (rolling count of event dates)
    counts = []
    fail_by_well = failures.groupby("uwi")["failure_date"].apply(lambda s: s.values)
    for uwi, dates in d.groupby("uwi")["production_date"]:
        fd = fail_by_well.get(uwi, np.array([], dtype="datetime64[ns]"))
        v = dates.values
        counts.append(pd.Series(np.searchsorted(fd, v, side="right")
                                - np.searchsorted(fd, v - np.timedelta64(365, "D"), side="right"),
                                index=dates.index))
    d["failures_prior_365d"] = pd.concat(counts).reindex(d.index)
    return d


FEATURES = [
    "oil_ratio_1d", "oil_ratio_3d", "oil_ratio_7d", "hours_on_3d", "hours_on_7d", "hours_down",
    "water_cut", "water_cut_delta_7d", "gas_ratio", "torque_ratio", "current_ratio", "eff_ratio",
    "rpm_ratio", "pcp_pump_rpm", "pump_efficiency_pct", "tubing_pressure_kpa", "casing_pressure_kpa",
    "pcp_pump_displacement_m3d100rpm", "well_age_years", "field_code", "pump_make_code",
    # days_since_rod_job is left out: the repair job is often logged days before failure_start_date (leak)
    "days_since_failure", "failures_prior_365d",
]


def failure_shortfall(d: pd.DataFrame, failures: pd.DataFrame) -> pd.DataFrame:
    """Per failure: oil below baseline in the PRE_FAILURE_DAYS before and on the failure date, and lead time.

    lead_days_low = days before the failure that the 3-day oil ratio first dropped under LOW_RATIO
    (within the window, continuously up to the failure). 0 means it only dropped on the failure day.
    """
    idx = d.set_index(["uwi", "production_date"])[["oil_produced_m3", "oil_base", "oil_ratio_3d", "lost_oil_m3"]]
    rows = []
    for f in failures.itertuples():
        days = pd.date_range(f.failure_date - pd.Timedelta(days=PRE_FAILURE_DAYS), f.failure_date)
        try:
            w = idx.loc[f.uwi].reindex(days)
        except KeyError:
            continue
        if w["oil_base"].notna().sum() < PRE_FAILURE_DAYS // 2:
            continue
        base = w["oil_base"].ffill().bfill()
        oil = w["oil_produced_m3"].fillna(0)  # a missing producing day means no oil reported
        low = (w["oil_ratio_3d"] < LOW_RATIO).to_numpy()[::-1]
        lead = int(np.argmin(low)) - 1 if not low.all() else PRE_FAILURE_DAYS
        rows.append({"uwi": f.uwi, "failure_date": f.failure_date, "component": f.component,
                     "cause": f.cause, "field": f.field_operating_area,
                     "shortfall_m3": float((base - oil).clip(lower=0).sum()),
                     "lost_oil_logged_m3": float(w["lost_oil_m3"].fillna(0).sum()),
                     "lead_days_low": max(lead, 0)})
    return pd.DataFrame(rows)


def attach_repair_cost(fs: pd.DataFrame, jobs: pd.DataFrame) -> pd.DataFrame:
    """Field cost estimate of the first job on the well from 3 days before to 21 days after the failure."""
    j = jobs.dropna(subset=["start_date"]).sort_values("start_date")
    m = pd.merge_asof(fs.assign(probe=fs["failure_date"] - pd.Timedelta(days=3)).sort_values("probe"),
                      j[["uwi", "start_date", "job_category", "job_duration_days", "field_est_total"]],
                      left_on="probe", right_on="start_date", by="uwi", direction="forward",
                      tolerance=pd.Timedelta(days=24))
    return m.drop(columns="probe")


def threshold_for_rate(scores: np.ndarray, rate: float) -> float:
    """Score cut-off that flags the top `rate` share of rows."""
    return float(np.quantile(scores, 1 - rate))


def event_metrics(test: pd.DataFrame, flag: pd.Series, failures: pd.DataFrame) -> dict:
    """Failure-level recall and lead time: a failure is caught if any of its prior 7 well-days was flagged."""
    t = test.assign(flag=flag.values, dtn=days_to_next_failure(test, failures))
    w = t[t["dtn"].between(1, HORIZON_DAYS)].copy()
    w["failure_date"] = w["production_date"] + pd.to_timedelta(w["dtn"], unit="D")
    per = w.groupby(["uwi", "failure_date"]).agg(caught=("flag", "max"),
                                                 lead=("dtn", lambda s: s[w.loc[s.index, "flag"]].max()))
    caught = per[per["caught"]]
    return {
        "failures_in_test": int(len(per)),
        "failures_caught": int(len(caught)),
        "event_recall": float(len(caught) / max(len(per), 1)),
        "median_warning_days": float(caught["lead"].median()) if len(caught) else 0.0,
        "alert_precision": float(t.loc[t["flag"], "label"].mean()) if t["flag"].any() else 0.0,
        "alerts_per_day": float(t["flag"].sum() / t["production_date"].nunique()),
    }


def run() -> dict:
    OUT.mkdir(exist_ok=True)
    failures = load_failures()
    jobs = load_jobs()
    daily = load_daily(sorted(failures["field_operating_area"].dropna().unique()))
    feats = build_features(daily, failures, jobs)

    # --- 1. Business case: what failures cost -------------------------------------------------
    study_fail = failures[failures["failure_date"] >= STUDY_START]
    fs = attach_repair_cost(failure_shortfall(feats, study_fail), jobs)
    fs.to_csv(OUT / "failure_shortfall.csv", index=False)

    healthy = feats[(feats["production_date"] >= STUDY_START) & feats["oil_ratio_3d"].notna()]
    healthy = healthy[~(days_to_next_failure(healthy, failures) <= 45)]
    healthy = healthy[~(healthy["days_since_failure"] <= 45)]
    healthy_low_share = float((healthy["oil_ratio_3d"] < LOW_RATIO).mean())

    # --- 2. Model: time-split backtest -------------------------------------------------------
    m = feats[(feats["production_date"] >= STUDY_START)
              & (feats["production_date"] <= failures["failure_date"].max() - pd.Timedelta(days=HORIZON_DAYS))
              & feats["oil_base"].notna()]
    m = m[~(m["days_since_failure"].between(0, HORIZON_DAYS))]  # skip the repair week itself
    train = m[m["production_date"] < TEST_START - pd.Timedelta(days=HORIZON_DAYS)]  # gap stops label leak
    test = m[m["production_date"] >= TEST_START]

    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                         l2_regularization=1.0, class_weight="balanced", random_state=0)
    clf.fit(train[FEATURES], train["label"])
    score = clf.predict_proba(test[FEATURES])[:, 1]
    thr = threshold_for_rate(score, ALERT_RATE)
    model_flag = pd.Series(score >= thr, index=test.index)
    rule_flag = test["oil_ratio_3d"] < LOW_RATIO  # simple threshold rule to beat

    model_m = event_metrics(test, model_flag, failures)
    rule_m = event_metrics(test, rule_flag, failures)
    model_m |= {"roc_auc": float(roc_auc_score(test["label"], score)),
                "pr_auc": float(average_precision_score(test["label"], score)),
                "base_rate": float(test["label"].mean())}
    # matched alert budget: rule restricted to the same number of alerts, worst ratio first
    rule_top = test["oil_ratio_3d"].rank(method="first") <= model_flag.sum()
    rule_matched = event_metrics(test, rule_top, failures)
    # same comparison on well-days where the well is still running: alerts on wells already down are
    # easy, so this checks the model also finds failures before the well stops
    run_mask = (test["hours_on_3d"] > 0).to_numpy()
    running = test[run_mask]
    run_rule_top = running["oil_ratio_3d"].rank(method="first") <= int(model_flag[run_mask].sum())
    running_cmp = {"model": event_metrics(running, model_flag[run_mask], failures),
                   "rule_matched_budget": event_metrics(running, run_rule_top, failures)}

    # oil lost from the first model alert to the failure date = what earlier action could address
    t = test.assign(flag=model_flag, score=score, dtn=days_to_next_failure(test, failures))
    t["failure_date"] = t["production_date"] + pd.to_timedelta(t["dtn"], unit="D")
    first_alert = (t[t["flag"] & t["dtn"].between(1, HORIZON_DAYS)]
                   .groupby(["uwi", "failure_date"])["production_date"].min().rename("first_alert"))
    gap = feats.set_index(["uwi", "production_date"]).eval("oil_base - oil_produced_m3").clip(lower=0)
    after_alert = 0.0
    for (uwi, fdate), a in first_alert.items():
        after_alert += float(gap.loc[uwi].loc[a:fdate].sum())

    # importance: drop in PR-AUC when a feature is shuffled
    rng = np.random.default_rng(0)
    sample = test.sample(min(len(test), 200_000), random_state=0)
    base_ap = average_precision_score(sample["label"], clf.predict_proba(sample[FEATURES])[:, 1])
    importance = {}
    for col in FEATURES:
        x = sample[FEATURES].copy()
        x[col] = rng.permutation(x[col].values)
        importance[col] = float(base_ap - average_precision_score(sample["label"], clf.predict_proba(x)[:, 1]))

    # --- 3. Risk list on the last day of data (historical demo, not live) ---------------------
    last_day = feats["production_date"].max()
    latest = feats[feats["production_date"] == last_day].copy()
    latest["risk_score"] = clf.predict_proba(latest[FEATURES])[:, 1]
    latest["alert"] = latest["risk_score"] >= thr
    latest = latest[latest["hours_on_3d"] > 0]  # wells already down are known to operators
    risk = (latest.sort_values("risk_score", ascending=False)
            [["uwi", "well_name", "field_operating_area", "surface_latitude", "surface_longitude",
              "risk_score", "alert", "oil_produced_m3", "oil_base", "oil_ratio_3d", "hours_on_3d",
              "days_since_failure", "failures_prior_365d"]])
    risk.to_csv(OUT / "risk_latest.csv", index=False)

    # Canary-style tag export (timestamp, tag, value, quality) of the test-period risk scores
    tags = t[["uwi", "production_date", "score"]].rename(columns={"production_date": "timestamp", "score": "value"})
    tags["tag"] = "WellGuard." + tags.pop("uwi") + ".FailureRisk7d"
    tags["quality"] = 192  # OPC "Good"
    tags[["timestamp", "tag", "value", "quality"]].to_csv(OUT / "canary_risk_tags.csv", index=False)

    # daily alert counts in the test period, for the dashboard chart
    daily_alerts = (t.groupby("production_date")
                     .agg(alerts=("flag", "sum"), true_alerts=("flag", lambda s: (s & (t.loc[s.index, "label"] == 1)).sum()))
                     .reset_index())

    priced = fs.dropna(subset=["field_est_total"])
    summary = {
        "data_end": str(last_day.date()),
        "study_start": str(STUDY_START.date()),
        "test_start": str(TEST_START.date()),
        "wells_modelled": int(m["uwi"].nunique()),
        "well_days_train": int(len(train)), "well_days_test": int(len(test)),
        "failures_scored": int(len(fs)),
        "shortfall_m3": float(fs["shortfall_m3"].sum()),
        "shortfall_bbl": float(fs["shortfall_m3"].sum() * M3_TO_BBL),
        "lost_oil_logged_m3": float(fs["lost_oil_logged_m3"].sum()),
        "median_lead_days_low": float(fs["lead_days_low"].median()),
        "share_lead_7plus": fs.groupby("component")["lead_days_low"].apply(lambda s: float((s >= 7).mean())).to_dict(),
        "repair_cost_matched_failures": int(len(priced)),
        "repair_cost_total_cad": float(priced["field_est_total"].sum()),
        "repair_cost_median_cad": float(priced["field_est_total"].median()),
        "repair_duration_median_days": float(priced["job_duration_days"].median()),
        "healthy_low_share": healthy_low_share,
        "by_component": fs.groupby("component").agg(failures=("uwi", "size"), shortfall_m3=("shortfall_m3", "sum"),
                                                     cost_cad=("field_est_total", "sum")).reset_index().to_dict("records"),
        "by_cause": fs.groupby("cause").size().sort_values(ascending=False).head(6).to_dict(),
        "by_field": fs.groupby("field").agg(failures=("uwi", "size"), shortfall_m3=("shortfall_m3", "sum"))
                      .sort_values("failures", ascending=False).head(10).reset_index().to_dict("records"),
        "monthly_failures": study_fail.groupby(study_fail["failure_date"].dt.to_period("M").astype(str))
                                      .size().to_dict(),
        "alert_rate": ALERT_RATE, "threshold": thr,
        "model": model_m, "rule_80pct": rule_m, "rule_matched_budget": rule_matched,
        "running_only": running_cmp,
        "shortfall_after_first_alert_m3": after_alert,
        "importance": dict(sorted(importance.items(), key=lambda kv: -kv[1])[:10]),
        "daily_alerts": {"date": daily_alerts["production_date"].dt.strftime("%Y-%m-%d").tolist(),
                         "alerts": daily_alerts["alerts"].astype(int).tolist(),
                         "true_alerts": daily_alerts["true_alerts"].astype(int).tolist()},
        "risk_top": json.loads(risk.head(25).to_json(orient="records")),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    # the dashboard opens from file://, where fetch() is blocked, so it loads the summary as a script
    (ROOT / "dashboard" / "data.js").write_text(
        "window.WELLGUARD = " + json.dumps(summary, default=float) + ";\n")
    return summary


if __name__ == "__main__":
    s = run()
    print(json.dumps({k: v for k, v in s.items() if k not in ("daily_alerts", "risk_top", "monthly_failures")},
                     indent=2, default=float))
