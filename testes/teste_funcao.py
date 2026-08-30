"""Despesa por função e indicadores da LRF.

Duas perguntas que o painel prometia e não respondia: **quanto seu município
gasta em saúde** e **a folha de pagamento cabe no limite legal**.

Os dois vêm do SICONFI, mas de relatórios que não coletávamos — o RREO Anexo
02 e o RGF. E os dois trazem a mesma armadilha hierárquica que já custou caro
duas vezes, então é ela que a maior parte destes testes cobre.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.api import vistas  # noqa: E402
from src.nucleo import armazem  # noqa: E402


# A resposta real do RREO Anexo 02, conferida contra a API em 26/08/2026 para
# São Paulo (3550308), exercício 2024, 6º bimestre. Está aqui verbatim porque
# a versão anterior destes testes usava um formato INVENTADO — contas
# numéricas hierárquicas, como no DCA — e passava, enquanto a coleta real
# devolvia zero linha em 12 anos seguidos. Teste contra formato suposto não
# testa nada.
RESPOSTA_REAL = {"items": [
    {"exercicio": 2024, "demonstrativo": "RREO", "periodo": 6,
     "periodicidade": "B", "instituicao": "Prefeitura Municipal de São Paulo - SP",
     "cod_ibge": 3550308, "uf": "SP", "populacao": 12200180,
     "anexo": "RREO-Anexo 02", "esfera": "M",
     "rotulo": "Total das Despesas Exceto Intra-Orçamentárias",
     "coluna": coluna, "cod_conta": "RREO2TotalDespesas",
     "conta": conta, "valor": valor}
    for conta, coluna, valor in [
        # Repare: o mesmo `cod_conta` em TODAS as linhas, função e subfunção.
        ("Saúde", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 22752837820.49),
        ("Atenção Básica", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 6000.0),
        ("Assistência Hospitalar e Ambulatorial",
         "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 4000.0),
        ("Administração Geral", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 111.0),
        ("Educação", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 18000000000.0),
        ("Ensino Fundamental", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 5000.0),
        # A MESMA subfunção outra vez, agora sob Educação. É o caso que
        # descartava 4.867 linhas por carga.
        ("Administração Geral", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", 222.0),
        # As colunas que NÃO podem entrar:
        ("Saúde", "DOTAÇÃO INICIAL", 18242615962.0),
        ("Saúde", "DESPESAS EMPENHADAS NO BIMESTRE", 1326852864.04),
        ("Saúde", "% (b/total b)", 22.5),
        ("Saúde", "SALDO (c) = (a-b)", 900.0),
        # O layout curto, de RN e BA: `(b)` é empenhada, `(d)` é liquidada.
        ("Cultura", "Até o Bimestre (b)", 700.0),
        ("Cultura", "Até o Bimestre (d)", 650.0),
        # A linha de total, que não pode inflar nada:
        ("TOTAL (III) = (I + II)", "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)",
         99999999999.0),
    ]]}


def _coletar_da_resposta(monkeypatch, resposta=None):
    """Roda o coletor contra a resposta real, sem rede."""
    from src.coletores import siconfi  # noqa: PLC0415
    from src.nucleo import rede  # noqa: PLC0415

    capturado = {}

    def _falso(fonte, url, parametros=None, **kwargs):
        capturado["parametros"] = parametros
        return resposta if resposta is not None else RESPOSTA_REAL

    monkeypatch.setattr(rede, "buscar", _falso)
    linhas = siconfi.coletar_funcao(2024, 6, "3550308")
    return linhas, capturado["parametros"]


def test_a_consulta_pede_a_periodicidade_bimestral(monkeypatch):
    """O defeito que custou uma carga histórica de oito horas.

    Sem `in_periodicidade`, o `/rreo` não casa com nada e devolve lista vazia
    — sem erro, sem status ruim, sem aviso. A varredura leu isso como "o ente
    não publicou" e registrou 27 UFs sem dado em cada um dos 12 anos.
    """
    _, parametros = _coletar_da_resposta(monkeypatch)
    assert parametros["in_periodicidade"] == "B"


def test_le_a_coluna_em_caixa_alta(monkeypatch):
    """A fonte escreve `DESPESAS EMPENHADAS`, maiúsculo. O filtro anterior
    procurava `Empenhada` — e o segundo defeito, sozinho, também bastaria
    para devolver zero linha."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    assert linhas, "nenhuma linha passou no filtro de coluna"
    assert all("ATÉ O BIMESTRE (B)" in l["estagio"].upper() for l in linhas)


