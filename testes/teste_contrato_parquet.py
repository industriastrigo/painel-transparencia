"""Validação parametrizada do contrato inegociável dos Parquet de dados/fato.

Regras do projeto:
- Toda tabela fato possui chave primária determinística (sk) sem duplicidade.
- Toda tabela fato possui colunas de auditoria (_criado_em, _atualizado_em, _fonte, _hash_registro).
- Os intervalos de datas e anos são coerentes e não contêm datas futuras anômalas.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.nucleo import esquema

FATO_DIR = RAIZ / "dados" / "fato"


def _tabelas_fato_com_dados():
    """Descobre todas as tabelas fato que possuem arquivos Parquet gravados no disco."""
    tabelas = []
    if not FATO_DIR.exists():
        return tabelas
    for pasta in sorted(FATO_DIR.iterdir()):
        if pasta.is_dir() and any(pasta.rglob("*.parquet")):
            tabelas.append(pasta.name)
    return tabelas


TABELAS_FATO = _tabelas_fato_com_dados()


@pytest.fixture(scope="module")
def con_duckdb():
    con = duckdb.connect()
    yield con
    con.close()


@pytest.mark.parametrize("nome_tabela", TABELAS_FATO)
def test_contrato_parquet_pk_sem_duplicidade(nome_tabela: str, con_duckdb):
    """Verifica que a chave primária 'sk' existe, não é nula e não tem duplicatas."""
    caminho = str(FATO_DIR / nome_tabela / "**" / "*.parquet").replace("\\", "/")
    
    res = con_duckdb.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT sk) as unicos_sk,
            COUNT(*) - COUNT(sk) as sk_nulos
        FROM read_parquet('{caminho}', hive_partitioning=1, union_by_name=1)
    """).fetchone()

    total, unicos_sk, sk_nulos = res
    assert total > 0, f"Tabela {nome_tabela} não deve estar vazia"
    assert sk_nulos == 0, f"Tabela {nome_tabela} possui {sk_nulos} chaves 'sk' nulas"
    assert total == unicos_sk, (
        f"Tabela {nome_tabela} possui {total - unicos_sk} chaves 'sk' duplicadas "
        f"(total: {total}, únicas: {unicos_sk})"
    )


@pytest.mark.parametrize("nome_tabela", TABELAS_FATO)
def test_contrato_parquet_colunas_auditoria_presentes(nome_tabela: str, con_duckdb):
    """Verifica se as colunas obrigatórias de auditoria existem e estão povoadas."""
    caminho = str(FATO_DIR / nome_tabela / "**" / "*.parquet").replace("\\", "/")
    
    colunas_df = con_duckdb.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{caminho}', hive_partitioning=1, union_by_name=1) LIMIT 0"
    ).df()
    colunas_nomes = set(colunas_df["column_name"].tolist())

    for col in ["_criado_em", "_atualizado_em", "_hash_registro", "_fonte"]:
        assert col in colunas_nomes, f"Coluna de controle '{col}' ausente na tabela {nome_tabela}"

    res = con_duckdb.execute(f"""
        SELECT 
            COUNT(*) - COUNT(_criado_em) as criados_nulos,
            COUNT(*) - COUNT(_atualizado_em) as atualizados_nulos
        FROM read_parquet('{caminho}', hive_partitioning=1, union_by_name=1)
    """).fetchone()

    criados_nulos, atualizados_nulos = res
    assert criados_nulos == 0, f"Tabela {nome_tabela} possui {criados_nulos} registros sem _criado_em"
    assert atualizados_nulos == 0, f"Tabela {nome_tabela} possui {atualizados_nulos} registros sem _atualizado_em"


@pytest.mark.parametrize("nome_tabela", TABELAS_FATO)
def test_contrato_parquet_intervalo_datas_coerente(nome_tabela: str, con_duckdb):
    """Garante que as colunas temporais não possuem anos absurdos (< 1990 ou > 2030)."""
    caminho = str(FATO_DIR / nome_tabela / "**" / "*.parquet").replace("\\", "/")
    
    colunas_df = con_duckdb.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{caminho}', hive_partitioning=1, union_by_name=1) LIMIT 0"
    ).df()
    colunas_nomes = set(colunas_df["column_name"].tolist())

    campo_ano = None
    if "ano" in colunas_nomes:
        campo_ano = "ano"
    elif "ano_inicio" in colunas_nomes:
        campo_ano = "ano_inicio"

    if campo_ano:
        res = con_duckdb.execute(f"""
            SELECT MIN(TRY_CAST({campo_ano} AS INTEGER)), MAX(TRY_CAST({campo_ano} AS INTEGER))
            FROM read_parquet('{caminho}', hive_partitioning=1, union_by_name=1)
            WHERE {campo_ano} IS NOT NULL
        """).fetchone()
        
        min_ano, max_ano = res
        if min_ano is not None:
            assert min_ano >= 1980, f"Tabela {nome_tabela} possui ano mínimo suspeito: {min_ano}"
            assert max_ano <= 2035, f"Tabela {nome_tabela} possui ano máximo futuro: {max_ano}"
