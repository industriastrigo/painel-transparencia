"""Script para modularizar a API do servidor FastAPI em routers temáticos."""
from pathlib import Path

RAIZ_API = Path("src/api")
(RAIZ_API / "rotas").mkdir(parents=True, exist_ok=True)

# 1. db.py: Conexão, cursor DuckDB, _consultar, _registros, etc.
(RAIZ_API / "db.py").write_text("""\"\"\"Gerenciamento de conexão DuckDB e consultas da API.\"\"\"
from __future__ import annotations

import threading
from typing import Any
import pandas as pd
from fastapi import HTTPException

from ..nucleo.registro import obter as obter_log
from . import vistas

log = obter_log("api.db")

_con = None
_dados_mudaram = False
_trava_con = threading.Lock()

def marcar_dados_alterados() -> None:
    global _dados_mudaram
    _dados_mudaram = True

def con():
    global _con, _dados_mudaram
    with _trava_con:
        if _con is None:
            _con = vistas.conexao_leitura()
            _dados_mudaram = False
        elif _dados_mudaram:
            vistas.criar(_con)
            _dados_mudaram = False
        return _con

def reiniciar_conexao() -> None:
    global _con
    if _con is not None:
        try:
            _con.close()
        except Exception:  # noqa: BLE001
            pass
    _con = None

def recarregar_views() -> list[str]:
    return vistas.criar(con())

def _registros(df) -> list[dict]:
    if df.empty:
        return []
    limpo = df.replace([float("inf"), float("-inf")], pd.NA)
    return limpo.astype(object).where(limpo.notna(), None).to_dict("records")

def _consultar(sql: str, parametros: list[Any] | None = None) -> list[dict]:
    cursor = con().cursor()
    try:
        return _registros(cursor.execute(sql, parametros or []).df())
    except Exception as erro:  # noqa: BLE001
        log.warning("consulta falhou (%s) — recriando views e repetindo", erro)
        try:
            recarregar_views()
            return _registros(con().cursor().execute(sql, parametros or []).df())
        except Exception as erro2:  # noqa: BLE001
            log.error("consulta falhou definitivamente: %s", erro2)
            raise HTTPException(500, f"consulta falhou: {erro2}") from erro2
    finally:
        try:
            cursor.close()
        except Exception:  # noqa: BLE001
            pass
""", encoding="utf-8")
print("db.py criado com sucesso!")
