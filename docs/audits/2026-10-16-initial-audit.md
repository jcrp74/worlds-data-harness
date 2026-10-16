# Auditoría inicial y propuesta de primer incremento

Ventana de observación: 16 de octubre de 2026, 10:32–10:40 UTC (05:32–05:40 en
America/Lima). Esta auditoría es una instantánea, no una garantía de vigencia futura.
Estado: **auditoría terminada; implementación pendiente de autorización de alcance**.

## 1. Observaciones comprobadas

### Entorno y repositorio

- Directorio y repositorio coinciden con los indicados en el mandato.
- Rama activa: `feature/initial-audit`; inicialmente sin cambios locales.
- `origin` apunta al repositorio indicado. La consulta real `git ls-remote`
  confirmó que las dos ramas locales coinciden con sus respectivas puntas remotas:
  - desarrollo: `cd3e92ef2a9c383e812545fd8f8aa6bc327b3dc9`;
  - `main`: `0794636394464c9d515bcc47ae7f3dd99ccf993c`.
- Solo había un archivo versionado, `README.md`. No había código, manifiesto de
  dependencias, pruebas, CI, entorno virtual ni archivo de exclusiones.
- Git 2.56.0, Python 3.11.9 y OpenSSH disponibles. No hace falta reinstalarlos.
- GitHub CLI 2.102.0 existe, pero su carpeta no está en el `PATH` de esta sesión.
  Se pudo ejecutar mediante su ruta absoluta.
- `python` funciona; `py -0p` no encuentra instalaciones. Se propone usar `python`
  y, después, `.venv/Scripts/python.exe`, sin depender del lanzador `py`.
- Un entorno virtual temporal se creó con éxito y ejecutó `pip 24.0`.
  Se eliminó al finalizar la prueba.
- Un segundo entorno virtual aislado no pudo cargar `ZoneInfo('America/Lima')`:
  faltaba `tzdata`. El Python global tiene `tzdata 2026.2`, pero eso no se hereda
  en un entorno virtual normal. Es una dependencia de ejecución justificada.
- Hubo conexiones HTTPS reales a GitHub y a las fuentes indicadas más abajo.
  El reloj UTC se obtuvo durante la ejecución; no se auditó su sincronización NTP.

### Firmas, acceso y gobernanza

- La configuración local conserva `gpg.format=ssh`, `commit.gpgsign=true` y la
  referencia a la clave pública del proyecto. No se leyó la clave privada.
- GitHub verificó la firma del commit de desarrollo: `verified=true`,
  `reason=valid`, con verificación registrada a las `08:05:59Z` del 16 de octubre.
- La verificación local predeterminada falló al lanzar `ssh-keygen`
  (`waitpid ... No child processes`). Con el ejecutable nativo de Windows y
  un archivo temporal de confianza limitado a la clave pública del proyecto,
  Git devolvió `G`: firma válida. No se cambió la configuración permanente.
- El ruleset `Protect main`, ID `25206470`, está **activo**, apunta a la rama
  predeterminada y sus reglas efectivas para `main` incluyen PR obligatorio,
  bloqueo de eliminación, bloqueo de force push y **firmas obligatorias**.
  La firma obligatoria ya no está pendiente.
- Exige cero aprobaciones de revisión; no exige status checks y no descarta
  revisiones antiguas después de un push. No hace obligatoria por sí mismo la
  doble autorización humana e IA ni la correspondencia con el commit aprobado.
- La respuesta pública del ruleset omite `bypass_actors`: no se comprobó la lista
  actual de excepciones. No se debe interpretar el campo ausente como lista vacía.
- `gh auth status` reporta token inválido; `GET /user` devuelve **401**.
  Las lecturas públicas de repositorio, reglas y commits funcionan. Esto no
  demuestra autorización para publicar ramas o PR. La escritura queda sin verificar.

## 2. Fuentes: evidencia y límites

Se hicieron GET acotados, con TLS normal, sin credenciales de Riot, sin reintentos
automáticos y sin intentar superar controles de acceso. No se descargaron CSV
completos, ejecutaron scripts externos ni conservaron páginas completas.

