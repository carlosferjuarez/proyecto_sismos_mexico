INSERT INTO sismos_dwh.dim_date (
    date_key, full_date, year, quarter, month, month_name, day, day_of_week, is_weekend
)
SELECT
    TO_CHAR(d::date, 'YYYYMMDD')::integer AS date_key,
    d::date AS full_date,
    EXTRACT(YEAR FROM d)::integer AS year,
    EXTRACT(QUARTER FROM d)::integer AS quarter,
    EXTRACT(MONTH FROM d)::integer AS month,
    TO_CHAR(d, 'TMMonth') AS month_name,
    EXTRACT(DAY FROM d)::integer AS day,
    TO_CHAR(d, 'TMDay') AS day_of_week,
    EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend
FROM generate_series('2000-01-01'::date, '2030-12-31'::date, '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;
