"""Cliente HTTP para a API da CGU."""
from __future__ import annotations

from typing import Any
from ...nucleo import config, rede

FONTE = "portal_transparencia"

def buscar_emendas(ano: int, pagina: int = 1) -> list[dict]:
    return rede.buscar(FONTE, f"{config.PORTAL_TRANSPARENCIA}/emendas", {"ano": ano, "pagina": pagina})

def buscar_cartoes(mes_str: str, pagina: int = 1) -> list[dict]:
    return rede.buscar(FONTE, f"{config.PORTAL_TRANSPARENCIA}/cartoes", {
        "mesExtratoInicio": mes_str,
        "mesExtratoFim": mes_str,
        "pagina": pagina
    })
