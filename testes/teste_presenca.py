"""Presença em sessões deliberativas e fidelidade partidária.

O caso do Bruno é o que importa aqui. Um deputado que assumiu em abril não
pode aparecer como faltoso em fevereiro. A primeira versão da view dizia 50%
de presença para ele, porque punha o ano inteiro no denominador — e esse
número iria para a tela ao lado do nome de uma pessoa real.
"""
from __future__ import annotations

import duckdb
import pytest

from src.api import vistas

VISTAS_TESTADAS = (
    "vw_sessao_deliberativa",
    "vw_janela_exercicio",
    "vw_presenca_deputado",
    "vw_voto_contra_orientacao",
    "vw_fidelidade_partidaria",
)

# Quatro sessões deliberativas encerradas, uma por mês.
SESSOES = [("E1", "2026-02-10"), ("E2", "2026-03-10"),
           ("E3", "2026-04-10"), ("E4", "2026-05-10")]


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE evento(
            casa VARCHAR, id_evento VARCHAR, data_hora_inicio VARCHAR,
            data_hora_fim VARCHAR, descricao_tipo VARCHAR, descricao VARCHAR,
            situacao VARCHAR, local VARCHAR, deliberativo BOOLEAN,
            ano INTEGER)""")
    con.execute("""
        CREATE TABLE presenca_evento(
            casa VARCHAR, id_evento VARCHAR, id_politico VARCHAR,
            data_hora_inicio VARCHAR, ano INTEGER, mes INTEGER)""")
    con.execute("""
        CREATE TABLE orientacao_bancada(
            casa VARCHAR, id_votacao VARCHAR, sigla_bancada VARCHAR,
            orientacao VARCHAR, sigla_orgao VARCHAR, ano INTEGER)""")
    con.execute("""
        CREATE TABLE voto(
            casa VARCHAR, id_votacao VARCHAR, id_politico VARCHAR,
            nome_politico VARCHAR, sigla_partido VARCHAR, sigla_uf VARCHAR,
            voto VARCHAR, data_hora VARCHAR, ano INTEGER, mes INTEGER)""")

    for identificador, dia in SESSOES:
        con.execute(
            "INSERT INTO evento VALUES ('camara',?,?,NULL,"
            "'Sessão Deliberativa','x','Encerrada',NULL,TRUE,2026)",
            [identificador, f"{dia}T14:00"])
    # Audiência pública: trabalho parlamentar, mas não obrigação de
    # comparecimento. Não pode entrar no denominador nem no numerador.
    con.execute(
        "INSERT INTO evento VALUES ('camara','E9','2026-03-11T14:00',NULL,"
        "'Audiência Pública','x','Encerrada',NULL,FALSE,2026)")

    # Ana: em exercício o ano todo, faltou a uma das quatro.
    for identificador, dia in [("E1", "2026-02-10"), ("E2", "2026-03-10"),
                               ("E4", "2026-05-10")]:
        con.execute("INSERT INTO presenca_evento VALUES "
                    "('camara',?,'1',?,2026,1)",
                    [identificador, f"{dia}T14:00"])
    con.execute("INSERT INTO presenca_evento VALUES "
                "('camara','E9','1','2026-03-11T14:00',2026,3)")

    # Bruno: assumiu em abril. Compareceu a tudo que existia depois disso.
    for identificador, dia in [("E3", "2026-04-10"), ("E4", "2026-05-10")]:
        con.execute("INSERT INTO presenca_evento VALUES "
                    "('camara',?,'2',?,2026,1)",
                    [identificador, f"{dia}T14:00"])

    con.execute("INSERT INTO voto VALUES ('camara','V1','1','ANA','PP','SP',"
                "'Sim','2026-02-10T15:00',2026,2)")
    con.execute("INSERT INTO voto VALUES ('camara','V1','2','BRUNO','PP','SP',"
                "'Não','2026-04-10T15:00',2026,4)")
    con.execute("INSERT INTO voto VALUES ('camara','V2','1','ANA','PP','SP',"
                "'Sim','2026-03-10T15:00',2026,3)")
    con.execute("INSERT INTO orientacao_bancada VALUES "
                "('camara','V1','PP','Sim','PLEN',2026)")
    con.execute("INSERT INTO orientacao_bancada VALUES "
                "('camara','V2','PP','Liberado','PLEN',2026)")

    for nome in VISTAS_TESTADAS:
        con.execute(f"CREATE VIEW {nome} AS {vistas.DERIVADAS[nome]}")
    return con


def _presenca(con, id_politico: str) -> dict:
    return con.execute(
        "SELECT * FROM vw_presenca_deputado WHERE id_politico = ?",
        [id_politico]).df().to_dict("records")[0]


def test_ausencia_e_a_subtracao_dentro_da_janela(con):
    """Ana esteve o ano todo: 3 de 4, uma falta de verdade."""
    ana = _presenca(con, "1")
    assert ana["presencas"] == 3
    assert ana["sessoes_possiveis"] == 4
    assert ana["ausencias"] == 1
    assert ana["taxa_presenca"] == pytest.approx(0.75)
    assert not ana["janela_aproximada"]


def test_quem_assumiu_no_meio_do_ano_nao_falta_ao_passado(con):
    """O defeito que este arquivo existe para impedir.

    Bruno assumiu em abril. Contando o ano inteiro ele apareceria com 50% de
    presença e duas faltas que nunca poderiam ter acontecido.
    """
    bruno = _presenca(con, "2")
    assert bruno["sessoes_possiveis"] == 2, "denominador vazou para antes da posse"
    assert bruno["ausencias"] == 0
    assert bruno["taxa_presenca"] == pytest.approx(1.0)
    assert bruno["janela_aproximada"], (
        "a tela precisa saber que a taxa cobre só parte do ano")


def test_audiencia_publica_fica_fora_da_conta(con):
    """Ana compareceu à audiência; ela não pode virar presença nem sessão."""
    assert con.execute("SELECT COUNT(*) FROM vw_sessao_deliberativa").fetchone()[0] == 4
    assert _presenca(con, "1")["presencas"] == 3


def test_bancada_liberada_nao_conta_como_divergencia(con):
    """Sem orientação não há o que descumprir."""
    linhas = con.execute(
        "SELECT id_politico, votos_com_orientacao, votos_divergentes "
        "FROM vw_fidelidade_partidaria ORDER BY id_politico"
    ).df().to_dict("records")
    assert linhas[0]["votos_com_orientacao"] == 1, "V2 estava liberada"
    assert linhas[0]["votos_divergentes"] == 0
    assert linhas[1]["votos_divergentes"] == 1
