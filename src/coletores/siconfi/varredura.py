"""Controle de concorrência, lotes e varredura massiva do SICONFI."""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log
from . import cliente, parser

log = obter_log("coletores.siconfi.varredura")
FONTE = "siconfi"

TABELA_DE = {
    "dca": "financas_ente",
    "receita": "financas_ente",
    "funcao": "despesa_funcao",
    "rgf": "indicador_fiscal",
}

def _obter_coletor_dca():
    mod = sys.modules.get("src.coletores.siconfi")
    if mod and hasattr(mod, "coletar_dca"):
        return mod.coletar_dca
    return lambda a, c: parser.interpretar_dca(cliente.buscar_dca(a, cliente.ANEXO_DESPESA_FUNCAO, c).get("items", []), a, c)

def _obter_coletor_funcao():
    mod = sys.modules.get("src.coletores.siconfi")
    if mod and hasattr(mod, "coletar_funcao"):
        return mod.coletar_funcao
    return lambda a, c, b=6: parser.interpretar_funcao(cliente.buscar_rreo(a, b, c).get("items", []), a, b, c)

def _obter_coletor_rgf():
    mod = sys.modules.get("src.coletores.siconfi")
    if mod and hasattr(mod, "coletar_rgf"):
        return mod.coletar_rgf
    def _rgf(a, c, q=3):
        linhas = []
        for anexo in (cliente.ANEXO_PESSOAL, cliente.ANEXO_DIVIDA):
            res = cliente.buscar_rgf(a, q, anexo, c)
            linhas.extend(parser.interpretar_rgf(res.get("items", []), a, q, c, "E", anexo))
        return linhas
    return _rgf

def _varrer_recurso(
    recurso: str,
    ano: int,
    entes: list[str],
    trabalhadores: int = 6,
    intervalo: float = 0.15,
    lote: int = 50,
    amostra_inicial: int = 100,
    refazer_vazios: bool = False,
    refazer_tudo: bool = False,
    bimestre: int = 6,
    quadrimestre: int = 3,
) -> dict:
    pendentes = controle.entes_pendentes(
        FONTE, recurso, ano, entes,
        refazer_vazios=refazer_vazios, refazer_tudo=refazer_tudo,
    )
    if not pendentes:
        log.info("SICONFI %s/%d: todos os %d entes já estão com coleta válida no histórico",
                 recurso, ano, len(entes))
        return {"entes": 0, "linhas": 0, "erros": 0, "vazios": 0}

    rede.definir_intervalo(FONTE, intervalo)
    inicio = time.monotonic()
    total = {"entes": 0, "linhas": 0, "erros": 0, "vazios": 0}
    buffer_linhas: list[dict] = []
    buffer_controle: list[dict] = []
    trava = threading.Lock()
    desistir = threading.Event()
    amostra = amostra_inicial
    pode_desistir = len(pendentes) > amostra * 2

    fn_dca = _obter_coletor_dca()
    fn_funcao = _obter_coletor_funcao()
    fn_rgf = _obter_coletor_rgf()

    def descarregar() -> None:
        nonlocal buffer_linhas, buffer_controle
        if buffer_linhas:
            armazem.mesclar(TABELA_DE[recurso], buffer_linhas, f"{FONTE}_{recurso}")
            buffer_linhas = []
        if buffer_controle:
            controle.registrar_entes(FONTE, recurso, ano, buffer_controle)
            buffer_controle = []

    def trabalhar(cod: str) -> None:
        if desistir.is_set():
            return
        try:
            if recurso == "dca":
                linhas = fn_dca(ano, cod)
            elif recurso == "receita":
                res = cliente.buscar_dca(ano, cliente.ANEXO_RECEITA, cod)
                linhas = parser.interpretar_dca_receita(res.get("items", []), ano, cod)
            elif recurso == "funcao":
                linhas = fn_funcao(ano, cod, bimestre)
            elif recurso == "rgf":
                linhas = fn_rgf(ano, cod, quadrimestre)
            else:
                linhas = fn_funcao(ano, cod, 6)
            desfecho = {"cod_ibge": cod, "linhas": len(linhas), "situacao": "ok" if linhas else "vazio"}
        except Exception as erro:  # noqa: BLE001
            linhas = []
            desfecho = {"cod_ibge": cod, "linhas": 0, "situacao": "erro", "detalhe": str(erro)}

        with trava:
            buffer_linhas.extend(linhas)
            buffer_controle.append(desfecho)
            total["entes"] += 1
            total["linhas"] += len(linhas)
            if desfecho["situacao"] == "erro":
                total["erros"] += 1
            elif desfecho["situacao"] == "vazio":
                total["vazios"] += 1

            if (pode_desistir and total["entes"] >= amostra
                    and total["linhas"] == 0 and total["erros"] == 0
                    and not desistir.is_set()):
                desistir.set()
                log.warning(
                    "SICONFI %s/%d: os %d primeiros entes vieram sem nenhum dado. "
                    "O exercício de %d provavelmente ainda não foi publicado — abandonando.",
                    recurso, ano, total["entes"], ano)
                return

            if len(buffer_controle) >= lote:
                descarregar()

    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        try:
            list(executor.map(trabalhar, pendentes))
        except KeyboardInterrupt:
            log.warning("interrompido — o que já foi coletado está gravado")
            raise
        finally:
            with trava:
                descarregar()

    minutos = (time.monotonic() - inicio) / 60

    if desistir.is_set():
        esquecidas = controle.esquecer_entes(FONTE, recurso, ano)
        log.warning("SICONFI %s/%d abandonado em %.1f min. %d marcas apagadas.",
                    recurso, ano, minutos, esquecidas)
        controle.gravar_marca(
            FONTE, f"{recurso}_{ano}", None, 0, situacao="nao_publicado",
            detalhe=f"amostra de {amostra} entes sem nenhum dado")
        total["abandonado"] = 1
        return total

    if total["linhas"] == 0 and total["vazios"] == total["entes"] and total["entes"] > 0:
        controle.gravar_marca(FONTE, f"{recurso}_{ano}", str(ano), 0, situacao="sem_dado",
                              detalhe=f"{total['entes']} entes sem dados publicados")
    else:
        controle.gravar_marca(FONTE, f"{recurso}_{ano}", str(ano), total["linhas"],
                              situacao="ok" if total["erros"] == 0 else "erro",
                              detalhe=f"{total['vazios']} vazios, {total['erros']} erros")

    return total

def varrer(ano: int, entes: list[str], **kwargs) -> dict:
    return _varrer_recurso("dca", ano, entes, **kwargs)

def varrer_funcao(ano: int, entes: list[str], **kwargs) -> dict:
    return _varrer_recurso("funcao", ano, entes, **kwargs)

def varrer_rgf(ano: int, entes: list[str], **kwargs) -> dict:
    return _varrer_recurso("rgf", ano, entes, **kwargs)
