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


# ---------------- download grande: truncamento e retomada (30/08/2026)
class _RespostaFalsa:
    def __init__(self, conteudo=b"", status=200, cabecalhos=None):
        self.content = conteudo
        self.status_code = status
        self.headers = cabecalhos or {}
        self.encoding = "utf-8"

    def raise_for_status(self):
        return None

    def json(self):
        raise AssertionError("este teste não usa json")


def test_corpo_menor_que_o_declarado_e_truncamento_nomeado(monkeypatch):
    """`proposicoes-2025.csv` caía sempre, e a mensagem falava de conexão. Já
    `eventosPresencaDeputados-2026.csv` chegava cortado em silêncio e só
    estourava depois, como "não consegui ler como tabela" — com a
    investigação indo para o leitor de CSV em vez do download."""
    from src.nucleo import rede  # noqa: PLC0415

    resp = _RespostaFalsa(b"12345", 200, {"Content-Length": "10"})
    with pytest.raises(rede.RespostaTruncada) as erro:
        rede._completo("camara", "http://x/a.csv", resp, bytearray())
    assert "5 de 10 bytes" in str(erro.value)


def test_corpo_comprimido_nao_e_acusado_de_truncado():
    """Com `Content-Encoding`, o tamanho declarado é o COMPRIMIDO e o corpo já
    veio descomprimido: comparar os dois acusaria todo download bom."""
    from src.nucleo import rede  # noqa: PLC0415

    resp = _RespostaFalsa(b"conteudo bem maior", 200,
                          {"Content-Length": "5", "Content-Encoding": "gzip"})
    assert rede._completo("camara", "http://x", resp, bytearray()) == b"conteudo bem maior"


def test_retomada_junta_os_pedacos_em_ordem():
    """206 continua de onde parou; 200 significa que o servidor ignorou o
    Range, e aí o que já veio tem de ser descartado para não duplicar."""
    from src.nucleo import rede  # noqa: PLC0415

    parcial = bytearray(b"comeco-")
    resp = _RespostaFalsa(b"fim", 206,
                          {"Content-Range": "bytes 7-9/10"})
    assert rede._completo("camara", "http://x", resp, parcial) == b"comeco-fim"

    parcial = bytearray(b"comeco-")
    resp = _RespostaFalsa(b"tudo de novo", 200)
    assert rede._completo("camara", "http://x", resp, parcial) == b"tudo de novo"


def test_arquivo_cortado_explica_que_e_download_e_nao_separador():
    """A mensagem antiga mandava investigar separador e codificação. O erro do
    pandas dizia "EOF inside string", que é assinatura de arquivo cortado."""
    from src.nucleo import tabela  # noqa: PLC0415

    # Aspas abertas e arquivo termina: exatamente o que um download cortado faz.
    cortado = b'"idEvento";"uriEvento"\n"74889";"https://dadosabertos'
    with pytest.raises(RuntimeError) as erro:
        tabela.ler(cortado, origem="presenca.csv")
    assert "CORTADO" in str(erro.value)
