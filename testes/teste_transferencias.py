"""Transferências constitucionais da União.

O ponto delicado aqui não é somar: é **não confundir duas medidas**. O painel
passa a ter dois números com o mesmo nome popular, "transferências", e eles
não batem:

- `vw_transferencia_recebida` — o que o ENTE declarou receber (SICONFI,
  anual, qualquer origem, inclusive o ICMS que o estado repassa a ele);
- `vw_transferencia_uniao` — o que a UNIÃO pagou (Tesouro/SIAFI, mensal, só
  as obrigatórias federais).

Somar os dois contaria o FPM duas vezes. Estes testes existem para o dia em
que alguém achar que "seria mais simples juntar numa coluna só".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.api import vistas  # noqa: E402
from src.coletores import transferencias  # noqa: E402
from src.nucleo import armazem  # noqa: E402
from src.nucleo.erros import ConfiguracaoAusente  # noqa: E402


def _amostra():
    armazem.remover("transferencia_uniao")
    linhas = []
    for mes, valor in [(1, 100.0), (2, 120.0), (3, 90.0)]:
        linhas.append({
            "cod_ibge": "3550308", "nivel": "municipio", "uf": "SP",
            "nome_ente": "São Paulo", "cod_transferencia": "FPM",
            "transferencia": "Fundo de Participação dos Municípios",
            "ano": 2024, "mes": mes, "valor": valor,
            "cod_siafi": "7107", "data_referencia": "2024-12-31",
        })
    linhas.append({
        "cod_ibge": "3550308", "nivel": "municipio", "uf": "SP",
        "nome_ente": "São Paulo", "cod_transferencia": "FUNDEB",
        "transferencia": "FUNDEB", "ano": 2024, "mes": 1, "valor": 500.0,
        "cod_siafi": "7107", "data_referencia": "2024-12-31",
    })
    armazem.mesclar("transferencia_uniao", linhas, "teste")


def test_soma_os_meses_de_cada_modalidade():
    _amostra()
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT transferencia_uniao FROM vw_transferencia_uniao "
        " WHERE cod_ibge = '3550308' AND ano = 2024").fetchone()[0]
    assert total == 810.0, "310 de FPM + 500 de FUNDEB"


def test_modalidade_fica_visivel_separada():
    """Somar tudo num número só responde 'quanto', nunca 'por quê'. O FPM cair
    e o FUNDEB subir some no total e aparece aqui."""
    _amostra()
    con = vistas.conexao_leitura()
    por_tipo = dict(con.execute(
        "SELECT cod_transferencia, valor FROM vw_transferencia_modalidade "
        " WHERE cod_ibge = '3550308' AND ano = 2024").fetchall())
    assert por_tipo == {"FPM": 310.0, "FUNDEB": 500.0}


def test_recoletar_o_mesmo_mes_nao_duplica():
    """A série é revisada pelo Tesouro ('podem retroceder até o início do
    exercício em curso'), então recoletar é rotina, não exceção."""
    _amostra()
    _amostra()
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT transferencia_uniao FROM vw_transferencia_uniao "
        " WHERE cod_ibge = '3550308'").fetchone()[0]
    assert total == 810.0, "a segunda coleta duplicou as linhas"


def test_valor_revisado_substitui_em_vez_de_somar():
    _amostra()
    armazem.mesclar("transferencia_uniao", [{
        "cod_ibge": "3550308", "nivel": "municipio", "uf": "SP",
        "nome_ente": "São Paulo", "cod_transferencia": "FPM",
        "transferencia": "Fundo de Participação dos Municípios",
        "ano": 2024, "mes": 1, "valor": 150.0,      # era 100
        "cod_siafi": "7107", "data_referencia": "2024-12-31",
    }], "teste")

    con = vistas.conexao_leitura()
    fpm = con.execute(
        "SELECT valor FROM vw_transferencia_modalidade "
        " WHERE cod_ibge = '3550308' AND cod_transferencia = 'FPM'"
    ).fetchone()[0]
    assert fpm == 360.0, "150 + 120 + 90 — a revisão substitui o mês"


def test_as_duas_medidas_de_transferencia_nao_se_misturam():
    """A que o ente declarou e a que a União pagou ficam em colunas distintas
    do mapa. Se um dia virarem uma só, o FPM é contado duas vezes."""
    _amostra()
    armazem.remover("financas_ente")
    armazem.mesclar("financas_ente", [{
        "cod_ibge": "3550308", "ano": 2024, "periodo": "anual",
        "cod_conta": "1.7.0.0.00.0.0", "cod_funcao": None, "funcao": None,
        "rotulo_conta": "Transferências Correntes",
        "estagio": "Receitas Brutas Realizadas", "valor": 2000.0,
        "esfera": "municipio", "uf": "SP", "data_referencia": "2024-12-31",
    }], "teste")
    armazem.mesclar("dim_ente", [{
        "cod_ibge": "3550308", "nivel": "municipio", "nome": "São Paulo",
        "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste",
        "cod_regiao": "3"}], "teste")

    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT transferencia_recebida, transferencia_uniao "
        "  FROM vw_mapa WHERE cod_ibge = '3550308' AND ano = 2024").fetchone()
    assert linha == (2000.0, 810.0), (
        "as duas medidas precisam continuar separadas e com valores próprios")


