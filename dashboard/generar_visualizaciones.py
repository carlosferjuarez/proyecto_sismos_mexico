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


try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    CARTOPY_DISPONIBLE = True
except ImportError:
    CARTOPY_DISPONIBLE = False


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

        # OJO: estos datos demo son rectangulares, no siguen la forma real de México
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
    magnitudes = df["magnitude"].fillna(3)
    sizes = ((magnitudes - magnitudes.min() + 1.2) ** 3) * 4

    if CARTOPY_DISPONIBLE:
        fig = plt.figure(figsize=(10, 8))
        ax = plt.axes(projection=ccrs.PlateCarree())

        ax.set_extent([-118.5, -85.0, 13.0, 33.5], crs=ccrs.PlateCarree())

        ax.add_feature(cfeature.OCEAN, facecolor="#dbeaf7")
        ax.add_feature(cfeature.LAND, facecolor="#f5f1e6")
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linewidth=0.8, edgecolor="gray")

        gl = ax.gridlines(
            draw_labels=True,
            linewidth=0.4,
            color="gray",
            alpha=0.5,
            linestyle="--"
        )
        gl.top_labels = False
        gl.right_labels = False

        sc = ax.scatter(
            df["longitude"],
            df["latitude"],
            s=sizes,
            c=magnitudes,
            cmap="YlOrRd",
            alpha=0.45,
            edgecolors="black",
            linewidths=0.2,
            transform=ccrs.PlateCarree()
        )

        cbar = plt.colorbar(sc, ax=ax, shrink=0.8, pad=0.03)
        cbar.set_label("Magnitud")

        plt.title("Epicentros de sismos en México por magnitud", fontsize=14)

    else:
        print("Cartopy no está instalado. Generando mapa básico sin contorno geográfico.")

        plt.figure(figsize=(10, 7))

        sc = plt.scatter(
            df["longitude"],
            df["latitude"],
            s=sizes,
            c=magnitudes,
            cmap="YlOrRd",
            alpha=0.45,
            edgecolors="black",
            linewidths=0.2
        )

        plt.colorbar(sc, label="Magnitud")
        plt.xlabel("Longitud")
        plt.ylabel("Latitud")
        plt.title("Epicentros de sismos por magnitud")

        plt.xlim(-118.5, -85.0)
        plt.ylim(13.0, 33.5)
        plt.grid(alpha=0.3, linestyle="--")

    plt.tight_layout()
    plt.savefig(OUT / "01_mapa_epicentros.png", dpi=200, bbox_inches="tight")
    plt.close()


def serie_mensual(df):
    monthly = df.groupby("year_month").size().reset_index(name="total_sismos")
    monthly["year_month"] = pd.to_datetime(monthly["year_month"])
    monthly = monthly.sort_values("year_month")

    plt.figure(figsize=(11, 4.5))
    plt.plot(monthly["year_month"], monthly["total_sismos"], marker="o", linewidth=1.5, markersize=4)
    plt.grid(alpha=0.3, linestyle="--")
    plt.xlabel("Mes")
    plt.ylabel("Número de sismos")
    plt.title("Serie mensual de sismicidad")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUT / "02_serie_mensual.png", dpi=180)
    plt.close()


def top_regiones(df):
    top = df.groupby("region_name").size().sort_values(ascending=False).head(10)
    top = top.sort_values(ascending=True)

    plt.figure(figsize=(9, 5.5))
    plt.barh(top.index, top.values)
    plt.xlabel("Número de sismos")
    plt.title("Top 10 regiones por eventos registrados")
    plt.grid(axis="x", alpha=0.3, linestyle="--")
    plt.tight_layout()
    plt.savefig(OUT / "03_top_regiones.png", dpi=180)
    plt.close()


def heatmap_hora_mes(df):
    pivot = df.pivot_table(
        index="hour",
        columns="month",
        values="magnitude",
        aggfunc="count",
        fill_value=0
    )

    # Asegurar orden completo
    pivot = pivot.reindex(index=range(24), columns=range(1, 13), fill_value=0)

    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    plt.figure(figsize=(9, 6))
    im = plt.imshow(pivot, aspect="auto", origin="lower", cmap="YlOrRd")
    plt.colorbar(im, label="Número de sismos")
    plt.xticks(range(12), meses)
    plt.yticks(range(24), range(24))
    plt.xlabel("Mes")
    plt.ylabel("Hora UTC")
    plt.title("Heatmap de sismos por hora y mes")
    plt.tight_layout()
    plt.savefig(OUT / "04_heatmap_hora_mes.png", dpi=180)
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