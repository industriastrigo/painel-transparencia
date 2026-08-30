"""Arrecadação e transferências recebidas.

As contas de receita do SICONFI são hierárquicas exatamente como as de
despesa. A armadilha 2j (somar a função com as subfunções e inflar a despesa
em 5×) tem aqui um gêmeo: somar `1.0.0.0.00.0.0` junto com `1.1.0.0.00.0.0`
conta o mesmo real duas vezes.

Por isso os testes abaixo usam uma amostra HIERÁRQUICA. Testar com contas
planas faz a soma dar certo por acidente — foi assim que a agregação de
despesa passou por meses com o defeito dentro.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from src.api import vistas  # noqa: E402
from src.nucleo import armazem  # noqa: E402


def _receita_hierarquica():
    """Como o Anexo I-C vem: pai e filhos como linhas irmãs.

    Receitas Correntes 1.000 = tributos 300 + transferências 700.
    Receitas de Capital 200 = operações de crédito 150 + transf. de capital 50.
    Total honesto: 1.200. Transferências recebidas: 750.
    """
    armazem.remover("financas_ente")
    linhas = []
    for conta, rotulo, valor in [
        ("1.0.0.0.00.0.0", "Receitas Correntes", 1000.0),
        ("1.1.0.0.00.0.0", "Impostos, Taxas e Contribuições", 300.0),
        ("1.7.0.0.00.0.0", "Transferências Correntes", 700.0),
        ("1.7.1.8.00.0.0", "Transferências da União", 500.0),
        ("1.7.2.8.00.0.0", "Transferências dos Estados", 200.0),
        ("2.0.0.0.00.0.0", "Receitas de Capital", 200.0),
        ("2.1.0.0.00.0.0", "Operações de Crédito", 150.0),
        ("2.4.0.0.00.0.0", "Transferências de Capital", 50.0),
        # Deduções: existem no anexo e NÃO entram na receita bruta.
        ("9.7.2.1.01.0.0", "Dedução para o FUNDEB", -80.0),
    ]:
        linhas.append({
            "cod_ibge": "35", "ano": 2024, "periodo": "anual",
            "cod_conta": conta, "cod_funcao": None, "funcao": None,
            "rotulo_conta": rotulo, "estagio": "Receitas Brutas Realizadas",
            "valor": valor, "esfera": "estado", "uf": "SP",
            "data_referencia": "2024-12-31",
        })
    # Uma linha de DESPESA no mesmo ente e ano: as views de receita não podem
    # enxergá-la, e as de despesa não podem enxergar a receita.
    linhas.append({
        "cod_ibge": "35", "ano": 2024, "periodo": "anual",
        "cod_conta": "10", "cod_funcao": "10", "funcao": "Saúde",
        "rotulo_conta": "Saúde", "estagio": "Despesas Empenhadas",
        "valor": 900.0, "esfera": "estado", "uf": "SP",
        "data_referencia": "2024-12-31",
    })
    armazem.mesclar("financas_ente", linhas, "teste")


def test_arrecadacao_nao_soma_conta_pai_com_as_filhas():
    _receita_hierarquica()
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT receita_total FROM vw_receita_total "
        " WHERE cod_ibge = '35' AND ano = 2024").fetchone()[0]
    assert total == 1200.0, (
        f"somou {total} em vez de 1200 — está contando pai e filha juntos")


def test_deducao_fica_de_fora_da_receita_bruta():
    """A coluna da fonte é BRUTA. Descontar o FUNDEB aqui produziria um número
    que não é nem bruto nem líquido, e nenhuma fonte confirmaria."""
    _receita_hierarquica()
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT receita_total FROM vw_receita_total WHERE cod_ibge = '35'"
    ).fetchone()[0]
    assert total == 1200.0, "a dedução de -80 não pode ter entrado"


def test_transferencias_somam_correntes_e_de_capital_sem_duplicar():
    _receita_hierarquica()
    con = vistas.conexao_leitura()
    valor = con.execute(
        "SELECT transferencia_recebida FROM vw_transferencia_recebida "
        " WHERE cod_ibge = '35' AND ano = 2024").fetchone()[0]
    # 700 (1.7) + 50 (2.4). As filhas 1.7.1.8 e 1.7.2.8 estão no nível 4 e
    # não podem entrar, senão as transferências passariam a receita inteira.
    assert valor == 750.0, f"somou {valor} em vez de 750"


def test_nivel_da_conta_sai_do_codigo():
    _receita_hierarquica()
    con = vistas.conexao_leitura()
    niveis = dict(con.execute(
        "SELECT cod_conta, nivel_receita FROM vw_receita_conta").fetchall())
    assert niveis["1.0.0.0.00.0.0"] == 1
    assert niveis["1.7.0.0.00.0.0"] == 2
    assert niveis["1.7.1.8.00.0.0"] == 4


def test_receita_e_despesa_nao_se_contaminam():
    """A mesma tabela guarda os dois. Se um filtro vazar, a despesa de São
    Paulo passa a incluir a arrecadação — e o número continua plausível."""
    _receita_hierarquica()
    con = vistas.conexao_leitura()
    despesa = con.execute(
        "SELECT despesa_total FROM vw_despesa_total WHERE cod_ibge = '35'"
    ).fetchone()[0]
    assert despesa == 900.0, "a receita entrou na despesa"

    contas_receita = con.execute(
        "SELECT COUNT(*) FROM vw_receita_conta WHERE cod_conta = '10'"
    ).fetchone()[0]
    assert contas_receita == 0, "a despesa entrou na receita"


def test_dependencia_de_transferencia_e_percentual_da_arrecadacao():
    _receita_hierarquica()
    armazem.mesclar("dim_ente", [{
        "cod_ibge": "35", "nivel": "estado", "nome": "São Paulo",
        "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste",
        "cod_regiao": "3"}], "teste")

    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT receita_total, transferencia_recebida, "
        "       dependencia_transferencia "
        "  FROM vw_mapa WHERE cod_ibge = '35' AND ano = 2024").fetchone()
    assert linha[0] == 1200.0
    assert linha[1] == 750.0
    assert abs(linha[2] - 62.5) < 0.01, "750/1200 = 62,5%"


def test_ente_sem_receita_coletada_fica_nulo_e_nunca_zero():
    """Zero é uma afirmação sobre o mundo; ausência é sobre o acervo."""
    _receita_hierarquica()
    armazem.mesclar("dim_ente", [{
        "cod_ibge": "33", "nivel": "estado", "nome": "Rio de Janeiro",
        "sigla_uf": "RJ", "cod_uf": "33", "regiao": "Sudeste",
        "cod_regiao": "3"}], "teste")

    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT receita_total, transferencia_recebida, "
        "       dependencia_transferencia "
        "  FROM vw_mapa WHERE cod_ibge = '33' AND ano = 2024").fetchone()
    assert linha == (None, None, None), f"deveria ser nulo, veio {linha}"


def test_rota_do_mapa_traz_as_mesmas_colunas_nos_dois_niveis():
    """Armadilha 2d ao contrário: um SELECT diferente por nível faria o campo
    existir no mapa do Brasil e sumir dentro de uma UF, sem erro nenhum."""
    _receita_hierarquica()
    armazem.mesclar("dim_ente", [
        {"cod_ibge": "35", "nivel": "estado", "nome": "São Paulo",
         "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste",
         "cod_regiao": "3"},
        {"cod_ibge": "3550308", "nivel": "municipio", "nome": "São Paulo",
         "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste",
         "cod_regiao": "3"},
    ], "teste")

    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    pais = cliente.get("/api/mapa", params={"ano": 2024}).json()
    uf = cliente.get("/api/mapa", params={"ano": 2024, "uf": "SP"}).json()

    assert pais["entes"] and uf["entes"]
    assert set(pais["entes"][0]) == set(uf["entes"][0]), (
        "o mapa do país e o da UF precisam devolver a mesma estrutura")
    for campo in ("receita_total", "transferencia_recebida",
                  "dependencia_transferencia", "populacao", "despesa_total"):
        assert campo in pais["entes"][0], f"falta {campo}"


def test_metricas_novas_sao_aceitas_pela_rota():
    _receita_hierarquica()
    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    for metrica in ("receita_total", "receita_per_capita",
                    "transferencia_recebida", "dependencia_transferencia"):
        resposta = cliente.get("/api/mapa",
                               params={"ano": 2024, "metrica": metrica})
        assert resposta.status_code == 200, f"{metrica} recusada"
        assert resposta.json()["metrica"] == metrica


# ============ o prefixo do código da conta (descoberto numa coleta real)
def _receita_com_prefixo():
    """Como o SICONFI devolve DE VERDADE: `RO1.0.0.0.00.0.0`.

    O Swagger não diz isso e eu supus que o código era só o número. Com o
    prefixo, o cálculo de nível dava 0 e o filtro `LIKE '1%'` nunca casava:
    373 mil linhas coletadas em uma hora não apareciam no painel, e a tela
    dizia "não coletado" — sem um erro sequer.
    """
    armazem.remover("financas_ente")
    linhas = []
    for conta, rotulo, valor in [
        ("RO1.0.0.0.00.0.0", "1.0.0.0.00.0.0 - Receitas Correntes", 1000.0),
        ("RO1.1.0.0.00.0.0", "1.1.0.0.00.0.0 - Impostos", 300.0),
        ("RO1.7.0.0.00.0.0", "1.7.0.0.00.0.0 - Transferências Correntes", 700.0),
        ("RO1.7.1.8.00.0.0", "1.7.1.8.00.0.0 - Transferências da União", 500.0),
        ("RO2.0.0.0.00.0.0", "2.0.0.0.00.0.0 - Receitas de Capital", 200.0),
        ("RO2.4.0.0.00.0.0", "2.4.0.0.00.0.0 - Transferências de Capital", 50.0),
    ]:
        linhas.append({
            "cod_ibge": "35", "ano": 2024, "periodo": "anual",
            "cod_conta": conta, "cod_funcao": None, "funcao": None,
            "rotulo_conta": rotulo, "estagio": "Receitas Brutas Realizadas",
            "valor": valor, "esfera": "estado", "uf": "SP",
            "data_referencia": "2024-12-31",
        })
    armazem.mesclar("financas_ente", linhas, "teste")


def test_prefixo_de_letras_no_codigo_nao_quebra_o_nivel():
    _receita_com_prefixo()
    con = vistas.conexao_leitura()
    niveis = dict(con.execute(
        "SELECT cod_conta, nivel_receita FROM vw_receita_conta").fetchall())
    assert niveis["RO1.0.0.0.00.0.0"] == 1
    assert niveis["RO1.7.0.0.00.0.0"] == 2
    assert niveis["RO1.7.1.8.00.0.0"] == 4


def test_arrecadacao_aparece_mesmo_com_prefixo():
    _receita_com_prefixo()
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT receita_total FROM vw_receita_total WHERE cod_ibge = '35'"
    ).fetchone()
    assert total is not None, "com o prefixo, a view devolvia VAZIO"
    assert total[0] == 1200.0


def test_transferencias_aparecem_mesmo_com_prefixo():
    _receita_com_prefixo()
    con = vistas.conexao_leitura()
    valor = con.execute(
        "SELECT transferencia_recebida FROM vw_transferencia_recebida "
        " WHERE cod_ibge = '35'").fetchone()
    assert valor is not None and valor[0] == 750.0


# ============ despesa: conta textual convivendo com contas de função
def _despesa_com_total_textual(com_funcoes: bool):
    armazem.remover("financas_ente")
    linhas = [{
        "cod_ibge": "29", "ano": 2025, "periodo": "anual",
        "cod_conta": "TotalGeralDaDespesa", "cod_funcao": None,
        "funcao": "Total Geral da Despesa",
        "rotulo_conta": "Total Geral da Despesa",
        "estagio": "Despesas Empenhadas", "valor": 1800.0,
        "esfera": "estado", "uf": "BA", "data_referencia": "2025-12-31",
    }]
    if com_funcoes:
        for conta, funcao, valor in [("RD10", "Saúde", 1000.0),
                                     ("RD12", "Educação", 800.0),
                                     ("RD10.301", "Atenção Básica", 600.0)]:
            linhas.append({
                "cod_ibge": "29", "ano": 2025, "periodo": "anual",
                "cod_conta": conta, "cod_funcao": conta[-2:],
                "funcao": funcao, "rotulo_conta": funcao,
                "estagio": "Despesas Empenhadas", "valor": valor,
                "esfera": "estado", "uf": "BA",
                "data_referencia": "2025-12-31",
            })
    armazem.mesclar("financas_ente", linhas, "teste")


def test_total_textual_sai_quando_ha_funcoes():
    """Somar "Total Geral da Despesa" junto com as funções conta o mesmo
    gasto duas vezes — o total viraria 3.600 em vez de 1.800."""
    _despesa_com_total_textual(com_funcoes=True)
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT despesa_total FROM vw_despesa_total WHERE cod_ibge = '29'"
    ).fetchone()[0]
    assert total == 1800.0, f"somou {total} — a linha de total entrou junto"


def test_total_textual_fica_quando_e_tudo_que_existe():
    """Descartar sempre a linha textual deixaria sem despesa nenhuma o ente
    que só entregou o total. A regra decide pelo dado, não por suposição."""
    _despesa_com_total_textual(com_funcoes=False)
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT despesa_total FROM vw_despesa_total WHERE cod_ibge = '29'"
    ).fetchone()
    assert total is not None, "o ente ficaria sem despesa nenhuma"
    assert total[0] == 1800.0
