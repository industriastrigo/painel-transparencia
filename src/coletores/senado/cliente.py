"""Cliente HTTP para a API do Senado."""
from __future__ import annotations

from typing import Any
from ...nucleo import config, rede

FONTE = "senado"

def buscar_senadores_atual() -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SENADO}/senador/lista/atual.json")

def buscar_votacoes_materia(codigo_materia: str) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SENADO}/materia/votacoes/{codigo_materia}.json")
