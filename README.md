# Worlds Data Harness

Herramientas locales pequeñas para consultar fuentes externas de League of Legends
Worlds 2026 con procedencia, límites y contexto temporal explícitos.

La primera herramienta, `estado_actual`, consulta el calendario HTML público de
LoL Esports. Devuelve el reloj UTC y local, entradas con horarios explícitos,
evidencia de la solicitud y las limitaciones de cobertura e identidad.

**La versión 0.1 devuelve cobertura parcial.** El directo y el último encuentro
finalizado se mantienen desconocidos. Los horarios publicados no prueban que un
encuentro haya empezado o terminado. La precisión y la latencia deportiva no han
sido medidas; no se ofrece una garantía de datos en tiempo real.

## Instalación en Windows

Requiere Python 3.11 o posterior. El entorno comprobado es Python 3.11.9 en Windows.
Desde la carpeta del repositorio, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Las dependencias de ejecución y desarrollo están fijadas. `tzdata` permite utilizar
zonas IANA en un entorno aislado de Windows. HTTP, JSON y HTML usan la biblioteca
estándar. No se necesita activar el entorno ni instalar componentes globales.

Si un entorno restringido impide escribir en el directorio temporal de Windows,
se puede establecer `TEMP` y `TMP` **solo para el proceso de instalación**, apuntando
a una carpeta temporal dentro de `.local/`. No es necesario elevar privilegios.

Para uso sin herramientas de desarrollo: `python -m pip install .` dentro de un
entorno virtual. La instalación necesita acceso al índice de paquetes.

## Consultar

```powershell
.\.venv\Scripts\python.exe -m worlds_data_harness estado_actual
.\.venv\Scripts\python.exe -m worlds_data_harness estado_actual --timezone UTC --timeout 15
```

También se instala el comando `worlds-data-harness` en `.venv/Scripts/`.
El torneo admitido es `worlds-2026`; no se selecciona automáticamente otro año.
La zona predeterminada es `America/Lima`. Cada ejecución obtiene una nueva hora.

Para guardar un resultado utilizable de forma atómica:

```powershell
New-Item -ItemType Directory -Force .local | Out-Null
.\.venv\Scripts\python.exe -m worlds_data_harness estado_actual --output .local/estado.json
$LASTEXITCODE
```

El JSON siempre se imprime en UTF-8. Si la fuente falla, la salida estándar informa
el error y el archivo anterior se conserva. `.local/` está excluida de Git.
No hay almacenamiento ni caché local automáticos, sondeo periódico o servicios.

| Código de salida | Significado |
| --- | --- |
| `0` | Contrato completo; reservado para una capacidad futura con evidencia suficiente |
| `2`, con JSON | Resultado parcial; es el resultado esperado del adaptador actual |
| `1`, con JSON | Fuente no disponible o respuesta rechazada |
| `2`, con ayuda/error de argumentos | Entrada inválida; no se consulta la red |
| `74` | No se pudo guardar el resultado solicitado |

Un array vacío o un `null` no demuestra que no haya encuentros. Consulta
`completeness`, `coverage`, `live.presence`, `warnings` y `errors`.
El [contrato](docs/estado_actual.md) detalla estos campos y las capacidades reales.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

La suite normal usa fixtures sintéticas y bloquea conexiones de red. Cubre reglas
temporales, series frente a mapas, duplicados, correcciones, errores HTTP, formato
cambiado, límites de recursos y conservación de archivos ante fallos.

La prueba optativa consulta la página real; puede fallar si cambia la fuente:

```powershell
.\.venv\Scripts\python.exe -m pytest --live -m live
```

No exige que exista un encuentro en curso ni conserva HTML de terceros en el repo.
El workflow de CI ejecuta únicamente las pruebas deterministas en Windows.

## Fuentes, licencias y contribuciones

Fuente de la versión 0.1: [calendario público de LoL Esports](https://lolesports.com/en-US/).
Su HTML puede cambiar y su cobertura es paginada. Se consulta una vez por ejecución,
con TLS, límites y sin claves, redirects ni reintentos automáticos. Los servicios
de esports son distintos de la API local del cliente del juego.

La licencia del código está pendiente de decisión; todavía no se ha otorgado una
licencia de código abierto. Los derechos de datos y marcas de terceros se evalúan
por separado. No se redistribuyen respuestas reales completas ni datasets.

El desarrollo ocurre en ramas temáticas. La integración en `main` requiere pruebas,
revisión favorable de otra IA y aprobación humana explícita del SHA exacto. La
autoría no equivale a aprobación, aunque utilice credenciales humanas. Cualquier
cambio posterior relevante invalida la aprobación anterior. Las protecciones de
GitHub todavía no imponen por sí solas todo este procedimiento.

La [auditoría inicial](docs/audits/2026-10-16-initial-audit.md) documenta el punto de
partida y sus observaciones fechadas; no es un diagnóstico permanente del sistema.
