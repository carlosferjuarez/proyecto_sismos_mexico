# Proyecto final — Análisis de sismicidad en México y LATAM

> Proyecto inspirado en la estructura del ejemplo del diplomado: modelo dimensional, ETL reproducible, SQL analítico y visualizaciones para dashboard.

## Resumen ejecutivo

| Campo | Valor |
|---|---|
| Pregunta analítica | ¿Dónde, cuándo y con qué intensidad se concentran los sismos registrados en México/LATAM, y qué patrones temporales aparecen por región, magnitud y profundidad? |
| Dataset | Eventos sísmicos de USGS Earthquake Catalog API filtrados por caja geográfica México/LATAM. |
| Fuente | USGS Earthquake Catalog API: `https://earthquake.usgs.gov/fdsnws/event/1/query` |
| Modelo | Esquema estrella con 1 fact + 4 dimensiones: fecha, hora, magnitud, región. |
| Infraestructura | PostgreSQL/Aurora PostgreSQL, schema `sismos_dwh`. |
| ETL | `scripts/etl_pipeline.py` descarga GeoJSON, transforma a tabla limpia y carga a PostgreSQL. |
| SQL avanzado | CTE, window functions, percentiles, ranking, densidad temporal y comparación mensual. |
| Dashboard | 4 visualizaciones estáticas con matplotlib: mapa, serie mensual, top regiones y heatmap hora × mes. |

## Problema y motivación

México es un país con alta actividad sísmica por su ubicación tectónica. Analizar los patrones espaciales y temporales de los sismos permite responder preguntas útiles para gestión de riesgo, comunicación pública y análisis exploratorio:

1. ¿Qué regiones concentran más sismos y cuáles tienen mayor magnitud promedio?
2. ¿Hay patrones por mes, día de la semana u hora?
3. ¿Cómo se distribuye la profundidad según la magnitud?
4. ¿Qué eventos destacan por magnitud o por poca profundidad?

## Origen de los datos

El ETL usa la API pública de USGS porque permite descargar datos de forma programática y reproducible. Para un proyecto estrictamente mexicano también se puede reemplazar la fuente por el catálogo del Servicio Sismológico Nacional, cuando esté disponible.

### Flujo end-to-end

```text
┌──────────────────────────────────────┐
│ USGS Earthquake Catalog API           │
│ GeoJSON por rango de fechas y bbox    │
└──────────────────┬───────────────────┘
                   │ HTTP GET
                   ▼
┌──────────────────────────────────────┐
│ ETL Python — etl_pipeline.py          │
│ Extract: requests                     │
│ Transform: pandas                     │
│ Load: SQLAlchemy/to_sql               │
└──────────────────┬───────────────────┘
                   │ INSERT
                   ▼
┌──────────────────────────────────────┐
│ PostgreSQL / Aurora                   │
│ Schema: sismos_dwh                    │
│ dim_date, dim_hour, dim_magnitude,    │
│ dim_region, fact_sismos               │
└──────────────────┬───────────────────┘
                   │ SELECT
                   ▼
┌──────────────────────────────────────┐
│ SQL analítico + dashboard matplotlib  │
└──────────────────────────────────────┘
```

## Estructura del repositorio

```text
proyecto_sismos_mexico/
├── README.md
├── requirements.txt
├── scripts/
│   ├── 01_schema_ddl.sql
│   ├── 02_dim_date_populate.sql
│   ├── 03_dim_magnitude_populate.sql
│   ├── 04_dim_region_populate.sql
│   └── etl_pipeline.py
├── analisis/
│   └── queries_analiticas.sql
├── dashboard/
│   ├── generar_visualizaciones.py
│   └── img/
└── data/
    ├── raw/
    └── processed/
```

## Cómo ejecutar

### 1. Crear el schema

```bash
psql "postgresql://postgres:TU_PASSWORD@HOST:5432/northwind" -f scripts/01_schema_ddl.sql
```

### 2. Poblar dimensiones

```bash
psql "postgresql://postgres:TU_PASSWORD@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -f scripts/02_dim_date_populate.sql
psql "postgresql://postgres:TU_PASSWORD@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -f scripts/03_dim_magnitude_populate.sql
psql "postgresql://postgres:TU_PASSWORD@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -f scripts/04_dim_region_populate.sql
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Descargar y cargar datos

Ejemplo para México, 2020–2025, magnitud mínima 3.5:

```bash
python scripts/etl_pipeline.py \
  --host HOST \
  --database northwind \
  --user postgres \
  --password TU_PASSWORD \
  --start-date 2020-01-01 \
  --end-date 2025-12-31 \
  --scope mexico \
  --min-magnitude 3.5
```

Para LATAM:

```bash
python scripts/etl_pipeline.py \
  --host HOST \
  --database northwind \
  --user postgres \
  --password TU_PASSWORD \
  --start-date 2020-01-01 \
  --end-date 2025-12-31 \
  --scope latam \
  --min-magnitude 4.0
```

### 5. Correr consultas analíticas

```bash
psql "postgresql://postgres:TU_PASSWORD@aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com:5432/northwind" -f analisis/queries_analiticas.sql
```

### 6. Generar visualizaciones

```bash
export AURORA_HOST='aurora-mod4.cluster-cspvdhxirjyp.us-east-1.rds.amazonaws.com'
export AURORA_PASSWORD='TU_PASSWORD'
export AURORA_USER="postgres"
export AURORA_DATABASE="northwind"
export AURORA_PORT="5432"
python dashboard/generar_visualizaciones.py
```

Las imágenes se guardan en `dashboard/img/`.

## Modelo dimensional

```text
                         ┌──────────────┐
                         │ dim_date     │
                         │ date_key PK  │
                         │ full_date    │
                         │ year/month   │
                         │ day_of_week  │
                         └──────▲───────┘
                                │
┌──────────────┐        ┌────────┴────────┐        ┌────────────────┐
│ dim_hour     │◄───────│   fact_sismos   │───────►│ dim_magnitude  │
│ hour_key PK  │        │ event_id PK     │        │ magnitude_key  │
│ hour         │        │ date_key FK     │        │ bucket         │
│ day_part     │        │ hour_key FK     │        │ min/max mag    │
└──────────────┘        │ region_key FK   │        └────────────────┘
                        │ mag_key FK      │
                        │ magnitude       │
                        │ depth_km        │
                        │ latitude        │
                        │ longitude       │
                        │ place           │
                        └────────▲────────┘
                                 │
                         ┌───────┴───────┐
                         │ dim_region    │
                         │ region_key PK │
                         │ region_name   │
                         │ country_scope │
                         │ bbox coords   │
                         └───────────────┘
```

## Decisiones de diseño

- **Grano de la fact:** una fila por evento sísmico reportado por la API.
- **Fecha y hora separadas:** permite analizar estacionalidad por mes y patrones por hora.
- **Región derivada:** se asigna con bounding boxes sencillos para México y LATAM; puede refinarse con shapefiles si el curso lo permite.
- **Magnitud como dimensión:** facilita agrupar por rangos: ligera, moderada, fuerte, mayor.
- **Profundidad como medida:** permite comparar eventos superficiales vs profundos.

## Visualizaciones propuestas

1. Mapa de epicentros por magnitud.
2. Serie mensual de número de sismos.
3. Top 10 regiones por número de eventos.
4. Heatmap de eventos por hora y mes.

## Posibles extensiones

- Unir con población por estado/país para medir exposición.
- Agregar sismos históricos del SSN como segunda fuente.
- Clasificar eventos por cercanía a CDMX, costa del Pacífico o zona de subducción.
- Crear dashboard en Streamlit o Power BI con los resultados SQL.
