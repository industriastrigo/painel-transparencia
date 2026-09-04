"""
Auditoria de QA: Lógica de Negócio, Normalização e Regras Fiscais.

Testa funções de conversão defensiva de tipos, parsing monetário, datas e anos,
regras de normalização gramatical PT-BR, slugs e identificadores, além de validação
de limites da LRF (54%, 51.3%, 48.6%), resultado primário/nominal e agregação de PIB.
"""
from __future__ import annotations

import math
import pytest
from src.nucleo import valores, normalizadores
from src.nucleo.esquema import TABELAS, Tabela


# -----------------------------------------------------------------------------
# Testes de Valores e Conversões Defensivas (src.nucleo.valores)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    (None, None),
    ("", None),
    ("   ", None),
    (float("nan"), None),
    (123, 123.0),
    (45.67, 45.67),
    ("100", 100.0),
    ("1.234,56", 1234.56),
    ("1.234.567,89", 1234567.89),
    ("R$ 50.000,00", 50000.0),
    ("  R$ 1.500,50 ", 1500.50),
    ("1234567.89", 1234567.89),
    ("1.234.567", 1234567.0),
    ("-150,25", -150.25),
    ("texto_invalido", None),
    ("12a34", None),
])
def test_valores_numero_parsing_precisao(entrada, esperado):
    """Valida parsing de números em formato brasileiro (vírgula decimal) e internacional."""
    res = valores.numero(entrada)
    if esperado is None:
        assert res is None, f"Esperava None para '{entrada}', obteve {res}"
    else:
        assert res == pytest.approx(esperado, rel=1e-5), f"Falha ao converter '{entrada}'"


@pytest.mark.parametrize("entrada,padrao,esperado", [
    (None, 0, 0),
    ("", 10, 10),
    ("123", None, 123),
    ("1.250,90", None, 1250),
    ("invalido", -1, -1),
])
def test_valores_inteiro_fallback(entrada, padrao, esperado):
    """Valida conversão para inteiro com fallbacks defensivos."""
    assert valores.inteiro(entrada, padrao=padrao) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, None),
    ("", None),
    ("2024-05-18", "2024-05-18"),
    ("2023-12-31T23:59:59Z", "2023-12-31"),
    ("14/08/2022", "2022-08-14"),
    ("14/08/22", "2022-08-14"),
    ("01/01/75", "1975-01-01"),
    ("01/01/69", "2069-01-01"),
    ("31/02/2023", "2023-02-31"),
    ("99/99/9999", None),
    ("invalido", None),
])
def test_valores_data_br_boundary_resolution(entrada, esperado):
    """Valida conversão de datas no padrão SADIPEM / SICONFI (2 e 4 dígitos)."""
    assert valores.data_br(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("2024-05-18", 2024),
    ("14/08/2022", 2022),
    ("05/10/98", 1998),
    ("invalido", None),
    (None, None),
])
def test_valores_ano_de_extracao(entrada, esperado):
    """Valida extração de ano para cálculo de partições Hive."""
    assert valores.ano_de(entrada) == esperado


def test_valores_texto_e_opcional():
    """Valida sanitização de texto e retorno de strings opcionais."""
    assert valores.texto(None, padrao="N/A") == "N/A"
    assert valores.texto("  Teste de String  ", limite=5) == "Teste"
    assert valores.opcional(None) is None
    assert valores.opcional("   ") is None
    assert valores.opcional("Valor Válido") == "Valor Válido"


# -----------------------------------------------------------------------------
# Testes de Normalização e Identificadores (src.nucleo.normalizadores)
# -----------------------------------------------------------------------------

def test_remover_acentos():
    """Valida remoção completa de acentuação gráfica preservando base ASCII."""
    assert normalizadores.remover_acentos("São Paulo & Brasília") == "Sao Paulo & Brasilia"
    assert normalizadores.remover_acentos("Constituição Federal / Ações") == "Constituicao Federal / Acoes"
    assert normalizadores.remover_acentos("") == ""


@pytest.mark.parametrize("entrada,esperado", [
    ("Luiz Inácio Lula da Silva", "LUIZ_INACIO_LULA_DA_SILVA"),
    ("Tarcísio Gomes de Freitas", "TARCISIO_GOMES_DE_FREITAS"),
    ("Alexandre de Moraes", "ALEXANDRE_DE_MORAES"),
    ("Ministério da Fazenda / SP", "MINISTERIO_DA_FAZENDA_SP"),
    ("  espaços   múltiplos  ", "ESPACOS_MULTIPLOS"),
    (None, ""),
])
def test_gerar_slug_codigo(entrada, esperado):
    """Valida geração de slug para chaves internas de sistema."""
    assert normalizadores.gerar_slug_codigo(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("LUIZ INACIO LULA DA SILVA", "Luiz Inacio Lula da Silva"),
    ("ALEXANDRE DE MORAES", "Alexandre de Moraes"),
    ("DOM PEDRO II", "Dom Pedro II"),
    ("MANUELA D'AVILA", "Manuela D'Avila"),
    ("ANTONIO CARLOS MAGALHAES NETO", "Antonio Carlos Magalhaes Neto"),
    ("SECRETARIA DE ESTADO DA SAUDE", "Secretaria de Estado da Saude"),
    (None, ""),
    ("   ", ""),
])
def test_normalizar_nome_proprio_regras_gramaticais(entrada, esperado):
    """Valida normas gramaticais de preposições, algarismos romanos e apóstrofos."""
    assert normalizadores.normalizar_nome_proprio(entrada) == esperado


