-- Ride supply-demand gap analysis (SQLite)
-- Table `requests`: one row per ride request, cleaned in src/prep.py
-- columns: request_id, pickup_point, driver_id, status, request_ts, drop_ts,
--          hour, date, weekday, slot, slot_order, completed (1/0), trip_min

-- name: kpis
SELECT COUNT(*)                                        AS requests,
       SUM(completed)                                  AS completed,
       ROUND(100.0 * AVG(completed), 1)                AS fulfilment_pct,
       SUM(status = 'Cancelled')                       AS cancelled,
       SUM(status = 'No Cars Available')               AS no_cars,
       COUNT(DISTINCT driver_id)                       AS drivers,
       COUNT(DISTINCT date)                            AS days
FROM requests;

-- name: fulfilment_by_pickup_slot
SELECT pickup_point, slot,
       COUNT(*)                                            AS requests,
       SUM(completed)                                      AS completed,
       SUM(status = 'Cancelled')                           AS cancelled_n,
       SUM(status = 'No Cars Available')                   AS no_cars_n,
       ROUND(100.0 * AVG(completed), 1)                    AS fulfilment_pct,
       ROUND(100.0 * AVG(status = 'Cancelled'), 1)         AS cancelled_pct,
       ROUND(100.0 * AVG(status = 'No Cars Available'), 1) AS no_cars_pct
FROM requests
GROUP BY pickup_point, slot_order, slot
ORDER BY pickup_point, slot_order;

-- name: lost_requests_ranked
-- Where are unfulfilled requests concentrated? (window functions)
WITH lost AS (
    SELECT pickup_point, slot, slot_order,
           COUNT(*)                          AS lost,
           SUM(status = 'Cancelled')         AS cancelled,
           SUM(status = 'No Cars Available') AS no_cars
    FROM requests
    WHERE completed = 0
    GROUP BY pickup_point, slot, slot_order
)
SELECT pickup_point, slot, lost, cancelled, no_cars,
       ROUND(100.0 * lost / SUM(lost) OVER (), 1)                         AS pct_of_all_lost,
       ROUND(100.0 * SUM(lost) OVER (ORDER BY lost DESC) / SUM(lost) OVER (), 1) AS cumulative_pct,
       RANK() OVER (ORDER BY lost DESC)                                   AS rank
FROM lost
ORDER BY rank;

-- name: hourly_demand_supply
SELECT pickup_point, hour,
       COUNT(*)                  AS demand,
       SUM(completed)            AS supply,
       COUNT(*) - SUM(completed) AS gap
FROM requests
GROUP BY pickup_point, hour
ORDER BY pickup_point, hour;

-- name: directional_imbalance
-- Requests leaving the city vs leaving the airport in each time slot
SELECT slot,
       SUM(pickup_point = 'City')    AS city_to_airport,
       SUM(pickup_point = 'Airport') AS airport_to_city,
       ROUND(1.0 * SUM(pickup_point = 'City') / SUM(pickup_point = 'Airport'), 2) AS city_airport_ratio
FROM requests
GROUP BY slot_order, slot
ORDER BY slot_order;

-- name: daily_trend
SELECT date, weekday,
       COUNT(*)                         AS requests,
       ROUND(100.0 * AVG(completed), 1) AS fulfilment_pct
FROM requests
GROUP BY date, weekday
ORDER BY date;

-- name: driver_scorecard
WITH d AS (
    SELECT driver_id,
           COUNT(*)                  AS assigned,
           SUM(completed)            AS trips,
           SUM(status = 'Cancelled') AS cancels
    FROM requests
    WHERE driver_id IS NOT NULL
    GROUP BY driver_id
)
SELECT driver_id, assigned, trips, cancels,
       ROUND(100.0 * cancels / assigned, 1)                    AS cancel_rate_pct,
       NTILE(5) OVER (ORDER BY 1.0 * cancels / assigned DESC)  AS cancel_quintile
FROM d
ORDER BY cancel_rate_pct DESC, driver_id;

-- name: driver_quintiles
-- Are cancellations spread evenly, or driven by a small group of drivers?
WITH d AS (
    SELECT driver_id, COUNT(*) AS assigned, SUM(completed) AS trips,
           SUM(status = 'Cancelled') AS cancels
    FROM requests WHERE driver_id IS NOT NULL GROUP BY driver_id
), q AS (
    SELECT *, NTILE(5) OVER (ORDER BY 1.0 * cancels / assigned DESC) AS quintile FROM d
)
SELECT quintile,
       COUNT(*)                                                     AS drivers,
       ROUND(100.0 * SUM(cancels) / SUM(assigned), 1)               AS cancel_rate_pct,
       SUM(cancels)                                                 AS cancels,
       ROUND(100.0 * SUM(cancels) / (SELECT SUM(cancels) FROM d), 1) AS pct_of_all_cancels,
       ROUND(AVG(trips), 1)                                         AS avg_trips_per_driver
FROM q
GROUP BY quintile
ORDER BY quintile;
