"""Builds docs/index.html: an interactive Plotly dashboard (run from the repo root)."""
import sqlite3, html
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
from prep import load, to_sqlite, load_queries, SLOT_ORDER

BLUE, ORANGE, AQUA, GRAY, INK, INK2, GRID = "#257de0", "#f47230", "#00b894", "#c9c9c9", "#191919", "#666666", "#ececec"
SEQ = [[0, "#cce3fd"], [0.25, "#9dc8f7"], [0.5, "#519ced"], [0.75, "#2370cd"], [1, "#0e3d7e"]]

d = load("data/uber_request_data.csv")
con = sqlite3.connect(":memory:"); to_sqlite(d, con)
R = {n: pd.read_sql(q, con) for n, q in load_queries("sql/analysis.sql").items()}
k = R["kpis"].iloc[0]
fs = R["fulfilment_by_pickup_slot"]
short = {s: s.split(" (")[0] for s in SLOT_ORDER}


def style(fig, h=380):
    fig.update_layout(template="none", height=h, margin=dict(l=55, r=20, t=40, b=45), font=dict(family="Inter, Arial", size=12, color=INK),
                      paper_bgcolor="white", plot_bgcolor="white", hoverlabel=dict(bgcolor="white", font_color=INK),
                      legend=dict(orientation="h", y=1.12, x=0))
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=INK2))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=INK2))
    return fig


# 1 heatmap
pv = fs.pivot(index="pickup_point", columns="slot", values="fulfilment_pct").reindex(columns=SLOT_ORDER).loc[["City", "Airport"]]
f1 = go.Figure(go.Heatmap(z=pv.values, x=[short[s] for s in SLOT_ORDER], y=["City", "Airport"], colorscale=SEQ,
                          zmin=0, zmax=100, text=[[f"{v:.0f}%" for v in r] for r in pv.values], texttemplate="%{text}",
                          textfont=dict(size=15), hovertemplate="%{y}, %{x}<br>Fulfilment: %{z:.1f}%<extra></extra>",
                          xgap=2, ygap=2, colorbar=dict(title="%", thickness=10)))
style(f1, 260)

# 2 status mix
f2 = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=("City pickups", "Airport pickups"), horizontal_spacing=0.05)
for ci, pp in enumerate(["City", "Airport"], 1):
    s = fs[fs.pickup_point == pp].set_index("slot").reindex(SLOT_ORDER)
    for col, name, colr in [("completed", "Trip Completed", BLUE), ("cancelled_n", "Cancelled", ORANGE), ("no_cars_n", "No Cars Available", AQUA)]:
        f2.add_bar(x=[short[x] for x in SLOT_ORDER], y=s[col], name=name, marker=dict(color=colr, line=dict(color="white", width=2)),
                   legendgroup=name, showlegend=(ci == 1),
                   customdata=(s[col] / s.requests * 100).round(1),
                   hovertemplate=f"{pp}, %{{x}}<br>{name}: %{{y}} (%{{customdata}}%)<extra></extra>", row=1, col=ci)
style(f2, 420); f2.update_layout(barmode="stack", margin=dict(t=80), legend=dict(y=1.2))

# 3 hourly demand vs supply
h = R["hourly_demand_supply"]
f3 = make_subplots(rows=1, cols=2, shared_yaxes=True, subplot_titles=("City pickups", "Airport pickups"), horizontal_spacing=0.05)
for ci, pp in enumerate(["City", "Airport"], 1):
    s = h[h.pickup_point == pp]
    f3.add_bar(x=s.hour, y=s.demand, name="Requests (demand)", marker_color=GRAY, legendgroup="d", showlegend=(ci == 1),
               customdata=s.gap, hovertemplate=f"{pp}, %{{x}}:00<br>Requests: %{{y}}<br>Unfulfilled: %{{customdata}}<extra></extra>", row=1, col=ci)
    f3.add_bar(x=s.hour, y=s.supply, name="Completed trips (supply)", marker_color=BLUE, legendgroup="s", showlegend=(ci == 1),
               width=0.5, hovertemplate=f"{pp}, %{{x}}:00<br>Completed: %{{y}}<extra></extra>", row=1, col=ci)
