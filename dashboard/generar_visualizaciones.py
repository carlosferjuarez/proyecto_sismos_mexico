"""Genera visualizaciones del proyecto desde PostgreSQL o con datos demo.

Si no hay variables de entorno AURORA_HOST/AURORA_PASSWORD, genera datos sintéticos
para previsualizar el estilo de las gráficas.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

OUT = Path(__file__).resolve().parent / "img"
OUT.mkdir(parents=True, exist_ok=True)


def get_engine():
    host = os.getenv("AURORA_HOST")
    password = os.getenv("AURORA_PASSWORD")
    if not host or not password:
        return None
    user = os.getenv("AURORA_USER", "postgres")
    db = os.getenv("AURORA_DATABASE", "northwind")
    port = os.getenv("AURORA_PORT", "5432")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}")


def demo_data(n=1200):
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
    regions = ["Sur-Pacifico de México", "Occidente de México", "Centro de México", "Centroamérica", "Andes Norte"]
    df = pd.DataFrame({
        "event_time_utc": rng.choice(dates, n),
        "region_name": rng.choice(regions, n, p=[0.38, 0.22, 0.12, 0.16, 0.12]),
        "magnitude": np.clip(rng.normal(4.2, 0.65, n), 3.0, 7.8),
        "depth_km": np.clip(rng.gamma(2.0, 25, n), 2, 250),
        "latitude": rng.uniform(14, 24, n),
        "longitude": rng.uniform(-108, -92, n),
    })
    df["month"] = pd.to_datetime(df["event_time_utc"]).dt.month
    df["year_month"] = pd.to_datetime(df["event_time_utc"]).dt.to_period("M").astype(str)
    df["hour"] = rng.integers(0, 24, n)
    return df


def load_data():
    engine = get_engine()
    if engine is None:
        print("Sin conexión definida; usando datos sintéticos para previsualización.")
        return demo_data()
    query = """
    SELECT
        fs.event_time_utc,
        dr.region_name,
        fs.magnitude,
        fs.depth_km,
        fs.latitude,
        fs.longitude,
        dd.month,
        TO_CHAR(dd.full_date, 'YYYY-MM') AS year_month,
        dh.hour
    FROM sismos_dwh.fact_sismos fs
    JOIN sismos_dwh.dim_region dr USING (region_key)
    JOIN sismos_dwh.dim_date dd USING (date_key)
    JOIN sismos_dwh.dim_hour dh USING (hour_key);
    """
    return pd.read_sql(query, engine)


def mapa_epicentros(df):
    plt.figure(figsize=(8, 6))
    sizes = (df["magnitude"].fillna(3) ** 2) * 4
    plt.scatter(df["longitude"], df["latitude"], s=sizes, alpha=0.35)
    plt.xlabel("Longitud")
    plt.ylabel("Latitud")
    plt.title("Epicentros de sismos por magnitud")
    plt.tight_layout()
    plt.savefig(OUT / "01_mapa_epicentros.png", dpi=160)
    plt.close()


def serie_mensual(df):
    monthly = df.groupby("year_month").size().reset_index(name="total_sismos")
    plt.figure(figsize=(10, 4))
    plt.plot(monthly["year_month"], monthly["total_sismos"], marker="o", linewidth=1)
    plt.xticks(rotation=90)
    plt.xlabel("Mes")
    plt.ylabel("Número de sismos")
    plt.title("Serie mensual de sismicidad")
    plt.tight_layout()
    plt.savefig(OUT / "02_serie_mensual.png", dpi=160)
    plt.close()


def top_regiones(df):
    top = df.groupby("region_name").size().sort_values(ascending=True).tail(10)
    plt.figure(figsize=(8, 5))
    plt.barh(top.index, top.values)
    plt.xlabel("Número de sismos")
    plt.title("Top regiones por eventos registrados")
    plt.tight_layout()
    plt.savefig(OUT / "03_top_regiones.png", dpi=160)
    plt.close()


def heatmap_hora_mes(df):
    pivot = df.pivot_table(index="hour", columns="month", values="magnitude", aggfunc="count", fill_value=0)
    plt.figure(figsize=(8, 6))
    plt.imshow(pivot, aspect="auto")
    plt.colorbar(label="Número de sismos")
    plt.xticks(range(len(pivot.columns)), pivot.columns)
    plt.yticks(range(len(pivot.index)), pivot.index)
    plt.xlabel("Mes")
    plt.ylabel("Hora UTC")
    plt.title("Heatmap hora × mes")
    plt.tight_layout()
    plt.savefig(OUT / "04_heatmap_hora_mes.png", dpi=160)
    plt.close()


def main():
    df = load_data()
    mapa_epicentros(df)
    serie_mensual(df)
    top_regiones(df)
    heatmap_hora_mes(df)
    print(f"Visualizaciones guardadas en {OUT}")


if __name__ == "__main__":
    main()
