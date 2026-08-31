"""Módulo SADIPEM (Operações de Crédito)."""
from __future__ import annotations

from ...nucleo import armazem, controle
from ...nucleo.registro import obter as obter_log

from .cliente import buscar_pagina_pvl as _pagina
from .parser import normalizar_pvl
from .erros import ErroSADIPEM, diagnosticar_erro

log = obter_log("coletores.sadipem")
FONTE = "sadipem"
TETO_PAGINAS = 60

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]

def coletar_uf(uf: str) -> list[dict]:
    brutos: list[dict] = []
    offset = 0
    for pagina in range(TETO_PAGINAS):
        itens, tem_mais = _pagina({"uf": uf}, offset)
        brutos.extend(itens)
        if not tem_mais:
            break
        offset += len(itens) or 1

    linhas = []
    for bruto in brutos:
        l = normalizar_pvl(bruto, uf)
        if l:
            linhas.append(l)
    return linhas

def executar(anos: list[int] | None = None, ufs: list[str] | None = None, refazer: bool = False) -> int:
    alvos = list(ufs or UFS)
    if not refazer:
        pendentes = set(controle.recortes_pendentes(FONTE, [f"pvl_{u}" for u in alvos]))
        alvos = [u for u in alvos if f"pvl_{u}" in pendentes]
    if not alvos:
        return 0

    total_linhas = 0
    for uf in alvos:
        try:
            linhas = coletar_uf(uf)
            if linhas:
                armazem.mesclar("operacao_credito", linhas, FONTE)
            total_linhas += len(linhas)
            controle.gravar_marca(FONTE, f"pvl_{uf}", None, len(linhas), situacao="ok")
        except Exception as erro:  # noqa: BLE001
            log.error("SADIPEM %s falhou: %s", uf, erro)
            controle.gravar_marca(FONTE, f"pvl_{uf}", None, 0, situacao="erro", detalhe=str(erro))
    return total_linhas
