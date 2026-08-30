"""Operações de crédito — SADIPEM.

O risco aqui não é aritmético, é de **rótulo**. O dado é o valor de um
PEDIDO; chamá-lo de "dívida" seria errado três vezes, e o número resultante
pareceria perfeitamente plausível. Estes testes cravam a separação entre
pedido, deferido e contratado.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.api import vistas  # noqa: E402
from src.nucleo import armazem  # noqa: E402
from src.nucleo.valores import ano_de, data_br  # noqa: E402


def _pleitos():
    armazem.remover("operacao_credito")
    base = {
        "cod_ibge": "3502804", "uf": "SP", "tipo_interessado": "Município",
        "interessado": "Araçatuba", "num_processo": "17944.000617/2002-48",
        "tipo_operacao": "Operação contratual interna",
        "tipo_credor": "Instituição Financeira Nacional",
        "moeda": "Real", "data_protocolo": "2017-08-14",
        "data_status": "2019-03-14", "ano": 2017,
        "data_referencia": "2017-08-14",
    }
    armazem.mesclar("operacao_credito", [
        {**base, "id_pleito": 1, "num_pvl": "PVL02.000001/2017-60",
         "status": "Deferido", "contratado": 1, "valor": 1000.0,
         "finalidade": "Aquisição de máquinas, equipamentos e veículos",
         "credor": "Banco do Brasil"},
        {**base, "id_pleito": 2, "num_pvl": "PVL02.000002/2017-60",
         "status": "Deferido", "contratado": 0, "valor": 500.0,
         "finalidade": "Infraestrutura", "credor": "Caixa"},
        {**base, "id_pleito": 3, "num_pvl": "PVL02.000003/2017-60",
         "status": "Indeferido", "contratado": 0, "valor": 9000.0,
         "finalidade": "Infraestrutura", "credor": "Caixa"},
    ], "teste")


def test_pedido_negado_nao_entra_no_deferido():
    """R$ 9.000 indeferidos nunca viraram dinheiro. Somá-los produziria um
    número dez vezes maior, e perfeitamente plausível."""
    _pleitos()
    con = vistas.conexao_leitura()
    linha = con.execute(
        "SELECT valor_pleiteado, valor_deferido, valor_contratado, pleitos "
        "  FROM vw_credito_ente WHERE cod_ibge = '3502804' AND ano = 2017"
    ).fetchone()

    assert linha[0] == 10500.0, "pleiteado é tudo que foi protocolado"
    assert linha[1] == 1500.0, "deferido exclui o indeferido"
    assert linha[2] == 1000.0, "contratado exclui o que foi autorizado e não usado"
    assert linha[3] == 3


def test_as_tres_medidas_sao_diferentes_e_continuam_separadas():
    """Se um dia virarem uma coluna só, a diferença entre autorizar e
    contratar — que é a informação — desaparece."""
    _pleitos()
    con = vistas.conexao_leitura()
    pleiteado, deferido, contratado = con.execute(
        "SELECT valor_pleiteado, valor_deferido, valor_contratado "
        "  FROM vw_credito_ente WHERE cod_ibge = '3502804'").fetchone()
    assert pleiteado > deferido > contratado


def test_finalidade_so_lista_o_que_foi_deferido():
    _pleitos()
    con = vistas.conexao_leitura()
    linhas = con.execute(
        "SELECT finalidade, valor FROM vw_credito_finalidade "
        " WHERE cod_ibge = '3502804' ORDER BY valor DESC").fetchall()
    assert dict(linhas) == {
        "Aquisição de máquinas, equipamentos e veículos": 1000.0,
        "Infraestrutura": 500.0,
    }, "o pedido indeferido de 9.000 não pode aparecer como finalidade"


def test_recoletar_nao_duplica_pleito():
    _pleitos()
    _pleitos()
    con = vistas.conexao_leitura()
    pleitos = con.execute(
        "SELECT pleitos FROM vw_credito_ente WHERE cod_ibge = '3502804'"
    ).fetchone()[0]
    assert pleitos == 3


def test_mudanca_de_status_substitui_a_linha():
    """Um pleito em análise que é deferido depois não vira duas linhas: a PK é
    o id_pleito, e o merge reescreve."""
    _pleitos()
    armazem.mesclar("operacao_credito", [{
        "id_pleito": 3, "cod_ibge": "3502804", "uf": "SP",
        "tipo_interessado": "Município", "interessado": "Araçatuba",
        "num_pvl": "PVL02.000003/2017-60",
        "num_processo": "17944.000617/2002-48",
        "status": "Deferido", "tipo_operacao": "Operação contratual interna",
        "finalidade": "Infraestrutura",
        "tipo_credor": "Instituição Financeira Nacional", "credor": "Caixa",
        "moeda": "Real", "valor": 9000.0, "contratado": 1,
        "data_protocolo": "2017-08-14", "data_status": "2020-01-10",
        "ano": 2017, "data_referencia": "2017-08-14",
    }], "teste")

    con = vistas.conexao_leitura()
    pleitos, deferido = con.execute(
        "SELECT pleitos, valor_deferido FROM vw_credito_ente "
        " WHERE cod_ibge = '3502804'").fetchone()
    assert pleitos == 3, "continuam três pleitos, não quatro"
    assert deferido == 10500.0, "o pleito reanalisado passou a contar"


# ------------------------------------------------------------- datas
def test_ano_de_dois_digitos_vira_o_seculo_certo():
    """O MESMO registro traz "14/08/02" e "14/03/2019". Dois dígitos é
    ambíguo, e a regra de corte precisa ser explícita e testada."""
    assert data_br("14/08/02") == "2002-08-14"
    assert data_br("14/03/2019") == "2019-03-14"
    assert data_br("31/12/98") == "1998-12-31"
    assert ano_de("14/08/02") == 2002


def test_data_irreconhecivel_vira_nulo_e_nao_chute():
    """Data errada é pior que data ausente: entra nos filtros como verdade."""
    for lixo in ("", None, "abc", "2019", "32/13/2019", "14-08"):
        assert data_br(lixo) is None, f"{lixo!r} deveria virar None"


def test_dia_e_mes_nao_sao_trocados():
    """dd/mm, nunca mm/dd. 08/12 é dezembro, não agosto."""
    assert data_br("08/12/2020") == "2020-12-08"


def test_data_iso_do_sadipem_e_reconhecida():
    """A documentação mostra "14/08/02"; a API devolveu ISO. A versão
    anterior lia "2017-08-14" como DIA 2017, reprovava na validação e
    devolvia None — 84 de 84 pleitos do Acre ficaram sem ano."""
    assert data_br("2017-08-14T00:00:00Z") == "2017-08-14"
    assert data_br("2014-05-31T23:00:03Z") == "2014-05-31"
    assert data_br("2017-08-14") == "2017-08-14"
    assert ano_de("2017-08-14T00:00:00Z") == 2017

    # E o formato brasileiro continua valendo — os dois convivem na fonte.
    assert data_br("14/08/02") == "2002-08-14"


def test_particao_nula_nao_chega_ao_disco():
    """Sem ano, a linha não tem partição. Antes, o valor nulo virava o texto
    `<NA>` no caminho e o Windows recusava com WinError 123 — uma mensagem que
    não menciona tabela, coluna nem partição, e que derrubou o coletor
    inteiro."""
    from src.nucleo import armazem as arm  # noqa: PLC0415

    arm.remover("operacao_credito")
    base = {
        "cod_ibge": "3502804", "uf": "SP", "tipo_interessado": "Município",
        "interessado": "Araçatuba", "num_pvl": "PVL", "num_processo": "1",
        "status": "Deferido", "tipo_operacao": "interna",
        "finalidade": "Infraestrutura", "tipo_credor": "IFN",
        "credor": "Caixa", "moeda": "Real", "valor": 100.0, "contratado": 1,
        "data_protocolo": None, "data_status": None,
        "data_referencia": None,
    }
    total = arm.mesclar("operacao_credito", [
        {**base, "id_pleito": 1, "ano": 2020, "data_protocolo": "2020-01-01",
         "data_referencia": "2020-01-01"},
        {**base, "id_pleito": 2, "ano": None},     # sem ano: descartada
    ], "teste")

    assert total["inseridos"] == 1, "a linha sem partição não pode ser gravada"

    con = vistas.conexao_leitura()
    ids = [r[0] for r in con.execute(
        "SELECT id_pleito FROM operacao_credito ORDER BY id_pleito").fetchall()]
    assert ids == [1]


def test_lote_inteiro_sem_particao_nao_estoura():
    """O caso do Acre: 84 de 84 sem data. Precisa registrar erro e seguir, não
    derrubar a coleta das outras 26 UFs."""
    from src.nucleo import armazem as arm  # noqa: PLC0415

    arm.remover("operacao_credito")
    total = arm.mesclar("operacao_credito", [{
        "id_pleito": 9, "cod_ibge": "1200013", "uf": "AC",
        "tipo_interessado": "Município", "interessado": "Acrelândia",
        "num_pvl": "PVL", "num_processo": "1", "status": "Deferido",
        "tipo_operacao": "interna", "finalidade": "x", "tipo_credor": "IFN",
        "credor": "BB", "moeda": "Real", "valor": 1.0, "contratado": 0,
        "data_protocolo": None, "data_status": None, "ano": None,
        "data_referencia": None,
    }], "teste")
    assert total["inseridos"] == 0


def test_le_o_campo_com_o_erro_de_digitacao_da_fonte():
    """A API escreve `pvl_contradado_credor` — "contradado", com erro de
    digitação dela. Ler só o nome correto devolvia None em 100% das linhas, e
    o painel mostraria zero contratado para o país inteiro.

    Armadilha 2d na forma mais crua: o campo existe, o nome é que está torto.
    """
    from unittest import mock  # noqa: PLC0415

    from src.coletores import sadipem  # noqa: PLC0415

    bruto = {"id_pleito": 1, "cod_ibge": 1200013, "uf": "AC", "valor": 100.0,
             "pvl_contradado_credor": 1, "status": "Deferido",
             "data_protocolo": "2017-10-27T21:55:35Z", "data_status": None}

    with mock.patch.object(sadipem, "_pagina", lambda *a: ([bruto], False)):
        linha = sadipem.coletar_uf("AC")[0]

    assert linha["contratado"] == 1, "o campo torto não foi lido"
    assert linha["ano"] == 2017


def test_o_nome_correto_tambem_funciona_se_a_fonte_consertar():
    """Quando o Tesouro corrigir a digitação, o coletor não pode quebrar."""
    from unittest import mock  # noqa: PLC0415

    from src.coletores import sadipem  # noqa: PLC0415

    bruto = {"id_pleito": 2, "cod_ibge": 1200013, "uf": "AC", "valor": 1.0,
             "pvl_contratado_credor": 1, "status": "Deferido",
             "data_protocolo": "2017-10-27T00:00:00Z", "data_status": None}

    with mock.patch.object(sadipem, "_pagina", lambda *a: ([bruto], False)):
        assert sadipem.coletar_uf("AC")[0]["contratado"] == 1
