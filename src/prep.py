import pandas as pd, numpy as np

SLOTS = [(0, 4, "Early Morning (00-04)"), (5, 9, "Morning Rush (05-09)"), (10, 16, "Daytime (10-16)"),
         (17, 21, "Evening Rush (17-21)"), (22, 23, "Late Night (22-23)")]
SLOT_ORDER = [s[2] for s in SLOTS]


def slot_of(h):
    for a, b, n in SLOTS:
        if a <= h <= b:
            return n


def load(path="data/uber_request_data.csv"):
    d = pd.read_csv(path)
    d.columns = ["request_id", "pickup_point", "driver_id", "status", "request_ts", "drop_ts"]
    for c in ["request_ts", "drop_ts"]:
        d[c] = pd.to_datetime(d[c].str.replace("/", "-"), dayfirst=True, format="mixed")
    d["hour"] = d.request_ts.dt.hour
    d["date"] = d.request_ts.dt.date
    d["weekday"] = d.request_ts.dt.day_name()
    d["slot"] = pd.Categorical(d.hour.map(slot_of), SLOT_ORDER, ordered=True)
    d["completed"] = (d.status == "Trip Completed").astype(int)
    d["trip_min"] = (d.drop_ts - d.request_ts).dt.total_seconds() / 60
    return d


def to_sqlite(d, conn):
    """Write the cleaned table to SQLite so the SQL in sql/analysis.sql can run on it."""
    t = d.copy()
    t["slot_order"] = t.slot.cat.codes + 1
    t["slot"] = t.slot.astype(str)
    t["date"] = t.date.astype(str)
    t["request_ts"] = t.request_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    t["drop_ts"] = t.drop_ts.dt.strftime("%Y-%m-%d %H:%M:%S")
    t.to_sql("requests", conn, index=False, if_exists="replace")


def load_queries(path="sql/analysis.sql"):
    """Split the SQL file into {name: query} using '-- name: <name>' markers."""
    out, name, buf = {}, None, []
    for line in open(path):
        if line.startswith("-- name:"):
            if name:
                out[name] = "".join(buf).strip()
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        out[name] = "".join(buf).strip()
    return out
