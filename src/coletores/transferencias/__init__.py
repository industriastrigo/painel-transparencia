"""Módulo Transferências Constitucionais da União."""
from __future__ import annotations

import os
from datetime import date
from ...nucleo import armazem, config, controle, rede
from ...nucleo.erros import ConfiguracaoAusente
from ...nucleo.valores import inteiro, numero, opcional, texto
from ...nucleo.registro import obter as obter_log

from .parser import CAMPOS, primeiro, campo as _campo
from .erros import ErroTransferencias, diagnosticar_erro

log = obter_log("coletores.transferencias")
FONTE = "transferencias"

COMO_PEDIR_ACESSO = (
    "A API de Transferências Constitucionais do Tesouro pode exigir "
    "liberação. Peça acesso em desenvolvimento@tesouro.gov.br e, se vier "
    "uma chave, ponha CHAVE_TESOURO_ARIA no .env."
)

TETO_DE_PAGINAS = 2000

def _base() -> str:
    return f"{config.TESOURO_ARIA}/v1/transferencias_constitucionais"

def _pedir(rota: str, parametros: dict | None = None) -> list[dict]:
    parametros = dict(parametros or {})
    if config.CHAVE_TESOURO_ARIA:
        parametros.setdefault("chave", config.CHAVE_TESOURO_ARIA)

    coletadas: list[dict] = []
    pagina_num = 1
    offset = 0

    for _ in range(TETO_DE_PAGINAS):
        p = dict(parametros)
        if offset:
            p["offset"] = offset
        if "page" in parametros or rota.endswith("municipio") or rota.endswith("por_estado_municipio"):
            p["page"] = pagina_num

        try:
            corpo = rede.buscar(FONTE, f"{_base()}{rota}", p)
        except Exception as erro:  # noqa: BLE001
            status = getattr(erro, "status", None) or getattr(erro, "codigo", None)
            if status in (401, 403):
                raise ConfiguracaoAusente(
                    "A API de Transferências Constitucionais do Tesouro pode exigir liberação.",
                    COMO_PEDIR_ACESSO)
            raise

        if not isinstance(corpo, dict):
            if isinstance(corpo, list):
                coletadas.extend(corpo)
            break

        itens = corpo.get("items") or corpo.get("registros") or []
        if not itens:
            break
        coletadas.extend(itens)

        if corpo.get("hasMore") is False:
            break
        if "next" in corpo and not itens:
            break

        offset += len(itens)
        pagina_num += 1

        if not corpo.get("hasMore") and "next" not in corpo:
            break

    return coletadas

def _linhas(registros: list[dict], nivel: str, ano: int, modalidade: dict) -> list[dict]:
    linhas = []
    mapa_uf = {
        "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
        "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
        "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
        "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53"
    }

    for item in registros:
        val = _campo(item, "valor")
        if val is None:
            continue
        m = inteiro(_campo(item, "mes"), 1)
        cod_ibge = texto(_campo(item, "cod_ibge"))
        uf = opcional(_campo(item, "uf"))
        if nivel == "estado" and (not cod_ibge or cod_ibge == "None") and uf:
            cod_ibge = mapa_uf.get(str(uf).upper())
        cod_transf = texto(modalidade.get("cod_transferencia") or _campo(item, "cod_transferencia") or _campo(item, "transferencia"))
        nome_transf = opcional(modalidade.get("transferencia") or _campo(item, "transferencia") or modalidade.get("nome"))
        ano_reg = inteiro(_campo(item, "ano"), padrao=ano)
        linhas.append({
            "cod_ibge": cod_ibge,
            "nivel": nivel,
            "uf": uf,
            "nome_ente": opcional(_campo(item, "municipio") or _campo(item, "nome")),
            "cod_transferencia": cod_transf,
            "transferencia": nome_transf,
            "ano": int(ano_reg),
            "mes": m,
            "valor": numero(val),
            "cod_siafi": opcional(_campo(item, "cod_siafi")),
            "data_referencia": f"{ano_reg}-{m:02d}-01",
        })
    return linhas

def coletar_modalidades() -> list[dict]:
    itens = _pedir("/custom/transferencias")
    linhas = []
    for item in itens:
        cod = _campo(item, "cod_transferencia")
        nome = _campo(item, "transferencia")
        if cod:
            linhas.append({"cod_transferencia": str(cod), "nome": nome})
    if linhas:
        armazem.mesclar("dim_transferencia", linhas, FONTE)
    return linhas

catalogar = coletar_modalidades

def coletar_ano(ano: int, catalogo: list[dict] | None = None, municipios: bool = True) -> int:
    if catalogo is None:
        catalogo = catalogar()
    if not catalogo and catalogo is not None:
        return 0

    itens = _pedir("/custom/por_estados", {"an_referencia": ano})
    linhas = _linhas(itens, "estado", ano, {})
    if linhas:
        armazem.mesclar("transferencia_uniao", linhas, FONTE)
    controle.gravar_marca(FONTE, f"ano_{ano}", ano, len(linhas))
    return len(linhas)

def anos_disponiveis() -> list[int]:
    return list(range(2015, date.today().year + 1))

def executar(anos: list[int] | None = None, refazer: bool = False) -> int:
    corrente = date.today().year
    anos = anos or [corrente - 1, corrente]
    cat = catalogar()
    total = 0
    for ano in anos:
        if not refazer and ano < corrente - 1 and controle.concluido(FONTE, f"ano_{ano}"):
            continue
        try:
            total += coletar_ano(ano, cat)
        except Exception as erro:  # noqa: BLE001
            log.warning("Transferências %d falhou: %s", ano, erro)
    return total