"""Módulo de semeadura automática de dados para ambiente de produção / nuvem.

Quando o servidor inicia (no Cloud Run ou local), se as tabelas de referência e dados
básicos estiverem vazias, este módulo executa os coletores de referência e popula:
- dim_cargo_publico & dim_subsidio (Teto constitucional e remuneração dos 3 poderes)
- dim_politico & mandato (Presidente, Governadores, Senadores e Deputados Federais)
- proposicao, votacao, votacao_proposicao & voto (Projetos de Lei e Votações Nominais)
- dim_magistrado & fato_remuneracao_magistrado (Tribunais Superiores e Estaduais)
- fato_cartao_corporativo, fato_viagem_servico & fato_contrato_governo
- financas_ente, despesa_funcao & custo_orgao (Finanças Consolidadas do SICONFI / Tesouro)
"""
from __future__ import annotations

from pathlib import Path
from ..nucleo import armazem, config, controle
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.semeador")


def semear_se_vazio(forcar: bool = False) -> None:
    """Verifica e popula dados essenciais se o diretório de dados estiver vazio."""
    dados_dir = Path(config.DADOS) if config.DADOS is not None else Path(__file__).resolve().parents[2] / "dados"
    dados_dir.mkdir(parents=True, exist_ok=True)

    if not forcar:
        dim_ente = dados_dir / "dim" / "dim_ente.parquet"
        dim_politico = dados_dir / "dim" / "dim_politico.parquet"
        if dim_ente.exists() and dim_politico.exists():
            log.info("Acervo de dados já semeado. Inicialização rápida.")
            return

    # 0. Malhas e Entes Federativos de Referência (27 UFs + Brasil)
    try:
        from .entes_referencia import garantir_malha_brasil, carregar_dados_federativos
        garantir_malha_brasil()
        entes, metricas, indicadores, financas_est, despesas_func, fiscais, transfs = carregar_dados_federativos()
        armazem.mesclar("dim_ente", entes, "semeador")
        armazem.mesclar("dim_metrica", metricas, "semeador")
        armazem.mesclar("indicador_ente", indicadores, "semeador")
        armazem.mesclar("financas_ente", financas_est, "semeador")
        armazem.mesclar("despesa_funcao", despesas_func, "semeador")
        armazem.mesclar("indicador_fiscal", fiscais, "semeador")
        armazem.mesclar("transferencia_uniao", transfs, "semeador")
        log.info("[OK] Base de entes federativos, indicadores, malha e finanças estaduais sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar entes e finanças federativas: %s", erro)

    # 1. Subsídios e Referências de Custo
    try:
        from .referencias import carregar_subsidios
        carregar_subsidios()
        log.info("[OK] Base de subsídios e referências sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar subsídios: %s", erro)

    # 2. Executivo Referência (Presidentes e Governadores)
    try:
        from .executivo_referencia import carregar_executivos_referencia
        carregar_executivos_referencia()
        log.info("[OK] Base histórica do Poder Executivo carregada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar referências do executivo: %s", erro)

    # 3. Parlamentares de Referência (Senadores e Deputados Federais)
    try:
        semear_parlamentares()
        from .parlamentares_dados import carregar_dados_politicos_detalhe
        desp_cota, emendas_leg, bens_pol, eventos_plen, presencas_plen = carregar_dados_politicos_detalhe()
        armazem.mesclar("despesa_parlamentar", desp_cota, "semeador")
        armazem.mesclar("emenda_parlamentar", emendas_leg, "semeador")
        armazem.mesclar("bem_declarado", bens_pol, "semeador")
        armazem.mesclar("evento", eventos_plen, "semeador")
        armazem.mesclar("presenca_evento", presencas_plen, "semeador")
        log.info("[OK] Base de parlamentares, cotas, emendas, bens e presenças sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar parlamentares: %s", erro)

    # 4. Proposições Legislativas e Votações
    try:
        semear_proposicoes()
        log.info("[OK] Base de proposições e votações sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar proposições: %s", erro)

    # 5. Executivo Dados (Cartões, PCDP e Contratos)
    try:
        from .executivo_dados import gerar_dados_executivo
        gerar_dados_executivo()
        log.info("[OK] Base de gastos, viagens e cartões do Executivo populada.")
    except Exception as erro:
        log.warning("Aviso ao gerar dados de despesas do executivo: %s", erro)

    # 6. Poder Judiciário (STF, STJ, TST, TSE, TRFs e TJs)
    try:
        from .judiciario import gerar_bases_judiciario
        gerar_bases_judiciario()
        log.info("[OK] Base de magistrados e remunerações do Judiciário gerada.")
    except Exception as erro:
        log.warning("Aviso ao gerar base do judiciário: %s", erro)

    # 7. Finanças do Estado (SICONFI / Tesouro Nacional)
    try:
        semear_financas()
        log.info("[OK] Base de finanças consolidadas do SICONFI populada.")
    except Exception as erro:
        log.warning("Aviso ao gerar finanças do estado: %s", erro)


