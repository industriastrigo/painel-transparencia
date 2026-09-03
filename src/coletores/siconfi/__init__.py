"""Módulo SICONFI (Secretaria do Tesouro Nacional)."""
from __future__ import annotations

from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log

from . import cliente, parser
from .cliente import ANEXO_DESPESA_FUNCAO, ANEXO_RECEITA, ANEXO_FUNCAO, ANEXO_PESSOAL, ANEXO_DIVIDA
from .parser import (
    _funcao_oficial,
    interpretar_dca, interpretar_funcao, interpretar_rgf,
    periodo_publicado, FUNCOES_OFICIAIS, FUNCOES_DE_INTERESSE, esfera,
    _POR_NOME, _medida_da_coluna, _contas_vistas, _contas_funcao_vistas, _contas_rgf_vistas,
)
from .varredura import varrer, varrer_funcao, varrer_rgf
from .erros import ErroSiconfi, ErroSICONFI, FalhaExtracaoSICONFI, diagnosticar_erro

log = obter_log("coletores.siconfi")
FONTE = "siconfi"

def coletar_dca(ano: int, cod_ibge: str, anexo: str = ANEXO_DESPESA_FUNCAO) -> list[dict]:
    res = cliente.buscar_dca(ano, anexo, cod_ibge)
    return interpretar_dca(res.get("items", []), ano, cod_ibge)

def coletar_rreo(ano: int, bimestre: int, cod_ibge: str) -> list[dict]:
    res = cliente.buscar_rreo(ano, bimestre, cod_ibge)
    return interpretar_funcao(res.get("items", []), ano, bimestre, cod_ibge)

def coletar_funcao(ano: int, arg2: any = 6, arg3: any = None) -> list[dict]:
    if isinstance(arg2, int) and isinstance(arg3, (str, int)):
        bimestre = arg2
        cod_ibge = str(arg3)
    elif isinstance(arg2, (str, int)) and (arg3 is None or isinstance(arg3, int)):
        cod_ibge = str(arg2)
        bimestre = arg3 if arg3 is not None else 6
    else:
        cod_ibge = str(arg2)
        bimestre = 6
    res = cliente.buscar_rreo(ano, bimestre, cod_ibge)
    return interpretar_funcao(res.get("items", []), ano, bimestre, cod_ibge)

def coletar_rgf(ano: int, arg2: any = 3, arg3: any = None, anexo: str | None = None) -> list[dict]:
    if isinstance(arg2, int) and isinstance(arg3, (str, int)):
        quadrimestre = arg2
        cod_ibge = str(arg3)
    elif isinstance(arg2, (str, int)) and (arg3 is None or isinstance(arg3, int)):
        cod_ibge = str(arg2)
        quadrimestre = arg3 if arg3 is not None else 3
    else:
        cod_ibge = str(arg2)
        quadrimestre = 3

    anexos = (anexo,) if anexo else (ANEXO_PESSOAL, ANEXO_DIVIDA)
    linhas = []
    for a in anexos:
        res = cliente.buscar_rgf(ano, quadrimestre, a, cod_ibge)
        linhas.extend(interpretar_rgf(res.get("items", []), ano, quadrimestre, cod_ibge, "E", a))
    return linhas

def executar(
    anos: list[int] | None = None,
    ano: int | None = None,
    recursos: tuple[str, ...] | list[str] | None = None,
    nivel: str = "estado",
    trabalhadores: int = 6,
    intervalo: float = 0.15,
    refazer_vazios: bool = False,
    refazer_tudo: bool = False,
    refazer: bool = False,
    ufs: list[str] | None = None,
) -> None:
    if ano is not None and anos is None:
        anos = [ano]
    anos = anos or [2023, 2024]
    refazer_final = refazer_tudo or refazer

    filtro_nivel = f"nivel = '{nivel}'" if nivel else "nivel IN ('estado', 'municipio')"
    df_entes = armazem.ler("dim_ente", filtro=filtro_nivel, colunas=["cod_ibge", "sigla_uf"])
    if ufs:
        df_entes = df_entes[df_entes["sigla_uf"].isin([u.upper() for u in ufs])]
    codigos = list(df_entes["cod_ibge"].astype(str))

    rec_lista = list(recursos) if recursos else ["dca", "funcao", "rgf"]
    for a in anos:
        if "dca" in rec_lista or "receita" in rec_lista:
            varrer(a, codigos, trabalhadores=trabalhadores, intervalo=intervalo, refazer_vazios=refazer_vazios, refazer_tudo=refazer_final)
        if "funcao" in rec_lista or "despesa" in rec_lista:
            varrer_funcao(a, codigos, trabalhadores=trabalhadores, intervalo=intervalo, refazer_vazios=refazer_vazios, refazer_tudo=refazer_final)
        if "rgf" in rec_lista or "fiscal" in rec_lista:
            varrer_rgf(a, codigos, trabalhadores=trabalhadores, intervalo=intervalo, refazer_vazios=refazer_vazios, refazer_tudo=refazer_final)
