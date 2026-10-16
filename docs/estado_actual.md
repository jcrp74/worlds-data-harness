# Contrato de estado_actual, esquema 1.0

## Capacidades de la versión 0.1

Consulta fija: `https://lolesports.com/en-US/`. Una petición por invocación.
Sin claves de Riot, ejecución de JavaScript, acceso al cliente local ni persistencia
automática. No se siguen redirecciones ni la paginación. Las respuestas son datos
no confiables; su contenido nunca dirige operaciones del programa.

El adaptador reconoce el título de la página, secciones de fecha y tarjetas con
`footer`, logo y etiqueta `Worlds`. Extrae un `time[datetime]` con offset explícito
y dos plazas de equipo en esa misma tarjeta. La etiqueta Worlds y el año UTC 2026
del timestamp establecen el ámbito. Las clases CSS y las fechas relativas no se
usan como identidad ni como reloj. Las tarjetas sin hora explícita no se convierten
en encuentros. El documento puede contener contenido de streaming temporalmente
oculto; no se ejecutan los scripts que lo insertan en el navegador.

Las entradas extraídas llevan `provider_event_id=null`, `identity_status=unresolved`
y `state=desconocido`. Las plazas `TBD` se representan con `null`. La hora es una
programación publicada, sin garantía de inicio real. La posición del footer solo
localiza evidencia dentro del cuerpo cuyo SHA-256 se devuelve; no es un ID estable.

`matches` contiene únicamente identidades validadas. El adaptador actual no produce
esas identidades; por tanto `matches=[]`, `live.presence=unknown` y
`latest_finished=null`. Los tests sintéticos de directo y series validan reglas del
contrato, no una capacidad deportiva real del adaptador.

## Campos

| Campo | Contrato |
| --- | --- |
| `schema_version`, `tournament` | `1.0`, `worlds-2026` |
| `now_utc`, `now_local`, `timezone` | Instante de esta ejecución; IANA y offset explícitos |
| `requested_at`, `received_at` | Reloj local de solicitud y recepción, normalizado a UTC |
| `source` | ID de fuente, URL fija, versión del adaptador, HTTP, bytes leídos y hash del cuerpo |
| `source.http_date`, `source.http_age_seconds` | Metadatos de transporte y caché HTTP; nunca fecha de actualización deportiva |
| `provider_updated_at` | `null` en el adaptador actual |
| `freshness` | Edad observada por el reloj propio, edad deportiva y límite de validez cuando se conocen; desconocimiento explícito |
| `coverage` | Alcance `observed_response`, completitud e IDs conflictivos descartados; paginación sin recorrer |
| `scheduled_entries` | Entradas extraídas con hora publicada, plazas de equipo, identidad, estado y procedencia |
| `matches` | Encuentros identificados dentro de la observación; no incluye entradas de identidad no resuelta |
| `live` | `present`, `absent` o `unknown`, con lista de encuentros cuando se confirman |
| `latest_finished` | Último confirmado dentro de la cobertura observada, o `null` |
| `latest_finished_scope`, `latest_finished_reason` | Alcance y explicación de la determinación o indeterminación |
| `completeness` | `complete`, `partial` o `unavailable`; en HTML utilizable siempre `partial` |
| `warnings`, `errors` | Listas de códigos estables, ordenadas y sin cuerpos externos |
| `recheck` | Bajo demanda; `not_before` conserva `Retry-After` válido; `recommended_at=null` sin cadencia deportiva comprobada |

Cada entrada incluye las horas UTC/local, dos plazas, marcador de serie opcional,
estados de mapas opcionales y procedencia con localizador y hash. Los campos de
marcador, mapas y finalización permanecen vacíos en este adaptador. Un resultado
observado como en vivo pero caducado conserva el estado de origen en la evidencia;
`live.presence` se vuelve desconocido. El consumidor debe leer ambos niveles.

## Reglas temporales e integridad