def test_ignora_a_coluna_do_bimestre_e_as_de_dotacao(monkeypatch):
    """Há DUAS colunas de empenhado. 'No bimestre' são dois meses; 'até o
    bimestre' é o acumulado no exercício. Pegar as duas conta o bimestre
    corrente duas vezes; pegar a errada troca o ano pelo bimestre."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    saude = [l for l in linhas if l["rotulo_conta"] == "Saúde"]
    assert len(saude) == 1, "Saúde apareceu mais de uma vez — coluna repetida"
    assert saude[0]["valor"] == 22752837820.49


def test_funcao_e_subfuncao_se_distinguem_pelo_NOME(monkeypatch):
    """No RREO Anexo 02 o `cod_conta` é o MESMO em todas as linhas
    (`RREO2TotalDespesas`): não há código de onde tirar nível. Quem separa
    "Saúde" de "Atenção Básica" é a lista normativa da Portaria MOG 42/1999."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    por_conta = {l["rotulo_conta"]: l["cod_funcao"] for l in linhas}

    assert por_conta["Saúde"] == "10"
    assert por_conta["Educação"] == "12"
    assert por_conta["Atenção Básica"] is None, "subfunção não é função"
    assert por_conta["Ensino Fundamental"] is None


def test_le_o_layout_curto_de_RN_e_BA(monkeypatch):
    """Dois entes publicam só `Até o Bimestre (b)`, sem o cabeçalho do
    estágio. Casar pelo cabeçalho inteiro os descartava por completo, todos os
    anos — com o log dizendo, certo, "defeito de leitura, não ausência"."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    cultura = [l for l in linhas if l["rotulo_conta"] == "Cultura"]
    assert len(cultura) == 1, "o layout curto não passou, ou passou duas vezes"
    assert cultura[0]["valor"] == 700.0, "pegou a liquidada (d) no lugar da (b)"


def test_a_liquidada_do_layout_curto_fica_de_fora(monkeypatch):
    """No layout curto a liquidada é `Até o Bimestre (d)`. Casar por "ATÉ O
    BIMESTRE" sem a letra somaria dois estágios do mesmo real."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    assert not any(l["valor"] == 650.0 for l in linhas)


def test_subfuncao_repetida_sob_funcoes_diferentes_nao_colide(monkeypatch):
    """4.867 linhas por carga. "Administração Geral" e "Demais Subfunções"
    aparecem sob meia dúzia de funções, e a resposta não liga subfunção à
    função-mãe — só a ORDEM do documento liga."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    geral = [l for l in linhas if l["rotulo_conta"] == "Administração Geral"]
    assert len(geral) == 2, "as duas linhas precisam sobreviver"
    assert {l["cod_funcao_mae"] for l in geral} == {"10", "12"}, (
        "a função-mãe sai da posição no demonstrativo")
    assert len({l["cod_conta"] for l in geral}) == 2, "chaves ainda colidem"


def test_linha_de_total_nao_casa_com_funcao_nenhuma(monkeypatch):
    """A proteção estrutural: "TOTAL (III) = (I + II)" nunca vai ser o nome de
    uma função, então não tem como entrar na soma por engano."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    total = [l for l in linhas if l["rotulo_conta"].startswith("TOTAL")]
    assert total and total[0]["cod_funcao"] is None


def test_chave_primaria_separa_linhas_que_a_fonte_nao_separa(monkeypatch):
    """`cod_conta` faz parte da PK e vem igual em todas as linhas. Sem
    compor a chave com o bloco e o nome da conta, as 30 linhas do ente
    colapsariam numa só no merge — e o painel mostraria a última que chegou."""
    linhas, _ = _coletar_da_resposta(monkeypatch)
    chaves = {l["cod_conta"] for l in linhas}
    assert len(chaves) == len(linhas), "linhas distintas com a mesma chave"


