"""Módulo de semeadura automática de dados para ambiente de produção / nuvem.

Quando o servidor inicia (no Cloud Run ou local), se as tabelas de referência e dados
básicos estiverem vazias, este módulo executa os coletores de referência e popula:
- dim_subsidio (Teto constitucional e remuneração dos 3 poderes)
- dim_politico & mandato (Chefes do Executivo Nacional e Estadual)
- dim_magistrado & fato_remuneracao_magistrado (Tribunais Superiores e Estaduais)
- fato_cartao_corporativo & fato_viagem_servico & fato_contrato_governo
"""
from __future__ import annotations

from pathlib import Path
from ..nucleo import config
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.semeador")


def semear_se_vazio() -> None:
    """Verifica e popula dados essenciais se o diretório de dados estiver vazio."""
    dados_dir = Path(config.DADOS) if config.DADOS is not None else Path(__file__).resolve().parents[2] / "dados"
    dados_dir.mkdir(parents=True, exist_ok=True)

    log.info("Verificando integridade das bases de dados no diretório: %s", dados_dir)

    # 1. Subsídios e Referências de Custo
    try:
        from .referencias import coletar as coletar_referencias
        coletar_referencias()
        log.info("[OK] Base de subsídios e referências sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar subsídios: %s", erro)

    # 2. Executivo Referência (Presidentes e Governadores)
    try:
        from .executivo_referencia import carregar_referencias_executivo
        carregar_referencias_executivo()
        log.info("[OK] Base histórica do Poder Executivo carregada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar referências do executivo: %s", erro)

    # 3. Executivo Dados (Cartões, PCDP e Contratos)
    try:
        from .executivo_dados import gerar_dados_executivo
        gerar_dados_executivo()
        log.info("[OK] Base de gastos, viagens e cartões do Executivo populada.")
    except Exception as erro:
        log.warning("Aviso ao gerar dados de despesas do executivo: %s", erro)

    # 4. Poder Judiciário (STF, STJ, TST, TSE, TRFs e TJs)
    try:
        from .judiciario import gerar_bases_judiciario
        gerar_bases_judiciario()
        log.info("[OK] Base de magistrados e remunerações do Judiciário gerada.")
    except Exception as erro:
        log.warning("Aviso ao gerar base do judiciário: %s", erro)
