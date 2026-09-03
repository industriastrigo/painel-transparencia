"""Módulo Custos do Governo Federal (Tesouro Nacional)."""
from __future__ import annotations

import time
from datetime import date
from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log
from ...nucleo.valores import inteiro, numero, opcional, texto

from .cliente import buscar_custos
from .parser import CONJUNTOS, CAMPOS, primeiro, campo as _campo, valor_custo as _valor
from .erros import ErroTesouro, diagnosticar_erro

log = obter_log("coletores.tesouro")
FONTE = "tesouro"
PAGINA = 10_000

def _retomada(conjunto: str, ano: int) -> int:
    marca = controle.ler_marca(FONTE, f"{conjunto}_{ano}") or ""
    if marca.startswith("offset="):
        try:
            return int(marca.split("=", 1)[1])
        except ValueError:
            return 0
    return 0

def descobrir(ano: int) -> dict:
    descobertas = {}
    for conjunto, recurso in CONJUNTOS.items():
        try:
            corpo = buscar_custos(recurso, {"ano": ano, "limit": 1})
            itens = corpo.get("items", []) if isinstance(corpo, dict) else []
            if itens:
                descobertas[conjunto] = itens[0]
        except Exception:
            pass
    return descobertas

def coletar(conjunto: str, ano: int, mes: int | None = None, offset: int = 0, retomar: bool = False) -> tuple[list[dict], bool, int]:
    recurso = CONJUNTOS.get(conjunto, conjunto)
    parametros = {"ano": ano}
    if mes:
        parametros["mes"] = mes

    if retomar and offset == 0:
        offset = _retomada(conjunto, ano)

    agregados: dict[tuple, dict] = {}
    completo = False
    alcancado = offset

    while True:
        p = dict(parametros)
        p["limit"] = PAGINA
        if offset > 0:
            p["offset"] = offset

        try:
            corpo = buscar_custos(recurso, p)
        except Exception as erro:
            if alcancado > 0:
                log.warning("coleta de %s %d interrompida por erro — dados PARCIAIS gravados até offset %d: %s",
                            conjunto, ano, alcancado, erro)
                break
            raise

        if not isinstance(corpo, dict) or "items" not in corpo:
            chaves = list(corpo.keys()) if isinstance(corpo, dict) else []
            log.warning("resposta sem lista para %s: status chaves=%s", conjunto, chaves)
            break

        itens = corpo.get("items")
        if itens is None:
            log.warning("resposta sem lista para %s", conjunto)
            break

        if not itens:
            if corpo.get("hasMore"):
                log.warning("página vazia com hasMore verdadeiro para %s — girar em falso", conjunto)
            else:
                completo = True
            break

        limite_servidor = corpo.get("limit")
        if limite_servidor and limite_servidor < PAGINA:
            log.info("o servidor aplicou limite de %d itens por página", limite_servidor)

        for item in itens:
            val = _valor(item)
            if val is None:
                continue
            m = inteiro(_campo(item, "mes"), 1)
            chave = (
                int(ano),
                m,
                conjunto,
                texto(_campo(item, "orgao_codigo")),
                opcional(_campo(item, "orgao_nome")),
                opcional(_campo(item, "orgao_n2")),
                opcional(_campo(item, "orgao_n3")),
                opcional(_campo(item, "item_custo")),
                opcional(_campo(item, "natureza_juridica")),
            )
            if chave not in agregados:
                agregados[chave] = {
                    "ano": chave[0],
                    "mes": chave[1],
                    "conjunto": chave[2],
                    "orgao_codigo": chave[3],
                    "orgao_nome": chave[4],
                    "orgao_n2": chave[5],
                    "orgao_n3": chave[6],
                    "item_custo": chave[7],
                    "natureza_juridica": chave[8],
                    "valor": numero(val),
                    "data_referencia": f"{ano}-{m:02d}-01",
                }
            else:
                agregados[chave]["valor"] += numero(val)

        offset += len(itens)
        alcancado = offset

        if not corpo.get("hasMore"):
            completo = True
            break

    linhas = list(agregados.values())

    if retomar and linhas:
        try:
            filtro_conj = f"(conjunto = '{conjunto}' OR conjunto = '{recurso}') AND ano = {ano}"
            df_existente = armazem.ler("custo_orgao", filtro=filtro_conj)
            if not df_existente.empty:
                for row in linhas:
                    filtro_antigo = df_existente[
                        (df_existente["orgao_nome"] == row["orgao_nome"]) &
                        (df_existente["item_custo"] == row["item_custo"]) &
                        (df_existente["mes"] == row["mes"])
                    ]
                    if not filtro_antigo.empty:
                        row["valor"] += float(filtro_antigo.iloc[0]["valor"])
        except Exception:
            pass

    return linhas, completo, alcancado

def anos_disponiveis() -> list[int]:
    return list(range(2015, date.today().year + 1))

def executar(anos: list[int] | None = None, conjuntos: list[str] | None = None, refazer: bool = False) -> int:
    anos = anos or [date.today().year]
    conjuntos = conjuntos or list(CONJUNTOS.keys())
    total = 0

    for ano in anos:
        for c in conjuntos:
            recurso = f"{c}_{ano}"
            if not refazer and controle.concluido(FONTE, recurso):
                continue
            try:
                linhas, completo, alcancado = coletar(c, ano, retomar=not refazer)
                if linhas:
                    armazem.mesclar("custo_orgao", linhas, FONTE)
                total += len(linhas)
                if completo:
                    controle.gravar_marca(FONTE, recurso, str(ano), len(linhas), situacao="ok")
                else:
                    controle.gravar_marca(FONTE, recurso, f"offset={alcancado}", len(linhas),
                                          situacao="parcial", detalhe=f"offset={alcancado}")
            except Exception as erro:  # noqa: BLE001
                log.error("Tesouro %s %d falhou: %s", c, ano, erro)
                controle.gravar_marca(FONTE, recurso, str(ano), 0, situacao="erro", detalhe=str(erro))
    return total
