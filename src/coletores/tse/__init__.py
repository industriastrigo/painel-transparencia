"""Módulo TSE (Tribunal Superior Eleitoral)."""
from __future__ import annotations

import pandas as pd
from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log
from ...nucleo.valores import texto

from .cliente import baixar_consulta_cand as _baixar_consulta_cand
from .parser import CARGOS, SITUACOES_ELEITO, codigos_uf as _codigos_uf, construir_de_para
from .erros import ErroTSE, diagnosticar_erro

log = obter_log("coletores.tse")
FONTE = "tse"

def catalogo_cargos() -> int:
    linhas = [{
        "cod_cargo": codigo,
        "cargo": nome,
        "nivel_ente": nivel,
        "poder": "executivo" if nome in ("presidente", "governador", "prefeito") else "legislativo",
    } for codigo, (nome, nivel) in CARGOS.items()]
    armazem.mesclar("dim_cargo", linhas, FONTE)
    return len(linhas)

def coletar_eleitos(ano: int) -> int:
    df = _baixar_consulta_cand(ano)
    if df.empty:
        return 0

    situacao = df.get("DS_SIT_TOT_TURNO", pd.Series(dtype=str)).str.upper()
    eleitos = df[situacao.isin(SITUACOES_ELEITO)].copy()
    log.info("TSE %d: %d candidaturas, %d eleitos", ano, len(df), len(eleitos))

    if eleitos.empty and len(df):
        log.warning(
            "TSE %d tem %d candidaturas mas nenhum eleito — a apuração de %d "
            "provavelmente ainda não saiu. Use um ano de eleição já apurada "
            "(ex.: --anos 2022 2024).", ano, len(df), ano)
        controle.gravar_marca(FONTE, f"eleitos_{ano}", None, 0, situacao="nao_apurado", detalhe=f"{len(df)} candidaturas, 0 eleitos")
        return 0

    ue_para_ibge = construir_de_para(eleitos)
    uf_para_ibge = _codigos_uf()

    politicos, mandatos, desconhecidos = [], [], set()
    for _, c in eleitos.iterrows():
        cod_cargo = str(c.get("CD_CARGO"))
        nome_cargo, nivel = CARGOS.get(cod_cargo, (f"cargo_{cod_cargo}", "uf"))
        if nome_cargo.startswith("cargo_"):
            desconhecidos.add(cod_cargo)
        id_origem = str(c.get("SQ_CANDIDATO"))

        politicos.append({
            "fonte_origem": FONTE,
            "id_origem": id_origem,
            "nome": c.get("NM_CANDIDATO"),
            "nome_eleitoral": c.get("NM_URNA_CANDIDATO"),
            "sigla_partido": c.get("SG_PARTIDO"),
            "sigla_uf": c.get("SG_UF"),
            "id_legislatura": str(ano),
            "email": c.get("DS_EMAIL"),
            "url_foto": None,
            "casa": None,
            "cargo": nome_cargo,
            "genero": c.get("DS_GENERO"),
            "cor_raca": c.get("DS_COR_RACA"),
            "grau_instrucao": c.get("DS_GRAU_INSTRUCAO"),
            "ocupacao": c.get("DS_OCUPACAO"),
            "data_nascimento": c.get("DT_NASCIMENTO"),
        })

        cod_ue = texto(c.get("SG_UE"))
        if nivel == "municipio":
            cod_ibge = ue_para_ibge.get(cod_ue)
        elif nivel == "uf":
            cod_ibge = uf_para_ibge.get(texto(c.get("SG_UF")))
        else:
            cod_ibge = "0"

        mandatos.append({
            "sk_politico": id_origem,
            "cod_cargo": cod_cargo,
            "cargo": nome_cargo,
            "cod_ue": cod_ue,
            "cod_ibge": cod_ibge,
            "sigla_uf": c.get("SG_UF"),
            "nome_ente": c.get("NM_UE"),
            "ano_inicio": int(ano) + 1,
            "ano_fim": int(ano) + 5 if nome_cargo != "senador" else int(ano) + 9,
            "data_inicio": f"{int(ano) + 1}-01-01",
            "nome": c.get("NM_URNA_CANDIDATO"),
            "sigla_partido": c.get("SG_PARTIDO"),
            "ano_eleicao": int(ano),
        })

    armazem.mesclar("dim_politico", politicos, f"{FONTE}_cand")
    armazem.mesclar("mandato", mandatos, f"{FONTE}_cand")

    if desconhecidos:
        log.warning("TSE %d: códigos de cargo sem tradução: %s — acrescente em CARGOS, senão aparecem como `cargo_N` no painel",
                    ano, sorted(desconhecidos))

    sem_ente = sum(1 for m in mandatos if not m["cod_ibge"])
    controle.gravar_marca(FONTE, f"eleitos_{ano}", ano, len(mandatos), detalhe=f"{sem_ente} sem código IBGE")
    return len(mandatos)

def coletar_partidos(ano: int) -> int:
    df = _baixar_consulta_cand(ano)
    if df.empty:
        return 0
    partidos = (df[["SG_PARTIDO", "NM_PARTIDO", "NR_PARTIDO"]]
                .drop_duplicates("SG_PARTIDO").dropna(subset=["SG_PARTIDO"]))
    linhas = [{
        "sigla": p["SG_PARTIDO"],
        "nome": p["NM_PARTIDO"],
        "numero": p["NR_PARTIDO"],
        "ano_referencia": ano,
    } for _, p in partidos.iterrows()]
    armazem.mesclar("dim_partido", linhas, FONTE)
    return len(linhas)

def executar(anos: list[int] | None = None) -> None:
    catalogo_cargos()
    anos = anos or [2022, 2024]
    for ano in anos:
        try:
            coletar_partidos(ano)
            coletar_eleitos(ano)
        except Exception as erro:  # noqa: BLE001
            log.error("TSE %d falhou: %s", ano, erro)
            controle.gravar_marca(FONTE, f"eleitos_{ano}", None, situacao="erro", detalhe=str(erro))
