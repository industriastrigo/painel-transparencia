"""Testes do de-para TSE → IBGE, com os nomes que realmente divergem.

Todos os casos abaixo são divergências reais entre como o TSE e o IBGE
escrevem o mesmo município. É o teste que impede o painel de perder metade
dos prefeitos num JOIN silencioso.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from src.coletores import de_para  # noqa: E402
from src.nucleo import armazem  # noqa: E402
from src.nucleo.nomes import chave_estrita, chave_frouxa, similaridade  # noqa: E402

# (cod_ibge, nome como o IBGE escreve, UF)
MUNICIPIOS = [
    ("4317103", "Sant'Ana do Livramento", "RS"),
    ("1100098", "Espigão D'Oeste", "RO"),
    ("3506607", "Biritiba Mirim", "SP"),
    ("3530607", "Mogi Mirim", "SP"),
    ("3550308", "São Paulo", "SP"),
    ("3516309", "Florínea", "SP"),
    ("3515004", "Embu das Artes", "SP"),
    ("2402600", "Campo Grande", "RN"),
    ("2412005", "Serra Caiada", "RN"),
    ("2408003", "Natal", "RN"),
    ("3147105", "Passa-Vinte", "MG"),
    ("3162922", "São Tomé das Letras", "MG"),
    ("1502772", "Eldorado do Carajás", "PA"),
    ("2408102", "São Gonçalo do Amarante", "RN"),
    ("2307304", "São Gonçalo do Amarante", "CE"),
    ("5002209", "Bonito", "MS"),
    ("1501758", "Bonito", "PA"),
    ("2602100", "Bonito", "PE"),
    ("2903904", "Bonito", "BA"),
    ("2927408", "Salvador", "BA"),
]


@pytest.fixture(scope="module", autouse=True)
def semear():
    armazem.mesclar("dim_ente", [
        {"cod_ibge": cod, "nivel": "municipio", "nome": nome, "sigla_uf": uf,
         "cod_uf": cod[:2], "regiao": None, "cod_regiao": None}
        for cod, nome, uf in MUNICIPIOS
    ], "teste")
    yield


def casar(nome_tse: str, uf: str, id_origem: str = "1") -> dict:
    resultado = de_para.construir(
        [{"id_origem": id_origem, "nome": nome_tse, "sigla_uf": uf}],
        gravar=False)
    return resultado.iloc[0].to_dict()


# ------------------------------------------------------------------ chaves
def test_chave_estrita_tira_acento_e_caixa():
    assert chave_estrita("São Paulo") == "sao paulo"
    assert chave_estrita("ELDORADO DOS CARAJÁS") == "eldorado dos carajas"


def test_chave_estrita_transforma_pontuacao_em_espaco():
    assert chave_estrita("Biritiba-Mirim") == "biritiba mirim"
    assert chave_estrita("Sant'Ana do Livramento") == "sant ana do livramento"


def test_chave_frouxa_absorve_preposicoes_e_pontuacao():
    assert chave_frouxa("Espigão D'Oeste") == chave_frouxa("ESPIGAO DO OESTE")
    assert chave_frouxa("Sant'Ana do Livramento") \
        == chave_frouxa("SANTANA DO LIVRAMENTO")
    assert chave_frouxa("Biritiba-Mirim") == chave_frouxa("BIRITIBA MIRIM")


def test_chave_frouxa_nao_apaga_nome_que_so_tem_preposicao():
    assert chave_frouxa("Do") != ""


def test_similaridade_e_simetrica_e_limitada():
    assert similaridade("bonito", "bonito") == 1.0
    assert similaridade("bonito", "brejinho") == similaridade("brejinho", "bonito")
    assert 0.0 <= similaridade("bonito", "brejinho") < 0.5


# -------------------------------------------------------------- casamentos
def test_nome_identico_casa_exato():
    r = casar("SAO PAULO", "SP")
    assert (r["metodo"], r["cod_ibge"]) == ("exata", "3550308")


def test_apostrofo_do_ibge_contra_juncao_do_tse():
    r = casar("SANTANA DO LIVRAMENTO", "RS")
    assert r["cod_ibge"] == "4317103"
    assert r["metodo"] in ("excecao", "frouxa")


def test_d_oeste_contra_do_oeste():
    r = casar("ESPIGAO DO OESTE", "RO")
    assert (r["metodo"], r["cod_ibge"]) == ("frouxa", "1100098")


def test_hifen_do_ibge_contra_espaco_do_tse():
    r = casar("BIRITIBA MIRIM", "SP")
    assert r["cod_ibge"] == "3506607"


def test_hifen_do_tse_contra_espaco_do_ibge():
    r = casar("PASSA VINTE", "MG")
    assert r["cod_ibge"] == "3147105"


def test_grafia_divergente_resolve_por_excecao():
    """Mogi/Moji não cede a nenhuma regra — é exceção escrita à mão."""
    r = casar("MOJI MIRIM", "SP")
    assert (r["metodo"], r["cod_ibge"]) == ("excecao", "3530607")


def test_municipio_renomeado_resolve_por_excecao():
    """Augusto Severo virou Campo Grande; o TSE demorou a acompanhar."""
    r = casar("AUGUSTO SEVERO", "RN")
    assert (r["metodo"], r["cod_ibge"]) == ("excecao", "2402600")
    assert r["nome_ibge"] == "Campo Grande"


def test_renomeacao_nao_atrapalha_o_nome_novo():
    """'Campo Grande' escrito pelo TSE tem que casar direto, sem exceção."""
    r = casar("CAMPO GRANDE", "RN")
    assert (r["metodo"], r["cod_ibge"]) == ("exata", "2402600")


# ---------------------------------------------------------------- limites
def test_homonimo_em_outra_uf_nao_confunde():
    """Bonito existe em MS, PA, PE e BA. A UF é o que desempata."""
    for uf, esperado in [("MS", "5002209"), ("PA", "1501758"),
                         ("PE", "2602100"), ("BA", "2903904")]:
        r = casar("BONITO", uf)
        assert r["cod_ibge"] == esperado, f"errou em {uf}"


def test_mesmo_nome_em_ufs_diferentes_sao_registros_distintos():
    a = casar("SAO GONCALO DO AMARANTE", "RN")
    b = casar("SAO GONCALO DO AMARANTE", "CE")
    assert a["cod_ibge"] == "2408102"
    assert b["cod_ibge"] == "2307304"


def test_erro_de_digitacao_casa_por_aproximacao():
    r = casar("SAO GONCALO DO AMARENTE", "RN")
    assert r["metodo"] == "aproximada"
    assert r["cod_ibge"] == "2408102"
    assert r["similaridade"] >= de_para.LIMIAR_APROXIMADO


def test_nome_muito_diferente_vira_pendencia_e_nao_chute():
    r = casar("CIDADE QUE NAO EXISTE", "SP")
    assert r["cod_ibge"] is None
    assert r["metodo"] == "pendente"


def test_uf_desconhecida_nao_inventa_municipio():
    r = casar("SAO PAULO", "ZZ")
    assert (r["cod_ibge"], r["metodo"]) == (None, "sem_uf")


def test_empate_apertado_nao_resolve(monkeypatch):
    """Dois candidatos igualmente parecidos: melhor sem prefeito do que errado."""
    armazem.mesclar("dim_ente", [
        {"cod_ibge": "9900001", "nivel": "municipio", "nome": "Vila Nova A",
         "sigla_uf": "ZY", "cod_uf": "99", "regiao": None, "cod_regiao": None},
        {"cod_ibge": "9900002", "nivel": "municipio", "nome": "Vila Nova B",
         "sigla_uf": "ZY", "cod_uf": "99", "regiao": None, "cod_regiao": None},
    ], "teste")
    r = casar("VILA NOVA C", "ZY")
    assert r["cod_ibge"] is None
    assert r["metodo"] == "pendente"


# ------------------------------------------------------------- integração
def test_construir_grava_e_o_mapa_le_de_volta():
    unidades = [
        {"id_origem": "71072", "nome": "SAO PAULO", "sigla_uf": "SP"},
        {"id_origem": "38490", "nome": "SALVADOR", "sigla_uf": "BA"},
        {"id_origem": "99999", "nome": "LUGAR NENHUM", "sigla_uf": "SP"},
    ]
    de_para.construir(unidades)

    mapa = de_para.mapa()
    assert mapa["71072"] == "3550308"
    assert mapa["38490"] == "2927408"
    assert "99999" not in mapa, "pendência não pode virar entrada no mapa"

    pendentes = de_para.pendencias()
    assert "LUGAR NENHUM" in set(pendentes["nome_origem"])


def test_reconstruir_e_idempotente():
    unidades = [{"id_origem": "71072", "nome": "SAO PAULO", "sigla_uf": "SP"}]
    de_para.construir(unidades)
    antes = len(armazem.ler("dim_de_para_ente"))
    de_para.construir(unidades)
    assert len(armazem.ler("dim_de_para_ente")) == antes


def test_relatorio_conta_por_metodo():
    resultado = de_para.construir([
        {"id_origem": "a", "nome": "SAO PAULO", "sigla_uf": "SP"},
        {"id_origem": "b", "nome": "MOJI MIRIM", "sigla_uf": "SP"},
        {"id_origem": "c", "nome": "NAO EXISTE MESMO", "sigla_uf": "SP"},
    ], gravar=False)
    contagem = de_para.relatar(resultado)
    assert contagem.get("exata") == 1
    assert contagem.get("excecao") == 1
    assert contagem.get("pendente") == 1