# --------------------------------------------------- leitura da resposta
def test_campo_e_lido_por_qualquer_um_dos_nomes_conhecidos():
    """Armadilha 2d: o mesmo dado com dois nomes. Aqui não há um nome só
    cravado — a API pode devolver `co_ibge` ou `cod_ibge`."""
    assert transferencias.primeiro({"co_ibge": "35"}, "co_ibge", "cod_ibge") == "35"
    assert transferencias.primeiro({"cod_ibge": "35"}, "co_ibge", "cod_ibge") == "35"
    assert transferencias.primeiro({"outro": 1}, "co_ibge", "cod_ibge") is None


def test_campo_vazio_conta_como_ausente():
    """String vazia não é valor: sem isto, `uf: ""` venceria o nome seguinte
    da lista e o campo ficaria em branco em vez de tentar o apelido certo."""
    assert transferencias.primeiro({"uf": "", "sg_uf": "BA"}, "uf", "sg_uf") == "BA"


def test_acesso_negado_vira_pendencia_de_configuracao_e_nao_erro():
    """A API pede liberação por e-mail. Sem chave, o certo é a tela dizer o
    que fazer — não um erro genérico, e muito menos um tique verde com zero
    linhas (a armadilha 2e)."""
    pendencia = ConfiguracaoAusente("Transferências: acesso negado (HTTP 403).",
                                    transferencias.COMO_PEDIR_ACESSO)
    assert "desenvolvimento@tesouro.gov.br" in str(pendencia)
    assert "CHAVE_TESOURO_ARIA" in pendencia.como_resolver


def test_catalogo_vazio_nao_finge_coleta():
    """Sem catálogo não há o que pedir. Devolver 0 em silêncio seria dizer
    'coletei nada com sucesso'."""
    assert transferencias.coletar_ano(2024, catalogo=[]) == 0


# ---------------------------------------------- a chave que apagava dado
def test_cod_ibge_do_estado_sai_da_sigla():
    """A rota por estado não devolve código IBGE, só a sigla — e o `cod_ibge`
    é o que liga estas linhas ao mapa. Sem ele, o dado fica no disco e a
    métrica fica cinza na tela."""
    from src.coletores.transferencias import _linhas  # noqa: PLC0415

    linhas = _linhas(
        [{"uf": "PR", "valor": 100.0, "mes": 1},
         {"uf": "sc", "valor": 200.0, "mes": 1}],
        "estado", 1997, {"cod_transferencia": "5", "transferencia": "Kandir"})
    assert [l["cod_ibge"] for l in linhas] == ["41", "42"]


def test_as_27_ufs_nao_colapsam_numa_linha_so():
    """O defeito que reduziu 840 linhas de 1997 a 53 no acervo.

    A chave era (cod_ibge, cod_transferencia, ano, mes). Com `cod_ibge` nulo
    em todas as linhas, as 27 UFs viravam UMA por modalidade e mês, e o merge
    guardava a última — com aviso no log, repetido 239 vezes, que ninguém viu.
    """
    from src.coletores.transferencias import _linhas  # noqa: PLC0415
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("transferencia_uniao")
    linhas = _linhas(
        [{"uf": uf, "valor": float(i), "mes": 1}
         for i, uf in enumerate(["PR", "SC", "RS", "SP", "MG"])],
        "estado", 2024, {"cod_transferencia": "5", "transferencia": "Kandir"})
    armazem.mesclar("transferencia_uniao", linhas, "teste")

    guardadas = armazem.ler("transferencia_uniao")
    assert len(guardadas) == 5, (
        f"{len(guardadas)} de 5 linhas sobreviveram — a chave está "
        f"descrevendo um grão mais grosso que o dado")


