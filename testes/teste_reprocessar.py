"""Reconstrução a partir do arquivo bruto.

Este arquivo existe porque `despesa_funcao` e `indicador_fiscal` ficaram
VAZIAS no acervo real: a chave mudou, os parquets antigos saíram, e a
recoleta que deveria repor nunca rodou. Recoletar são oito horas de rede; o
arquivo bruto refaz em minutos — desde que a leitura do payload guardado
continue igual à da coleta.

É isso que os testes aqui prendem: a regra de leitura é UMA só, e o
reprocessamento não pode virar uma segunda cópia dela.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src.coletores import siconfi
from src.nucleo import reprocessar

# Uma resposta do RREO Anexo 02 no formato REAL, conferido contra a API em
# 2026-08-26: `cod_conta` igual em toda linha, coluna em caixa alta, e a
# função-mãe existindo só na ORDEM.
ITENS_RREO = [
    {"cod_conta": "RREO2TotalDespesas", "conta": "Saúde",
     "rotulo": "DESPESAS EXCETO INTRA-ORÇAMENTÁRIAS",
     "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
     "valor": 1000.0, "uf": "SP"},
    {"cod_conta": "RREO2TotalDespesas", "conta": "Atenção Básica",
     "rotulo": "DESPESAS EXCETO INTRA-ORÇAMENTÁRIAS",
     "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
     "valor": 400.0, "uf": "SP"},
    {"cod_conta": "RREO2TotalDespesas", "conta": "Educação",
     "rotulo": "DESPESAS EXCETO INTRA-ORÇAMENTÁRIAS",
     "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
     "valor": 800.0, "uf": "SP"},
    # Mesmo nome de subfunção, outra função-mãe. É a repetição que colidia
    # na chave e descartava 4.867 linhas numa carga.
    {"cod_conta": "RREO2TotalDespesas", "conta": "Atenção Básica",
     "rotulo": "DESPESAS EXCETO INTRA-ORÇAMENTÁRIAS",
     "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
     "valor": 90.0, "uf": "SP"},
    # Coluna do bimestre isolado: não é a acumulada, tem de ficar fora.
    {"cod_conta": "RREO2TotalDespesas", "conta": "Saúde",
     "rotulo": "DESPESAS EXCETO INTRA-ORÇAMENTÁRIAS",
     "coluna": "DESPESAS EMPENHADAS NO BIMESTRE",
     "valor": 123.0, "uf": "SP"},
]

ITENS_RGF = [
    {"cod_conta": "DespesaTotalComPessoalDTP", "conta": "Despesa com pessoal",
     "rotulo": "DESPESA COM PESSOAL", "coluna": "Valor",
     "valor": 5000.0, "uf": "SP"},
    # A MESMA conta, outra coluna: no RGF é a coluna que decide o
    # significado. As duas linhas têm de sobreviver, com medidas diferentes.
    {"cod_conta": "DespesaTotalComPessoalDTP", "conta": "Despesa com pessoal",
     "rotulo": "DESPESA COM PESSOAL", "coluna": "% sobre a RCL Ajustada",
     "valor": 41.2, "uf": "SP"},
]


def _arquivo(parametros: dict, itens: list) -> dict:
    """Uma linha do arquivo bruto, como `bruto.consultar` a devolve."""
    return {"parametros": json.dumps(parametros),
            "carga": json.dumps({"items": itens})}


def test_reconstroi_despesa_funcao_do_bruto(monkeypatch):
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6,
                      "id_ente": "35", "no_anexo": "RREO-Anexo 02"},
                     ITENS_RREO)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    gravadas = {}
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.update({t: linhas}))

    total = reprocessar.reprocessar("despesa_funcao")
    linhas = gravadas["despesa_funcao"]
    assert total == 4, "a coluna 'NO BIMESTRE' não podia entrar"

    # As duas "Atenção Básica" precisam continuar distintas: é a função-mãe,
    # que só existe na ordem do documento, que as separa.
    basicas = [x for x in linhas if x["rotulo_conta"] == "Atenção Básica"]
    assert len(basicas) == 2
    assert {x["funcao_mae"] for x in basicas} == {"Saúde", "Educação"}
    assert len({x["cod_conta"] for x in basicas}) == 2, (
        "as duas colidiriam na chave primária")


def test_reconstroi_indicador_fiscal_do_bruto(monkeypatch):
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 3, "id_ente": "35",
                      "no_anexo": siconfi.ANEXO_PESSOAL, "co_poder": "E"},
                     ITENS_RGF)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    gravadas = {}
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.update({t: linhas}))

    assert reprocessar.reprocessar("indicador_fiscal") == 2
    linhas = gravadas["indicador_fiscal"]
    assert len({x["medida"] for x in linhas}) == 2, (
        "valor e percentual viraram a mesma medida")


def test_anexo_errado_do_rreo_nao_entra(monkeypatch):
    """O arquivo guarda RREO de vários anexos; só o 02 tem função."""
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                      "no_anexo": "RREO-Anexo 01"}, ITENS_RREO)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda *a, **k: pytest.fail("não podia gravar"))
    assert reprocessar.reprocessar("despesa_funcao") == 0


def test_zero_linha_sai_como_erro_nao_como_sucesso(monkeypatch, caplog):
    """O modo de falha mais caro do projeto: rodou, não deu erro, gravou nada.

    Se a regra de leitura deixar de casar com o formato guardado, isso tem de
    aparecer como ERROR — não passar por 'esse ente não publicou'.
    """
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                      "no_anexo": "RREO-Anexo 02"},
                     [{"cod_conta": "X", "conta": "Saúde", "rotulo": "B",
                       "coluna": "COLUNA QUE NÃO EXISTE MAIS", "valor": 1.0}])
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda *a, **k: pytest.fail("não podia gravar"))

    with caplog.at_level("ERROR"):
        assert reprocessar.reprocessar("despesa_funcao") == 0
    assert any(r.levelname == "ERROR" for r in caplog.records), (
        "reprocessamento vazio precisa gritar")


def test_ensaio_nao_grava(monkeypatch):
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                      "no_anexo": "RREO-Anexo 02"}, ITENS_RREO)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda *a, **k: pytest.fail("--ensaio não grava"))
    assert reprocessar.reprocessar("despesa_funcao", ensaio=True) == 4


def test_intra_e_exceto_intra_nao_colidem_com_rotulo_nulo():
    """Caso real: Alagoas, 2016, RREO Anexo 02.

    A fonte lista cada função duas vezes — despesa comum e
    intra-orçamentária — e marca a diferença no sufixo `Intra` do
    `cod_conta`. O campo `rotulo`, que descreve o mesmo bloco por extenso,
    veio NULO neste ente, e era ele que eu usava como discriminador.

    Resultado: a Legislativa exceto-intra (R$ 245,8 mi) e a intra
    (R$ 33,6 mi) recebiam a mesma chave, e o merge guardava só uma.
    Foram 1.737 linhas perdidas assim numa única reconstrução — e a coleta
    original tinha o mesmo defeito.
    """
    itens = [
        {"cod_conta": "RREO2TotalDespesas", "conta": "Legislativa",
         "rotulo": None, "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
         "valor": 245768381.73, "uf": "AL"},
        {"cod_conta": "RREO2TotalDespesasIntra", "conta": "Legislativa",
         "rotulo": None, "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
         "valor": 33623242.55, "uf": "AL"},
    ]
    linhas = siconfi.interpretar_funcao(itens, 2016, 6, "27")
    assert len(linhas) == 2
    assert {x["bloco"] for x in linhas} == {"exceto_intra", "intra"}
    chaves = {(x["cod_ibge"], x["ano"], x["periodo"], x["cod_conta"])
              for x in linhas}
    assert len(chaves) == 2, "as duas colidiriam e uma seria descartada"
    assert sum(x["valor"] for x in linhas) == pytest.approx(279391624.28)


def test_a_leitura_e_uma_so():
    """O reprocessamento usa a MESMA função da coleta, não uma cópia.

    Se alguém reescrever a regra aqui, as duas envelhecem separadas e o
    painel passa a mostrar números diferentes conforme o caminho por onde o
    dado entrou.
    """
    do_bruto = reprocessar._refazer_despesa_funcao([
        _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                  "no_anexo": "RREO-Anexo 02"}, ITENS_RREO)])
    da_coleta = siconfi.interpretar_funcao(ITENS_RREO, 2024, 6, "35")
    assert do_bruto == da_coleta


def test_do_zero_apaga_antes_de_gravar(monkeypatch):
    """Regra nova gera `sk` novo: sem apagar, as duas versões conviveriam.

    O merge identifica linha por `sk`. Quando a REGRA de leitura muda, o
    mesmo dado da fonte vira um `sk` diferente — o merge vê duas identidades
    e guarda as duas. O acervo fica com a versão certa e a errada juntas, e
    qualquer soma conta parte do dinheiro duas vezes.
    """
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                      "no_anexo": "RREO-Anexo 02"}, ITENS_RREO)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    ordem = []
    monkeypatch.setattr(reprocessar.armazem, "remover",
                        lambda t: ordem.append(("remover", t)))
    monkeypatch.setattr(reprocessar.armazem, "mesclar",
                        lambda t, l, f: ordem.append(("mesclar", t)))

    reprocessar.reprocessar("despesa_funcao", do_zero=True)
    assert ordem == [("remover", "despesa_funcao"),
                     ("mesclar", "despesa_funcao")], "apagar vem ANTES"


def test_sem_do_zero_nao_apaga_nada(monkeypatch):
    """O padrão é conservador: mescla por cima, não destrói."""
    linha = _arquivo({"an_exercicio": 2024, "nr_periodo": 6, "id_ente": "35",
                      "no_anexo": "RREO-Anexo 02"}, ITENS_RREO)
    monkeypatch.setattr(reprocessar.bruto, "consultar",
                        lambda *a, **k: pd.DataFrame([linha]))
    monkeypatch.setattr(reprocessar.armazem, "remover",
                        lambda t: pytest.fail("não podia apagar sem --do-zero"))
    monkeypatch.setattr(reprocessar.armazem, "mesclar", lambda *a, **k: None)
    reprocessar.reprocessar("despesa_funcao")
