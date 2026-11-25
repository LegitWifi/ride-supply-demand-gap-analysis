"""Builds notebooks/analysis.ipynb (run from the repo root, then execute with nbconvert)."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
C = []

C.append(md("""# Ride Supply-Demand Gap Analysis

**Question:** Why do so many ride requests between the city and the airport go unfulfilled, where exactly is the gap,
and what should operations change first?

**Data:** 6,745 masked ride requests (11-15 July 2016, Mon-Fri), one row per request: pickup point (City / Airport),
driver ID, status (Trip Completed / Cancelled / No Cars Available), request and drop timestamps.

**Approach:** clean in Python → analyse in SQL (SQLite, `sql/analysis.sql`) → visualise → size the opportunity →
design an experiment to test the fix."""))

C.append(code("""import sys, sqlite3, pandas as pd
sys.path.insert(0, "../src")
from prep import load, to_sqlite, load_queries, SLOT_ORDER
import charts
from IPython.display import display
pd.set_option("display.width", 200)

d = load("../data/uber_request_data.csv")
print(d.shape)
print("Missing values:\\n", d.isna().sum())
d.head()"""))

C.append(md("""### Data cleaning notes
* Timestamps came in two formats (`11/7/2016 11:51` and `13-07-2016 08:33:16`); both are parsed day-first.
* `driver_id` and `drop_ts` are empty by design for *No Cars Available* (no driver was assigned), and `drop_ts` is empty
  for *Cancelled* trips. These are not errors, so no rows are dropped.
* Each request is tagged with an hour and a time slot: Early Morning (00-04), Morning Rush (05-09), Daytime (10-16),
  Evening Rush (17-21), Late Night (22-23)."""))

C.append(code("""con = sqlite3.connect(":memory:")
to_sqlite(d, con)
Q = load_queries("../sql/analysis.sql")
R = {name: pd.read_sql(q, con) for name, q in Q.items()}
R["kpis"]"""))

C.append(md("## 1. Where is the gap?"))
C.append(code("""print(Q["fulfilment_by_pickup_slot"])
R["fulfilment_by_pickup_slot"]"""))
C.append(code("""charts.fulfilment_heatmap(R["fulfilment_by_pickup_slot"], SLOT_ORDER, "../images/3_fulfilment_heatmap.png");"""))
C.append(code("""charts.status_mix(R["fulfilment_by_pickup_slot"], SLOT_ORDER, "../images/2_status_mix.png");"""))
C.append(code("""print(Q["lost_requests_ranked"])
R["lost_requests_ranked"]"""))
C.append(md("""**Finding 1. Two time slots cause two-thirds of all failed requests.**
* **Airport pickups, Evening Rush (17-21):** 1,800 requests, only **20.7% fulfilled**; 73% fail with *No Cars Available*.
* **City pickups, Morning Rush (05-09):** 1,677 requests, only **28.1% fulfilled**; **49% are cancelled by drivers**.
* Together they account for **67.2% of all 3,914 unfulfilled requests**. Overall fulfilment is just **42.0%**.
* The two failures are different problems: in the morning **cars exist but drivers refuse the trip**; in the evening
  **there are simply no cars at the airport**."""))

C.append(md("## 2. Why? Demand runs in one direction at a time"))
C.append(code("""charts.hourly_demand_supply(R["hourly_demand_supply"], "../images/1_hourly_demand_supply.png");"""))
C.append(code("""print(Q["directional_imbalance"])
R["directional_imbalance"]"""))
C.append(code("""charts.imbalance(R["directional_imbalance"], "../images/4_directional_imbalance.png");"""))
C.append(md("""**Finding 2. The gap is a direction problem, not a total-supply problem.**
* In the Morning Rush there are **3.94 city-to-airport requests for every airport-to-city request**. A driver who takes
  a city passenger to the airport at 7 am finds few passengers going back, so the trip often means a long unpaid wait or
  an empty return. **Likely reason drivers cancel city pickups in the morning.**
* In the Evening Rush it flips to **0.30** (about 3.3 airport requests for each city request). Few cars went to the airport
  in the afternoon, so there are **no cars waiting when evening flights land**.
* Trip duration is the same from both sides (median ~52 min), so trip length itself does not explain the gap.

