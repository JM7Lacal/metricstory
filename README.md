# MetricStory

De las métricas de campaña al informe que le mandás al cliente.

## El problema

Cada fin de mes, en una agencia de marketing digital, alguien tiene que
convertir el export de métricas de Meta Ads (o Google Ads) en un informe
que un cliente no técnico entienda: qué pasó, por qué importa, qué se
recomienda para el próximo período. Es una tarea repetitiva que igual
requiere criterio — la combinación perfecta para IA bien aplicada.

## Cómo funciona

```
CSV de la plataforma de ads
        │
        ▼
 mapeo tolerante de columnas    (columns.py — soporta headers en
        │                        inglés/español, distintas plataformas)
        ▼
 capa determinística            (metrics.py — CTR, CPC, CPA, ROAS,
        │                        comparación vs. período anterior,
        │                        ritmo de presupuesto. 100% testeado,
        │                        cero IA acá)
        ▼
 hechos estructurados (JSON)    (facts.py)
        │
        ▼
 redacción con IA               (report.py + llm/ — el modelo recibe
        │                        SOLO el JSON de hechos, nunca el CSV
        │                        crudo. No puede inventar una cifra
        │                        que no esté ahí)
        ▼
 informe en Markdown → export a .md / .html imprimible
```

`app.py` (UI) nunca llama a `report.py` ni a `llm/` directamente: pasa por
`service.py`, la capa de aplicación. Así el mismo flujo se reusa desde una
CLI o una API sin tocar la UI, y `service.py` es testeable sin Streamlit.

**Regla de diseño central:** la IA nunca calcula un número, solo narra
sobre números ya calculados y validados por código determinístico. Esto
evita que alucine cifras — el riesgo más obvio de este tipo de herramienta.

## Proveedores de IA intercambiables

Mismo patrón que usé en otro proyecto (Foundry, un editor WPF): el resto
del programa depende solo del puerto `ChatModel` (`llm/base.py`), no de
un proveedor concreto. Cambiar de proveedor es una línea en
`config.toml`, sin tocar código:

| Proveedor | Uso |
|---|---|
| `stub` | Sin red, sin API key. Para demos offline y para los tests (salida determinística). |
| `anthropic` | Anthropic Messages API directa. |
| `openai` | OpenAI (o cualquier endpoint compatible: Azure, Groq, OpenRouter...). |
| `ollama` | Modelo local — útil si el CSV del cliente es sensible y no puede salir de la máquina. |
| `claude-cli` | Usa el CLI de Claude Code (`claude -p`) ya logueado, sin API key aparte. |

Agregar un proveedor nuevo: un archivo en `metricstory/llm/`, registrarlo
en `factory.py`. Nada más se entera.

## Correr localmente

Requiere Python 3.11+ (se desarrolló con 3.12).

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m streamlit run app.py
```

Por defecto usa el CSV sintético de `samples/meta-ads-sample.csv` (schema
real de Meta Ads Manager, 6 campañas × 60 días, con una historia armada
a propósito: una campaña estacional que explota, otra que se deteriora,
una que hay que pausar).

## Configuración (`config.toml`)

```toml
provider = "claude-cli"          # una palabra, sin recompilar

[report]
account_currency = "USD"
monthly_budget = 18000
default_tone = "cliente"         # cliente | interno | ejecutivo
```

`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` van como variable de entorno, no
en el archivo.

## Tests

```bash
.venv/Scripts/python -m pytest
```

Cubren: mapeo de columnas (headers en inglés/español), parseo de números
y fechas en formatos regionales, cálculo de métricas y deltas entre
períodos, ritmo de presupuesto, que el prompt le pasa al modelo únicamente
el JSON de hechos (nunca prosa con datos sin validar), la capa de servicio
(selección de proveedor y su config), el parseo de respuesta de cada
adapter de IA (con la red mockeada) y el export a Markdown/HTML.

## Qué haría después

- Mapeo de columnas persistente por plantilla de plataforma (Meta / Google
  Ads / GA4), para no reconfigurar cada mes.
- Comparación de más de 2 períodos (tendencia, no solo delta).
- Voz de marca por cliente (glosario, tono, disclaimers) guardada aparte
  del prompt genérico.
- Caché de informes generados + historial por cliente.
