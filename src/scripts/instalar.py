"""Verificação de ambiente e primeira carga.

  python -m src.scripts.instalar          # só confere
  python -m src.scripts.instalar --carga  # confere e faz a primeira fatia
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

MINIMO_PYTHON = (3, 10)
PACOTES = ["duckdb", "pandas", "pyarrow", "requests", "fastapi", "uvicorn"]


def verificar() -> bool:
    ok = True

    if sys.version_info < MINIMO_PYTHON:
        print(f"  [x] Python {'.'.join(map(str, MINIMO_PYTHON))}+ necessário "
              f"(atual: {sys.version.split()[0]})")
        ok = False
    else:
        print(f"  [ok] Python {sys.version.split()[0]}")

    for pacote in PACOTES:
        try:
            __import__(pacote)
            print(f"  [ok] {pacote}")
        except ImportError:
            print(f"  [x] {pacote} ausente — rode: pip install -r requirements.txt")
            ok = False

    raiz = Path(__file__).resolve().parents[2]
    env = raiz / ".env"
    if not env.exists():
        exemplo = raiz / ".env.example"
        if exemplo.exists():
            shutil.copy(exemplo, env)
            print("  [ok] .env criado a partir de .env.example")
    else:
        print("  [ok] .env presente")

    from ..nucleo import config  # noqa: PLC0415
    livre = shutil.disk_usage(config.DADOS).free / 1e9
    print(f"  [{'ok' if livre > 10 else '!'}] {livre:.1f} GB livres "
          f"(acervo completo de 10 anos: 2 a 5 GB)")

    return ok


def primeira_carga() -> None:
    """A fatia mínima que prova o pipeline ponta a ponta:
    mapa Brasil → UF → município colorido por despesa per capita."""
    from ..coletores import ibge, siconfi  # noqa: PLC0415

    print("\n[1/3] IBGE — entes, métricas e malha do Brasil")
    ibge.executar(com_malhas=True)

    print("\n[2/3] SICONFI — despesa por função das 27 UFs")
    siconfi.executar()

    print("\n[3/3] conferindo as views")
    from ..api import vistas  # noqa: PLC0415
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT COUNT(*) FROM vw_mapa WHERE despesa_per_capita IS NOT NULL"
    ).fetchone()[0]
    print(f"  {total} entes com despesa per capita calculada")


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Instalação do Painel")
    p.add_argument("--carga", action="store_true",
                   help="faz a primeira carga depois de verificar")
    args = p.parse_args(argv)

    print("Verificando ambiente...\n")
    ok = verificar()
    if not ok:
        print("\nCorrija os itens marcados com [x] e rode de novo.")
        return 1

    if args.carga:
        primeira_carga()

    print("\nPronto. Para abrir o painel: python -m src.scripts.painel")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
