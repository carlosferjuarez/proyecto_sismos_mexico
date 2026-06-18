-- 1. Top 10 regiones por número de sismos y magnitud promedio
WITH resumen AS (
    SELECT
        dr.region_name,
        COUNT(*) AS total_sismos,
        ROUND(AVG(fs.magnitude), 2) AS magnitud_promedio,
        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY fs.magnitude)::numeric, 2) AS p95_magnitud,
        ROUND(AVG(fs.depth_km), 2) AS profundidad_promedio
    FROM sismos_dwh.fact_sismos fs
    JOIN sismos_dwh.dim_region dr USING (region_key)
    GROUP BY dr.region_name
)
SELECT *, RANK() OVER (ORDER BY total_sismos DESC) AS ranking_eventos
FROM resumen
ORDER BY total_sismos DESC
LIMIT 10;

-- 2. Serie mensual con variación contra mes anterior
WITH mensual AS (
    SELECT
        dd.year,
        dd.month,
        COUNT(*) AS total_sismos,
        ROUND(AVG(fs.magnitude), 2) AS magnitud_promedio
    FROM sismos_dwh.fact_sismos fs
    JOIN sismos_dwh.dim_date dd USING (date_key)
    GROUP BY dd.year, dd.month
), comparativo AS (
    SELECT
        *,
        LAG(total_sismos) OVER (ORDER BY year, month) AS total_mes_anterior
    FROM mensual
)
SELECT
    year,
    month,
    total_sismos,
    total_mes_anterior,
    total_sismos - COALESCE(total_mes_anterior, 0) AS cambio_absoluto,
    magnitud_promedio
FROM comparativo
ORDER BY year, month;

-- 3. Eventos superficiales de alta magnitud
SELECT
    fs.event_time_utc,
    fs.place,
    dr.region_name,
    fs.magnitude,
    fs.depth_km,
    fs.latitude,
    fs.longitude
FROM sismos_dwh.fact_sismos fs
JOIN sismos_dwh.dim_region dr USING (region_key)
WHERE fs.magnitude >= 5.5
  AND fs.depth_km <= 70
ORDER BY fs.magnitude DESC, fs.depth_km ASC
LIMIT 25;

-- 4. Heatmap base: hora x mes
SELECT
    dd.month,
    dh.hour,
    COUNT(*) AS total_sismos
FROM sismos_dwh.fact_sismos fs
JOIN sismos_dwh.dim_date dd USING (date_key)
JOIN sismos_dwh.dim_hour dh USING (hour_key)
GROUP BY dd.month, dh.hour
ORDER BY dd.month, dh.hour;

-- 5. Ranking mensual por región con window function
WITH region_mes AS (
    SELECT
        dd.year,
        dd.month,
        dr.region_name,
        COUNT(*) AS total_sismos
    FROM sismos_dwh.fact_sismos fs
    JOIN sismos_dwh.dim_date dd USING (date_key)
    JOIN sismos_dwh.dim_region dr USING (region_key)
    GROUP BY dd.year, dd.month, dr.region_name
)
SELECT *
FROM (
    SELECT
        *,
        RANK() OVER (PARTITION BY year, month ORDER BY total_sismos DESC) AS rank_region_mes
    FROM region_mes
) ranked
WHERE rank_region_mes <= 3
ORDER BY year, month, rank_region_mes;

-- 6. Distribución por rango de magnitud
SELECT
    dm.bucket,
    COUNT(*) AS total_sismos,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS porcentaje
FROM sismos_dwh.fact_sismos fs
JOIN sismos_dwh.dim_magnitude dm USING (magnitude_key)
GROUP BY dm.bucket, dm.magnitude_key
ORDER BY dm.magnitude_key;
