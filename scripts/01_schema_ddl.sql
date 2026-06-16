-- =====================================================================
-- Proyecto Final Módulo 4. Diplomado UNAM - IIMAS
-- Sismicidad Global 1990-2023
-- =====================================================================

-- Limpieza previa
DROP TABLE IF EXISTS fact_sismo;
DROP TABLE IF EXISTS dim_fecha;
DROP TABLE IF EXISTS dim_ubicacion;
DROP TABLE IF EXISTS dim_magnitud;
DROP TABLE IF EXISTS dim_profundidad;
DROP TABLE IF EXISTS dim_calidad;

-- =====================================================================
-- DIMENSIÓN: dim_fecha
-- =====================================================================
CREATE TABLE dim_fecha (
    date_key        SERIAL PRIMARY KEY,
    full_timestamp  TIMESTAMP NOT NULL,
    year            SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(15) NOT NULL,
    day             SMALLINT NOT NULL,
    hour_utc        SMALLINT NOT NULL,
    day_of_week     VARCHAR(10) NOT NULL,
    decade          VARCHAR(10) NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    UNIQUE (full_timestamp)
);

-- =====================================================================
-- DIMENSIÓN: dim_ubicacion
-- =====================================================================
CREATE TABLE dim_ubicacion (
    location_key    SERIAL PRIMARY KEY,
    place_raw       TEXT,
    country         VARCHAR(100),
    region          VARCHAR(150),
    latitude        NUMERIC(9,6) NOT NULL,
    longitude       NUMERIC(9,6) NOT NULL,
    zona_tectonica  VARCHAR(100),
    es_mexico       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_ubicacion_pais ON dim_ubicacion (country);
CREATE INDEX idx_ubicacion_mexico ON dim_ubicacion (es_mexico);

-- =====================================================================
-- DIMENSIÓN: dim_magnitud
-- =====================================================================
CREATE TABLE dim_magnitud (
    magnitude_key       SERIAL PRIMARY KEY,
    mag_value           NUMERIC(4,2) NOT NULL,
    mag_type_raw        VARCHAR(10),
    mag_type_normalized VARCHAR(20) NOT NULL,
    categoria           VARCHAR(20) NOT NULL  -- micro, menor, moderado, fuerte, mayor
);

CREATE INDEX idx_magnitud_categoria ON dim_magnitud (categoria);

-- =====================================================================
-- DIMENSIÓN: dim_profundidad
-- =====================================================================
CREATE TABLE dim_profundidad (
    depth_key   SERIAL PRIMARY KEY,
    depth_km    NUMERIC(8,3) NOT NULL,
    categoria   VARCHAR(20) NOT NULL,  -- superficial, intermedio, profundo
    rango_km    VARCHAR(20) NOT NULL
);

-- =====================================================================
-- DIMENSIÓN: dim_calidad
-- =====================================================================
CREATE TABLE dim_calidad (
    quality_key      SERIAL PRIMARY KEY,
    status           VARCHAR(20) NOT NULL,  -- reviewed, automatic
    net              VARCHAR(10),
    location_source  VARCHAR(20),
    mag_source       VARCHAR(20),
    tiene_errores    BOOLEAN NOT NULL DEFAULT FALSE,
    nst              INTEGER
);

-- =====================================================================
-- TABLA DE HECHOS: fact_sismo
-- Grano: un registro por evento sísmico individual reportado por USGS
-- =====================================================================
CREATE TABLE fact_sismo (
    sismo_id          BIGSERIAL PRIMARY KEY,
    usgs_event_id     VARCHAR(30) NOT NULL UNIQUE,  -- id original del USGS, para trazabilidad
    date_key          INTEGER NOT NULL REFERENCES dim_fecha (date_key),
    location_key      INTEGER NOT NULL REFERENCES dim_ubicacion (location_key),
    magnitude_key     INTEGER NOT NULL REFERENCES dim_magnitud (magnitude_key),
    depth_key         INTEGER NOT NULL REFERENCES dim_profundidad (depth_key),
    quality_key       INTEGER NOT NULL REFERENCES dim_calidad (quality_key),

    -- Medidas numéricas (también viven en las dims correspondientes,
    -- se repiten aquí para evitar joins en agregaciones simples)
    mag               NUMERIC(4,2) NOT NULL,
    depth_km          NUMERIC(8,3) NOT NULL,
    gap               NUMERIC(6,2),
    rms               NUMERIC(6,4),
    horizontal_error  NUMERIC(8,3),
    mag_error         NUMERIC(5,3),

    -- Metadatos de calidad poco densos, consolidados en JSONB
    quality_meta      JSONB,

    created_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fact_date ON fact_sismo (date_key);
CREATE INDEX idx_fact_location ON fact_sismo (location_key);
CREATE INDEX idx_fact_magnitude ON fact_sismo (magnitude_key);
CREATE INDEX idx_fact_mag_value ON fact_sismo (mag);
CREATE INDEX idx_fact_quality_meta ON fact_sismo USING GIN (quality_meta);

-- =====================================================================
-- Comentarios de documentación (visibles en \d+ y en herramientas de catálogo)
-- =====================================================================
COMMENT ON TABLE fact_sismo IS
    'Tabla de hechos: un registro por evento sísmico individual del catálogo USGS (1990-2023).';
COMMENT ON COLUMN fact_sismo.usgs_event_id IS
    'ID original del evento en USGS, usado para deduplicación en el ETL y trazabilidad a la fuente.';
COMMENT ON COLUMN fact_sismo.quality_meta IS
    'Metadatos de calidad con alta tasa de nulidad en origen (horizontalError, depthError, magError, magNst), consolidados en JSONB.';