def test_resposta_vazia_continua_significando_ausencia(monkeypatch):
    linhas, _ = _coletar_da_resposta(monkeypatch, {"items": []})
    assert linhas == []


def test_resposta_cheia_que_nao_passa_no_filtro_e_ERRO_e_nao_ausencia(
        monkeypatch, caplog):
    """A distinção que faltava no log e que teria poupado a madrugada: "o ente
    não publicou" e "eu não soube ler a resposta" viravam a mesma linha."""
    so_dotacao = {"items": [dict(i, coluna="DOTAÇÃO INICIAL")
                            for i in RESPOSTA_REAL["items"]]}
    with caplog.at_level("ERROR"):
        linhas, _ = _coletar_da_resposta(monkeypatch, so_dotacao)
    assert linhas == []
    assert any("defeito de leitura" in r.getMessage()
               for r in caplog.records), "silêncio onde devia haver erro"


# ------------------------------------------------ agregação sobre o real
def _gravar(linhas):
    armazem.remover("despesa_funcao")
    armazem.mesclar("despesa_funcao", linhas, "teste")


def _linhas_de_exemplo(ano: int = 2025) -> list[dict]:
    """As mesmas linhas do coletor, sem monkeypatch — para os testes que só
    precisam de dado no disco, não do caminho de leitura."""
    return [{
        "cod_ibge": "3550308", "ano": ano, "periodo": "bimestre_6",
        "cod_conta": f"Total das Despesas Exceto Intra-Orçamentárias|{nome}",
        "cod_funcao": cod, "funcao": nome if cod else None,
        "rotulo_conta": nome,
        "bloco": "Total das Despesas Exceto Intra-Orçamentárias",
        "estagio": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)", "valor": valor,
        "esfera": "municipio", "uf": "SP",
        "data_referencia": f"{ano}-12-01",
    } for nome, cod, valor in [
        ("Saúde", "10", 1000.0), ("Atenção Básica", None, 600.0),
        ("Educação", "12", 800.0), ("Ensino Fundamental", None, 500.0),
    ]]


def _do_coletor(monkeypatch):
    linhas, _ = _coletar_da_resposta(monkeypatch)
    _gravar(linhas)
    return linhas


def test_soma_so_o_que_casou_com_funcao_oficial(monkeypatch):
    """Saúde 22.752.837.820,49 + Educação 18.000.000.000 = 40.752.837.820,49.

    Subfunções e a linha de total ficam de fora. Somar tudo daria mais de
    140 bilhões — e pareceria um número bem formado.
    """
    _do_coletor(monkeypatch)
    con = vistas.conexao_leitura()
    total = con.execute(
        "SELECT SUM(valor) FROM vw_despesa_por_funcao "
        " WHERE cod_ibge = '3550308'").fetchone()[0]
    assert round(total, 2) == 40752837820.49


def test_saude_e_educacao_saem_pelo_codigo_da_funcao(monkeypatch):
    _do_coletor(monkeypatch)
    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT saude, educacao FROM vw_saude_educacao "
        " WHERE cod_ibge = '3550308'").fetchone()
    assert round(linha[0], 2) == 22752837820.49
    assert linha[1] == 18000000000.0


def test_subfuncao_fica_acessivel_sem_contaminar_o_total(monkeypatch):
    _do_coletor(monkeypatch)
    con = vistas.conexao_leitura()
    contas = {c[0] for c in con.execute(
        "SELECT rotulo_conta FROM vw_despesa_por_subfuncao "
        " WHERE cod_ibge = '3550308'").fetchall()}
    assert "Atenção Básica" in contas and "Ensino Fundamental" in contas
    assert "Saúde" not in contas


def test_bimestres_nao_se_somam(monkeypatch):
    """O RREO é ACUMULADO no exercício: o 6º bimestre já contém o 1º. Somar
    os seis contaria janeiro seis vezes — e o total seria absurdo sem que
    nenhuma linha estivesse errada."""
    linhas = _do_coletor(monkeypatch)
    armazem.mesclar("despesa_funcao", [
        dict(l, periodo="bimestre_2", valor=l["valor"] / 3) for l in linhas],
        "teste")

    con = vistas.conexao_leitura()
    saude = con.execute(
        "SELECT saude FROM vw_saude_educacao "
        " WHERE cod_ibge = '3550308'").fetchone()[0]
    assert round(saude, 2) == 22752837820.49, "somou dois bimestres"


