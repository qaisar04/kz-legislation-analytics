"""Named analytical SQL queries (SQLite dialect). Each entry: description + sql."""

QUERIES = {
    "yearly_activity": {
        "description": "Acts per year with YoY change (LAG), 3-year moving average and running total",
        "sql": """
WITH yearly AS (
    SELECT adoption_year AS year, COUNT(*) AS acts, SUM(is_repealed) AS repealed
    FROM act GROUP BY adoption_year
)
SELECT year, acts, repealed,
       acts - LAG(acts) OVER (ORDER BY year)                               AS yoy_change,
       ROUND(100.0 * (acts - LAG(acts) OVER (ORDER BY year))
             / LAG(acts) OVER (ORDER BY year), 1)                          AS yoy_pct,
       ROUND(AVG(acts) OVER (ORDER BY year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1)
                                                                           AS moving_avg_3y,
       SUM(acts) OVER (ORDER BY year)                                      AS cumulative_acts
FROM yearly ORDER BY year""",
    },
    "authority_share_by_year": {
        "description": "JOIN legal_force: acts per authority level and year, share of the year (window SUM)",
        "sql": """
SELECT a.adoption_year AS year, lf.authority_level, COUNT(*) AS acts,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY a.adoption_year), 1) AS share_pct
FROM act a JOIN legal_force lf ON lf.legal_force_id = a.legal_force_id
WHERE a.adoption_year >= 1992
GROUP BY a.adoption_year, lf.authority_level
ORDER BY year, acts DESC""",
    },
    "top_bodies_per_year": {
        "description": "CTE + ROW_NUMBER: top-3 adopting bodies in each year",
        "sql": """
WITH body_year AS (
    SELECT a.adoption_year AS year, b.short_name AS body, b.body_type, COUNT(*) AS acts
    FROM act a JOIN body b ON b.body_id = a.body_id
    GROUP BY a.adoption_year, b.body_id
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY year ORDER BY acts DESC, body) AS rnk
    FROM body_year
)
SELECT year, rnk, body, body_type, acts FROM ranked
WHERE rnk <= 3 AND year >= 2000 ORDER BY year, rnk""",
    },
    "areas_repeal_rate": {
        "description": "M:N JOIN act_area/area, GROUP BY + HAVING: large regulation areas and their repeal rate",
        "sql": """
SELECT ar.name AS area, COUNT(*) AS acts, SUM(a.is_repealed) AS repealed,
       ROUND(100.0 * AVG(a.is_repealed), 1) AS repeal_rate_pct,
       MIN(a.adoption_year) AS first_year, MAX(a.adoption_year) AS last_year
FROM act a
JOIN act_area aa ON aa.act_id = a.act_id
JOIN area ar ON ar.area_id = aa.area_id
GROUP BY ar.area_id
HAVING COUNT(*) >= 2000
ORDER BY acts DESC""",
    },
    "repeal_rate_by_form": {
        "description": "M:N JOIN act_form/form, HAVING: repeal rate per act form, ranked (RANK)",
        "sql": """
SELECT f.name AS act_form, COUNT(*) AS acts,
       ROUND(100.0 * AVG(a.is_repealed), 1) AS repeal_rate_pct,
       RANK() OVER (ORDER BY AVG(a.is_repealed) DESC) AS repeal_rank
FROM act a
JOIN act_form af ON af.act_id = a.act_id
JOIN form f ON f.form_id = af.form_id
GROUP BY f.form_id
HAVING COUNT(*) >= 1000
ORDER BY repeal_rank""",
    },
    "region_level_summary": {
        "description": "JOIN region + scalar subquery: acts per territorial level and share of the total",
        "sql": """
SELECT r.region_level, COUNT(DISTINCT r.region_id) AS regions, COUNT(*) AS acts,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT r.region_id), 1) AS acts_per_region,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM act), 1) AS share_of_all_pct,
       ROUND(100.0 * AVG(a.is_repealed), 1) AS repeal_rate_pct
FROM act a JOIN region r ON r.region_id = a.region_id
GROUP BY r.region_level ORDER BY acts DESC""",
    },
    "top_regions_per_level": {
        "description": "CTE + DENSE_RANK partitioned by level: the five most active territories at each level",
        "sql": """
WITH region_counts AS (
    SELECT r.region_level, r.short_name AS region, COUNT(*) AS acts
    FROM act a JOIN region r ON r.region_id = a.region_id
    GROUP BY r.region_id
), ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY region_level ORDER BY acts DESC) AS rnk
    FROM region_counts
)
SELECT region_level, rnk, region, acts FROM ranked
WHERE rnk <= 5 ORDER BY region_level, rnk""",
    },
    "area_growth_periods": {
        "description": "Two CTEs: areas with the strongest growth 2015-2019 vs 2020-2024",
        "sql": """
WITH period_counts AS (
    SELECT aa.area_id,
           SUM(CASE WHEN a.adoption_year BETWEEN 2015 AND 2019 THEN 1 ELSE 0 END) AS p2015_2019,
           SUM(CASE WHEN a.adoption_year BETWEEN 2020 AND 2024 THEN 1 ELSE 0 END) AS p2020_2024
    FROM act a JOIN act_area aa ON aa.act_id = a.act_id
    GROUP BY aa.area_id
), growth AS (
    SELECT ar.name AS area, p2015_2019, p2020_2024,
           ROUND(1.0 * p2020_2024 / p2015_2019, 2) AS growth_ratio
    FROM period_counts pc JOIN area ar ON ar.area_id = pc.area_id
    WHERE p2015_2019 >= 300
)
SELECT * FROM growth ORDER BY growth_ratio DESC LIMIT 15""",
    },
    "monthly_seasonality": {
        "description": "CTE over month x year: average acts per calendar month and its index vs the mean",
        "sql": """
WITH month_year AS (
    SELECT adoption_year, adoption_month, COUNT(*) AS acts
    FROM act WHERE adoption_year BETWEEN 2010 AND 2025
    GROUP BY adoption_year, adoption_month
)
SELECT adoption_month AS month, ROUND(AVG(acts), 1) AS avg_acts,
       ROUND(AVG(acts) / (SELECT AVG(acts) FROM month_year), 2) AS seasonal_index
FROM month_year GROUP BY adoption_month ORDER BY adoption_month""",
    },
    "bodies_above_type_average": {
        "description": "Correlated subquery: bodies producing more than 5x the average of their body type",
        "sql": """
WITH body_counts AS (
    SELECT b.body_id, b.short_name AS name, b.body_type, COUNT(*) AS acts
    FROM act a JOIN body b ON b.body_id = a.body_id GROUP BY b.body_id
)
SELECT bc.body_type, bc.name, bc.acts,
       ROUND((SELECT AVG(acts) FROM body_counts x WHERE x.body_type = bc.body_type), 1) AS type_avg
FROM body_counts bc
WHERE bc.acts > 5 * (SELECT AVG(acts) FROM body_counts x WHERE x.body_type = bc.body_type)
ORDER BY bc.acts DESC LIMIT 20""",
    },
    "repeal_by_decade_authority": {
        "description": "JOIN + GROUP BY decade/authority: how repeal share depends on act age and issuer",
        "sql": """
SELECT (a.adoption_year / 10) * 10 AS decade, lf.authority_level, COUNT(*) AS acts,
       ROUND(100.0 * AVG(a.is_repealed), 1) AS repeal_rate_pct
FROM act a JOIN legal_force lf ON lf.legal_force_id = a.legal_force_id
WHERE a.adoption_year >= 1990
GROUP BY decade, lf.authority_level
HAVING COUNT(*) >= 100
ORDER BY decade, acts DESC""",
    },
    "amendment_lag": {
        "description": "Window LAG per body: median-like gap (days) between consecutive acts of the busiest bodies",
        "sql": """
WITH busiest AS (
    SELECT body_id FROM act GROUP BY body_id ORDER BY COUNT(*) DESC LIMIT 10
), ordered AS (
    SELECT a.body_id, julianday(a.date_adopted)
           - julianday(LAG(a.date_adopted) OVER (PARTITION BY a.body_id ORDER BY a.date_adopted)) AS gap_days
    FROM act a WHERE a.body_id IN (SELECT body_id FROM busiest)
)
SELECT b.short_name AS body, COUNT(*) AS acts, ROUND(AVG(gap_days), 1) AS avg_gap_days,
       MAX(gap_days) AS max_gap_days
FROM ordered o JOIN body b ON b.body_id = o.body_id
GROUP BY o.body_id ORDER BY avg_gap_days""",
    },
}
