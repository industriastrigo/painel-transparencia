"""Interpretação e normalização dos dados do Senado."""
from __future__ import annotations

from typing import Any

MAPA_VOTO = {
    "Sim": "Sim", "Não": "Não", "NCom": "Não compareceu",
    "AP": "Ausente (presidindo)", "P-NRV": "Presente (não votou)",
    "Abstenção": "Abstenção", "LP": "Licença particular",
}

def caminho(corpo: Any, *chaves: str, padrao: Any = None) -> Any:
    atual = corpo
    for chave in chaves:
        if not isinstance(atual, dict) or chave not in atual:
            return padrao
        atual = atual[chave]
    return atual
