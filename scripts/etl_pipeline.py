"""ETL para descargar sismos de USGS y cargarlos a PostgreSQL/Aurora.

Ejemplo:
python scripts/etl_pipeline.py --host HOST --database northwind --user postgres \
  --password TU_PASSWORD --start-date 2020-01-01 --end-date 2025-12-31 \
  --scope mexico --min-magnitude 3.5
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Dict, Tuple

import pandas as pd
import requests
from sqlalchemy import create_engine, text

USGS_ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"

BBOX = {
    # Caja aproximada para México: lat 14–33.5, lon -118.5–-86
    "mexico": {"minlatitude": 14.0, "maxlatitude": 33.5, "minlongitude": -118.5, "maxlongitude": -86.0},
    # Caja amplia para Latinoamérica y Caribe
    "latam": {"minlatitude": -56.0, "maxlatitude": 33.5, "minlongitude": -118.5, "maxlongitude": -34.0},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ETL sismos USGS -> PostgreSQL")
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--password", required=True)
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--scope", choices=["mexico", "latam"], default="mexico")
    parser.add_argument("--min-magnitude", type=float, default=3.5)
    return parser.parse_args()


def fetch_usgs(start_date: str, end_date: str, scope: str, min_magnitude: float) -> Dict:
    params = {
        "format": "geojson",
        "starttime": start_date,
        "endtime": end_date,
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
        "limit": 20000,
        **BBOX[scope],
    }
    response = requests.get(USGS_ENDPOINT, params=params, timeout=90)
    response.raise_for_status()
    return response.json()


def magnitude_key(mag: float | None) -> int:
    if mag is None or pd.isna(mag):
        return 1
    if mag < 3:
        return 1
    if mag < 4:
        return 2
    if mag < 5:
        return 3
    if mag < 6:
        return 4
    if mag < 7:
        return 5
    return 6


def transform(payload: Dict) -> pd.DataFrame:
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {}) or {}
        coords = geom.get("coordinates", [None, None, None])
        lon, lat, depth = coords[0], coords[1], coords[2]
        event_ms = props.get("time")
        if event_ms is None:
            continue
        event_dt = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
        rows.append({
            "event_id": feature.get("id"),
            "event_time_utc": event_dt,
            "date_key": int(event_dt.strftime("%Y%m%d")),
            "hour_key": event_dt.hour,
            "magnitude": props.get("mag"),
            "magnitude_key": magnitude_key(props.get("mag")),
            "depth_km": depth,
            "latitude": lat,
            "longitude": lon,
            "place": props.get("place"),
            "tsunami": props.get("tsunami"),
            "felt_reports": props.get("felt"),
            "alert_level": props.get("alert"),
            "source_net": props.get("net"),
        })
    return pd.DataFrame(rows)


def resolve_regions(df: pd.DataFrame, engine) -> pd.DataFrame:
    regions = pd.read_sql("SELECT * FROM sismos_dwh.dim_region", engine)

    def pick_region(row) -> int:
        lat, lon = row["latitude"], row["longitude"]
        matches = regions[
            (regions["min_lat"] <= lat) & (lat <= regions["max_lat"]) &
            (regions["min_lon"] <= lon) & (lon <= regions["max_lon"])
        ]
        # Preferir regiones específicas sobre 'Otra región'.
        matches = matches[matches["region_name"] != "Otra región"]
        if not matches.empty:
            return int(matches.iloc[0]["region_key"])
        return int(regions.loc[regions["region_name"] == "Otra región", "region_key"].iloc[0])

    df["region_key"] = df.apply(pick_region, axis=1)
    return df


def load(df: pd.DataFrame, engine) -> None:
    if df.empty:
        print("No hay eventos para cargar con esos filtros.")
        return

    cols = [
        "event_id", "date_key", "hour_key", "magnitude_key", "region_key", "event_time_utc",
        "magnitude", "depth_km", "latitude", "longitude", "place", "tsunami", "felt_reports",
        "alert_level", "source_net",
    ]
    temp_table = "tmp_fact_sismos"
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
    df[cols].to_sql(temp_table, engine, if_exists="replace", index=False, method="multi", chunksize=1000)

    insert_sql = f"""
    INSERT INTO sismos_dwh.fact_sismos ({', '.join(cols)})
    SELECT {', '.join(cols)}
    FROM {temp_table}
    ON CONFLICT (event_id) DO UPDATE SET
        magnitude = EXCLUDED.magnitude,
        depth_km = EXCLUDED.depth_km,
        place = EXCLUDED.place,
        alert_level = EXCLUDED.alert_level,
        felt_reports = EXCLUDED.felt_reports;
    DROP TABLE IF EXISTS {temp_table};
    """
    with engine.begin() as conn:
        conn.execute(text(insert_sql))
        count = conn.execute(text("SELECT COUNT(*) FROM sismos_dwh.fact_sismos")).scalar_one()
    print(f"Carga terminada. Total en fact_sismos: {count:,}")


def main() -> None:
    args = parse_args()
    engine = create_engine(
        f"postgresql+psycopg2://{args.user}:{args.password}@{args.host}:{args.port}/{args.database}"
    )
    print("Descargando eventos de USGS...")
    payload = fetch_usgs(args.start_date, args.end_date, args.scope, args.min_magnitude)
    print(f"Eventos recibidos: {payload.get('metadata', {}).get('count', 'NA')}")
    df = transform(payload)
    print(f"Eventos transformados: {len(df):,}")
    df = resolve_regions(df, engine)
    load(df, engine)


if __name__ == "__main__":
    main()
