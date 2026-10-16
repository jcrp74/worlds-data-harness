"""CLI sin servicios permanentes; salida completa, parcial o no disponible."""

import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .estado_actual import summarize, utc_now
from .lolesports import query_schedule


def _timeout(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout debe ser un número") from None
    if not math.isfinite(number) or not 0 < number <= 120:
        raise argparse.ArgumentTypeError("timeout debe ser mayor que 0 y como máximo 120 segundos")
    return number


def _timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise argparse.ArgumentTypeError("zona IANA no disponible; verifica el nombre y la instalación de tzdata") from None
    return value


def atomic_write(path: Path, content: str) -> None:
    """Reemplazo en el mismo volumen; un fallo previo conserva el archivo anterior."""
    if path.is_symlink():
        raise OSError("El archivo de salida no puede ser un enlace simbólico")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Worlds Data Harness")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("estado_actual", help="Contexto temporal y calendario parcial de Worlds 2026")
    command.add_argument("--tournament", choices=["worlds-2026"], default="worlds-2026")
    command.add_argument("--timezone", type=_timezone, default="America/Lima")
    command.add_argument("--timeout", type=_timeout, default=15.0)
    command.add_argument("--output", type=Path, help="JSON a reemplazar atómicamente; la carpeta debe existir")
    args = parser.parse_args(argv)
    result = summarize(query_schedule(timeout=args.timeout), now=utc_now(), timezone_name=args.timezone)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output and result["completeness"] == "unavailable":
        print("Fuente no disponible: se conserva el archivo de salida anterior.", file=sys.stderr)
    elif args.output:
        try:
            atomic_write(args.output, content)
        except OSError:
            parser.exit(74, "No se pudo reemplazar el archivo de salida; comprueba la ruta y los permisos.\n")
    print(content, end="")
    return {"complete": 0, "partial": 2, "unavailable": 1}[result["completeness"]]


if __name__ == "__main__":
    raise SystemExit(main())
