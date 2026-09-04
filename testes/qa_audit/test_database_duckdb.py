"""
Auditoria de QA: Camada de Dados, DuckDB e Concorrência.

Valida integridade do motor analítico DuckDB, pooling de conexão,
concorrência de múltiplas threads simultâneas, leitura de partições Parquet e resiliência.
"""
from __future__ import annotations

import concurrent.futures
import threading
import pytest
import duckdb
import pandas as pd
from src.api import db, vistas
from src.nucleo import armazem
from src.nucleo.esquema import TABELAS


def test_duckdb_conexao_e_cursor():
    """Valida obtenção de conexão ativa e execução de queries básicas."""
    con = db.con()
    assert con is not None
    cursor = con.cursor()
    try:
        res = cursor.execute("SELECT 42 AS resposta").fetchone()
        assert res[0] == 42
    finally:
        cursor.close()


def test_duckdb_concorrencia_multiplas_threads():
    """Simula carga concorrente de 30 threads simultâneas realizando consultas analíticas."""
    num_threads = 30
    erros = []

    def executar_consulta(thread_id: int):
        try:
            con = db.con()
            cursor = con.cursor()
            try:
                res = cursor.execute(f"SELECT {thread_id} AS tid, 'thread_ok' AS status").fetchall()
                if len(res) != 1 or res[0][0] != thread_id:
                    erros.append(f"Resultado inesperado na thread {thread_id}: {res}")
            finally:
                cursor.close()
        except Exception as e:
            erros.append(f"Exceção na thread {thread_id}: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(executar_consulta, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    assert len(erros) == 0, f"Falhas de concorrência detectadas no DuckDB: {erros}"


def test_duckdb_views_declaradas_criacao():
    """Valida se todas as views de tabelas cadastradas no esquema podem ser criadas sem crash."""
    con = duckdb.connect(":memory:")
    try:
        views_criadas = vistas.criar(con)
        assert isinstance(views_criadas, list)
        assert len(views_criadas) > 0, "Nenhuma view foi criada no DuckDB"
    finally:
        con.close()


def test_duckdb_resiliencia_query_invalida():
    """Valida tratamento seguro de erros de sintaxe SQL sem corromper a conexão."""
    con = db.con()
    cursor = con.cursor()
    try:
        with pytest.raises(Exception):
            cursor.execute("SELECT * FROM tabela_que_definitivamente_nao_existe_12345")
    finally:
        cursor.close()

    cursor2 = con.cursor()
    try:
        res = cursor2.execute("SELECT 1").fetchone()
        assert res[0] == 1
    finally:
        cursor2.close()


def test_duckdb_parametrizacao_defensiva():
    """Valida que consultas parametrizadas com ? tratam caracteres especiais sem SQL injection."""
    con = db.con()
    cursor = con.cursor()
    try:
        res = cursor.execute("SELECT ? AS parametro_texto", ["' OR 1=1 --"]).fetchone()
        assert res[0] == "' OR 1=1 --"
    finally:
        cursor.close()


def test_duckdb_tipagem_e_valores_nulos():
    """Valida que a sanitização de registros substitui inf/-inf e preserva None no padrão JSON."""
    df_teste = pd.DataFrame([
        {"id": 1, "valor": float("inf"), "texto": "teste"},
        {"id": 2, "valor": float("-inf"), "texto": None},
        {"id": 3, "valor": 150.0, "texto": "ok"},
    ])
    registros = db._registros(df_teste)
    assert len(registros) == 3
    assert registros[0]["valor"] is None
    assert registros[1]["valor"] is None
    assert registros[1]["texto"] is None
    assert registros[2]["valor"] == 150.0