f3.update_xaxes(title_text="Hour of request", dtick=2); style(f3, 400); f3.update_layout(barmode="overlay", margin=dict(t=80), legend=dict(y=1.2))

# 4 imbalance
di = R["directional_imbalance"]
f4 = go.Figure(go.Bar(x=[short[s] for s in di.slot], y=di.city_airport_ratio, marker_color=BLUE, text=[f"{v:.2f}x" for v in di.city_airport_ratio],
                      textposition=["inside" if 0.6 < v < 1.15 else "outside" for v in di.city_airport_ratio], insidetextanchor="end", insidetextfont=dict(color="white"),
                      customdata=di[["city_to_airport", "airport_to_city"]].values,
                      hovertemplate="%{x}<br>City→Airport: %{customdata[0]}<br>Airport→City: %{customdata[1]}<br>Ratio: %{y:.2f}<extra></extra>"))
f4.add_hline(y=1, line_dash="dash", line_color=INK2, line_width=1.5)
f4.update_yaxes(title_text="City→Airport per Airport→City", range=[0, 4.6]); style(f4, 340)

# 5 driver quintiles
q = R["driver_quintiles"]
f5 = go.Figure(go.Bar(x=[f"Q{i}" for i in q.quintile], y=q.pct_of_all_cancels, marker_color=BLUE,
                      text=[f"{v:.1f}%" for v in q.pct_of_all_cancels], textposition="outside",
                      customdata=q[["cancel_rate_pct", "drivers", "avg_trips_per_driver"]].values,
                      hovertemplate="%{x} (%{customdata[1]} drivers)<br>Share of all cancellations: %{y:.1f}%<br>"
                                    "Cancel rate: %{customdata[0]:.1f}%<br>Avg trips: %{customdata[2]}<extra></extra>"))
f5.update_xaxes(title_text="Drivers grouped by cancellation rate (Q1 = highest)")
f5.update_yaxes(title_text="% of all cancellations", range=[0, 38]); style(f5, 340)

# 6 daily trend
dt = R["daily_trend"]
f6 = go.Figure(go.Scatter(x=[f"{w[:3]} {dd[-2:]} Jul" for w, dd in zip(dt.weekday, dt.date)], y=dt.fulfilment_pct, mode="lines+markers+text",
                          line=dict(color=BLUE, width=2), marker=dict(size=9, color=BLUE, line=dict(color="white", width=2)),
                          text=[f"{v:.1f}%" for v in dt.fulfilment_pct], textposition="top center", customdata=dt.requests,
                          hovertemplate="%{x}<br>Fulfilment: %{y:.1f}%<br>Requests: %{customdata}<extra></extra>"))
f6.update_yaxes(title_text="Fulfilment %", range=[0, 60]); style(f6, 300)

charts_html = {n: pio.to_html(f, include_plotlyjs=("cdn" if i == 0 else False), full_html=False, config={"displayModeBar": False})
               for i, (n, f) in enumerate([("heat", f1), ("mix", f2), ("hourly", f3), ("imb", f4), ("drv", f5), ("day", f6)])}

tbl = fs[["pickup_point", "slot", "requests", "completed", "cancelled_n", "no_cars_n", "fulfilment_pct"]].rename(columns={
    "pickup_point": "Pickup", "slot": "Time slot", "requests": "Requests", "completed": "Completed", "cancelled_n": "Cancelled",
    "no_cars_n": "No cars", "fulfilment_pct": "Fulfilment %"}).to_html(index=False, classes="tbl", border=0)


def tile(label, value, note=""):
    return f'<div class="tile"><div class="tl">{label}</div><div class="tv">{value}</div><div class="tn">{note}</div></div>'