- El reloj y el transporte se pueden sustituir en pruebas; las consultas reales
  obtienen el reloj durante la ejecución. No se certifica sincronización NTP.
- La hora del sistema, HTTP `Date`, HTTP `Age` y una fecha deportiva tienen
  significados distintos. Una observación nueva no prueba un calendario nuevo.
- Una hora pasada no implica directo; un resultado parcial no termina una serie.
  Los estados de los mapas no sustituyen al estado explícito del encuentro.
- La presencia en vivo exige estado explícito y ausencia de caducidad o anomalías
  conocidas. La ausencia exige además cobertura completa y estados resueltos.
  La frescura deportiva desconocida permanece declarada como tal.
- El último finalizado se ordena por finalización explícita, nunca por hora prevista.
  Fechas contradictorias, tiempos faltantes, empates o IDs conflictivos impiden
  afirmar un orden único. Con cobertura parcial el alcance siempre es local.
- Duplicados idénticos con ID se colapsan; versiones incompatibles del mismo ID
  se ponen en cuarentena. Entradas sin ID se conservan por separado y una posible
  coincidencia se advierte. No se infiere identidad por nombre u hora.
- Una corrección posterior sustituye la observación anterior en la consulta nueva;
  no se acumulan registros. La idempotencia lógica no exige conservar las horas
  de observación de solicitudes diferentes.

## Red, errores y límites

El cuerpo máximo es 4 MiB, con un margen explícito sobre los 2,53 MB observados.
Se limita además el árbol a 60.000 nodos y profundidad 96; scripts, estilos, SVG,
templates y noscript no se interpretan. Se exige UTF-8 y `text/html`.

El timeout predeterminado es 15 segundos de socket y se comprueba un presupuesto
entre lecturas. Una lectura de socket en curso puede consumir su timeout antes de
devolver el control: no es una garantía de cancelación instantánea de proceso.
No hay reintentos; `Retry-After` se informa para invocaciones posteriores, sin un
planificador persistente. No se establece un TTL deportivo arbitrario.

| Códigos de error | Significado |
| --- | --- |
| `http_forbidden`, `http_rate_limited`, `http_error` | HTTP 403, 429 u otro estado inesperado |
| `http_redirect_rejected` | La fuente propone una redirección; no se sigue |
| `network_error`, `timeout` | Fallo de transporte o tiempo agotado |
| `response_too_large`, `response_truncated`, `invalid_content_length` | Límite o incoherencia en la transferencia |
| `unsupported_content_encoding`, `unexpected_content_type`, `invalid_utf8` | Formato de transporte no admitido |
| `schema_changed`, `html_complexity_exceeded` | Estructura no validada o complejidad excesiva |

Las filas parciales válidas pueden conservarse junto con advertencias. Una página
vacía, un JSON en lugar de HTML o un formato no reconocible producen `unavailable`,
no un calendario vacío válido. Una página reconocible que dice que hoy no hay
partidos sigue sin demostrar ausencia para todo Worlds.

Un archivo solicitado con `--output` se escribe en un temporal del mismo directorio,
se vacía a disco y se reemplaza con `os.replace`. Un fallo antes del reemplazo o
una fuente no disponible conservan el archivo anterior. No se sigue un enlace
simbólico como destino. No hay coordinación entre escritores concurrentes: cada
reemplazo es íntegro, pero puede ganar la última escritura que termine. No se
promete orden temporal entre procesos; el estado persistente compartido queda
fuera de este incremento.

## Extensiones pendientes

Validar una fuente con identificadores estables, estados explícitos, cadencia y
condiciones de uso verificadas antes de ampliar las capacidades. La falta actual
de autenticación de una API no se resuelve extrayendo claves del frontend.
La licencia del código y los cambios de protección de GitHub requieren decisiones
humanas separadas. La integración en `main` exige revisión independiente y
aprobación humana del SHA exacto.