| Fuente o ruta consultada | Observación | Alcance demostrado |
| --- | --- | --- |
| [LoL Esports público](https://lolesports.com/en-US/) | HTTP 200; HTML de 2.531.896 bytes en una lectura completa; 38 elementos `time[datetime]` de distintas competiciones; filas Worlds, resultados visibles y enlaces `/vod/<id>/1`; botón de más resultados | Calendario renderizado accesible y fechas UTC explícitas. Cobertura parcial; no contrato estable de eventos ni estado en vivo validado |
| `esports-api.../persisted/gw/getLeagues?hl=en-US` | HTTP 403, JSON `Forbidden` | Acceso sin credenciales rechazado |
| `.../getSchedule?hl=en-US` | HTTP 403 | No se obtuvo esquema de calendario de la API |
| `.../getLive?hl=en-US` | HTTP 403 | No se comprobó presencia ni ausencia de encuentros en vivo |
| `feed.../livestats/v1/window/0` | HTTP 404, `RESOURCE_NOT_FOUND`, identificador inexistente | La ruta responde con un error estructurado; no demuestra acceso a telemetría real |
| [Games of Legends](https://gol.gg/esports/home/) | La raíz responde HTTP 200 con una redirección JavaScript; una solicitud explícita al destino público `/esports/home/` devuelve HTTP 200 y enlaces estadísticos; lectura limitada a 500.001 bytes, truncada | Acceso a la página estadística comprobado. No se ejecutó el script ni se validaron sus tablas o cobertura Worlds 2026 |
| [Oracle's Elixir](https://lol.timsevenhuysen.com/) | HTTP 200; página reconocible del proveedor | Sitio accesible; esquema, archivos, cobertura Worlds 2026 y permisos de datos sin validar |
| [Leaguepedia en Fandom](https://lol.fandom.com/wiki/League_of_Legends_Esports_Wiki) | HTTP 403 desde Python; acceso también bloqueado en el navegador de investigación | No hay acceso directo comprobado a su API. La búsqueda aún identifica documentación de Leaguepedia en Fandom; no se confirmó una migración a otro dominio |
| [ChainCC](https://chaincc.lol/free/data) | HTTP 200; anuncia CSV comprimidos de jugadores y equipos por temporada y licencia CC BY 4.0 | Catálogo accesible; no se validaron archivos ni cobertura, cadencia o independencia respecto de otras fuentes |

La primera lectura de LoL Esports se limitó a 2.000.001 bytes y quedó truncada.
Las inspecciones posteriores, con tope de 8.000.001 bytes, leyeron el documento
completo de 2.531.896 bytes. Este tamaño es el del cuerpo leído, no una medición
de tráfico comprimido de red. El HTML usa streaming de React; no se encontró un
`__NEXT_DATA__` con calendario estructurado. Los objetos `EsportsSeasonEvent`
encontrados describen periodos de la temporada, no encuentros individuales.

El encabezado HTTP `Age: 19` muestra que una lectura reciente puede proceder de
caché. `Date` y `Age` no equivalen a la última actualización deportiva del dato.
No se estableció la antigüedad real del calendario.

Hay una discrepancia que exige cautela: el [artículo oficial de Worlds
2026](https://lolesports.com/en-US/news/worlds-2026-primer) enumera actividad
Play-In del 15 al 18 de octubre, mientras la página de calendario inspeccionada
mostraba filas del 15 y 17 y no una fila Worlds del 16. Puede deberse a actualización,
cobertura o cambios de programación; la causa no está comprobada. No se concluye
que el día 16 carezca de encuentros.

No se probaron `getEventDetails`, `getStandings` ni `livestats/.../details`:
no se obtuvo un identificador y acceso de API validados que justificaran ampliar
el sondeo. Tampoco se midieron cadencia, latencia deportiva o recuperación de cortes.
La [documentación de Riot](https://developer.riotgames.com/docs/lol) distingue la
API local del cliente; no se usó `127.0.0.1:2999` para consultar esports remotos.
No se confirmó soporte contractual para los endpoints de esports propuestos.

## 3. Recomendación de alcance: incremento 1

**Construir `estado_actual` como consulta local de alcance parcial, empezando por
el reloj y las entradas de calendario verificables de la página pública.**
El HTML es la única vía de calendario consultada con éxito sin credenciales;
su fragilidad y cobertura deben formar parte del contrato, no quedar ocultas.

Arquitectura propuesta, todavía no implementada:

```text
pyproject.toml
src/worlds_data_harness/
    __main__.py          # argumentos, JSON, código de salida
    estado_actual.py     # contrato, validación y reglas temporales puras
    lolesports.py        # GET y extracción específica de este proveedor
tests/                  # fixtures sintéticas y red simulada
```

- Python 3.11 y biblioteca estándar para HTTP, JSON y parsing HTML. `tzdata`
  fijada para zonas IANA en Windows; `pytest` fijado para desarrollo. Validar
  instalación de las versiones elegidas dentro de `.venv` antes de fijarlas.
- Una solicitud bajo demanda, con timeout, límite de respuesta y errores
  diferenciados para 403, 429, red, tamaño excedido y formato no reconocido.
- Extraer solo entradas con asociación comprobable a Worlds 2026 y fecha UTC
  explícita. No utilizar `Today`, el reloj ni un marcador para inferir estado.
  Si no se puede establecer la asociación, la fila no se presenta como encuentro.
- Identificadores del proveedor solo cuando existan. Una entrada sin ID permanece
  como entrada de calendario de identidad no resuelta; no inventar un ID estable
  ni fusionar identidades por nombre o por proximidad horaria.
- Estado en vivo y último encuentro finalizado quedan **desconocidos** cuando
  falte evidencia suficiente. Un marcador visible o un enlace VOD no bastan por sí
  solos para afirmar la finalización de la serie.
- Sin persistencia ni caché local en este incremento: repetir una consulta no
  acumula datos. El caché HTTP del proveedor se registra por separado.
- Sin sondeo periódico: nueva consulta bajo demanda. Respetar `Retry-After`
  cuando corresponda; no establecer TTL deportivo hasta medir o documentar la
  fuente. El momento recomendado de nueva consulta puede ser indeterminado.
- Preparar exclusiones, instalación reproducible, instrucciones y corregir la
  promesa de milisegundos del README. Añadir una comprobación de CI en Windows
  con pruebas deterministas; no convertirla en obligatoria en el ruleset todavía.
- Cualquier archivo de salida solicitado se reemplaza de forma atómica; las
  respuestas externas nunca se ejecutan ni se interpretan como instrucciones.

### Contrato preliminar

Entrada: torneo explícito `worlds-2026`, zona IANA (`America/Lima` por defecto),
timeout y formato JSON. El reloj y transporte se inyectan en las pruebas.
No se acepta una URL arbitraria del usuario como fuente del adaptador.

Salida propuesta:

| Campo | Significado |
| --- | --- |
| `schema_version`, `tournament` | Versión del contrato y ámbito de consulta |
| `now_utc`, `now_local`, `timezone` | Reloj de la ejecución, con offsets explícitos |
| `requested_at`, `received_at` | Instantes UTC de solicitud y recepción |
| `source` | Proveedor, URL, HTTP, hash de evidencia y adaptador |
| `provider_updated_at` | Fecha deportiva del proveedor o `null`; nunca sustituida por HTTP `Date` |
| `freshness` | Edad de observación, edad deportiva conocida o desconocida, y evidencia HTTP separada |
| `coverage` | Alcance observado, paginación y completitud; el HTML consultado no demuestra cobertura completa |
| `scheduled_entries` | Entradas de calendario, con hora, procedencia y estado de identidad explícitos |
| `matches` | Solo encuentros cuya identidad y asociación hayan sido validadas; estados programado/en_vivo/finalizado/desconocido |
| `live` | Presencia `present`, `absent` o `unknown`; `absent` exige cobertura completa y evidencia explícita |
| `latest_finished` | Encuentro y evidencia, o `null` con causa de indeterminación; nunca «el último de todo el torneo» con cobertura parcial |
| `completeness`, `warnings`, `errors` | Resultado completo, parcial o no disponible y sus motivos tipificados |
| `recheck` | Consulta bajo demanda, restricciones de reintento y recomendación justificada o indeterminada |

Usar una lista para los encuentros en vivo: el contrato no debe asumir que solo
puede existir uno. Para afirmar ausencia se necesita una consulta válida con
cobertura pertinente completa. Dos respuestas equivalentes pueden diferir en
metadatos de observación sin violar idempotencia del resultado lógico.

### Pruebas y aceptación

Casos deterministas previstos: sin encuentros; programados; directo confirmado;
serie con un mapa terminado y otro en curso; serie finalizada; 403/red/timeout;
vacío válido frente a respuesta inválida; datos parciales; fuente antigua o de
edad desconocida; horario contradictorio; duplicados; corrección posterior;
reloj/zona distintos; formato cambiado. Añadir truncamiento, tamaño máximo,
identidad no resuelta, contenido malicioso y ausencia de efectos persistentes.

Los casos de directo y finalización prueban las reglas del contrato con datos
sintéticos; no certifican que el adaptador HTML pueda obtener esos estados.
La prueba real será optativa y separada: GET de la página pública con evidencia
de transporte y extracción parcial verificable, sin depender de que haya directo.

Aceptación mínima: ejecución en `.venv` de Windows; JSON válido; suite sin red
satisfactoria; GET real acotado; fechas extraídas trazables; falta de datos expresada
sin inventar estados; y manejo probado de cambios del HTML. Si no se puede validar
la extracción de calendario, el incremento se reportará incompleto y se revisará
la vía de acceso antes de declarar terminada la herramienta.

## 4. Decisiones y trabajo pendiente

1. **Autorizar el incremento 1 descrito arriba**, conforme a XII, fase D del
   mandato. Alternativa: posponer la extracción HTML hasta conseguir acceso
   autorizado a una API; reduce fragilidad, pero hoy depende de acceso no validado.
2. Antes de publicar una rama/PR, recuperar o verificar la autenticación de
   GitHub. No se cambió ni sustituyó ninguna credencial durante la auditoría.
3. Mantener la revisión independiente por otra IA y la aprobación humana ligadas
   al SHA exacto. Una futura propuesta de controles debe decidir cómo registrar
   ambas evidencias e invalidarlas ante cambios; requiere alcance propio.
4. Cualquier cambio de ruleset o permisos requiere autorización específica.
   La firma obligatoria ya está activa y no necesita volver a habilitarse.
5. Licencia del código pendiente: MIT es una opción inicial por sencillez;
   no se incorpora sin decisión humana. Las condiciones de terceros se evalúan
   por separado; el catálogo de ChainCC no concede derechos sobre otras fuentes.

Se crearon únicamente este informe y su resumen de evidencia JSON. No se modificó
el README existente, no se instaló ninguna dependencia permanente, no se crearon
commits ni PR y no se alteraron ramas, credenciales, protecciones ni otros proyectos.
