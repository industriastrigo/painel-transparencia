"""Testes dos achados da auditoria de caixa-preta de 24/08/2026.

Dois deles apontam falhas que meus próprios testes deixaram passar:

- **PROJ-1**: eu testei concorrência procurando EXCEÇÕES e não RESULTADOS
  CORRETOS. Não havia exceção — havia resposta trocada. O teste aqui verifica
  o que importa.
- **MAP-3**: nunca testei a agregação contra uma estrutura hierárquica, que é
  como o DCA realmente vem. Testei com contas planas, onde somar tudo dá
  certo por acidente.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from fastapi.testclient import TestClient  # noqa: E402

from src.api import vistas  # noqa: E402
from src.nucleo import armazem  # noqa: E402
from src.nucleo.valores import numero  # noqa: E402


# ===================== MAP-3: despesa inflada por somar pai e filho
def _dca_hierarquico():
    """Como o DCA vem de verdade: função e subfunções como linhas irmãs."""
    armazem.remover("financas_ente")
    linhas = []
    for conta, rotulo, valor in [
        ("10", "Saúde", 1000.0),
        ("10.301", "Atenção Básica", 600.0),
        ("10.302", "Assistência Hospitalar", 400.0),
        ("12", "Educação", 800.0),
        ("12.361", "Ensino Fundamental", 500.0),
        ("12.365", "Educação Infantil", 300.0),
    ]:
        linhas.append({
            "cod_ibge": "12", "ano": 2025, "periodo": "anual",
            "cod_conta": conta, "cod_funcao": conta.split(".")[0].zfill(2),
            "funcao": rotulo.split()[0], "rotulo_conta": rotulo,
            "estagio": "Despesas Empenhadas", "valor": valor,
            "esfera": "estado", "uf": "AC",
            "data_referencia": "2025-12-31",
        })
    armazem.mesclar("financas_ente", linhas, "teste")


def test_despesa_nao_soma_funcao_com_suas_subfuncoes():
    """O Acre aparecia com R$ 66,9 bi contra R$ 12,15 bi da LOA de 2025.

    A causa: o DCA traz a função e suas subfunções como linhas irmãs, e a
    view somava todas — contando o mesmo gasto duas ou três vezes.
    """
    _dca_hierarquico()
    con = vistas.conexao_leitura()

    total = con.execute(
        "SELECT SUM(despesa_total) FROM vw_despesa_total").fetchone()[0]

    assert total == 1800.0, (
        f"somou {total} em vez de 1800 — está contando pai e filho juntos")


def test_subfuncao_continua_acessivel_sem_contaminar_o_total():
    """Excluir do total não é jogar fora: o detalhe fica noutra view."""
    _dca_hierarquico()
    con = vistas.conexao_leitura()

    detalhe = con.execute("""
        SELECT cod_conta, valor FROM vw_financas_subfuncao
         ORDER BY cod_conta""").fetchall()

    assert [d[0] for d in detalhe] == ["10.301", "10.302", "12.361", "12.365"]
    assert sum(d[1] for d in detalhe) == 1800.0


def test_funcao_traz_o_total_da_funcao_nao_a_soma_dos_filhos():
    _dca_hierarquico()
    con = vistas.conexao_leitura()
    por_funcao = dict(con.execute(
        "SELECT cod_funcao, valor FROM vw_financas_funcao").fetchall())
    assert por_funcao == {"10": 1000.0, "12": 800.0}


def test_per_capita_deixa_de_estar_inflado():
    _dca_hierarquico()
    # vw_mapa parte de dim_ente: sem o ente cadastrado não há linha nenhuma.
    armazem.mesclar("dim_ente", [{
        "cod_ibge": "12", "nivel": "estado", "nome": "Acre", "sigla_uf": "AC",
        "cod_uf": "12", "regiao": "Norte", "cod_regiao": "1"}], "teste")
    armazem.mesclar("indicador_ente", [{
        "cod_ibge": "12", "cod_metrica": "populacao", "ano": 2025,
        "valor": 100.0, "unidade": "pessoas", "nivel_territorial": "N3",
        "data_referencia": "2025-12-31"}], "teste")

    con = vistas.conexao_leitura()
    per_capita = con.execute(
        "SELECT despesa_per_capita FROM vw_mapa "
        " WHERE cod_ibge = '12' AND ano = 2025").fetchone()[0]
    assert per_capita == 18.0, "1800 / 100 habitantes"


# ===================== PROJ-1: respostas trocadas entre requisições
def test_consultas_concorrentes_nao_trocam_de_resposta():
    """O teste que eu deveria ter escrito da primeira vez.

    O anterior verificava que consultas simultâneas não levantavam exceção.
    Levantar exceção não era o problema: o problema era a requisição A
    receber o resultado da requisição B. Foi assim que o filtro de Situação
    apareceu com 90 opções `undefined` — recebeu a resposta de /tipos.
    """
    armazem.remover("proposicao")
    comum = {"sigla_tipo": "PL", "ementa": "x", "nome_autor": None,
             "partido_autor": None, "uf_autor": None, "qtd_autores": 0,
             "url": None, "ultimo_status": None, "casa": "camara"}
    armazem.mesclar("proposicao", [
        {**comum, "id_proposicao": str(i), "identificador": f"PL {i}",
         "data_apresentacao": "2026-01-01", "situacao": "Em tramitação",
         "ano": 2026} for i in range(200)], "teste")

    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    problemas: list[str] = []

    def bater(rota: str, chave: str):
        for _ in range(40):
            corpo = cliente.get(rota).json()
            if not isinstance(corpo, list):
                problemas.append(f"{rota}: resposta não é lista")
                continue
            for item in corpo:
                if chave not in item:
                    problemas.append(
                        f"{rota} devolveu objeto sem `{chave}`: {list(item)[:4]}")

    threads = [
        threading.Thread(target=bater,
                         args=("/api/proposicoes/situacoes", "situacao")),
        threading.Thread(target=bater,
                         args=("/api/proposicoes/tipos", "sigla_tipo")),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert not problemas, f"{len(problemas)} respostas trocadas: {problemas[:3]}"


def test_consulta_concorrente_nunca_devolve_vazio_indevido():
    """O outro sintoma da conexão compartilhada: `.df()` voltava None."""
    armazem.remover("proposicao")
    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": "1", "sigla_tipo": "PL",
        "identificador": "PL 1/2026", "ementa": "x",
        "data_apresentacao": "2026-01-01", "situacao": "Em tramitação",
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "url": None, "ultimo_status": None, "ano": 2026,
    }], "teste")

    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    vazios = []

    def bater():
        for _ in range(40):
            if not cliente.get("/api/proposicoes").json():
                vazios.append(1)

    threads = [threading.Thread(target=bater) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not vazios, f"{len(vazios)} respostas vazias indevidas"


# ===================== ATU-3: valor monetário em formato brasileiro
def test_valor_da_cgu_no_formato_brasileiro_vira_numero():
    """`1.234.567,89` virava texto e quebrava qualquer soma depois."""
    assert numero("1.234.567,89") == 1234567.89
    assert numero("R$ 1.000,00") == 1000.0
    assert numero("1234567.89") == 1234567.89, "formato do SICONFI/IBGE"


def test_ponto_isolado_continua_sendo_decimal():
    assert numero("1.234") == 1.234


def test_dois_pontos_so_podem_ser_milhar():
    assert numero("1.234.567") == 1234567.0


def test_emenda_grava_valor_numerico(monkeypatch):
    from src.coletores import portal_transparencia
    from src.nucleo import config

    monkeypatch.setattr(config, "CHAVE_PORTAL_TRANSPARENCIA", "x" * 32)
    paginas = {"n": 0}

    def uma_pagina(*a, **k):
        paginas["n"] += 1
        if paginas["n"] > 1:
            return []
        return [{"codigoEmenda": "E1", "valorEmpenhado": "1.234.567,89",
                 "valorPago": "1.000.000,00", "nomeAutor": "Fulano"}]

    monkeypatch.setattr(portal_transparencia.rede, "buscar", uma_pagina)
    monkeypatch.setattr(portal_transparencia.controle, "gravar_marca",
                        lambda *a, **k: None)
    armazem.remover("emenda_parlamentar")

    portal_transparencia.coletar_emendas(2025)
    df = armazem.ler("emenda_parlamentar")

    assert float(df.iloc[0]["valor_empenhado"]) == 1234567.89
    assert str(df["valor_empenhado"].dtype) in ("float64", "Float64"), \
        "gravado como texto quebraria soma e ordenação"


# ===================== POL-1: código bruto do TSE vazando na tela
def test_todos_os_codigos_de_cargo_do_tse_tem_nome():
    from src.coletores.tse import CARGOS
    assert CARGOS["12"][0] == "vice_prefeito", "era o `cargo_12` da tela"
    for codigo in map(str, range(1, 14)):
        assert codigo in CARGOS, f"código {codigo} viraria `cargo_{codigo}`"
        assert not CARGOS[codigo][0].startswith("cargo_")


def test_codigo_desconhecido_avisa_no_log(monkeypatch, caplog):
    """Se o TSE criar um código novo, o painel não deve ser o primeiro a contar."""
    import pandas as pd
    from src.coletores import tse

    candidato = {
        "DS_SIT_TOT_TURNO": "ELEITO", "CD_CARGO": "99",
        "SQ_CANDIDATO": "1", "NM_CANDIDATO": "Fulano",
        "NM_URNA_CANDIDATO": "Fulano", "SG_PARTIDO": "X", "SG_UF": "SP",
        "SG_UE": "SP", "NM_UE": "SÃO PAULO", "DS_EMAIL": None,
        "DS_GENERO": None, "DS_COR_RACA": None, "DS_GRAU_INSTRUCAO": None,
        "DS_OCUPACAO": None, "DT_NASCIMENTO": None,
    }
    monkeypatch.setattr(tse, "_baixar_consulta_cand",
                        lambda ano: pd.DataFrame([candidato]))
    monkeypatch.setattr(tse.controle, "gravar_marca", lambda *a, **k: None)

    with caplog.at_level("WARNING"):
        tse.coletar_eleitos(2024)
    assert "sem tradução" in caplog.text and "99" in caplog.text


# ===================== FON-2: zero linha nunca é "ok"
def test_zero_linha_nao_e_ok(monkeypatch):
    from src.coletores import siconfi

    monkeypatch.setattr(siconfi, "coletar_dca", lambda ano, cod: [])
    marcas = {}
    monkeypatch.setattr(siconfi.controle, "gravar_marca",
                        lambda *a, **k: marcas.update(k))
    monkeypatch.setattr(siconfi.controle, "registrar_entes",
                        lambda *a, **k: None)
    monkeypatch.setattr(siconfi.controle, "entes_pendentes",
                        lambda *a, **k: [str(i) for i in range(27)])

    siconfi.varrer(2026, [str(i) for i in range(27)],
                   trabalhadores=2, intervalo=0)
    assert marcas.get("situacao") == "sem_dado", \
        "27 entes sem publicar não é uma coleta bem-sucedida"