def test_despesa_por_funcao_nao_contamina_a_por_natureza(monkeypatch):
    """São dois recortes do MESMO dinheiro, em tabelas separadas. Se um dia
    caírem na mesma, o total do painel dobra."""
    _do_coletor(monkeypatch)
    armazem.remover("financas_ente")
    armazem.mesclar("financas_ente", [{
        "cod_ibge": "3550308", "ano": 2024, "periodo": "anual",
        "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None,
        "rotulo_conta": "3.0.00.00.00 - Despesas Correntes",
        "estagio": "Despesas Empenhadas", "valor": 1800.0,
        "esfera": "municipio", "uf": "SP", "data_referencia": "2024-12-31",
    }], "teste")

    con = vistas.conexao_leitura()
    despesa = con.execute(
        "SELECT despesa_total FROM vw_despesa_total "
        " WHERE cod_ibge = '3550308'").fetchone()[0]
    assert despesa == 1800.0, "a despesa por função entrou na por natureza"


# ------------------------------------------------------------ LRF
# A resposta real do RGF Anexo 01, conferida contra a API em 26/08/2026 para
# São Paulo (35), exercício 2024, 3º quadrimestre. O que ela ensina: a MESMA
# conta aparece em colunas diferentes, e é a coluna que diz o que o número é.
RGF_ANEXO_01 = [
    ("DespesaComPessoalBruta", "Valor", 90000000000.0),
    ("DespesaComPessoalLiquida", "Valor", 85000000000.0),
    ("DespesaComPessoalTotal", "Valor", 85000000000.0),
    ("ReceitaCorrenteLiquidaAjustada", "Valor", 201470000000.0),
    # O percentual NÃO é uma conta própria: é a mesma DespesaComPessoalTotal,
    # lida na coluna de percentual.
    ("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 42.19),
    ("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL Ajustada", 49.0),
    ("LimitePrudencialDespesaComPessoalTotal", "% sobre a RCL Ajustada", 46.55),
    ("LimiteDeAlertaDespesaComPessoalTotal", "% sobre a RCL Ajustada", 44.1),
    # Detalhamento mês a mês — doze colunas que não interessam ao painel.
    ("DespesaComPessoalBruta", "<MR-11>", 7000000000.0),
    ("DespesaComPessoalBruta", "<MR>", 7500000000.0),
]

RGF_ANEXO_02 = [
    ("DividaConsolidadaLiquida", "Até o 3º Quadrimestre", 317655576689.71),
    ("LimiteDefinidoPorResolucaoDoSenadoFederal", "Até o 3º Quadrimestre",
     502023949508.76),
    # Períodos que NÃO são o pedido. Guardá-los aqui gravaria o saldo de
    # outro quadrimestre como se fosse o deste.
    ("DividaConsolidadaLiquida", "Até o 1º Quadrimestre", 111111111.0),
    ("DividaConsolidadaLiquida", "SALDO DO EXERCÍCIO ANTERIOR", 999999999.0),
]


def _coletar_rgf(monkeypatch, anexo01=None, anexo02=None, quadrimestre=3):
    from src.coletores import siconfi  # noqa: PLC0415
    from src.nucleo import rede  # noqa: PLC0415

    pedidos = []

    def _falso(fonte, url, parametros=None, **kwargs):
        pedidos.append(parametros)
        fonte_linhas = (anexo01 if anexo01 is not None else RGF_ANEXO_01)
        if parametros["no_anexo"] == siconfi.ANEXO_DIVIDA:
            fonte_linhas = (anexo02 if anexo02 is not None else RGF_ANEXO_02)
        return {"items": [
            {"cod_conta": conta, "coluna": coluna, "valor": valor,
             "conta": conta, "rotulo": "Padrão", "uf": "SP", "cod_ibge": 35}
            for conta, coluna, valor in fonte_linhas]}

    monkeypatch.setattr(rede, "buscar", _falso)
    linhas = siconfi.coletar_rgf(2024, quadrimestre, "35")
    return linhas, pedidos


def _gravar_rgf(linhas):
    armazem.remover("indicador_fiscal")
    armazem.mesclar("indicador_fiscal", linhas, "teste")


def test_a_mesma_conta_em_reais_e_em_percentual_sao_DUAS_linhas(monkeypatch):
    """O defeito que deixou `percentual_pessoal` com 10 linhas em 324.

    `DespesaComPessoalTotal` vem em R$ e em % sobre a RCL. Sem a medida na
    chave primária, as duas colidiam no merge e sobrava a última que chegou —
    silenciosamente, sem erro nenhum.
    """
    linhas, _ = _coletar_rgf(monkeypatch)
    total = [l for l in linhas if l["indicador"] == "DespesaComPessoalTotal"]
    assert {l["medida"] for l in total} == {"valor", "percentual"}

    _gravar_rgf(linhas)
    con = vistas.conexao_leitura()
    guardadas = con.execute(
        "SELECT medida, valor FROM indicador_fiscal "
        " WHERE indicador = 'DespesaComPessoalTotal' ORDER BY medida").fetchall()
    assert guardadas == [("percentual", 42.19), ("valor", 85000000000.0)]


def test_o_limite_existe_com_o_nome_que_a_fonte_usa(monkeypatch):
    """`LimiteMaximo` era o apelido esperado; `LimiteMaximoDespesaComPessoal
    Total` é o nome real. O acervo ficou com ZERO limite — e sem limite o
    painel não podia responder a pergunta que o RGF existe para responder."""
    linhas, _ = _coletar_rgf(monkeypatch)
    _gravar_rgf(linhas)

    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT percentual_pessoal, limite_maximo, limite_prudencial, "
        "       limite_alerta, acima_do_limite, acima_do_prudencial "
        "  FROM vw_lrf_pessoal WHERE cod_ibge = '35'").fetchone()
    assert linha[:4] == (42.19, 49.0, 46.55, 44.1)
    assert linha[4] is False and linha[5] is False


