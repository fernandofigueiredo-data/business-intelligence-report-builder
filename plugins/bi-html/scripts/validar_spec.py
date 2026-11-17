#!/usr/bin/env python3
"""
validar_spec.py — confere uma spec de dashboard contra o schema e as regras do bi-html.

    uv run --no-project --python 3.12 --with jsonschema scripts/validar_spec.py <spec.json> [--metricas a,b,c]

Sai com código 0 se a spec é válida e 1 se há problemas (listados um por linha).
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from bi_html.spec import validar_arquivo  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Valida uma spec de dashboard do bi-html.")
    p.add_argument("spec", help="caminho do arquivo JSON da spec")
    p.add_argument("--metricas", help="ids das métricas do modelo, separados por vírgula")
    a = p.parse_args()
    conhecidas = set(a.metricas.split(",")) if a.metricas else None
    problemas = validar_arquivo(a.spec, conhecidas)
    if not problemas:
        print(f"✅ {a.spec}: spec válida")
        return 0
    print(f"❌ {a.spec}: {len(problemas)} problema(s)")
    for linha in problemas:
        print(f"  - {linha}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