def test_colapso_de_chave_fica_contado_para_o_resumo():
    """O aviso por lote sempre existiu e estava certo. O problema era só que
    ele saía no meio de 1.476 linhas de log. Agora também é contado, e o
    resumo da manhã o mostra."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("transferencia_uniao")
    armazem.COLAPSOS.clear()
    repetidas = [{
        "cod_ibge": "41", "nivel": "estado", "uf": "PR",
        "cod_transferencia": "5", "transferencia": "Kandir",
        "ano": 2024, "mes": 1, "valor": v, "nome_ente": None,
        "cod_siafi": None, "data_referencia": "2024-12-31"} for v in (1.0, 2.0)]
    armazem.mesclar("transferencia_uniao", repetidas, "teste")

    assert armazem.COLAPSOS.get("transferencia_uniao") == 1


# ------------------------------- o que o arquivo bruto revelou (26/08/2026)
# As duas rotas desta MESMA API escrevem em caixas diferentes e paginam de
# jeitos diferentes. Os dois defeitos juntos deixaram o acervo com ZERO
# município — e nada no log parecia errado, porque as linhas chegavam e eram
# descartadas em silêncio, uma a uma, no teste de valor nulo.
MUNICIPAL = {
    "UF": "AC", "ANO": "1997", "TRANSFERENCIA": "FPM", "codigo_siafi": 643,
    "CO_IBGE": 1200013, "MES": "01", "MUNICIPIO": "Acrelândia",
    "VALOR": 73719.42,
}
ESTADUAL = {
    "transferencia": "LC 87/96 (Lei Kandir)", "uf": "MS", "ano": "1997",
    "valor": 768180.78, "mes": "01", "regiao": "Centro-Oeste",
}


def test_a_rota_municipal_vem_em_CAIXA_ALTA():
    """`CO_IBGE`, `VALOR`, `UF` — a busca de campo era exata e não casava
    nenhum. Toda linha municipal caía no `if valor is None: continue`."""
    from src.coletores.transferencias import _linhas  # noqa: PLC0415

    linhas = _linhas([MUNICIPAL], "municipio", 1997,
                     {"cod_transferencia": "1", "transferencia": "FPM"})
    assert linhas, "a linha municipal foi descartada de novo"
    assert linhas[0]["cod_ibge"] == "1200013"
    assert linhas[0]["uf"] == "AC"
    assert linhas[0]["nome_ente"] == "Acrelândia"
    assert linhas[0]["valor"] == 73719.42
    assert linhas[0]["cod_siafi"] == "643", "o campo é `codigo_siafi` aqui"


def test_a_rota_estadual_continua_lendo():
    from src.coletores.transferencias import _linhas  # noqa: PLC0415

    linhas = _linhas([ESTADUAL], "estado", 1997,
                     {"cod_transferencia": "5", "transferencia": "Kandir"})
    assert linhas[0]["cod_ibge"] == "50" and linhas[0]["valor"] == 768180.78


def test_segue_a_paginacao_por_next(monkeypatch):
    """A rota municipal usa `page`/`pageSize`/`next` e **nunca manda
    `hasMore`** — a única convenção que o laço conhecia. Parava sempre na
    primeira página, com `pageSize: 10`.

    O arquivo bruto mostrou o tamanho do buraco: 2.340 registros municipais
    capturados contra 55.214 estaduais, quando a municipal deveria ser a
    maior de longe.
    """
    from src.coletores import transferencias as t  # noqa: PLC0415
    from src.nucleo import rede  # noqa: PLC0415

    paginas = {
        1: {"status": "ok", "page": 1, "pageSize": 10,
            "next": "https://exemplo/...page=2", "registros": [MUNICIPAL] * 10},
        2: {"status": "ok", "page": 2, "pageSize": 10,
            "next": "https://exemplo/...page=3", "registros": [MUNICIPAL] * 4},
        3: {"status": "ok", "page": 3, "pageSize": 10,
            "next": "https://exemplo/...page=4", "registros": []},
    }
    pedidas = []

    def _falso(fonte, url, parametros=None, **kwargs):
        pagina = int((parametros or {}).get("page", 1))
        pedidas.append(pagina)
        return paginas[pagina]

    monkeypatch.setattr(rede, "buscar", _falso)
    linhas = t._pedir("/custom/por_estado_municipio", {"p_ano": 1997})

    assert pedidas == [1, 2, 3], f"não percorreu as páginas: {pedidas}"
    assert len(linhas) == 14


def test_pagina_vazia_com_next_nao_vira_laco_infinito(monkeypatch):
    """A API manda `next` MESMO quando a página veio vazia — seguir por ele
    sem olhar o conteúdo roda até o teto de páginas."""
    from src.coletores import transferencias as t  # noqa: PLC0415
    from src.nucleo import rede  # noqa: PLC0415

    chamadas = []

    def _falso(fonte, url, parametros=None, **kwargs):
        chamadas.append(1)
        return {"status": "ok", "page": 1, "pageSize": 10,
                "next": "https://exemplo/...page=2", "registros": []}

    monkeypatch.setattr(rede, "buscar", _falso)
    assert t._pedir("/custom/por_estado_municipio", {"p_ano": 1997}) == []
    assert len(chamadas) == 1, "seguiu o `next` de uma página vazia"


def test_hasMore_do_ORDS_continua_funcionando(monkeypatch):
    """A outra convenção não pode ter sido quebrada pelo conserto."""
    from src.coletores import transferencias as t  # noqa: PLC0415
    from src.nucleo import rede  # noqa: PLC0415

    respostas = [
        {"items": [ESTADUAL], "hasMore": True},
        {"items": [ESTADUAL], "hasMore": False},
    ]

    def _falso(fonte, url, parametros=None, **kwargs):
        return respostas.pop(0)

    monkeypatch.setattr(rede, "buscar", _falso)
    assert len(t._pedir("/custom/por_estados", {"p_ano": 1997})) == 2
