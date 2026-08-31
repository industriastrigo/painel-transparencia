"""Cliente HTTP para a API do IBGE."""
from __future__ import annotations

from typing import Any
from ...nucleo import config, rede

FONTE = "ibge"

def buscar_estados() -> list[dict]:
    return rede.buscar(FONTE, f"{config.IBGE_LOCALIDADES}/estados", {"orderBy": "nome"})

def buscar_municipios() -> list[dict]:
    return rede.buscar(FONTE, f"{config.IBGE_LOCALIDADES}/municipios")

def buscar_malha_brasil() -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.IBGE_MALHAS}/paises/BR", {
        "formato": "application/vnd.geo+json", "intrarregiao": "UF", "qualidade": "minima"
    })

def buscar_malha_uf(sigla_uf: str) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.IBGE_MALHAS}/estados/{sigla_uf.upper()}", {
        "formato": "application/vnd.geo+json", "intrarregiao": "municipio", "qualidade": "minima"
    })

def buscar_agregado(agregado: str, variavel: str, periodo: str, nivel: str) -> list[dict]:
    url = f"{config.IBGE_AGREGADOS}/{agregado}/periodos/{periodo}/variaveis/{variavel}?localidades={nivel}"
    return rede.buscar(FONTE, url)
