"""CLI: python -m tasasco actualizar | construir"""
from __future__ import annotations

import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(prog="tasasco", description="Tracker de tasas de interés en Colombia")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("actualizar", help="Descarga incremental desde datos.gov.co a data/")
    a.add_argument("--solo", default="", help="Fuentes separadas por coma: trm,tibc,cdt,credito")
    c = sub.add_parser("construir", help="Genera site/public/data/*.json y MOVIMIENTOS.md")
    c.add_argument("--salida", default=str(RAIZ / "site" / "public" / "data"))
    args = p.parse_args()

    if args.cmd == "actualizar":
        from .actualizar import actualizar
        actualizar(RAIZ / "data", {s.strip() for s in args.solo.split(",") if s.strip()} or None)
    else:
        from .construir import construir
        r = construir(RAIZ / "data", Path(args.salida), RAIZ / "MOVIMIENTOS.md")
        print(f"Construido: CDT al {r['cdt'].get('fecha')}, crédito al {r['credito'].get('fecha')}, "
              f"TRM {r['trm']['valor'] if r['trm'] else '—'}")


if __name__ == "__main__":
    main()
