"""Cliente HTTP para a API Aria do Tesouro."""
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "transferencias"

def base_url() -> str:
    return f"{config.TESOURO_ARIA}/v1/transferencias_constitucionais"

def pedir_transferencias(rota: str, parametros: dict | None = None) -> list[dict]:
    p = dict(parametros or {})
    if config.CHAVE_TESOURO_ARIA:
        p.setdefault("chave", config.CHAVE_TESOURO_ARIA)
    corpo = rede.buscar(FONTE, f"{base_url()}{rota}", p)
    if isinstance(corpo, dict):
        return corpo.get("items", [])
    return corpo if isinstance(corpo, list) else []
