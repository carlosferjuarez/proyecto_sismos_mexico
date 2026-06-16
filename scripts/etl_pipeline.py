"""
ETL. Sismicidad Global 1990-2023 (USGS / Kaggle)
Proyecto Módulo 4. Diplomado UNAM - IIMAS

Flujo:
    1. EXTRACT   -> descarga el dataset vía Kaggle API a una carpeta temporal
    2. TRANSFORM -> limpieza, normalización y construcción de dimensiones
    3. LOAD      -> upsert idempotente a Aurora PostgreSQL

Requiere ~/.kaggle/kaggle.json configurado (ver README.md).


Probar conexión con Kaggle
python3 -c "import kaggle; kaggle.api.authenticate(); print('Kaggle OK')"

Probar conexión con Aurora
python3 -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql+psycopg2://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind')
with engine.connect() as conn:
    print('Aurora OK')
"

Crear las tablas en Aurora ejecutando el DDL
psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -f scripts/01_schema_ddl.sql

Verifica que las tablas quedaron creadas
psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "\dt"

Corremos el ETL Completo
python3 scripts/etl_pipeline.py --host aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com --password CEwXrsjk3cP17q2KIGodJbEk --database northwind


psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "TRUNCATE TABLE fact_sismo, dim_fecha, dim_ubicacion, dim_magnitud, dim_profundidad, dim_calidad RESTART IDENTITY CASCADE;"



Obtener nombres de columnas del dataset
python3 -c "
import kaggle
kaggle.api.dataset_download_files('alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023', path='/tmp/sismos_check', unzip=True)
import pandas as pd
df = pd.read_csv('/tmp/sismos_check/Eartquakes-1990-2023.csv', nrows=5)
print(df.columns.tolist())
"
NOTA DE DISEÑO: el CSV real de este dataset NO trae las columnas estándar del
catálogo USGS (magType, nst, gap, rms, horizontalError, etc.). En su lugar trae:
    time (epoch ms), date (string con tz), place, status, tsunami,
    significance, data_type, magnitudo, state, longitude, latitude, depth
El modelo dimensional se ajustó a esta realidad: dim_calidad ahora se basa en
status/data_type/tsunami, y dim_magnitud ya no normaliza magType (no existe).

psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "TRUNCATE TABLE fact_sismo, dim_fecha, dim_ubicacion, dim_magnitud, dim_profundidad, dim_calidad RESTART IDENTITY CASCADE;"

psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT place_raw, latitude, longitude, COUNT(*) AS n_filas
FROM dim_ubicacion
GROUP BY place_raw, latitude, longitude
HAVING COUNT(*) > 1
ORDER BY n_filas DESC
LIMIT 10;
"


psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT place_raw, latitude, longitude, COUNT(*) AS n_filas
FROM dim_ubicacion
GROUP BY place_raw, latitude, longitude
HAVING COUNT(*) > 1
ORDER BY n_filas DESC
LIMIT 5;
"



psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT full_timestamp, COUNT(*) AS n_filas
FROM dim_fecha
GROUP BY full_timestamp
HAVING COUNT(*) > 1
ORDER BY n_filas DESC
LIMIT 5;
"

psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT mag_value, COUNT(*) AS n_filas
FROM dim_magnitud
GROUP BY mag_value
HAVING COUNT(*) > 1
ORDER BY n_filas DESC
LIMIT 5;
"


psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT depth_km, COUNT(*) AS n_filas
FROM dim_profundidad
GROUP BY depth_km
HAVING COUNT(*) > 1
ORDER BY n_filas DESC
LIMIT 5;
"

psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT * FROM dim_magnitud WHERE mag_value = 2.36;
"

psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT COUNT(*) FROM dim_magnitud;
"


psql "postgresql://postgres:CEwXrsjk3cP17q2KIGodJbEk@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -c "
SELECT magnitude_key, mag_value,
       mag_type_raw IS NULL AS es_null,
       mag_type_raw = '' AS es_string_vacio,
       length(mag_type_raw) AS longitud
FROM dim_magnitud WHERE mag_value = 2.36;
"


"""