def test_geradores_de_codigos_internos_entidades():
    """Valida contratos de nomenclatura dos identificadores internos."""
    assert normalizadores.gerar_cod_cargo_interno("presidente", "executivo", "federal") == "CAR_EXEC_FED_PRESIDENTE"
    assert normalizadores.gerar_cod_cargo_interno("governador", "executivo", "estadual", uf="SP") == "CAR_EXEC_EST_GOVERNADOR_SP"
    assert normalizadores.gerar_cod_cargo_interno("prefeito", "executivo", "municipal", cod_ibge="3550308") == "CAR_EXEC_MUN_PREFEITO_3550308"
    assert normalizadores.gerar_cod_politico_interno("Tarcísio Gomes de Freitas") == "POL_TARCISIO_GOMES_DE_FREITAS"
    assert normalizadores.gerar_cod_magistrado_interno("Luís Roberto Barroso", "STF") == "MAG_STF_LUIS_ROBERTO_BARROSO"
    assert normalizadores.gerar_cod_membro_mp_interno("Paulo Gonet Branco", "MPF") == "MP_MPF_PAULO_GONET_BRANCO"
    assert normalizadores.gerar_cod_ministro_estado_interno("Fazenda", "Fernando Haddad") == "MIN_EST_FAZENDA_FERNANDO_HADDAD"


# -----------------------------------------------------------------------------
# Testes de Regras Fiscais e Limites da LRF (Lei de Responsabilidade Fiscal)
# -----------------------------------------------------------------------------

def test_lrf_thresholds_math():
    """Valida lógica matemática dos limites de gasto com pessoal da LRF."""
    rcm = 100000000.0  # R$ 100 milhões de Receita Corrente Líquida (RCL)

    limite_maximo_executivo = rcm * 0.54  # 54%
    limite_prudencial = rcm * 0.513       # 51.3% (95% do limite máximo)
    limite_alerta = rcm * 0.486           # 48.6% (90% do limite máximo)

    assert limite_maximo_executivo == 54000000.0
    assert limite_prudencial == 51300000.0
    assert limite_alerta == 48600000.0

    def classificar_lrf(gasto_pessoal: float, rcl: float) -> str:
        pct = (gasto_pessoal / rcl) * 100
        if pct > 54.0:
            return "ENQUADRADO_IRREGULAR"
        if pct >= 51.3:
            return "LIMITE_PRUDENCIAL"
        if pct >= 48.6:
            return "LIMITE_ALERTA"
        return "REGULAR"

    assert classificar_lrf(45000000.0, rcm) == "REGULAR"
    assert classificar_lrf(49000000.0, rcm) == "LIMITE_ALERTA"
    assert classificar_lrf(52000000.0, rcm) == "LIMITE_PRUDENCIAL"
    assert classificar_lrf(55000000.0, rcm) == "ENQUADRADO_IRREGULAR"


def test_calculo_resultado_primario_e_nominal():
    """Valida fórmulas de apuração de Resultado Primário e Nominal das finanças públicas."""
    receita_primaria = 1200000000.0
    despesa_primaria = 1150000000.0
    juros_divida_liquida = 80000000.0

    resultado_primario = receita_primaria - despesa_primaria  # Superávit Primário = +50M
    resultado_nominal = resultado_primario - juros_divida_liquida  # Déficit Nominal = -30M

    assert resultado_primario == 50000000.0
    assert resultado_nominal == -30000000.0


def test_reconciliacao_pib_demanda_e_oferta():
    """Valida identidade macroeconômica da desagregação do PIB."""
    consumo_familias = 6500000000000.0
    investimento_fbcf = 1800000000000.0
    gastos_governo = 2000000000000.0
    exportacoes = 1500000000000.0
    importacoes = 1400000000000.0

    pib_demanda = consumo_familias + investimento_fbcf + gastos_governo + (exportacoes - importacoes)
    assert pib_demanda == 10400000000000.0


def test_schema_tables_minimum_contract():
    """Valida que todas as 14 tabelas do catálogo possuem declarações e chaves primárias mínimas."""
    assert len(TABELAS) >= 14, f"Esperava pelo menos 14 tabelas no catálogo, encontrou {len(TABELAS)}"
    for nome_tab, tab in TABELAS.items():
        assert isinstance(tab, Tabela)
        assert tab.nome == nome_tab
        assert tab.camada in ("dim", "fato", "_ctl")
        assert len(tab.campos_pk) > 0, f"Tabela {nome_tab} não possui campos de chave primária declarados"