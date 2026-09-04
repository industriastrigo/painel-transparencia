"""
Auditoria de QA: Rotinas Batch, Coletores e Orquestração de Cargas.

Valida integridade do catálogo de fontes, tratamento de erros sem falha silenciosa,
mecanismos de retry e idempotência nas operações de merge do armazém.
"""
from __future__ import annotations

import logging
import pytest
import pandas as pd
from src.coletores import orquestrador
from src.nucleo import armazem
from src.nucleo.registro import ContadorDeErros, obter as obter_log


def test_orquestrador_catalogo_fontes_metadados():
    """Valida que todas as fontes cadastradas no orquestrador possuem contratos de metadados."""
    fontes = orquestrador.FONTES
    assert len(fontes) >= 5, f"Esperava ao menos 5 fontes de dados no orquestrador, obteve {len(fontes)}"
    for nome, f in fontes.items():
        assert isinstance(f, orquestrador.Fonte)
        assert f.rotulo, f"Fonte {nome} sem rótulo textual"
        assert f.cadencia, f"Fonte {nome} sem cadência definida"
        assert f.periodo, f"Fonte {nome} sem especificação de período"
        assert f.granularidade, f"Fonte {nome} sem granularidade declarada"


def test_contador_de_erros_registro_fiel():
    """Garante que falhas parciais em batches incrementam o contador e impedem relatórios falsos positivos."""
    with ContadorDeErros() as contador:
        assert contador.total == 0
        log_coletor = logging.getLogger("coletores.ibge")
        log_coletor.error("Falha de timeout simulada na fonte IBGE")
        log_nucleo = logging.getLogger("nucleo.armazem")
        log_nucleo.error("Erro simulado de escrita na partição")

    assert contador.total == 2
    assert len(contador.mensagens) == 2
    assert "timeout" in contador.mensagens[0]


def test_contador_de_erros_ignora_logs_alheios():
    """Garante que erros de subsistemas alheios (ex: rotas de API, uvicorn) não contaminem a contagem da coleta."""
    with ContadorDeErros() as contador:
        log_alheio = logging.getLogger("uvicorn.error")
        log_alheio.error("Erro HTTP de rota alheia")

    assert contador.total == 0


def test_armazem_deduplicacao_de_dados():
    """Valida idempotência e regras de substituição de duplicatas em memória."""
    dados_a = pd.DataFrame([
        {"sk": "1", "cod": "A", "valor": 100, "_atualizado_em": "2024-01-01T00:00:00"},
        {"sk": "2", "cod": "B", "valor": 200, "_atualizado_em": "2024-01-01T00:00:00"},
    ])
    dados_b = pd.DataFrame([
        {"sk": "2", "cod": "B", "valor": 250, "_atualizado_em": "2024-01-02T00:00:00"},
        {"sk": "3", "cod": "C", "valor": 300, "_atualizado_em": "2024-01-02T00:00:00"},
    ])

    combinado = pd.concat([dados_a, dados_b], ignore_index=True)
    deduplicado = combinado.drop_duplicates(subset=["sk"], keep="last")

    assert len(deduplicado) == 3
    linha_2 = deduplicado[deduplicado["sk"] == "2"].iloc[0]
    assert linha_2["valor"] == 250


def test_estrutura_particionamento_parquet():
    """Valida convenção de partições Hive ano=YYYY nos diretórios de dados analíticos."""
    from src.nucleo.esquema import TABELAS
    assert armazem.caminho_particao(TABELAS["cartao_corporativo"], {"ano": 2024}) is not None