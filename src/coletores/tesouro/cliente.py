"""Cliente HTTP para a API de Custos do Tesouro."""
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "tesouro"

def buscar_custos(recurso: str, parametros: dict[str, Any]) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.TESOURO_CUSTOS}/{recurso}", parametros)
