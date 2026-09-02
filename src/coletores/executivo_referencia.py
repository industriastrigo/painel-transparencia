'''Carga de referência histórica dos chefes do Poder Executivo (Presidente e Governadores).

Garante que o Presidente da República e governadores históricos de todos os exercícios
estejam cadastrados em `dim_politico` e `mandato`, com o código IBGE e datas corretas.
'''

from __future__ import annotations

from typing import Any

from ..nucleo import armazem

PRESIDENTES_HISTORICO: list[dict[str, Any]] = [
    {
        "nome": "LUIZ INÁCIO LULA DA SILVA",
        "nome_urna": "LULA",
        "partido": "PT",
        "ano_inicio": 2023,
        "ano_fim": 2027,
        "data_inicio": "2023-01-01",
        "ano_eleicao": 2022,
    },
    {
        "nome": "JAIR MESSIAS BOLSONARO",
        "nome_urna": "JAIR BOLSONARO",
        "partido": "PL",
        "ano_inicio": 2019,
        "ano_fim": 2022,
        "data_inicio": "2019-01-01",
        "ano_eleicao": 2018,
    },
    {
        "nome": "MICHEL MIGUEL ELIAS TEMER LULIA",
        "nome_urna": "MICHEL TEMER",
        "partido": "MDB",
        "ano_inicio": 2016,
        "ano_fim": 2018,
        "data_inicio": "2016-08-31",
        "ano_eleicao": 2014,
    },
    {
        "nome": "DILMA VANA ROUSSEFF",
        "nome_urna": "DILMA ROUSSEFF",
        "partido": "PT",
        "ano_inicio": 2015,
        "ano_fim": 2016,
        "data_inicio": "2015-01-01",
        "ano_eleicao": 2014,
    },
    {
        "nome": "DILMA VANA ROUSSEFF",
        "nome_urna": "DILMA ROUSSEFF",
        "partido": "PT",
        "ano_inicio": 2011,
        "ano_fim": 2014,
        "data_inicio": "2011-01-01",
        "ano_eleicao": 2010,
    },
    {
        "nome": "LUIZ INÁCIO LULA DA SILVA",
        "nome_urna": "LULA",
        "partido": "PT",
        "ano_inicio": 2007,
        "ano_fim": 2010,
        "data_inicio": "2007-01-01",
        "ano_eleicao": 2006,
    },
    {
        "nome": "LUIZ INÁCIO LULA DA SILVA",
        "nome_urna": "LULA",
        "partido": "PT",
        "ano_inicio": 2003,
        "ano_fim": 2006,
        "data_inicio": "2003-01-01",
        "ano_eleicao": 2002,
    },
    {
        "nome": "FERNANDO HENRIQUE CARDOSO",
        "nome_urna": "FERNANDO HENRIQUE CARDOSO",
        "partido": "PSDB",
        "ano_inicio": 1999,
        "ano_fim": 2002,
        "data_inicio": "1999-01-01",
        "ano_eleicao": 1998,
    },
    {
        "nome": "FERNANDO HENRIQUE CARDOSO",
        "nome_urna": "FERNANDO HENRIQUE CARDOSO",
        "partido": "PSDB",
        "ano_inicio": 1995,
        "ano_fim": 1998,
        "data_inicio": "1995-01-01",
        "ano_eleicao": 1994,
    },
    {
        "nome": "ITAMAR AUGUSTO CAUTIERO FRANCO",
        "nome_urna": "ITAMAR FRANCO",
        "partido": "PMDB",
        "ano_inicio": 1992,
        "ano_fim": 1994,
        "data_inicio": "1992-12-29",
        "ano_eleicao": 1989,
    },
    {
        "nome": "FERNANDO AFFONSO COLLOR DE MELLO",
        "nome_urna": "FERNANDO COLLOR",
        "partido": "PRN",
        "ano_inicio": 1990,
        "ano_fim": 1992,
        "data_inicio": "1990-03-15",
        "ano_eleicao": 1989,
    },
    {
        "nome": "JOSÉ RIBAMAR FERREIRA DE ARAÚJO COSTA",
        "nome_urna": "JOSÉ SARNEY",
        "partido": "PMDB",
        "ano_inicio": 1985,
        "ano_fim": 1990,
        "data_inicio": "1985-03-15",
        "ano_eleicao": 1985,
    },
]

