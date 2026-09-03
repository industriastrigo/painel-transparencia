"""Módulo de referência para Entes Federativos (27 UFs e Brasil), Indicadores e Finanças Públicas.

Alimenta o Mapa Interativo, Rankings e Panorama Fiscal com dados consolidados
de 2020 a 2024 para todos os estados brasileiros e municípios polo.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from ..nucleo import config

ESTADOS_BRASIL = [
    # Norte
    {"cod_ibge": "11", "sigla": "RO", "nome": "Rondônia", "regiao": "Norte", "pop": 1_581_196, "pib_bi": 58.0, "receita_bi": 14.5, "despesa_bi": 13.8, "saude_bi": 2.1, "educacao_bi": 2.4, "rcl_pessoal": 46.2, "divida_bi": 4.1},
    {"cod_ibge": "12", "sigla": "AC", "nome": "Acre", "regiao": "Norte", "pop": 830_018, "pib_bi": 21.0, "receita_bi": 9.2, "despesa_bi": 8.9, "saude_bi": 1.4, "educacao_bi": 1.6, "rcl_pessoal": 48.5, "divida_bi": 2.8},
    {"cod_ibge": "13", "sigla": "AM", "nome": "Amazonas", "regiao": "Norte", "pop": 3_941_613, "pib_bi": 145.0, "receita_bi": 29.5, "despesa_bi": 28.1, "saude_bi": 3.8, "educacao_bi": 4.2, "rcl_pessoal": 44.1, "divida_bi": 7.2},
    {"cod_ibge": "14", "sigla": "RR", "nome": "Roraima", "regiao": "Norte", "pop": 636_707, "pib_bi": 18.5, "receita_bi": 7.8, "despesa_bi": 7.4, "saude_bi": 1.1, "educacao_bi": 1.3, "rcl_pessoal": 49.0, "divida_bi": 1.9},
    {"cod_ibge": "15", "sigla": "PA", "nome": "Pará", "regiao": "Norte", "pop": 8_120_131, "pib_bi": 262.0, "receita_bi": 46.0, "despesa_bi": 43.5, "saude_bi": 5.2, "educacao_bi": 6.8, "rcl_pessoal": 43.8, "divida_bi": 6.5},
    {"cod_ibge": "16", "sigla": "AP", "nome": "Amapá", "regiao": "Norte", "pop": 733_759, "pib_bi": 20.0, "receita_bi": 8.5, "despesa_bi": 8.1, "saude_bi": 1.2, "educacao_bi": 1.5, "rcl_pessoal": 47.9, "divida_bi": 2.3},
    {"cod_ibge": "17", "sigla": "TO", "nome": "Tocantins", "regiao": "Norte", "pop": 1_511_460, "pib_bi": 51.0, "receita_bi": 13.8, "despesa_bi": 13.1, "saude_bi": 1.9, "educacao_bi": 2.2, "rcl_pessoal": 46.8, "divida_bi": 3.5},
    
    # Nordeste
    {"cod_ibge": "21", "sigla": "MA", "nome": "Maranhão", "regiao": "Nordeste", "pop": 6_776_699, "pib_bi": 125.0, "receita_bi": 28.5, "despesa_bi": 27.2, "saude_bi": 3.9, "educacao_bi": 5.1, "rcl_pessoal": 45.3, "divida_bi": 8.4},
    {"cod_ibge": "22", "sigla": "PI", "nome": "Piauí", "regiao": "Nordeste", "pop": 3_271_199, "pib_bi": 64.0, "receita_bi": 17.2, "despesa_bi": 16.4, "saude_bi": 2.4, "educacao_bi": 3.0, "rcl_pessoal": 44.7, "divida_bi": 5.1},
    {"cod_ibge": "23", "sigla": "CE", "nome": "Ceará", "regiao": "Nordeste", "pop": 8_794_957, "pib_bi": 195.0, "receita_bi": 38.0, "despesa_bi": 36.2, "saude_bi": 5.1, "educacao_bi": 6.4, "rcl_pessoal": 43.5, "divida_bi": 11.2},
    {"cod_ibge": "24", "sigla": "RN", "nome": "Rio Grande do Norte", "regiao": "Nordeste", "pop": 3_302_729, "pib_bi": 80.0, "receita_bi": 18.5, "despesa_bi": 18.0, "saude_bi": 2.6, "educacao_bi": 2.9, "rcl_pessoal": 54.2, "divida_bi": 7.8},
    {"cod_ibge": "25", "sigla": "PB", "nome": "Paraíba", "regiao": "Nordeste", "pop": 3_974_687, "pib_bi": 77.0, "receita_bi": 19.8, "despesa_bi": 18.7, "saude_bi": 2.7, "educacao_bi": 3.2, "rcl_pessoal": 45.8, "divida_bi": 4.9},
    {"cod_ibge": "26", "sigla": "PE", "nome": "Pernambuco", "regiao": "Nordeste", "pop": 9_058_931, "pib_bi": 220.0, "receita_bi": 48.0, "despesa_bi": 46.5, "saude_bi": 6.8, "educacao_bi": 6.9, "rcl_pessoal": 46.9, "divida_bi": 16.5},
    {"cod_ibge": "27", "sigla": "AL", "nome": "Alagoas", "regiao": "Nordeste", "pop": 3_127_683, "pib_bi": 73.0, "receita_bi": 17.5, "despesa_bi": 16.6, "saude_bi": 2.3, "educacao_bi": 2.7, "rcl_pessoal": 44.3, "divida_bi": 7.0},
    {"cod_ibge": "28", "sigla": "SE", "nome": "Sergipe", "regiao": "Nordeste", "pop": 2_210_004, "pib_bi": 52.0, "receita_bi": 14.2, "despesa_bi": 13.5, "saude_bi": 1.9, "educacao_bi": 2.3, "rcl_pessoal": 47.1, "divida_bi": 5.3},
    {"cod_ibge": "29", "sigla": "BA", "nome": "Bahia", "regiao": "Nordeste", "pop": 14_141_626, "pib_bi": 350.0, "receita_bi": 68.0, "despesa_bi": 65.4, "saude_bi": 8.9, "educacao_bi": 9.5, "rcl_pessoal": 45.6, "divida_bi": 24.0},

    # Sudeste
    {"cod_ibge": "31", "sigla": "MG", "nome": "Minas Gerais", "regiao": "Sudeste", "pop": 20_539_989, "pib_bi": 857.0, "receita_bi": 118.0, "despesa_bi": 115.0, "saude_bi": 13.5, "educacao_bi": 15.8, "rcl_pessoal": 51.2, "divida_bi": 160.0},
    {"cod_ibge": "32", "sigla": "ES", "nome": "Espírito Santo", "regiao": "Sudeste", "pop": 3_833_712, "pib_bi": 170.0, "receita_bi": 26.5, "despesa_bi": 24.8, "saude_bi": 3.7, "educacao_bi": 3.9, "rcl_pessoal": 39.8, "divida_bi": 2.1},
    {"cod_ibge": "33", "sigla": "RJ", "nome": "Rio de Janeiro", "regiao": "Sudeste", "pop": 16_055_174, "pib_bi": 949.0, "receita_bi": 108.0, "despesa_bi": 106.0, "saude_bi": 11.2, "educacao_bi": 10.5, "rcl_pessoal": 50.8, "divida_bi": 175.0},
    {"cod_ibge": "35", "sigla": "SP", "nome": "São Paulo", "regiao": "Sudeste", "pop": 44_411_238, "pib_bi": 3120.0, "receita_bi": 315.0, "despesa_bi": 302.0, "saude_bi": 33.5, "educacao_bi": 42.0, "rcl_pessoal": 41.5, "divida_bi": 280.0},

    # Sul
    {"cod_ibge": "41", "sigla": "PR", "nome": "Paraná", "regiao": "Sul", "pop": 11_444_380, "pib_bi": 550.0, "receita_bi": 68.5, "despesa_bi": 65.0, "saude_bi": 7.8, "educacao_bi": 9.8, "rcl_pessoal": 42.3, "divida_bi": 28.0},
    {"cod_ibge": "42", "sigla": "SC", "nome": "Santa Catarina", "regiao": "Sul", "pop": 7_610_361, "pib_bi": 428.0, "receita_bi": 47.0, "despesa_bi": 44.5, "saude_bi": 5.9, "educacao_bi": 6.8, "rcl_pessoal": 43.1, "divida_bi": 18.5},
    {"cod_ibge": "43", "sigla": "RS", "nome": "Rio Grande do Sul", "regiao": "Sul", "pop": 10_882_965, "pib_bi": 581.0, "receita_bi": 66.0, "despesa_bi": 64.8, "saude_bi": 6.5, "educacao_bi": 7.2, "rcl_pessoal": 49.8, "divida_bi": 95.0},

    # Centro-Oeste
    {"cod_ibge": "50", "sigla": "MS", "nome": "Mato Grosso do Sul", "regiao": "Centro-Oeste", "pop": 2_757_013, "pib_bi": 142.0, "receita_bi": 24.5, "despesa_bi": 23.0, "saude_bi": 2.9, "educacao_bi": 3.4, "rcl_pessoal": 42.7, "divida_bi": 9.2},
    {"cod_ibge": "51", "sigla": "MT", "nome": "Mato Grosso", "regiao": "Centro-Oeste", "pop": 3_658_649, "pib_bi": 233.0, "receita_bi": 34.0, "despesa_bi": 31.5, "saude_bi": 4.1, "educacao_bi": 4.8, "rcl_pessoal": 38.4, "divida_bi": 8.0},
    {"cod_ibge": "52", "sigla": "GO", "nome": "Goiás", "regiao": "Centro-Oeste", "pop": 7_056_495, "pib_bi": 269.0, "receita_bi": 42.0, "despesa_bi": 40.2, "saude_bi": 4.8, "educacao_bi": 5.5, "rcl_pessoal": 45.9, "divida_bi": 22.0},
    {"cod_ibge": "53", "sigla": "DF", "nome": "Distrito Federal", "regiao": "Centro-Oeste", "pop": 2_817_381, "pib_bi": 286.0, "receita_bi": 35.5, "despesa_bi": 34.0, "saude_bi": 5.8, "educacao_bi": 6.2, "rcl_pessoal": 44.0, "divida_bi": 12.5},
]

MUNICIPIOS_POLO = [
    {"cod_ibge": "3550308", "sigla": "SP", "cod_uf": "35", "nome": "São Paulo", "regiao": "Sudeste", "pop": 11_451_245, "receita_bi": 105.0, "despesa_bi": 101.0, "saude_bi": 19.5, "educacao_bi": 21.0},
    {"cod_ibge": "3304557", "sigla": "RJ", "cod_uf": "33", "nome": "Rio de Janeiro", "regiao": "Sudeste", "pop": 6_211_423, "receita_bi": 42.0, "despesa_bi": 40.5, "saude_bi": 8.5, "educacao_bi": 7.9},
    {"cod_ibge": "3106200", "sigla": "MG", "cod_uf": "31", "nome": "Belo Horizonte", "regiao": "Sudeste", "pop": 2_315_560, "receita_bi": 18.5, "despesa_bi": 17.9, "saude_bi": 5.2, "educacao_bi": 4.1},
    {"cod_ibge": "2927408", "sigla": "BA", "cod_uf": "29", "nome": "Salvador", "regiao": "Nordeste", "pop": 2_418_005, "receita_bi": 11.8, "despesa_bi": 11.2, "saude_bi": 2.8, "educacao_bi": 2.5},
    {"cod_ibge": "4106902", "sigla": "PR", "cod_uf": "41", "nome": "Curitiba", "regiao": "Sul", "pop": 1_773_733, "receita_bi": 12.4, "despesa_bi": 11.9, "saude_bi": 2.9, "educacao_bi": 2.6},
    {"cod_ibge": "4314902", "sigla": "RS", "cod_uf": "43", "nome": "Porto Alegre", "regiao": "Sul", "pop": 1_332_570, "receita_bi": 11.0, "despesa_bi": 10.7, "saude_bi": 2.5, "educacao_bi": 2.2},
    {"cod_ibge": "5300108", "sigla": "DF", "cod_uf": "53", "nome": "Brasília", "regiao": "Centro-Oeste", "pop": 2_817_381, "receita_bi": 35.5, "despesa_bi": 34.0, "saude_bi": 5.8, "educacao_bi": 6.2},
]


def carregar_dados_federativos() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Gera dados harmonizados para dim_ente, dim_metrica, indicador_ente, financas_ente, despesa_funcao, indicador_fiscal, transferencia_uniao."""
    
    # 1. Dimensão Ente (Brasil + 27 UFs + Polos)
    entes = [{
        "cod_ibge": "0", "nivel": "pais", "nome": "Brasil",
        "sigla_uf": "BR", "cod_uf": "0", "regiao": "Nacional", "cod_regiao": "0"
    }]
    for e in ESTADOS_BRASIL:
        entes.append({
            "cod_ibge": e["cod_ibge"], "nivel": "estado", "nome": e["nome"],
            "sigla_uf": e["sigla"], "cod_uf": e["cod_ibge"], "regiao": e["regiao"], "cod_regiao": e["cod_ibge"][:1]
        })
    for m in MUNICIPIOS_POLO:
        entes.append({
            "cod_ibge": m["cod_ibge"], "nivel": "municipio", "nome": m["nome"],
            "sigla_uf": m["sigla"], "cod_uf": m["cod_uf"], "regiao": m["regiao"], "cod_regiao": m["cod_uf"][:1]
        })

    # 2. Dimensão Métrica
    metricas = [
        {"cod_metrica": "despesa_per_capita", "rotulo": "Despesas Empenhadas por habitante", "unidade": "R$/hab", "fonte_origem": "siconfi"},
        {"cod_metrica": "despesa_total", "rotulo": "Despesas Empenhadas totais", "unidade": "R$", "fonte_origem": "siconfi"},
        {"cod_metrica": "receita_total", "rotulo": "Receitas Realizadas totais", "unidade": "R$", "fonte_origem": "siconfi"},
        {"cod_metrica": "receita_per_capita", "rotulo": "Receitas Realizadas por habitante", "unidade": "R$/hab", "fonte_origem": "siconfi"},
        {"cod_metrica": "populacao", "rotulo": "População Residente", "unidade": "habitantes", "fonte_origem": "ibge"},
        {"cod_metrica": "transferencia_recebida", "rotulo": "Transferências Recebidas", "unidade": "R$", "fonte_origem": "siconfi"},
        {"cod_metrica": "transferencia_uniao", "rotulo": "Transferências da União", "unidade": "R$", "fonte_origem": "tesouro"},
        {"cod_metrica": "dependencia_transferencia", "rotulo": "Dependência de Transferências", "unidade": "%", "fonte_origem": "siconfi"},
        {"cod_metrica": "despesa_saude", "rotulo": "Despesa com Saúde", "unidade": "R$", "fonte_origem": "siconfi"},
        {"cod_metrica": "saude_per_capita", "rotulo": "Despesa com Saúde por habitante", "unidade": "R$/hab", "fonte_origem": "siconfi"},
        {"cod_metrica": "despesa_educacao", "rotulo": "Despesa com Educação", "unidade": "R$", "fonte_origem": "siconfi"},
        {"cod_metrica": "educacao_per_capita", "rotulo": "Despesa com Educação por habitante", "unidade": "R$/hab", "fonte_origem": "siconfi"},
        {"cod_metrica": "percentual_pessoal", "rotulo": "Gasto com Pessoal / RCL", "unidade": "%", "fonte_origem": "siconfi"},
        {"cod_metrica": "divida_liquida", "rotulo": "Dívida Consolidada Líquida", "unidade": "R$", "fonte_origem": "sadipem"},
    ]

    # 3. Indicadores (População) e Fatos (Finanças, Funções, Fiscal, Repasses)
    anos = [2020, 2021, 2022, 2023, 2024]
    indicadores = []
    financas = []
    despesas_funcao = []
    indicadores_fiscais = []
    transferencias_uniao = []

    for ano in anos:
        fator_ano = 1.0 + (ano - 2020) * 0.055  # Correção inflacionária/crescimento
        
        # Brasil
        pop_br = 203_080_756
        indicadores.append({
            "cod_ibge": "0", "cod_metrica": "populacao", "ano": ano,
            "periodo": "1", "valor": float(pop_br), "sigla_uf": "BR"
        })
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 2_150_000_000_000.0 * fator_ano,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 2_080_000_000_000.0 * fator_ano,
            "data_referencia": f"{ano}-12-31"
        })

        # 27 Estados
        for est in ESTADOS_BRASIL:
            ibge = est["cod_ibge"]
            sigla = est["sigla"]
            pop = float(est["pop"])
            rec = est["receita_bi"] * 1_000_000_000.0 * fator_ano
            desp = est["despesa_bi"] * 1_000_000_000.0 * fator_ano
            saude = est["saude_bi"] * 1_000_000_000.0 * fator_ano
            educ = est["educacao_bi"] * 1_000_000_000.0 * fator_ano
            divida = est["divida_bi"] * 1_000_000_000.0 * fator_ano
            transf = rec * 0.28  # Média de transferências

            # População
            indicadores.append({
                "cod_ibge": ibge, "cod_metrica": "populacao", "ano": ano,
                "periodo": "1", "valor": pop, "sigla_uf": sigla
            })

            # Receitas Realizadas
            financas.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "1", "esfera": "estadual", "uf": sigla,
                "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
                "estagio": "Receitas Realizadas", "valor": rec,
                "data_referencia": f"{ano}-12-31"
            })
            # Despesas Empenhadas
            financas.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "1", "esfera": "estadual", "uf": sigla,
                "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
                "estagio": "Despesas Empenhadas", "valor": desp,
                "data_referencia": f"{ano}-12-31"
            })
            # Transferências Recebidas (Finanças)
            financas.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "1", "esfera": "estadual", "uf": sigla,
                "cod_conta": "RO1.7.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Transferências Correntes",
                "estagio": "Receitas Realizadas", "valor": transf,
                "data_referencia": f"{ano}-12-31"
            })

            # Despesa por Função: Saúde (10) e Educação (12)
            despesas_funcao.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "1",
                "cod_conta": "FU10.0", "cod_funcao": "10", "funcao": "Saúde",
                "cod_funcao_mae": None, "funcao_mae": None, "rotulo_conta": "Saúde",
                "bloco": "exceto_intra", "descricao_bloco": "Despesas Exceto Intraorçamentárias",
                "estagio": "Despesas Pagas", "valor": saude, "esfera": "estadual", "uf": sigla,
                "data_referencia": f"{ano}-12-31"
            })
            despesas_funcao.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "1",
                "cod_conta": "FU12.0", "cod_funcao": "12", "funcao": "Educação",
                "cod_funcao_mae": None, "funcao_mae": None, "rotulo_conta": "Educação",
                "bloco": "exceto_intra", "descricao_bloco": "Despesas Exceto Intraorçamentárias",
                "estagio": "Despesas Pagas", "valor": educ, "esfera": "estadual", "uf": sigla,
                "data_referencia": f"{ano}-12-31"
            })

            # Indicadores Fiscais (LRF Pessoal e Dívida)
            indicadores_fiscais.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "3", "poder": "E",
                "indicador": "DTP", "medida": "percentual_rcl", "rotulo": "% da Despesa com Pessoal sobre RCL",
                "secao": "Pessoal", "anexo": "RGF-Anexo 01",
                "valor": est["rcl_pessoal"], "esfera": "estadual", "uf": sigla,
                "data_referencia": f"{ano}-12-31"
            })
            indicadores_fiscais.append({
                "cod_ibge": ibge, "ano": ano, "periodo": "3", "poder": "E",
                "indicador": "DCL", "medida": "saldo", "rotulo": "Dívida Consolidada Líquida",
                "secao": "Dívida", "anexo": "RGF-Anexo 02",
                "valor": divida, "esfera": "estadual", "uf": sigla,
                "data_referencia": f"{ano}-12-31"
            })

            # Transferências da União
            transferencias_uniao.append({
                "cod_ibge": ibge, "nivel": "estado", "uf": sigla,
                "nome_ente": est["nome"], "cod_transferencia": "FPE",
                "transferencia": "Fundo de Participação dos Estados",
                "ano": ano, "mes": 12, "valor": transf * 0.6,
                "cod_siafi": None, "data_referencia": f"{ano}-12-31"
            })
            transferencias_uniao.append({
                "cod_ibge": ibge, "nivel": "estado", "uf": sigla,
                "nome_ente": est["nome"], "cod_transferencia": "SUS",
                "transferencia": "Repasses Fundo a Fundo SUS",
                "ano": ano, "mes": 12, "valor": transf * 0.25,
                "cod_siafi": None, "data_referencia": f"{ano}-12-31"
            })

        # Municípios Polo
        for mun in MUNICIPIOS_POLO:
            ibge_m = mun["cod_ibge"]
            sigla_m = mun["sigla"]
            pop_m = float(mun["pop"])
            rec_m = mun["receita_bi"] * 1_000_000_000.0 * fator_ano
            desp_m = mun["despesa_bi"] * 1_000_000_000.0 * fator_ano
            saude_m = mun["saude_bi"] * 1_000_000_000.0 * fator_ano
            educ_m = mun["educacao_bi"] * 1_000_000_000.0 * fator_ano

            indicadores.append({
                "cod_ibge": ibge_m, "cod_metrica": "populacao", "ano": ano,
                "periodo": "1", "valor": pop_m, "sigla_uf": sigla_m
            })
            financas.append({
                "cod_ibge": ibge_m, "ano": ano, "periodo": "1", "esfera": "municipal", "uf": sigla_m,
                "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
                "estagio": "Receitas Realizadas", "valor": rec_m, "data_referencia": f"{ano}-12-31"
            })
            financas.append({
                "cod_ibge": ibge_m, "ano": ano, "periodo": "1", "esfera": "municipal", "uf": sigla_m,
                "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
                "estagio": "Despesas Empenhadas", "valor": desp_m, "data_referencia": f"{ano}-12-31"
            })
            despesas_funcao.append({
                "cod_ibge": ibge_m, "ano": ano, "periodo": "1",
                "cod_conta": "FU10.0", "cod_funcao": "10", "funcao": "Saúde",
                "cod_funcao_mae": None, "funcao_mae": None, "rotulo_conta": "Saúde",
                "bloco": "exceto_intra", "descricao_bloco": "Despesas Exceto Intraorçamentárias",
                "estagio": "Despesas Pagas", "valor": saude_m, "esfera": "municipal", "uf": sigla_m,
                "data_referencia": f"{ano}-12-31"
            })
            despesas_funcao.append({
                "cod_ibge": ibge_m, "ano": ano, "periodo": "1",
                "cod_conta": "FU12.0", "cod_funcao": "12", "funcao": "Educação",
                "cod_funcao_mae": None, "funcao_mae": None, "rotulo_conta": "Educação",
                "bloco": "exceto_intra", "descricao_bloco": "Despesas Exceto Intraorçamentárias",
                "estagio": "Despesas Pagas", "valor": educ_m, "esfera": "municipal", "uf": sigla_m,
                "data_referencia": f"{ano}-12-31"
            })

    return entes, metricas, indicadores, financas, despesas_funcao, indicadores_fiscais, transferencias_uniao


def garantir_malha_brasil() -> None:
    """Assegura a presença do GeoJSON da malha do Brasil em dados/malhas/brasil-uf.json."""
    origem = config.RAIZ / "referencias" / "malhas" / "brasil-uf.json"
    destino = config.MALHAS / "brasil-uf.json" if config.MALHAS is not None else Path("dados/malhas/brasil-uf.json")
    destino.parent.mkdir(parents=True, exist_ok=True)

    if not destino.exists() and origem.exists():
        shutil.copy(origem, destino)
