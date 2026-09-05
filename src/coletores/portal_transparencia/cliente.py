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

def buscar_viagens(ano: int, mes: int, pagina: int = 1) -> list[dict]:
    import calendar
    _, ultimo_dia = calendar.monthrange(ano, mes)
    data_inicio = f"01/{mes:02d}/{ano}"
    data_fim = f"{ultimo_dia:02d}/{mes:02d}/{ano}"
    return rede.buscar(FONTE, f"{config.PORTAL_TRANSPARENCIA}/viagens", {
        "dataIdaDe": data_inicio,
        "dataIdaAte": data_fim,
        "pagina": pagina
    })

def buscar_contratos(ano: int, mes: int, pagina: int = 1) -> list[dict]:
    import calendar
    _, ultimo_dia = calendar.monthrange(ano, mes)
    data_inicio = f"01/{mes:02d}/{ano}"
    data_fim = f"{ultimo_dia:02d}/{mes:02d}/{ano}"
    return rede.buscar(FONTE, f"{config.PORTAL_TRANSPARENCIA}/contratos", {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "pagina": pagina
    })