import argparse
import logging
import shutil
import tempfile
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("etl_sismos")

KAGGLE_DATASET = "alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023"
CSV_FILENAME_HINT = "Eartquakes-1990-2023.csv"  # nombre real del archivo (con el typo de origen)

PAISES_CONOCIDOS = [
    "mexico", "alaska", "hawaii", "california", "japan", "indonesia", "chile",
    "peru", "philippines", "turkey", "greece", "italy", "china", "russia",
    "papua new guinea", "new zealand", "fiji", "tonga", "vanuatu", "ecuador",
    "colombia", "argentina", "guatemala", "el salvador", "nicaragua",
]


# =====================================================================
# 1. EXTRACT
# =====================================================================

def extract(tmp_dir: Path) -> pd.DataFrame:
    """Descarga el dataset de Kaggle a una carpeta temporal y lo carga a un DataFrame."""
    try:
        import kaggle
    except ImportError as exc:
        raise RuntimeError(
            "Falta el paquete 'kaggle'. Instálalo con: pip install kaggle"
        ) from exc

    log.info("Descargando dataset de Kaggle a carpeta temporal (no se guarda en el repo)...")
    kaggle.api.dataset_download_files(
        KAGGLE_DATASET, path=str(tmp_dir), unzip=True, quiet=False
    )

    csv_files = list(tmp_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("No se encontró ningún CSV tras descomprimir el dataset.")

    csv_path = csv_files[0]
    log.info(f"Leyendo {csv_path.name} ...")
    df = pd.read_csv(csv_path, low_memory=False)
    log.info(f"Filas leídas: {len(df):,}")
    return df


# =====================================================================
# 2. TRANSFORM
# =====================================================================

def categorize_magnitude(mag: float) -> str:
    if mag < 2:
        return "micro"
    if mag < 4:
        return "menor"
    if mag < 5:
        return "moderado"
    if mag < 7:
        return "fuerte"
    return "mayor"


def categorize_depth(depth_km: float) -> tuple[str, str]:
    if depth_km < 70:
        return "superficial", "0-70km"
    if depth_km < 300:
        return "intermedio", "70-300km"
    return "profundo", ">300km"


def infer_country(place: str, state: str) -> str:
    """Heurística simple: busca un país conocido en 'place'; si no, usa 'state' como fallback."""
    text_search = f"{place}".lower() if isinstance(place, str) else ""
    for pais in PAISES_CONOCIDOS:
        if pais in text_search:
            return pais.title()
    # Fallback: si el 'state' es un estado de EE.UU. conocido lo dejamos como país "United States"
    return state if isinstance(state, str) else "Unknown"


def transform(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    log.info("Iniciando limpieza y transformación...")

    df = df.rename(columns={c: c.strip() for c in df.columns})

    # --- Generar un ID de negocio propio (el dataset no trae uno) ---
    df = df.reset_index(drop=True)
    df["usgs_event_id"] = "EVT-" + df.index.astype(str) + "-" + df["time"].astype(str)

    # --- Deduplicación de eventos (duplicados blandos por mismas coordenadas/tiempo) ---
    before = len(df)
    df["status_priority"] = (df["status"].str.lower() == "reviewed").astype(int)
    df = (
        df.sort_values("status_priority", ascending=False)
        .drop_duplicates(subset=["time", "latitude", "longitude"], keep="first")
        .drop(columns="status_priority")
    )
    log.info(f"Duplicados blandos eliminados: {before - len(df):,}")

    # --- Limpieza de magnitud, profundidad y coordenadas ---
    df = df.dropna(subset=["magnitudo", "depth", "latitude", "longitude", "date"])
    df = df[(df["depth"] >= -10) & (df["depth"] <= 800)]
    df = df[(df["magnitudo"] >= -2) & (df["magnitudo"] <= 10)]

    df["mag_categoria"] = df["magnitudo"].apply(categorize_magnitude)

    depth_info = df["depth"].apply(categorize_depth)
    df["depth_categoria"] = depth_info.apply(lambda t: t[0])
    df["depth_rango"] = depth_info.apply(lambda t: t[1])

    # --- Ubicación: 'state' ya viene parseado; inferimos país con heurística ---
    df["country"] = df.apply(lambda r: infer_country(r["place"], r["state"]), axis=1)
    df["es_mexico"] = df["country"].str.contains("mexico", case=False, na=False)

    # --- Fecha/hora: usamos 'date' (string con tz) como fuente principal, más confiable que 'time' (epoch ms) ---
    df["full_timestamp"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["full_timestamp"])
    df["year"] = df["full_timestamp"].dt.year
    df["month"] = df["full_timestamp"].dt.month
    df["month_name"] = df["full_timestamp"].dt.month_name()
    df["day"] = df["full_timestamp"].dt.day
    df["hour_utc"] = df["full_timestamp"].dt.hour
    df["day_of_week"] = df["full_timestamp"].dt.day_name()
    df["decade"] = (df["year"] // 10 * 10).astype(str) + "s"
    df["is_weekend"] = df["day_of_week"].isin(["Saturday", "Sunday"])

    # --- Calidad: ya no hay errores instrumentales; usamos status/data_type/tsunami ---
    df["tsunami_bool"] = df["tsunami"].astype(bool)
    df["tiene_alerta_tsunami"] = df["tsunami_bool"]

    log.info(f"Filas tras limpieza: {len(df):,}")

    # =================================================================
    # Construcción de dimensiones (deduplicadas)
    # =================================================================
    dim_fecha = (
        df[["full_timestamp", "year", "month", "month_name", "day",
            "hour_utc", "day_of_week", "decade", "is_weekend"]]
        .drop_duplicates(subset=["full_timestamp"])
        .reset_index(drop=True)
    )

    dim_ubicacion = (
        df[["place", "country", "state", "latitude", "longitude", "es_mexico"]]
        .rename(columns={"place": "place_raw", "state": "region"})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dim_ubicacion["zona_tectonica"] = None  # placeholder para enriquecimiento futuro

    dim_magnitud = (
        df[["magnitudo", "mag_categoria"]]
        .rename(columns={"magnitudo": "mag_value", "mag_categoria": "categoria"})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dim_magnitud["mag_type_raw"] = None
    dim_magnitud["mag_type_normalized"] = "unknown"  # el dataset no trae magType

    dim_profundidad = (
        df[["depth", "depth_categoria", "depth_rango"]]
        .rename(columns={"depth": "depth_km", "depth_categoria": "categoria", "depth_rango": "rango_km"})
        .drop_duplicates()
        .reset_index(drop=True)
    )
    
    dim_calidad = (
        df[["status", "data_type", "tiene_alerta_tsunami"]]
        .drop_duplicates()
        .reset_index(drop=True)
        .rename(columns={"tiene_alerta_tsunami": "tiene_errores"})
    )
    dim_calidad["net"] = None
    dim_calidad["location_source"] = None
    dim_calidad["mag_source"] = None
    dim_calidad["nst"] = None
    # nota: reutilizamos la columna 'tiene_errores' del esquema original para guardar
    # la bandera de tsunami, ya que el dataset no trae métricas de error instrumental.

    fact = df[[
        "usgs_event_id", "full_timestamp", "place", "country", "state", "latitude", "longitude", "es_mexico",
        "magnitudo", "mag_categoria",
        "depth", "depth_categoria", "depth_rango",
        "status", "data_type", "tiene_alerta_tsunami", "significance",
    ]]

    return {
        "dim_fecha": dim_fecha,
        "dim_ubicacion": dim_ubicacion,
        "dim_magnitud": dim_magnitud,
        "dim_profundidad": dim_profundidad,
        "dim_calidad": dim_calidad,
        "fact_staging": fact,
    }


# =====================================================================
# 3. LOAD
# =====================================================================

def get_engine(host: str, password: str, database: str, user: str, port: int) -> Engine:
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    return create_engine(url)

def load_dimension(df: pd.DataFrame, table_name: str, engine: Engine) -> pd.DataFrame:
    """Carga una dimensión de forma idempotente: si ya hay datos en la tabla,
    inserta solo las filas que aún no existen (comparando por todas las
    columnas no-clave). Permite reintentar el ETL sin duplicar registros."""
    with engine.connect() as conn:
        existing = pd.read_sql(f"SELECT * FROM {table_name}", conn)

    key_col = [c for c in existing.columns if c.endswith("_key")][0]
    compare_cols = [c for c in df.columns if c in existing.columns and c != key_col]

    df = df.copy()
    # Importante: deduplicar el DataFrame nuevo ANTES de compararlo contra Aurora.
    # Sin este paso, si la muestra de entrada ya trae filas repetidas por sus
    # columnas de comparación (ej. mismo place/lat/lon en distintos eventos),
    # cada una se trata como "nueva" frente a Aurora y se inserta más de una vez.
    df = df.drop_duplicates(subset=compare_cols).reset_index(drop=True)

    for col in compare_cols:
        if pd.api.types.is_datetime64_any_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(existing[col]):
            df[col] = pd.to_datetime(df[col], utc=True)
            existing[col] = pd.to_datetime(existing[col], utc=True)

    # BUG CRÍTICO RESUELTO: pandas.merge() nunca empareja NaN/None contra NaN/None
    # (igual que SQL trata cada NULL como distinto). Si una columna de comparación
    # es NULL en todas las filas (ej. mag_type_raw, que no existe en este dataset),
    # el merge jamás encuentra coincidencia y cada fila se trata como "nueva",
    # generando duplicados en cada reintento. Solución: reemplazar temporalmente
    # los nulos por un centinela idéntico solo para la comparación.
    SENTINEL = "__NULL_SENTINEL__"
    df_compare = df[compare_cols].fillna(SENTINEL)
    existing_compare = existing[compare_cols].fillna(SENTINEL)

    if len(existing) > 0:
        merged = df_compare.merge(
            existing_compare, on=compare_cols, how="left", indicator=True
        )
        is_new = (merged["_merge"] == "left_only").values
        new_rows = df[is_new]
    else:
        new_rows = df

    if len(new_rows) > 0:
        new_rows.to_sql(table_name, engine, if_exists="append", index=False)
        log.info(f"  {table_name}: +{len(new_rows):,} filas nuevas insertadas")
    else:
        log.info(f"  {table_name}: sin filas nuevas (ya estaban cargadas)")

    with engine.connect() as conn:
        loaded = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    log.info(f"  {table_name}: {len(loaded):,} filas totales en destino")
    return loaded

def load(tables: dict[str, pd.DataFrame], engine: Engine) -> None:
    log.info("Cargando dimensiones a Aurora...")

    dim_fecha = load_dimension(tables["dim_fecha"], "dim_fecha", engine)
    dim_ubicacion = load_dimension(tables["dim_ubicacion"], "dim_ubicacion", engine)
    dim_magnitud = load_dimension(tables["dim_magnitud"], "dim_magnitud", engine)
    dim_profundidad = load_dimension(tables["dim_profundidad"], "dim_profundidad", engine)
    dim_calidad = load_dimension(tables["dim_calidad"], "dim_calidad", engine)

    log.info("Resolviendo llaves foráneas en la tabla de hechos...")
    fact = tables["fact_staging"].copy()

    fact["full_timestamp"] = pd.to_datetime(fact["full_timestamp"], utc=True)
    dim_fecha["full_timestamp"] = pd.to_datetime(dim_fecha["full_timestamp"], utc=True)
    fact = fact.merge(dim_fecha[["date_key", "full_timestamp"]], on="full_timestamp", how="left")
    fact = fact.merge(
        dim_ubicacion[["location_key", "place_raw", "latitude", "longitude"]],
        left_on=["place", "latitude", "longitude"],
        right_on=["place_raw", "latitude", "longitude"],
        how="left",
    )
    fact = fact.merge(
        dim_magnitud[["magnitude_key", "mag_value"]],
        left_on="magnitudo", right_on="mag_value", how="left",
    )
    fact = fact.merge(
        dim_profundidad[["depth_key", "depth_km"]],
        left_on="depth", right_on="depth_km", how="left",
    )
    fact = fact.merge(
        dim_calidad[["quality_key", "status", "data_type"]],
        on=["status", "data_type"], how="left",
    )

    fact["quality_meta"] = fact.apply(
        lambda r: '{"tsunami": %s, "significance": %s}' % (
            str(r["tiene_alerta_tsunami"]).lower(), r["significance"]
        ),
        axis=1,
    )

    fact_final = fact[[
        "usgs_event_id", "date_key", "location_key", "magnitude_key",
        "depth_key", "quality_key", "magnitudo", "depth", "quality_meta",
    ]].rename(columns={"magnitudo": "mag", "depth": "depth_km"})

    fact_final = fact_final.dropna(
        subset=["date_key", "location_key", "magnitude_key", "depth_key", "quality_key"]
    )

    # Salvaguarda: los merges contra las dimensiones pueden multiplicar filas si
    # alguna combinación de columnas de comparación no es perfectamente única
    # en la dimensión (ej. mismo place/lat/lon repetido). Detectamos y reportamos
    # antes de quedarnos solo con la primera ocurrencia de cada evento.
    dup_count = fact_final["usgs_event_id"].duplicated().sum()
    if dup_count > 0:
        log.warning(
            f"Se detectaron {dup_count:,} filas con usgs_event_id duplicado tras los "
            "merges de dimensiones (probable 1-a-muchos en algún merge). "
            "Conservando solo la primera ocurrencia de cada evento."
        )
        fact_final = fact_final.drop_duplicates(subset=["usgs_event_id"], keep="first")

    log.info(f"Insertando {len(fact_final):,} filas en fact_sismo (upsert por usgs_event_id)...")
    with engine.begin() as conn:
        fact_final.to_sql("fact_sismo_staging", conn, if_exists="replace", index=False)
        conn.execute(text("""
            INSERT INTO fact_sismo (
                usgs_event_id, date_key, location_key, magnitude_key,
                depth_key, quality_key, mag, depth_km, quality_meta
            )
            SELECT usgs_event_id, date_key, location_key, magnitude_key,
                   depth_key, quality_key, mag, depth_km, quality_meta::jsonb
            FROM fact_sismo_staging
            ON CONFLICT (usgs_event_id) DO UPDATE SET
                mag = EXCLUDED.mag,
                depth_km = EXCLUDED.depth_km,
                quality_key = EXCLUDED.quality_key;
        """))
        conn.execute(text("DROP TABLE fact_sismo_staging;"))

    log.info("Carga completada.")


# =====================================================================
# MAIN
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="ETL Sismos Kaggle -> Aurora PostgreSQL")
    parser.add_argument("--host", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="northwind")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--sample", type=int, default=None,
                         help="Si se especifica, solo procesa una muestra de N filas (para pruebas rápidas)")
    args = parser.parse_args()

    tmp_dir = Path(tempfile.mkdtemp(prefix="sismos_kaggle_"))
    log.info(f"Carpeta temporal de trabajo: {tmp_dir}")

    try:
        df_raw = extract(tmp_dir)
        if args.sample:
            df_raw = df_raw.sample(n=min(args.sample, len(df_raw)), random_state=42)
            log.info(f"Modo muestra activado: usando {len(df_raw):,} filas")
        tables = transform(df_raw)
        engine = get_engine(args.host, args.password, args.database, args.user, args.port)
        load(tables, engine)
    finally:
        if not args.keep_temp:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            log.info("Carpeta temporal eliminada (el CSV de 494MB nunca se quedó en el repo).")


if __name__ == "__main__":
    main()
