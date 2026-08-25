"""Testes do núcleo: idempotência, detecção de alteração e partições.

  python -m pytest testes -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# Aponta o armazém para uma pasta temporária ANTES de importar o núcleo.
# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from src.nucleo import armazem, chaves, controle  # noqa: E402


def _linhas(valor=10.0):
    return [
        {"cod_ibge": "3550308", "cod_metrica": "populacao", "ano": 2024,
         "valor": valor, "data_referencia": "2024-12-31"},
        {"cod_ibge": "2927408", "cod_metrica": "populacao", "ano": 2024,
         "valor": 2.4, "data_referencia": "2024-12-31"},
        {"cod_ibge": "3550308", "cod_metrica": "populacao", "ano": 2023,
         "valor": 11.0, "data_referencia": "2023-12-31"},
    ]


@pytest.fixture(autouse=True)
def limpar():
    armazem.remover("indicador_ente")
    yield


# ------------------------------------------------------------------ chaves
def test_sk_e_deterministica():
    registro = {"a": 1, "b": "x"}
    assert chaves.sk(registro, ("a", "b")) == chaves.sk(dict(registro), ("a", "b"))


def test_sk_muda_com_a_pk():
    assert chaves.sk({"a": 1}, ("a",)) != chaves.sk({"a": 2}, ("a",))


def test_sk_ignora_ordem_de_insercao_do_dicionario():
    assert chaves.sk({"a": 1, "b": 2}, ("a", "b")) \
        == chaves.sk({"b": 2, "a": 1}, ("a", "b"))


def test_hash_ignora_colunas_de_controle():
    base = {"a": 1, "b": 2}
    assert chaves.hash_registro(base) == chaves.hash_registro(
        {**base, "_fonte": "x", "_criado_em": "hoje"})


def test_pk_ausente_falha_alto():
    with pytest.raises(KeyError):
        chaves.sk({"a": 1}, ("a", "b"))


# ------------------------------------------------------------------ merge
def test_primeira_carga_insere_tudo():
    r = armazem.mesclar("indicador_ente", _linhas(), "teste")
    assert r["inseridos"] == 3


def test_recarga_identica_nao_altera_nada():
    armazem.mesclar("indicador_ente", _linhas(), "teste")
    r = armazem.mesclar("indicador_ente", _linhas(), "teste")
    assert (r["inseridos"], r["alterados"]) == (0, 0)
    assert r["inalterados"] == 3


def test_reexecutar_nao_duplica():
    for _ in range(3):
        armazem.mesclar("indicador_ente", _linhas(), "teste")
    df = armazem.ler("indicador_ente")
    assert len(df) == 3
    assert df["sk"].is_unique


def test_alteracao_real_atualiza_so_a_linha_mudada():
    armazem.mesclar("indicador_ente", _linhas(), "teste")
    antes = armazem.ler("indicador_ente").set_index("sk")

    r = armazem.mesclar("indicador_ente", _linhas(valor=99.0), "teste")
    assert (r["alterados"], r["inalterados"]) == (1, 2)

    depois = armazem.ler("indicador_ente").set_index("sk")
    mudadas = [sk for sk in antes.index
               if antes.loc[sk, "_atualizado_em"] != depois.loc[sk, "_atualizado_em"]]
    assert len(mudadas) == 1
    # a data de criação nunca é reescrita
    assert (antes["_criado_em"].sort_index()
            .equals(depois["_criado_em"].sort_index()))


def test_particao_hive_por_ano():
    armazem.mesclar("indicador_ente", _linhas(), "teste")
    base = armazem.caminho_base(armazem.obter("indicador_ente"))
    anos = sorted(p.name for p in base.iterdir() if p.is_dir())
    assert anos == ["ano=2023", "ano=2024"]


def test_filtro_por_particao_le_so_o_que_precisa():
    armazem.mesclar("indicador_ente", _linhas(), "teste")
    df = armazem.ler("indicador_ente", filtro="ano = 2023")
    assert len(df) == 1 and int(df.iloc[0]["ano"]) == 2023


def test_colunas_de_controle_no_fim_e_sk_na_frente():
    armazem.mesclar("indicador_ente", _linhas(), "teste")
    colunas = list(armazem.ler("indicador_ente").columns)
    assert colunas[0] == "sk"
    assert colunas[-4:] == ["_hash_registro", "_fonte", "_criado_em", "_atualizado_em"]


def test_lote_vazio_nao_quebra():
    assert armazem.mesclar("indicador_ente", [], "teste")["inseridos"] == 0


def test_duplicata_no_mesmo_lote_mantem_a_ultima():
    duplicadas = _linhas() + [{
        "cod_ibge": "3550308", "cod_metrica": "populacao", "ano": 2024,
        "valor": 77.0, "data_referencia": "2024-12-31"}]
    armazem.mesclar("indicador_ente", duplicadas, "teste")
    df = armazem.ler("indicador_ente", filtro="cod_ibge = '3550308' AND ano = 2024")
    assert len(df) == 1 and float(df.iloc[0]["valor"]) == 77.0


# ------------------------------------------------------------------ controle
def test_marca_dagua_vai_e_volta():
    controle.gravar_marca("teste", "recurso", "2024-08-01", linhas=10)
    assert controle.ler_marca("teste", "recurso") == "2024-08-01"
    controle.gravar_marca("teste", "recurso", "2024-09-01", linhas=12)
    assert controle.ler_marca("teste", "recurso") == "2024-09-01"
    assert len(controle.situacao()) >= 1