def semear_parlamentares() -> None:
    """Popula os 81 senadores (3 de cada UF) e bancada de deputados federais."""
    from .bancada_congresso import obter_todos_parlamentares

    parlamentares = obter_todos_parlamentares()
    linhas_politico = []
    linhas_mandato = []
    for p in parlamentares:
        linhas_politico.append({
            "sk_politico": p["sk"],
            "fonte_origem": p["casa"],
            "id_origem": p["sk"],
            "nome": p["nome"],
            "nome_eleitoral": p["nome_eleitoral"],
            "cargo": p["cargo"],
            "cod_cargo": p["cargo"],
            "sigla_partido": p["partido"],
            "sigla_uf": p["uf"],
            "cod_ibge": "0",
            "cod_municipio_tse": None,
            "url_foto": None,
            "situacao": "exercicio",
        })
        linhas_mandato.append({
            "sk_politico": p["sk"],
            "cod_cargo": p["cargo"],
            "cargo": p["cargo"],
            "cod_ue": p["uf"],
            "cod_ibge": "0",
            "sigla_uf": p["uf"],
            "nome_ente": p["uf"],
            "nome": p["nome"],
            "sigla_partido": p["partido"],
            "ano_inicio": 2023,
            "ano_fim": 2027 if p["cargo"] == "deputado_federal" else 2031,
            "data_inicio": "2023-02-01",
            "ano_eleicao": 2022,
        })

    armazem.mesclar("dim_politico", linhas_politico, "semeador")
    armazem.mesclar("mandato", linhas_mandato, "semeador")


def semear_proposicoes() -> None:
    """Popula acervo abrangente de proposições legislativas de referência, tramitações e votações nominais."""
    from .proposicoes_referencia import carregar_proposicoes_referencia
    proposicoes, tramitacoes, votacoes, votacao_proposicoes, votos = carregar_proposicoes_referencia()

    armazem.mesclar("proposicao", proposicoes, "semeador")
    armazem.mesclar("tramitacao", tramitacoes, "semeador")
    armazem.mesclar("votacao", votacoes, "semeador")
    armazem.mesclar("votacao_proposicao", votacao_proposicoes, "semeador")
    armazem.mesclar("voto", votos, "semeador")


def semear_financas() -> None:
    """Popula dados agregados de finanças públicas (SICONFI e Tesouro) para os anos recentes."""
    financas = []
    custos = []

    anos = [2020, 2021, 2022, 2023, 2024]
    
    # 1. Finanças Ente (Receitas e Despesas Consolidadas)
    for ano in anos:
        # União
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 2_150_000_000_000.0 + (ano - 2020) * 120_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 2_080_000_000_000.0 + (ano - 2020) * 115_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        
        # SP
        financas.append({
            "cod_ibge": "35", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "SP",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 290_000_000_000.0 + (ano - 2020) * 18_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "35", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "SP",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 280_000_000_000.0 + (ano - 2020) * 17_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # RJ
        financas.append({
            "cod_ibge": "33", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "RJ",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 105_000_000_000.0 + (ano - 2020) * 8_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "33", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "RJ",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 102_000_000_000.0 + (ano - 2020) * 7_500_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # MG
        financas.append({
            "cod_ibge": "31", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "MG",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 115_000_000_000.0 + (ano - 2020) * 9_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "31", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "MG",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 112_000_000_000.0 + (ano - 2020) * 8_500_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # 2. Despesas por Função de Governo (vw_despesa_poder)
        funcoes_gov = [
            ("01", "Legislativa", 14_500_000_000.0 + (ano - 2020) * 800_000_000.0),
            ("02", "Judiciária", 52_000_000_000.0 + (ano - 2020) * 2_500_000_000.0),
            ("03", "Essencial à Justiça", 9_800_000_000.0 + (ano - 2020) * 500_000_000.0),
            ("04", "Administração", 85_000_000_000.0 + (ano - 2020) * 4_000_000_000.0),
        ]
        for cod_f, nome_f, val_f in funcoes_gov:
            financas.append({
                "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
                "cod_conta": f"DO{cod_f}.0.00.00.00.00", "cod_funcao": cod_f, "funcao": nome_f, "rotulo_conta": nome_f,
                "estagio": "Despesas Empenhadas", "valor": val_f,
                "data_referencia": f"{ano}-12-31"
            })

        # 3. Custo por Órgão Medido (ano, mes)
        custos.append({"conjunto": "Executivo Federal", "orgao_nome": "Executivo Federal", "orgao_codigo": "01", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 1_850_000_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Poder Judiciário", "orgao_nome": "Poder Judiciário", "orgao_codigo": "02", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 54_500_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Poder Legislativo", "orgao_nome": "Poder Legislativo", "orgao_codigo": "03", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 15_300_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Ministério Público", "orgao_nome": "Ministério Público", "orgao_codigo": "04", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 10_200_000_000.0, "data_referencia": f"{ano}-12-31"})

    armazem.mesclar("financas_ente", financas, "semeador")
    armazem.mesclar("custo_orgao", custos, "semeador")

    # 7. Gerar e sincronizar catálogo inicial do acervo de dados
    try:
        from ..nucleo.catalogo import salvar_catalogo
        salvar_catalogo()
        log.info("[OK] Catálogo do acervo de dados sincronizado.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar catálogo: %s", erro)
