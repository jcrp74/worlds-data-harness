# Validación del incremento 1

Entorno observado: Windows nativo, Python 3.11.9, 16 de octubre de 2026.
Esta evidencia describe una ejecución concreta y no garantiza la disponibilidad
futura del proveedor. Las pruebas pueden repetirse con los comandos del README.

## Resultados

- Instalación editable del paquete y dependencias fijadas: satisfactoria.
- `python -m pip check`: sin dependencias incompatibles.
- Suite determinista: **71 aprobadas**, una prueba real omitida deliberadamente.
  Las conexiones de red están bloqueadas por la fixture de la suite normal.
- `python -m pytest --live -m live -q`: **una aprobada**, 71 casos deseleccionados.
- Compilación de los módulos Python y comprobación de espacios de Git: satisfactorias.
- Invocación real del CLI con `--output`: JSON de salida estándar y archivo iguales;
  código de salida **2**, que expresa resultado parcial.

## Observación deportiva real

Solicitud de CLI completada a las `2026-10-16T11:39:37.342383Z`
(`06:39:37.342383-05:00`, America/Lima):

| Propiedad | Resultado |
| --- | --- |
| Fuente | `https://lolesports.com/en-US/` |
| HTTP | 200 |
| Cuerpo leído | 2.531.896 bytes |
| SHA-256 | `c4f986c439161f53f0c40a5d5d04e162d2a22d20fe99a34d570cd6a14923dc16` |
| HTTP Age | 26 segundos; no equivale a antigüedad deportiva |
| Entradas extraídas | 36; identidad sin resolver, con hora explícita |
| Completitud | `partial` |
| Directo | `unknown` |
| Último finalizado | `null` |
| Errores de esta solicitud | Ninguno |

No se redistribuye el HTML de la fuente. El resultado de ejecución y el snapshot
utilizado durante el desarrollo permanecen en `.local/`, excluida de Git.

## Incidencias de entorno conservadas como evidencia

El primer intento de instalación falló con `WinError 5` al renombrar un archivo
en el temporal restringido de Windows. La instalación con `TEMP` y `TMP` limitados
al proceso y apuntando a `.local/build-tmp` terminó correctamente; no se modificó
el entorno global ni se elevaron privilegios para instalar dependencias.

La primera ejecución de pytest tuvo 70 casos aprobados y un fallo de reemplazo
atómico en ese mismo temporal restringido. La suite se repitió con `--basetemp`
en una ruta nueva bajo `.local/`, comprobada dentro del proyecto: 71 aprobadas.
La prueba de reemplazo atómico se conservó. No se sustituyó `os.replace` por una
escritura parcial para sortear la restricción.

## Límites de la validación

La suite comprueba el contrato y sus fallos con fixtures sintéticas. Los casos de
directo, series y resultados finales no demuestran acceso a esos datos reales.
La cadencia deportiva, latencia, cobertura completa y API autenticada siguen sin
validarse. La definición de CI está preparada; una ejecución local no certifica
que el workflow ya haya pasado en GitHub.

La revisión independiente debe referirse al commit exacto que se someta a
integración. Este registro de pruebas no constituye aprobación humana ni permite
integrar unilateralmente en `main`.
