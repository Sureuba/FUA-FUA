# WellGuard

Failure-risk ranking for Strathcona Resources' heavy-oil PCP wells. Canary × Chirality 2026 Datathon, team FUA FUA.

- **Video (5 min):** TODO add link
- **Slides:** TODO add link
- **Dashboard:** open `dashboard/index.html` in a browser (static page, no server needed)

## Research question

How much oil does Strathcona lose in the days before a rod, pump or tubing failure is repaired, and how much of that loss happens after a model could have flagged the well?

## Findings (failure log, May 2025 to Oct 2026)

| | |
|---|---|
| Rod, pump and tubing failures scored | **2,786** on producing wells in the 17 failure-reporting fields |
| Oil below each well's normal rate, 14 days up to each failure | **52,721 m³ (331,600 bbl)** |
| Field-estimated repair cost (2,755 failures matched to a job) | **C$35.6M**, median C$5,932 per job, median job 0.25 days |
| Rods share | 2,177 of 2,786 failures (78%); top causes fatigue 1,213, corrosion 758 |
| Median days a well runs below 80% of baseline before failing | **2 days**. Only 15% of rod failures show 7+ days |
| Healthy well-days (no failure within 45 days) below 80% of baseline | **16%**, so a plain threshold rule floods engineers with alerts |

Repair jobs are short, so most of the loss comes in the days before the job starts. The lever is earlier detection and better prioritisation of which wells to visit first.

## Model and backtest

Gradient-boosted trees (`sklearn` `HistGradientBoostingClassifier`) score every producing well-day for "a failure is logged in the next 7 days". Inputs:

- oil, gas and water cut against the well's own baseline
- run hours and downtime
- pump RPM, torque, current and efficiency against baseline
- tubing and casing pressure
- well age, field and pump make
- failure history

**Time split:** trained on well-days from 2025-05-01 to 2026-02-21 and tested on 2026-03-01 onward, unseen. The 7-day gap stops labels leaking across the split.

| Test period (1,126 failures) at 22 alerts/day across 1,198 wells | Model | 80%-of-baseline rule, same alert budget |
|---|---|---|
| Failures caught (recall) | **59%** | 29% |
| Alerts followed by a failure within 7 days (precision) | **36%** | 24% |
| Median warning | 2 days | 3 days |
| Wells still running only (981 failures): recall / precision | **62% / 37%** | 29% / 14% |

The model has ROC-AUC 0.83 and PR-AUC 0.23, against a base rate of 3.0%. Oil lost between the model's first alert and the failure date in the test period was **8,156 m³ (51,300 bbl)**. That is an upper bound on what earlier action could address, not a savings claim. The dashboard converts it to dollars at an oil price the user enters.

## Limits (say these in the pitch)

- **Research prototype on historical data.** Data ends 2026-10-26. Every alert is a backtest result, not a live field warning.
- **Short warning:** median 2 days. WellGuard is early detection plus prioritisation, not a week-ahead forecast.
- **Signals, not causes.** The strongest inputs are downtime hours and the drop in oil rate. Nothing here tells engineers which setpoint to change, and there is no control data to write back to.
- **Labels cover only the fields that log failures.** Wells outside the failure log are not assumed healthy, so they are left out.
- **Leak removed.** Rod-truck jobs are often logged 1 to 7 days before `failure_start_date`. "Days since last rod job" is therefore excluded as a feature.
- **Repair cost** is `field_est_total` of the first job from 3 days before to 21 days after the failure. Some matches are larger workovers.

## Canary and Databricks

`src/wellguard.py` writes `outputs/canary_risk_tags.csv` with columns `timestamp, tag, value, quality`. Each well gets one tag, `WellGuard.<uwi>.FailureRisk7d`, so the risk score can be loaded into a Canary historian next to the sensor tags and trended or alarmed there. The same script runs unchanged in a Databricks notebook with the parquet files in DBFS.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install pandas pyarrow scikit-learn
# put daily_production.parquet, well_jobs.parquet and production_failures.parquet in data/
.venv/bin/python src/wellguard.py          # about 20 s; writes outputs/ and dashboard/data.js
.venv/bin/python -m unittest discover tests
open dashboard/index.html
```

## Layout

- `src/wellguard.py`: loading, baseline, features, shortfall and cost, model, backtest, exports
- `tests/`: unit tests on synthetic data
- `dashboard/`: static dashboard. `data.js` is generated
- `outputs/`: `summary.json`, `failure_shortfall.csv` (one row per failure), `risk_latest.csv`

## AI transparency

Built with help from Claude Code (Claude Opus 5.5). Every figure above comes from `outputs/summary.json`, produced by `src/wellguard.py`.