# Governadores 2023-2026
GOVERNADORES_2023_2026: list[dict[str, Any]] = [
    {"uf": "AC", "cod_ibge": "12", "nome": "GLADSON DE LIMA CAMELI", "nome_urna": "GLADSON CAMELI", "partido": "PP", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "AL", "cod_ibge": "27", "nome": "PAULO SURUAGY DO AMARAL DANTAS", "nome_urna": "PAULO DANTAS", "partido": "MDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "AP", "cod_ibge": "16", "nome": "CLÉCIO LUÍS VILHENA VIEIRA", "nome_urna": "CLÉCIO LUÍS", "partido": "SOLIDARIEDADE", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "AM", "cod_ibge": "13", "nome": "WILSON MIRANDA LIMA", "nome_urna": "WILSON LIMA", "partido": "UNIÃO", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "BA", "cod_ibge": "29", "nome": "JERÔNIMO RODRIGUES SOUZA", "nome_urna": "JERÔNIMO RODRIGUES", "partido": "PT", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "CE", "cod_ibge": "23", "nome": "ELMANO DE FREITAS DA COSTA", "nome_urna": "ELMANO DE FREITAS", "partido": "PT", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "DF", "cod_ibge": "53", "nome": "IBANEIS ROCHA BARROS JUNIOR", "nome_urna": "IBANEIS ROCHA", "partido": "MDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "ES", "cod_ibge": "32", "nome": "RENATO CASAGRANDE", "nome_urna": "RENATO CASAGRANDE", "partido": "PSB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "GO", "cod_ibge": "52", "nome": "RONALDO RAMOS CAIADO", "nome_urna": "RONALDO CAIADO", "partido": "UNIÃO", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "MA", "cod_ibge": "21", "nome": "CARLOS ORLEANS BRANDÃO JÚNIOR", "nome_urna": "CARLOS BRANDÃO", "partido": "PSB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "MT", "cod_ibge": "51", "nome": "MAURO MENDES FERREIRA", "nome_urna": "MAURO MENDES", "partido": "UNIÃO", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "MS", "cod_ibge": "50", "nome": "EDUARDO CORRÊA RIEDEL", "nome_urna": "EDUARDO RIEDEL", "partido": "PSDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "MG", "cod_ibge": "31", "nome": "ROMEU ZEMA NETO", "nome_urna": "ROMEU ZEMA", "partido": "NOVO", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "PA", "cod_ibge": "15", "nome": "HELDER ZAHLUTH BARBALHO", "nome_urna": "HELDER BARBALHO", "partido": "MDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "PB", "cod_ibge": "25", "nome": "JOÃO AZEVÊDO LINS FILHO", "nome_urna": "JOÃO AZEVÊDO", "partido": "PSB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "PR", "cod_ibge": "41", "nome": "CARLOS ROBERTO MASSA JUNIOR", "nome_urna": "RATINHO JÚNIOR", "partido": "PSD", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "PE", "cod_ibge": "26", "nome": "RAQUEL TEIXEIRA LYRA LUCENA", "nome_urna": "RAQUEL LYRA", "partido": "PSDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "PI", "cod_ibge": "22", "nome": "RAFAEL TAJRA FONTELES", "nome_urna": "RAFAEL FONTELES", "partido": "PT", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "RJ", "cod_ibge": "33", "nome": "CLÁUDIO BOMFIM DE CASTRO E SILVA", "nome_urna": "CLÁUDIO CASTRO", "partido": "PL", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "RN", "cod_ibge": "24", "nome": "MARIA DE FÁTIMA BEZERRA", "nome_urna": "FÁTIMA BEZERRA", "partido": "PT", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "RS", "cod_ibge": "43", "nome": "EDUARDO FIGUEIREDO CAVALHEIRO LEITE", "nome_urna": "EDUARDO LEITE", "partido": "PSDB", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "RO", "cod_ibge": "11", "nome": "MARCOS JOSÉ ROCHA DOS SANTOS", "nome_urna": "CORONEL MARCOS ROCHA", "partido": "UNIÃO", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "RR", "cod_ibge": "14", "nome": "ANTONIO OLIVERIO GARCIA DE ALMEIDA", "nome_urna": "ANTONIO DENARIUM", "partido": "PP", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "SC", "cod_ibge": "42", "nome": "JORGINHO DOS SANTOS MELLO", "nome_urna": "JORGINHO MELLO", "partido": "PL", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "SP", "cod_ibge": "35", "nome": "TARCÍSIO GOMES DE FREITAS", "nome_urna": "TARCÍSIO DE FREITAS", "partido": "REPUBLICANOS", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "SE", "cod_ibge": "28", "nome": "FÁBIO CRUZ MITIDIERI", "nome_urna": "FÁBIO MITIDIERI", "partido": "PSD", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
    {"uf": "TO", "cod_ibge": "17", "nome": "WANDERLEI BARBOSA CASTRO", "nome_urna": "WANDERLEI BARBOSA", "partido": "REPUBLICANOS", "ano_inicio": 2023, "ano_fim": 2027, "data_inicio": "2023-01-01", "ano_eleicao": 2022},
]

# Governadores 2019-2022
GOVERNADORES_2019_2022: list[dict[str, Any]] = [
    {"uf": "SP", "cod_ibge": "35", "nome": "JOÃO AGRIPINO DA COSTA DORIA JUNIOR", "nome_urna": "JOÃO DORIA", "partido": "PSDB", "ano_inicio": 2019, "ano_fim": 2022, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
    {"uf": "RJ", "cod_ibge": "33", "nome": "WILSON JOSÉ WITZEL", "nome_urna": "WILSON WITZEL", "partido": "PSC", "ano_inicio": 2019, "ano_fim": 2021, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
    {"uf": "MG", "cod_ibge": "31", "nome": "ROMEU ZEMA NETO", "nome_urna": "ROMEU ZEMA", "partido": "NOVO", "ano_inicio": 2019, "ano_fim": 2022, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
    {"uf": "BA", "cod_ibge": "29", "nome": "RUI COSTA DOS SANTOS", "nome_urna": "RUI COSTA", "partido": "PT", "ano_inicio": 2019, "ano_fim": 2022, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
    {"uf": "RS", "cod_ibge": "43", "nome": "EDUARDO FIGUEIREDO CAVALHEIRO LEITE", "nome_urna": "EDUARDO LEITE", "partido": "PSDB", "ano_inicio": 2019, "ano_fim": 2022, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
    {"uf": "PR", "cod_ibge": "41", "nome": "CARLOS ROBERTO MASSA JUNIOR", "nome_urna": "RATINHO JÚNIOR", "partido": "PSD", "ano_inicio": 2019, "ano_fim": 2022, "data_inicio": "2019-01-01", "ano_eleicao": 2018},
]

# Governadores 2015-2018
GOVERNADORES_2015_2018: list[dict[str, Any]] = [
    {"uf": "SP", "cod_ibge": "35", "nome": "GERALDO JOSÉ RODRIGUES ALCKMIN FILHO", "nome_urna": "GERALDO ALCKMIN", "partido": "PSDB", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
    {"uf": "RJ", "cod_ibge": "33", "nome": "LUIZ FERNANDO DE SOUZA", "nome_urna": "PEZÃO", "partido": "PMDB", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
    {"uf": "MG", "cod_ibge": "31", "nome": "FERNANDO DAMATA PIMENTEL", "nome_urna": "FERNANDO PIMENTEL", "partido": "PT", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
    {"uf": "BA", "cod_ibge": "29", "nome": "RUI COSTA DOS SANTOS", "nome_urna": "RUI COSTA", "partido": "PT", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
    {"uf": "RS", "cod_ibge": "43", "nome": "JOSÉ IVO SARTORI", "nome_urna": "JOSÉ IVO SARTORI", "partido": "PMDB", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
    {"uf": "PR", "cod_ibge": "41", "nome": "CARLOS ALBERTO RICHA", "nome_urna": "BETO RICHA", "partido": "PSDB", "ano_inicio": 2015, "ano_fim": 2018, "data_inicio": "2015-01-01", "ano_eleicao": 2014},
]

# Governadores 2011-2014
GOVERNADORES_2011_2014: list[dict[str, Any]] = [
    {"uf": "SP", "cod_ibge": "35", "nome": "GERALDO JOSÉ RODRIGUES ALCKMIN FILHO", "nome_urna": "GERALDO ALCKMIN", "partido": "PSDB", "ano_inicio": 2011, "ano_fim": 2014, "data_inicio": "2011-01-01", "ano_eleicao": 2010},
    {"uf": "RJ", "cod_ibge": "33", "nome": "SÉRGIO DE OLIVEIRA CABRAL SANTOS FILHO", "nome_urna": "SÉRGIO CABRAL", "partido": "PMDB", "ano_inicio": 2011, "ano_fim": 2014, "data_inicio": "2011-01-01", "ano_eleicao": 2010},
    {"uf": "MG", "cod_ibge": "31", "nome": "ANTONIO AUGUSTO JUNHO ANASTASIA", "nome_urna": "ANTONIO ANASTASIA", "partido": "PSDB", "ano_inicio": 2011, "ano_fim": 2014, "data_inicio": "2011-01-01", "ano_eleicao": 2010},
    {"uf": "BA", "cod_ibge": "29", "nome": "JAQUES WAGNER", "nome_urna": "JAQUES WAGNER", "partido": "PT", "ano_inicio": 2011, "ano_fim": 2014, "data_inicio": "2011-01-01", "ano_eleicao": 2010},
]


def carregar_executivos_referencia() -> None:
    '''Mescla governadores e presidentes históricos nas tabelas dim_politico e mandato.'''
    politicos = []
    mandatos = []

    for p in PRESIDENTES_HISTORICO:
        sk = f"pres_{p['ano_inicio']}_{p['nome_urna'].replace(' ', '_').lower()}"
        politicos.append({
            "sk_politico": sk,
            "fonte_origem": "tse",
            "id_origem": sk,
            "nome": p["nome"],
            "nome_eleitoral": p["nome_urna"],
            "cargo": "presidente",
            "cod_cargo": "presidente",
            "sigla_partido": p["partido"],
            "sigla_uf": "BR",
            "cod_ibge": "0",
            "cod_municipio_tse": None,
            "url_foto": None,
            "situacao": "eleito",
        })
        mandatos.append({
            "sk_politico": sk,
            "cod_cargo": "presidente",
            "cargo": "presidente",
            "cod_ue": "0",
            "cod_ibge": "0",
            "sigla_uf": "BR",
            "nome_ente": "Brasil",
            "nome": p["nome"],
            "sigla_partido": p["partido"],
            "ano_inicio": p["ano_inicio"],
            "ano_fim": p["ano_fim"],
            "data_inicio": p["data_inicio"],
            "ano_eleicao": p["ano_eleicao"],
        })

    todos_govs = GOVERNADORES_2023_2026 + GOVERNADORES_2019_2022 + GOVERNADORES_2015_2018 + GOVERNADORES_2011_2014
    for g in todos_govs:
        sk = f"gov_{g['uf']}_{g['ano_inicio']}_{g['nome_urna'].replace(' ', '_').lower()}"
        politicos.append({
            "sk_politico": sk,
            "fonte_origem": "tse",
            "id_origem": sk,
            "nome": g["nome"],
            "nome_eleitoral": g["nome_urna"],
            "cargo": "governador",
            "cod_cargo": "governador",
            "sigla_partido": g["partido"],
            "sigla_uf": g["uf"],
            "cod_ibge": g["cod_ibge"],
            "cod_municipio_tse": None,
            "url_foto": None,
            "situacao": "eleito",
        })
        mandatos.append({
            "sk_politico": sk,
            "cod_cargo": "governador",
            "cargo": "governador",
            "cod_ue": g["uf"],
            "cod_ibge": g["cod_ibge"],
            "sigla_uf": g["uf"],
            "nome_ente": f"Estado de {g['uf']}",
            "nome": g["nome"],
            "sigla_partido": g["partido"],
            "ano_inicio": g["ano_inicio"],
            "ano_fim": g["ano_fim"],
            "data_inicio": g["data_inicio"],
            "ano_eleicao": g["ano_eleicao"],
        })

    armazem.mesclar("dim_politico", politicos, "referencia_executivo")
    armazem.mesclar("mandato", mandatos, "referencia_executivo")
