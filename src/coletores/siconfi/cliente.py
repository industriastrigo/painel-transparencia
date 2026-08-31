"""Cliente HTTP para os endpoints da API SICONFI."""
from __future__ import annotations

from typing import Any
from ...nucleo import config, rede

FONTE = "siconfi"
ANEXO_DESPESA_FUNCAO = "DCA-Anexo I-D"
ANEXO_RECEITA = "DCA-Anexo I-C"
ANEXO_FUNCAO = "RREO-Anexo 02"
ANEXO_PESSOAL = "RGF-Anexo 01"
ANEXO_DIVIDA = "RGF-Anexo 02"

def buscar_dca(ano: int, anexo: str, cod_ibge: str) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SICONFI}/dca", {
        "an_exercicio": ano,
        "no_anexo": anexo,
        "id_ente": cod_ibge,
    })

def buscar_rreo(ano: int, bimestre: int, cod_ibge: str, anexo: str = ANEXO_FUNCAO) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SICONFI}/rreo", {
        "an_exercicio": ano,
        "in_periodicidade": "B",
        "nr_periodo": bimestre,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": anexo,
        "id_ente": cod_ibge,
    })

def buscar_rgf(ano: int, quadrimestre: int, anexo: str, cod_ibge: str, poder: str = "E") -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SICONFI}/rgf", {
        "an_exercicio": ano,
        "in_periodicidade": "Q",
        "nr_periodo": quadrimestre,
        "co_tipo_demonstrativo": "RGF",
        "no_anexo": anexo,
        "co_poder": poder,
        "id_ente": cod_ibge,
    })

def buscar_extrato_entregas(ano: int, cod_ibge: str) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.SICONFI}/extrato_entregas", {
        "id_ente": cod_ibge,
        "an_referencia": ano,
    })