page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ride Supply-Demand Gap Dashboard</title>
<style>
body{{margin:0;background:#f7f7f7;font-family:Inter,Arial,sans-serif;color:{INK}}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 20px 40px}}
h1{{font-size:24px;margin:0 0 4px}} .sub{{color:{INK2};margin:0 0 20px;font-size:14px}}
.tiles{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}}
.tile{{background:#fff;border:1px solid #e6e6e6;border-radius:10px;padding:14px 16px}}
.tl{{font-size:12px;color:{INK2}}} .tv{{font-size:26px;font-weight:700;margin-top:4px}} .tn{{font-size:12px;color:{INK2};margin-top:2px}}
.card{{background:#fff;border:1px solid #e6e6e6;border-radius:10px;padding:16px 18px;margin-bottom:16px}}
.card h2{{font-size:16px;margin:0 0 4px}} .card p.c{{font-size:13px;color:{INK2};margin:0 0 6px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.ins li{{margin:6px 0;font-size:14px;line-height:1.45}}
.tbl{{border-collapse:collapse;width:100%;font-size:13px}} .tbl th,.tbl td{{padding:6px 8px;border-bottom:1px solid #eee;text-align:right}}
.tbl th:nth-child(-n+2),.tbl td:nth-child(-n+2){{text-align:left}} .tbl th{{color:{INK2};font-weight:600}}
details summary{{cursor:pointer;font-weight:600;font-size:14px}}
@media(max-width:820px){{.tiles{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>Ride Supply-Demand Gap Dashboard</h1>
<p class="sub">6,745 city ⇄ airport ride requests, 11-15 July 2016 (Mon-Fri) · public masked dataset · hover any chart for details</p>
<div class="tiles">
{tile("Requests", f"{int(k.requests):,}", f"{int(k.days)} weekdays")}
{tile("Fulfilment", f"{k.fulfilment_pct:.1f}%", f"{int(k.completed):,} trips completed")}
{tile("Driver cancellations", f"{int(k.cancelled):,}", f"{k.cancelled / k.requests * 100:.1f}% of requests")}
{tile("No cars available", f"{int(k.no_cars):,}", f"{k.no_cars / k.requests * 100:.1f}% of requests")}
{tile("Drivers", f"{int(k.drivers)}", "~9.4 trips each in 5 days")}
</div>
<div class="card"><h2>Key insights</h2><ul class="ins">
<li><b>Two slots cause 67% of all failed requests:</b> airport pickups in the evening rush (only 20.7% fulfilled, 73% "no cars") and city pickups in the morning rush (28.1% fulfilled, 49% cancelled by drivers).</li>
<li><b>It is a direction problem:</b> 3.94 city→airport requests per airport→city request in the morning, but only 0.30 in the evening. Cars pile up away from where the next demand is.</li>
<li><b>Cancellations are concentrated:</b> the fifth of drivers who cancel most cause 31.5% of all cancellations (48% cancel rate vs 14% for the best fifth).</li>
<li><b>Opportunity:</b> halving morning city cancellations and lifting airport evening fulfilment to 50% would add ~187 trips a day and raise fulfilment from 42.0% to ~55.9%.</li>
</ul></div>
<div class="card"><h2>Fulfilment % by pickup point and time slot</h2><p class="c">Completed ÷ requested. Darker = better.</p>{charts_html["heat"]}</div>
<div class="card"><h2>What happens to requests in each slot</h2><p class="c">Morning city requests are lost to driver cancellations; evening airport requests are lost because no car is available.</p>{charts_html["mix"]}</div>
<div class="card"><h2>Demand vs supply by hour</h2><p class="c">Grey = requests, blue = completed trips. The gap peaks 05-09 for city pickups and 17-22 for airport pickups.</p>{charts_html["hourly"]}</div>
<div class="grid2">
<div class="card"><h2>Direction of demand</h2><p class="c">City→airport requests per airport→city request. Dashed line = 1.0 (balanced).</p>{charts_html["imb"]}</div>
<div class="card"><h2>Where cancellations come from</h2><p class="c">300 drivers split into fifths by cancellation rate.</p>{charts_html["drv"]}</div>
</div>
<div class="card"><h2>Fulfilment by day</h2><p class="c">The pattern holds every weekday, so it is structural.</p>{charts_html["day"]}</div>
<div class="card"><details><summary>Table view: fulfilment by pickup point and slot</summary>{tbl}</details></div>
<p class="sub">Built with Python (pandas), SQLite and Plotly · analysis notebook and SQL in this repository.</p>
</div></body></html>"""
open("docs/index.html", "w").write(page)
print("dashboard written", len(page) // 1024, "KB")
