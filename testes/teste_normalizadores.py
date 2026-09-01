"""Testes para o módulo de normalização de nomes e geração de códigos internos."""

import pytest
from src.nucleo.normalizadores import (
    remover_acentos,
    gerar_slug_codigo,
    normalizar_nome_proprio,
    gerar_cod_cargo_interno,
    gerar_cod_politico_interno,
    gerar_cod_magistrado_interno,
    gerar_cod_ministro_estado_interno,
)


def test_remover_acentos():
    assert remover_acentos("Luiz Inácio Lula da Silva") == "Luiz Inacio Lula da Silva"
    assert remover_acentos("Tarcísio") == "Tarcisio"
    assert remover_acentos("Cármen Lúcia") == "Carmen Lucia"
    assert remover_acentos("") == ""


def test_gerar_slug_codigo():
    assert gerar_slug_codigo("Luiz Inácio Lula da Silva") == "LUIZ_INACIO_LULA_DA_SILVA"
    assert gerar_slug_codigo("Alexandre de Moraes") == "ALEXANDRE_DE_MORAES"
    assert gerar_slug_codigo("Ministério da Fazenda") == "MINISTERIO_DA_FAZENDA"
    assert gerar_slug_codigo("  São   Paulo - SP  ") == "SAO_PAULO_SP"
    assert gerar_slug_codigo(None) == ""


def test_normalizar_nome_proprio():
    # Casos com preposições em minúsculas
    assert normalizar_nome_proprio("LUIZ INACIO LULA DA SILVA") == "Luiz Inacio Lula da Silva"
    assert normalizar_nome_proprio("ALEXANDRE DE MORAES") == "Alexandre de Moraes"
    assert normalizar_nome_proprio("TARCISIO GOMES DE FREITAS") == "Tarcisio Gomes de Freitas"
    assert normalizar_nome_proprio("FERNANDO HENRIQUE CARDOSO") == "Fernando Henrique Cardoso"

    # Preposição no início da frase mantém maiúscula
    assert normalizar_nome_proprio("DE SOUZA SILVA") == "De Souza Silva"

    # Numerais romanos
    assert normalizar_nome_proprio("DOM PEDRO II") == "Dom Pedro II"
    assert normalizar_nome_proprio("PAPA JOAO PAULO II") == "Papa Joao Paulo II"
    assert normalizar_nome_proprio("ENCONTRO NACIONAL IV") == "Encontro Nacional IV"

    # Siglas conhecidas
    assert normalizar_nome_proprio("PRESIDENTE DO STF") == "Presidente do STF"
    assert normalizar_nome_proprio("TRIBUNAL REGIONAL DO TRF3") == "Tribunal Regional do TRF3"

    # Apóstrofo
    assert normalizar_nome_proprio("MANUELA D'AVILA") == "Manuela D'Avila"
    assert normalizar_nome_proprio("CARLOS SANT'ANNA") == "Carlos Sant'Anna"

    # Sufixos
    assert normalizar_nome_proprio("ANTONIO CARLOS MAGALHAES NETO") == "Antonio Carlos Magalhaes Neto"
    assert normalizar_nome_proprio("JOSE SARNEY FILHO") == "Jose Sarney Filho"

    # Casos nulos ou vazios
    assert normalizar_nome_proprio("") == ""
    assert normalizar_nome_proprio(None) == ""
    assert normalizar_nome_proprio("   ") == ""


def test_gerar_cod_cargo_interno():
    assert gerar_cod_cargo_interno("presidente", "executivo", "federal") == "CAR_EXEC_FED_PRESIDENTE"
    assert gerar_cod_cargo_interno("governador", "executivo", "estadual", uf="SP") == "CAR_EXEC_EST_GOVERNADOR_SP"
    assert gerar_cod_cargo_interno("prefeito", "executivo", "municipal", cod_ibge="3550308") == "CAR_EXEC_MUN_PREFEITO_3550308"
    assert gerar_cod_cargo_interno("senador", "legislativo", "federal", uf="RJ") == "CAR_LEG_FED_SENADOR"
    assert gerar_cod_cargo_interno("deputado_estadual", "legislativo", "estadual", uf="MG") == "CAR_LEG_EST_DEPUTADO_ESTADUAL_MG"
    assert gerar_cod_cargo_interno("ministro_stf", "judiciario", "federal") == "CAR_JUD_FED_MINISTRO_STF"


def test_gerar_cod_politico_interno():
    assert gerar_cod_politico_interno("LUIZ INÁCIO LULA DA SILVA") == "POL_LUIZ_INACIO_LULA_DA_SILVA"
    assert gerar_cod_politico_interno("Jair Messias Bolsonaro") == "POL_JAIR_MESSIAS_BOLSONARO"
    assert gerar_cod_politico_interno("Tarcísio Gomes de Freitas") == "POL_TARCISIO_GOMES_DE_FREITAS"


def test_gerar_cod_magistrado_interno():
    assert gerar_cod_magistrado_interno("Alexandre de Moraes", "STF") == "MAG_STF_ALEXANDRE_DE_MORAES"
    assert gerar_cod_magistrado_interno("Luís Roberto Barroso", "STF") == "MAG_STF_LUIS_ROBERTO_BARROSO"
    assert gerar_cod_magistrado_interno("Cármen Lúcia Antunes Rocha", "STF") == "MAG_STF_CARMEN_LUCIA_ANTUNES_ROCHA"


def test_gerar_cod_ministro_estado_interno():
    assert gerar_cod_ministro_estado_interno("Fazenda", "Fernando Haddad") == "MIN_EST_FAZENDA_FERNANDO_HADDAD"
    assert gerar_cod_ministro_estado_interno("Justiça e Segurança Pública") == "MIN_EST_JUSTICA_E_SEGURANCA_PUBLICA"
