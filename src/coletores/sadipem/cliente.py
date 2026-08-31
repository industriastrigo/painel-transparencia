"""Cliente HTTP para a API SADIPEM."""
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "sadipem"

def buscar_pagina_pvl(parametros: dict, offset: int) -> tuple[list[dict], bool]:
    corpo = rede.buscar(FONTE, f"{config.SADIPEM}/pvl",
                        {**parametros, "offset": offset} if offset else parametros)
    if not isinstance(corpo, dict):
        return (corpo if isinstance(corpo, list) else []), False
    return corpo.get("items", []), bool(corpo.get("hasMore"))
