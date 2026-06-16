## Diagrama

```text
                        ┌─────────────────┐
                        │   dim_fecha      │
                        │──────────────────│
                        │ date_key PK      │
                        │ full_timestamp   │
                        │ year             │
                        │ month            │
                        │ month_name       │
                        │ day              │
                        │ hour_utc         │
                        │ day_of_week      │
                        │ decade           │
                        │ is_weekend       │
                        └────────┬─────────┘
                                 │
┌──────────────────┐    ┌────────┴──────────────────┐    ┌──────────────────────┐
│  dim_profundidad  │    │      fact_sismo            │    │   dim_magnitud        │
│───────────────────│    │─────────────────────────  │    │───────────────────────│
│ depth_key PK      │◄───│ sismo_id PK                │───►│ magnitude_key PK      │
│ depth_km          │    │ date_key FK                │    │ mag_value             │
│ categoria         │    │ location_key FK             │    │ mag_type_raw          │
│  (superficial     │    │ magnitude_key FK            │    │ mag_type_normalized   │
│   intermedio      │    │ depth_key FK                │    │ categoria             │
│   profundo)       │    │ quality_key FK               │    │  (micro/menor/        │
│ rango_km          │    │ ── medidas ──               │    │   moderado/fuerte/    │
└───────────────────┘    │ mag NUMERIC(4,2)            │    │   mayor)              │
                         │ depth_km NUMERIC(8,3)       │    └───────────────────────┘
                         │ gap NUMERIC(6,2)            │
                         │ rms NUMERIC(6,4)            │
                         │ horizontal_error            │
                         │ mag_error                   │
                         │ quality_meta JSONB           │
                         └──────────┬───────────────────┘
                                    │
                     ┌──────────────┴───────────────┐
                     │                              │
           ┌─────────┴─────────┐         ┌───────────┴───────────┐
           │  dim_ubicacion    │         │    dim_calidad         │
           │───────────────────│         │────────────────────────│
           │ location_key PK   │         │ quality_key PK         │
           │ place_raw         │         │ status                 │
           │ country           │         │  (reviewed/automatic)  │
           │ region            │         │ net                    │
           │ latitude          │         │ location_source        │
           │ longitude         │         │ mag_source             │
           │ zona_tectonica    │         │ tiene_errores BOOLEAN  │
           │ es_mexico BOOL    │         │ nst                    │
           └───────────────────┘         └────────────────────────┘
```

---

## Grano de la fact

**Una fila por evento sísmico individual** tal como lo reporta el USGS en su catálogo.
Un mismo evento físico puede aparecer con múltiples registros si fue detectado por
distintas redes (`net`). La fase de Transform del ETL elimina estos duplicados blandos
conservando el registro con `status = 'reviewed'` o, en su ausencia, el de mayor `magNst`.

---

## Decisiones de diseño

### ¿Por qué `dim_calidad` como dimensión separada?

La calidad instrumental del registro es una variable analítica por derecho propio, no un
simple atributo de la medición. Permite responder preguntas como:
- ¿Qué porcentaje de sismos ≥5.0 tienen revisión humana (`reviewed`)?
- ¿Qué redes de detección (`net`) generan datos más completos?
- ¿Los errores de localización son mayores en zonas oceánicas que continentales?

Separarlo en su propia dimensión evita mezclar atributos de calidad con medidas físicas
en la fact, y facilita filtrar el dashboard por nivel de confianza del dato.

### ¿Por qué `quality_meta JSONB` en la fact?

Los campos `horizontalError`, `depthError`, `magError` y `magNst` tienen una tasa de
nulidad de ~40–60% dependiendo de la red. Almacenarlos como columnas individuales genera
una fact muy dispersa. La solución es consolidarlos en un objeto JSONB:

```json
{
  "horizontal_error": 2.5,
  "depth_error": 1.8,
  "mag_error": 0.12,
  "mag_nst": 45
}
```

Esto permite consultas analíticas con operadores PostgreSQL `->` y `->>` sin desperdiciar
almacenamiento en columnas mayormente vacías.

### ¿Por qué `dim_profundidad` separada de `dim_ubicacion`?

Aunque la profundidad es una coordenada del hipocentro, su rol analítico es distinto al
de la ubicación geográfica. La profundidad determina el **tipo de sismo**:

| Categoría | Rango | Mecanismo típico |
|---|---|---|
| Superficial | 0 – 70 km | Fallas corticales, mayor daño superficial |
| Intermedio | 70 – 300 km | Zona de subducción media |
| Profundo | > 300 km | Subducción profunda, menor daño pese a gran magnitud |

Separar esta dimensión permite cruzar categoría de profundidad con zona tectónica y
magnitud en una sola query sin subconsultas complejas.

### Normalización de `magType`

El campo original mezcla al menos 8 notaciones distintas. La transformación aplica
este mapeo en el ETL:

| Valor original | Tipo normalizado | Descripción |
|---|---|---|
| `ml`, `md`, `mc` | `local` | Magnitud local (Richter) |
| `mb`, `mb_lg` | `body_wave` | Ondas de cuerpo |
| `ms`, `ms_20` | `surface_wave` | Ondas superficiales |
| `mw`, `mww`, `mwr` | `moment` | Magnitud de momento (más precisa) |
| `mh`, `m` | `other` | Sin clasificación estándar |

### Tratamiento de `place` (campo de texto libre)

El campo original contiene cadenas como `"15 km NNW of Oaxaca, Mexico"` o
`"Near the coast of Guerrero, Mexico"`. El ETL aplica una función `parse_place()`
con expresiones regulares para extraer:

1. **País**: último token tras la última coma
2. **Región/estado**: token anterior al país  
3. **Distancia de referencia**: número y dirección al inicio (`15 km NNW`)
4. **Es México**: flag booleano para filtros rápidos en el dashboard

---

## Fuentes y referencias del modelo

- Kimball, R. & Ross, M. *The Data Warehouse Toolkit* (3rd ed.) — Capítulos 5 y 9
- Documentación USGS: [earthquake.usgs.gov/data/comcat/](https://earthquake.usgs.gov/data/comcat/)
- PostgreSQL JSONB: [postgresql.org/docs/current/datatype-json.html](https://www.postgresql.org/docs/current/datatype-json.html)