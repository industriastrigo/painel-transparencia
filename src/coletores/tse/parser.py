"""Normalização de cargos e candidaturas do TSE."""
from __future__ import annotations
import pandas as pd
from .. import de_para
from ...nucleo import armazem

FONTE = "tse"
SITUACOES_ELEITO = {"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA", "MÉDIA"}

CARGOS = {
    "1": ("presidente", "0"),
    "2": ("vice_presidente", "0"),
    "3": ("governador", "uf"),
    "4": ("vice_governador", "uf"),
    "5": ("senador", "uf"),
    "6": ("deputado_federal", "uf"),
    "7": ("deputado_estadual", "uf"),
    "8": ("deputado_distrital", "uf"),
    "9": ("suplente_senador_1", "uf"),
    "10": ("suplente_senador_2", "uf"),
    "11": ("prefeito", "municipio"),
    "12": ("vice_prefeito", "municipio"),
    "13": ("vereador", "municipio"),
}

def codigos_uf() -> dict[str, str]:
    df = armazem.ler("dim_ente", filtro="nivel = 'estado'", colunas=["cod_ibge", "sigla_uf"])
    if df.empty:
        return {}
    return dict(zip(df["sigla_uf"].astype(str), df["cod_ibge"].astype(str)))

def construir_de_para(eleitos: pd.DataFrame) -> dict[str, str]:
    cargos_municipais = {c for c, (_, nivel) in CARGOS.items() if nivel == "municipio"}
    municipais = eleitos[eleitos["CD_CARGO"].astype(str).isin(cargos_municipais)]
    if municipais.empty:
        return {}
    unidades = (municipais[["SG_UE", "NM_UE", "SG_UF"]]
                .drop_duplicates("SG_UE")
                .rename(columns={"SG_UE": "id_origem", "NM_UE": "nome", "SG_UF": "sigla_uf"}))
    de_para.construir(unidades, fonte=FONTE)
    return de_para.mapa(FONTE)
