# Análisis de Sismicidad 1990–2023

> Proyecto Módulo 4 - Diplomado UNAM - IIMAS  

---

## Resumen

| Campo | Valor |
|---|---|
| **Pregunta analítica** | ¿Cuáles son los patrones espacio-temporales de la sismicidad global entre 1990 y 2023, y cómo se compara la actividad sísmica de México frente a otras regiones de alta sismicidad mundial? |
| **Dataset** | USGS Earthquake Dataset 1990–2023 — Kaggle (~200k registros) |
| **Fuente** | [kaggle.com/datasets/alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023](https://www.kaggle.com/datasets/alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023) |
| **Modelo** | Esquema estrella: 1 tabla de hechos + 4 dimensiones |
| **Infraestructura** | Aurora PostgreSQL en AWS |
| **ETL** | `scripts/etl_pipeline.py` — pandas + SQLAlchemy |
| **SQL avanzado** | Window functions, CTEs con LAG, PERCENTILE_CONT, JSONB |
| **Dashboard** | (mínimo 3 visualizaciones interactivas) |

---

## Problema y motivación

México es uno de los países más sísmicos del mundo, ubicado sobre la convergencia de cinco
placas tectónicas. Los sismos del 19 de septiembre de 1985 y 2017 dejaron una huella
profunda en la memoria colectiva y pusieron en evidencia la necesidad de entender los
patrones de actividad sísmica para la toma de decisiones en materia de protección civil,
construcción y política pública.

Este proyecto responde tres preguntas concretas:

1. **¿Qué zonas geográficas y rangos de profundidad concentran los sismos de mayor
   magnitud a nivel global y en México específicamente?**
2. **¿Existe una tendencia temporal en la frecuencia e intensidad de los sismos entre
   1990 y 2023?**
3. **¿Cómo varía la calidad de los datos sísmicos (`reviewed` vs `automatic`) según
   la red de detección, y qué impacto tiene en el análisis?**

---

## Origen de los datos

El dataset proviene del catálogo del **United States Geological Survey (USGS)**, publicado
en Kaggle. Cada registro corresponde a un evento sísmico individual con atributos
geofísicos, temporales y de calidad instrumental.

### Problemáticas de limpieza identificadas

| Columna | Problema |
|---|---|
| `magType` | Múltiples notaciones heterogéneas (`ml`, `mb`, `mw`, `md`, `ms`, `mww`) que requieren normalización |
| `place` | Campo de texto libre — mezcla de formatos, idiomas y niveles de detalle geográfico |
| `depth` | Valores negativos y outliers extremos (sismos reportados a -5 km o >700 km) |
| `horizontalError` / `depthError` / `magError` | Nulos en ~40–60% de registros según red de detección |
| `status` | Mezcla de eventos `automatic` (preliminares) vs `reviewed` (validados) |
| Duplicados blandos | Un mismo evento registrado por múltiples redes con IDs distintos |

Estas problemáticas son abordadas explícitamente en la fase de **Transform** del ETL.

---

## Modelo dimensional

Ver diagrama completo en [`docs/diagrama_modelo.md`](docs/diagrama_modelo.md)

### Esquema estrella — resumen

**Grano de la fact:** un registro por evento sísmico individual reportado por el USGS.

---

## Cómo ejecutar

### 1. Requisitos previos

```bash
pip install pandas sqlalchemy psycopg2-binary kaggle tqdm
```

### 2. Descargar el dataset de Kaggle

```bash
# Requiere tener configurado ~/.kaggle/kaggle.json con tus credenciales
kaggle datasets download -d alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023
unzip the-ultimate-earthquake-dataset-from-1990-2023.zip -d datasets/
```

### 3. Crear el schema en Aurora

```bash
psql "postgresql://postgres:TU_PASSWORD@TU_HOST:5432/postgres" \
     -f scripts/01_schema_ddl.sql
```

### 4. Ejecutar el ETL

```bash
python scripts/etl_pipeline.py \
    --host TU_HOST \
    --password TU_PASSWORD \
    --database postgres
```

### 5. Abrir el dashboard

Abre el archivo `dashboard/sismos_dashboard.pbix` en Power BI Desktop y actualiza
la conexión a tu instancia de Aurora.

---

## SQL avanzado destacado

Las queries analíticas viven en `scripts/02_queries_analiticas.sql` e incluyen:

- **Window functions**: ranking de países por magnitud promedio anual con `RANK() OVER`
- **CTE + LAG**: detección de semanas con actividad sísmica anómala (>2x la media)
- **PERCENTILE_CONT**: distribución de magnitud por zona tectónica
- **JSONB**: metadatos de calidad del evento almacenados como objeto y consultados con `->>`

---

## Dashboard — visualizaciones

| # | Visualización | Pregunta que responde |
|---|---|---|
| 1 | Mapa de calor global de epicentros (lat/lon × magnitud) | ¿Dónde se concentra la sismicidad de mayor impacto? |
| 2 | Serie temporal de frecuencia mensual por categoría de magnitud | ¿Hay tendencias o ciclos en 30 años? |
| 3 | Distribución profundidad vs magnitud por región tectónica | ¿Los sismos superficiales son más destructivos? |
| 4 | Comparativa México vs mundo: % de sismos ≥5.0 por año | ¿Qué tan relevante es México en la sismicidad global? |

---

## Hallazgos principales

> *Esta sección se completará una vez ejecutado el ETL y generadas las visualizaciones.*

---

## Estructura del repositorio

---

## Referencias

- [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/)
- [Kaggle Dataset — Alessandro Lobello](https://www.kaggle.com/datasets/alessandrolobello/the-ultimate-earthquake-dataset-from-1990-2023)
- [Servicio Sismológico Nacional — UNAM](http://www.ssn.unam.mx/)
- Material del módulo: Tema 02 (Modelo dimensional), Tema 04 (ETL Python), Tema 05 (SQL avanzado)