*Caveat:* the data has no driver location or flight schedule, so the "long wait at the airport" explanation is a
hypothesis consistent with the data, which the experiment in section 5 is designed to test."""))

C.append(code("""d.groupby("pickup_point").trip_min.describe().round(1)"""))
C.append(code("""R["daily_trend"]"""))
C.append(md("""The pattern holds on every weekday (fulfilment 39-44% each day), so it is structural, not a one-off bad day."""))

C.append(md("## 3. Driver (partner) view"))
C.append(code("""print(Q["driver_quintiles"])
R["driver_quintiles"]"""))
C.append(code("""charts.driver_quintiles(R["driver_quintiles"], "../images/5_driver_quintiles.png");"""))
C.append(code("""sc = R["driver_scorecard"]
print("Drivers:", len(sc), "| avg trips per driver over 5 days:", round(sc.trips.mean(), 1))
print("Drivers cancelling more than 40% of assigned trips:", (sc.cancel_rate_pct > 40).sum())
sc.head(10)"""))
C.append(md("""**Finding 3. Cancellations are concentrated in a group of drivers.**
* The fifth of drivers who cancel most (60 drivers) cancel **48% of their assigned trips** and cause **31.5% of all
  cancellations**; the best fifth cancel only 14%.
* **63 of 300 drivers** cancel more than 40% of trips assigned to them, a clear list for targeted nudges or coaching.
* Drivers average only ~9.4 completed trips in 5 days, so there is spare driver capacity to re-position."""))

C.append(md("## 4. Sizing the opportunity"))
C.append(code("""t = R["fulfilment_by_pickup_slot"].set_index(["pickup_point", "slot"])
city_am = t.loc[("City", "Morning Rush (05-09)")]
air_pm = t.loc[("Airport", "Evening Rush (17-21)")]
days = R["kpis"].days[0]
base = R["kpis"].completed[0]; total = R["kpis"].requests[0]

a = city_am.cancelled_n * 0.5                        # A: halve morning city cancellations
b = air_pm.requests * 0.50 - air_pm.completed        # B: airport evening fulfilment 20.7% -> 50% (late-night level)
scen = pd.DataFrame({
    "lever": ["A. Halve City Morning-Rush cancellations", "B. Lift Airport Evening-Rush fulfilment to 50%", "A + B"],
    "extra_trips_5_days": [a, b, a + b],
})
scen["extra_trips_per_day"] = (scen.extra_trips_5_days / days).round(0)
scen["overall_fulfilment_pct"] = ((base + scen.extra_trips_5_days) / total * 100).round(1)
print("Baseline overall fulfilment:", round(base / total * 100, 1), "%")
scen"""))
C.append(md("""Assumes each recovered request becomes a completed trip. The 50% target for airport evenings is the level the airport
already reaches late at night, so it is a realistic first goal rather than a best case. Both levers together would lift
overall fulfilment from **42.0% to about 55.9%**, roughly **187 more completed trips per day**."""))

C.append(md("""## 5. Recommendations and the experiment to test them

| # | Problem | Action | Metric to move |
|---|---|---|---|
| 1 | Airport has no cars 17-21 | Pull supply to the airport before 17:00: an incentive for drivers who are at the airport during the evening peak, and dynamic pricing at the airport 17-21 | Airport evening fulfilment %, No-Cars % |
| 2 | Drivers cancel city-to-airport trips 05-09 | Make the morning airport trip worth it: return-trip priority / guaranteed queue spot at the airport, or a bonus per morning airport drop | City morning cancellation % |
| 3 | 20% of drivers cause 31.5% of cancellations | Weekly cancellation scorecard, nudges and coaching for the 63 drivers above 40%; track if they improve | Driver cancellation rate |
| 4 | Ongoing | Daily dashboard of fulfilment by pickup point x time slot, with alerts when a slot drops below target | Fulfilment % by slot |

### Experiment design: airport evening supply incentive
* **Hypothesis:** paying drivers to be at the airport for the evening peak lifts airport evening fulfilment from ~21%.
* **Design:** *switchback* by day (alternate incentive days and control days). Drivers share one supply pool, so a
  driver-level A/B split would leak; switching whole days avoids that.
* **Primary metric:** airport fulfilment % 17-21. **Guardrails:** city evening fulfilment, cost per extra trip, driver
  earnings per hour.
* **Sample size** (below): requests needed per arm to detect a lift from 21% to 30%."""))
C.append(code("""from math import sqrt, ceil
p1, p2, za, zb = 0.207, 0.30, 1.96, 0.84          # alpha 0.05 two-sided, power 80%
pbar = (p1 + p2) / 2
n = ((za * sqrt(2 * pbar * (1 - pbar)) + zb * sqrt(p1 * (1 - p1) + p2 * (1 - p2))) / (p2 - p1)) ** 2
per_evening = air_pm.requests / days
print(f"Requests needed per arm: {ceil(n)}  |  airport evening requests per day: {per_evening:.0f}")
print(f"=> about {ceil(n / per_evening)} evenings per arm in theory; run 7 incentive + 7 control evenings (2 weeks)")
print("   to cover day-to-day variation, since days (not requests) are the unit that is switched.")"""))
C.append(md("""**Decision rule:** roll out if airport evening fulfilment rises by at least 8 points with cost per extra trip below
the average fare margin, and city evening fulfilment does not fall."""))

nb["cells"] = C
nbf.write(nb, "notebooks/analysis.ipynb")
print("notebook written")