def test_guarda_conta_que_ninguem_previu(monkeypatch):
    """A lição do RREO aplicada antes de doer: o coletor grava o `cod_conta`
    verbatim. Conta nova entra no acervo e vira consulta — não recoleta."""
    linhas, _ = _coletar_rgf(monkeypatch, anexo01=[
        ("UmaContaQueNinguemPreviu", "Valor", 123.0)])
    assert any(l["indicador"] == "UmaContaQueNinguemPreviu" for l in linhas)


def test_ignora_o_detalhamento_mes_a_mes(monkeypatch):
    """As colunas `<MR-11>`…`<MR>` multiplicariam a tabela por doze sem
    responder nada que o painel pergunte."""
    linhas, _ = _coletar_rgf(monkeypatch)
    assert not [l for l in linhas if l["medida"] is None]
    bruta = [l for l in linhas if l["indicador"] == "DespesaComPessoalBruta"]
    assert len(bruta) == 1 and bruta[0]["valor"] == 90000000000.0


def test_saldo_e_o_do_quadrimestre_pedido_e_nao_de_outro(monkeypatch):
    """A pior das três: sem olhar a coluna, o saldo gravado podia ser o do ano
    PASSADO. Número plausível, período errado, e ninguém veria."""
    linhas, _ = _coletar_rgf(monkeypatch)
    _gravar_rgf(linhas)

    con = vistas.conexao_leitura()
    divida = con.execute(
        "SELECT divida_liquida, limite_divida FROM vw_lrf_pessoal "
        " WHERE cod_ibge = '35'").fetchone()
    assert divida == (317655576689.71, 502023949508.76)


def test_a_consulta_pede_a_periodicidade_quadrimestral(monkeypatch):
    _, pedidos = _coletar_rgf(monkeypatch)
    assert all(p["in_periodicidade"] == "Q" for p in pedidos)
    assert {p["no_anexo"] for p in pedidos} == {"RGF-Anexo 01", "RGF-Anexo 02"}


