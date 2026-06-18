DROP SCHEMA IF EXISTS sismos_dwh CASCADE;
CREATE SCHEMA sismos_dwh;

CREATE TABLE sismos_dwh.dim_date (
    date_key      INTEGER PRIMARY KEY,
    full_date     DATE NOT NULL UNIQUE,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT NOT NULL,
    day           INTEGER NOT NULL,
    day_of_week   TEXT NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

CREATE TABLE sismos_dwh.dim_hour (
    hour_key      INTEGER PRIMARY KEY,
    hour          INTEGER NOT NULL UNIQUE,
    day_part      TEXT NOT NULL
);

CREATE TABLE sismos_dwh.dim_magnitude (
    magnitude_key INTEGER PRIMARY KEY,
    bucket        TEXT NOT NULL,
    min_mag       NUMERIC(3,1),
    max_mag       NUMERIC(3,1),
    description   TEXT NOT NULL
);

CREATE TABLE sismos_dwh.dim_region (
    region_key    SERIAL PRIMARY KEY,
    region_name   TEXT NOT NULL UNIQUE,
    country_scope TEXT NOT NULL,
    min_lat       NUMERIC(8,4),
    max_lat       NUMERIC(8,4),
    min_lon       NUMERIC(8,4),
    max_lon       NUMERIC(8,4)
);

CREATE TABLE sismos_dwh.fact_sismos (
    event_id       TEXT PRIMARY KEY,
    date_key       INTEGER NOT NULL REFERENCES sismos_dwh.dim_date(date_key),
    hour_key       INTEGER NOT NULL REFERENCES sismos_dwh.dim_hour(hour_key),
    magnitude_key  INTEGER NOT NULL REFERENCES sismos_dwh.dim_magnitude(magnitude_key),
    region_key     INTEGER NOT NULL REFERENCES sismos_dwh.dim_region(region_key),
    event_time_utc TIMESTAMP NOT NULL,
    magnitude      NUMERIC(4,2),
    depth_km       NUMERIC(8,2),
    latitude       NUMERIC(9,5),
    longitude      NUMERIC(9,5),
    place          TEXT,
    tsunami        INTEGER,
    felt_reports   INTEGER,
    alert_level    TEXT,
    source_net     TEXT,
    loaded_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO sismos_dwh.dim_hour(hour_key, hour, day_part)
SELECT h AS hour_key,
       h AS hour,
       CASE
           WHEN h BETWEEN 0 AND 5 THEN 'madrugada'
           WHEN h BETWEEN 6 AND 11 THEN 'mañana'
           WHEN h BETWEEN 12 AND 17 THEN 'tarde'
           ELSE 'noche'
       END AS day_part
FROM generate_series(0, 23) AS h;

CREATE INDEX idx_fact_sismos_date ON sismos_dwh.fact_sismos(date_key);
CREATE INDEX idx_fact_sismos_region ON sismos_dwh.fact_sismos(region_key);
CREATE INDEX idx_fact_sismos_mag ON sismos_dwh.fact_sismos(magnitude_key);
CREATE INDEX idx_fact_sismos_geo ON sismos_dwh.fact_sismos(latitude, longitude);