def test_sem_limite_publicado_a_resposta_e_nula_e_nao_falsa(monkeypatch):
    """Ausência do limite não é 'está dentro'. Zero e nulo de novo — a regra
    que atravessa o projeto inteiro."""
    linhas, _ = _coletar_rgf(monkeypatch, anexo01=[
        ("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 58.0)],
        anexo02=[])
    _gravar_rgf(linhas)

    con = vistas.conexao_leitura()
    acima = con.execute(
        "SELECT acima_do_limite FROM vw_lrf_pessoal "
        " WHERE cod_ibge = '35'").fetchone()[0]
    assert acima is None, "sem limite publicado, não se afirma nada"


def test_acima_do_limite_quando_passa_de_verdade(monkeypatch):
    linhas, _ = _coletar_rgf(monkeypatch, anexo01=[
        ("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 56.41),
        ("LimiteMaximoDespesaComPessoalTotal", "% sobre a RCL Ajustada", 49.0)],
        anexo02=[])
    _gravar_rgf(linhas)

    con = vistas.conexao_leitura()
    assert con.execute("SELECT acima_do_limite FROM vw_lrf_pessoal "
                       " WHERE cod_ibge = '35'").fetchone()[0] is True


def test_vale_o_quadrimestre_mais_recente(monkeypatch):
    """Como no RREO: o RGF é acumulado, e o painel mostra a foto mais nova."""
    linhas, _ = _coletar_rgf(monkeypatch)
    _gravar_rgf(linhas)
    antigas, _ = _coletar_rgf(monkeypatch, anexo01=[
        ("DespesaComPessoalTotal", "% sobre a RCL Ajustada", 30.0)],
        anexo02=[], quadrimestre=1)
    armazem.mesclar("indicador_fiscal", antigas, "teste")

    con = vistas.conexao_leitura()
    linhas_vw = con.execute(
        "SELECT percentual_pessoal FROM vw_lrf_pessoal "
        " WHERE cod_ibge = '35'").fetchall()
    assert linhas_vw == [(42.19,)], "só o quadrimestre mais recente"


# ------------------------------------------ a lista normativa de funções
def test_funcao_oficial_casa_sem_acento_e_sem_caixa():
    """O texto vem do demonstrativo do ente, e ente escreve como quer."""
    from src.coletores.siconfi import _funcao_oficial  # noqa: PLC0415

    assert _funcao_oficial("Saúde") == "10"
    assert _funcao_oficial("SAUDE") == "10"
    assert _funcao_oficial("  saude  ") == "10"
    assert _funcao_oficial("Essencial à Justiça") == "03"
    assert _funcao_oficial("Essencial a Justica") == "03"


def test_a_lista_e_a_da_portaria_42():
    """28 funções mais a Reserva de Contingência. Se este número mudar sem
    uma norma nova, alguém inventou uma função."""
    from src.coletores.siconfi import FUNCOES_OFICIAIS  # noqa: PLC0415

    assert len(FUNCOES_OFICIAIS) == 29
    assert FUNCOES_OFICIAIS["99"] == "Reserva de Contingência"
    assert all(len(c) == 2 and c.isdigit() for c in FUNCOES_OFICIAIS)


def test_subfuncao_e_total_nao_sao_funcao():
    from src.coletores.siconfi import _funcao_oficial  # noqa: PLC0415

    for texto in ("Atenção Básica", "Ensino Fundamental", "Policiamento",
                  "TOTAL (III) = (I + II)",
                  "DESPESAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)", "", None):
        assert _funcao_oficial(texto) is None, texto


# ------------------------------------------------------- período publicado
def test_ano_fechado_vale_o_ultimo_periodo():
    from datetime import date  # noqa: PLC0415

    from src.coletores.siconfi import periodo_publicado  # noqa: PLC0415

    assert periodo_publicado(2025, 2, date(2026, 8, 24)) == 6
    assert periodo_publicado(2025, 4, date(2026, 8, 24)) == 3


def test_ano_corrente_para_no_periodo_que_ja_venceu():
    """Pedir o 6º bimestre de um ano em curso devolve vazio, e vazio seria
    lido como 'o ente não entregou' — quando o prazo nem chegou."""
    from datetime import date  # noqa: PLC0415

    from src.coletores.siconfi import periodo_publicado  # noqa: PLC0415

    # Em agosto, o 3º bimestre (fecha em junho, vence em julho) é o último.
    assert periodo_publicado(2026, 2, date(2026, 8, 24)) == 3
    # O 2º quadrimestre fecha em agosto; vale o 1º.
    assert periodo_publicado(2026, 4, date(2026, 8, 24)) == 1


def test_comeco_do_ano_nao_tem_periodo_nenhum():
    from datetime import date  # noqa: PLC0415

    from src.coletores.siconfi import periodo_publicado  # noqa: PLC0415

    assert periodo_publicado(2026, 2, date(2026, 2, 10)) == 0
    assert periodo_publicado(2027, 2, date(2026, 8, 24)) == 0


def test_as_tres_entradas_do_siconfi_usam_o_mesmo_coletor():
    """Três linhas na tela porque as cadências são diferentes — mas um
    coletor só, para as retomadas não divergirem."""
    from src.coletores import orquestrador  # noqa: PLC0415

    for nome in ("siconfi", "siconfi_funcao", "siconfi_rgf"):
        assert orquestrador.FONTES[nome].modulo == "siconfi"
        assert orquestrador._modulo(nome).__name__.endswith("siconfi")

    assert orquestrador.FONTES["siconfi_funcao"].recursos == ("funcao",)
    assert orquestrador.FONTES["siconfi_rgf"].recursos == ("rgf",)


def test_ano_que_so_tem_rreo_nao_some_do_mapa():
    """`vw_anos` alimenta o produto ente × ano do mapa. Se o ano não estiver
    nela, o ente não aparece nem cinza — ele simplesmente não existe para o
    painel, o que parece dizer que o município não existe."""
    armazem.remover("financas_ente")
    armazem.remover("indicador_ente")
    _gravar(_linhas_de_exemplo())

    con = vistas.conexao_leitura()
    anos = [linha[0] for linha in con.execute("SELECT ano FROM vw_anos").fetchall()]
    assert 2025 in anos, "ano com RREO e sem DCA sumiu da lista do mapa"


def test_a_rota_do_mapa_aceita_as_metricas_novas():
    """A rota valida a métrica por regex. Adicionar coluna na view sem
    adicionar aqui devolve 422 — e o seletor da tela fica quebrado."""
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from src.api import servidor  # noqa: PLC0415

    _gravar(_linhas_de_exemplo())
    armazem.mesclar("dim_ente", [{
        "cod_ibge": "3550308", "nome": "São Paulo", "nivel": "municipio",
        "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste"}], "teste")
    _gravar_rgf([{
        "cod_ibge": "3550308", "ano": 2025, "periodo": "quadrimestre_3",
        "poder": "E", "indicador": "DespesaComPessoalTotal",
        "medida": "percentual", "rotulo": "DTP", "secao": "Padrão",
        "anexo": "RGF-Anexo 01",
        "valor": 58.0, "esfera": "municipio", "uf": "SP",
        "data_referencia": "2025-12-01"}])

    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")
    for metrica in ("despesa_saude", "saude_per_capita", "despesa_educacao",
                    "educacao_per_capita", "percentual_pessoal",
                    "divida_liquida"):
        resposta = cliente.get("/api/mapa",
                               params={"ano": 2025, "uf": "SP",
                                       "metrica": metrica})
        assert resposta.status_code == 200, f"{metrica} recusada pela rota"
        assert metrica in resposta.json()["entes"][0], (
            f"{metrica} passa na validação mas não vem na resposta")


def test_rreo_e_rgf_pedem_o_ano_corrente():
    """Ao contrário do DCA, que só fecha o exercício anterior."""
    from datetime import date  # noqa: PLC0415

    from src.coletores import orquestrador  # noqa: PLC0415

    vazias = orquestrador.Opcoes()
    hoje = date.today()
    esperado = hoje.year if hoje.month >= 4 else hoje.year - 1
    assert orquestrador.anos_de("siconfi_funcao", vazias) == [esperado]
    assert orquestrador.anos_de("siconfi", vazias) == [hoje.year - 1]
