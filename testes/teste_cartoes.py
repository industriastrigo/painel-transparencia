"""Testes dos módulos de Cartões Corporativos, Viagens/Diárias, Contratos e Patrimônio."""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient
from src.nucleo import armazem
from src.api.servidor import app


@pytest.fixture(scope="module")
def cliente():
    return TestClient(app)


def test_cartao_corporativo_schema_e_views(cliente):
    # Semeia transações de cartões
    armazem.remover("cartao_corporativo")
    armazem.mesclar("cartao_corporativo", [
        {
            "ano": 2025,
            "mes": 1,
            "codigo_orgao": "20000",
            "nome_orgao": "Presidência da República",
            "nome_portador": "JOAO SERVIDOR",
            "cpf_portador": "***.123.456-**",
            "nome_favorecido": "HOTEL NACIONAL LTDA",
            "cnpj_cpf_favorecido": "12.345.678/0001-90",
            "tipo_cartao": "CPGF",
            "data_transacao": "2025-01-15",
            "valor": 1500.50,
            "data_referencia": "2025-01-01",
        },
        {
            "ano": 2025,
            "mes": 2,
            "codigo_orgao": "20000",
            "nome_orgao": "Gabinete de Segurança Institucional",
            "nome_portador": "MARIA OFICIAL",
            "cpf_portador": "***.987.654-**",
            "nome_favorecido": "POSTO COMBUSTIVEL BRASIL",
            "cnpj_cpf_favorecido": "98.765.432/0001-10",
            "tipo_cartao": "CPGF",
            "data_transacao": "2025-02-20",
            "valor": 850.00,
            "data_referencia": "2025-02-01",
        },
        {
            "ano": 2025,
            "mes": 3,
            "codigo_orgao": "25000",
            "nome_orgao": "Ministério da Fazenda",
            "nome_portador": "CARLOS ANALISTA",
            "cpf_portador": "***.555.444-**",
            "nome_favorecido": "RESTAURANTE CENTRAL",
            "cnpj_cpf_favorecido": "11.222.333/0001-44",
            "tipo_cartao": "CPGF",
            "data_transacao": "2025-03-10",
            "valor": 320.00,
            "data_referencia": "2025-03-01",
        },
    ], "teste")

    cliente.post("/api/recarregar")

    res = cliente.get("/api/executivo/cartoes", params={"ano": 2025}).json()
    assert res["ano"] == 2025
    assert res["total_transacoes"] == 3
    assert res["total_gasto"] == 2670.50
    assert res["total_presidencia"] == 2350.50

    assert len(res["por_orgao"]) >= 2
    assert len(res["maiores_gastos"]) == 3
    assert res["maiores_gastos"][0]["nome_favorecido"] == "Hotel Nacional LTDA"
    assert res["maiores_gastos"][0]["nome_favorecido_extraido"] == "HOTEL NACIONAL LTDA"
    assert res["maiores_gastos"][0]["valor"] == 1500.50


def test_cartao_corporativo_filtro_orgao(cliente):
    res = cliente.get("/api/executivo/cartoes", params={"ano": 2025, "orgao": "Fazenda"}).json()
    assert res["total_transacoes"] == 1
    assert res["total_gasto"] == 320.00
    assert res["maiores_gastos"][0]["nome_orgao"] == "Ministério da Fazenda"


def test_viagens_servico_endpoint(cliente):
    armazem.remover("viagem_servico")
    armazem.mesclar("viagem_servico", [
        {
            "ano": 2025,
            "mes": 4,
            "id_viagem": "V1001",
            "codigo_orgao": "20000",
            "nome_orgao": "Presidência da República",
            "nome_viajante": "MINISTRO CHEFE",
            "cpf_viajante": "***.111.222-**",
            "cargo_viajante": "Ministro de Estado",
            "origem": "Brasília/DF",
            "destino": "Nova York/EUA",
            "motivo": "Assembleia Geral da ONU",
            "data_inicio": "2025-04-10",
            "data_fim": "2025-04-15",
            "valor_diarias": 8500.00,
            "valor_passagens": 12000.00,
            "valor_outros": 500.00,
            "valor_total": 21000.00,
            "data_referencia": "2025-04-01",
        },
    ], "teste")

    cliente.post("/api/recarregar")

    res = cliente.get("/api/executivo/viagens", params={"ano": 2025}).json()
    assert res["ano"] == 2025
    assert res["total_viagens"] == 1
    assert res["total_diarias"] == 8500.00
    assert res["total_passagens"] == 12000.00
    assert res["total_gasto"] == 21000.00
    assert res["maiores_viagens"][0]["destino"] == "Nova York/EUA"


def test_contratos_governo_endpoint(cliente):
    armazem.remover("contrato_governo")
    armazem.mesclar("contrato_governo", [
        {
            "ano": 2025,
            "id_contrato": "CT5001",
            "numero_contrato": "12/2025",
            "codigo_orgao": "25000",
            "nome_orgao": "Ministério da Fazenda",
            "cnpj_fornecedor": "00.111.222/0001-33",
            "nome_fornecedor": "TECNOLOGIA BRASIL S/A",
            "modalidade_licitacao": "Pregão Eletrônico",
            "objeto": "Prestação de serviços em nuvem",
            "valor_inicial": 5000000.00,
            "valor_atualizado": 5500000.00,
            "data_inicio_vigencia": "2025-01-01",
            "data_fim_vigencia": "2025-12-31",
            "data_referencia": "2025-01-01",
        },
    ], "teste")

    cliente.post("/api/recarregar")

    res = cliente.get("/api/executivo/contratos", params={"ano": 2025}).json()
    assert res["ano"] == 2025
    assert res["total_contratos"] == 1
    assert res["total_contratado"] == 5500000.00
    assert res["por_fornecedor"][0]["nome_fornecedor"] == "Tecnologia Brasil S/A"
    assert res["por_fornecedor"][0]["nome_fornecedor_extraido"] == "TECNOLOGIA BRASIL S/A"


def test_patrimonio_bens_declarados_politico(cliente):
    armazem.mesclar("dim_politico", [
        {
            "fonte_origem": "camara",
            "id_origem": "1",
            "casa": "camara",
            "id_politico": "1",
            "nome": "Deputado Teste",
            "nome_eleitoral": "Deputado Teste",
            "sigla_partido": "XYZ",
            "sigla_uf": "SP",
            "cargo": "deputado_federal",
            "cargo_extenso": "Deputado Federal",
            "ano_inicio": 2019,
            "ano_fim": 2026,
            "ativo": "1",
            "subsidio_cargo": 44008.52,
            "subsidio_conferido": True,
        }
    ], "teste")

    politico = armazem.ler("dim_politico")
    sk_politico = politico[politico["id_origem"] == "1"]["sk"].iloc[0]

    armazem.remover("bem_declarado")
    armazem.mesclar("bem_declarado", [
        {
            "id_politico": "1",
            "ano_eleicao": 2018,
            "sequencial_candidato": "10001",
            "cargo": "Deputado Federal",
            "tipo_bem": "Apartamento",
            "descricao_bem": "Apartamento em São Paulo",
            "valor_bem": 500000.00,
            "data_referencia": "2018-10-01",
        },
        {
            "id_politico": "1",
            "ano_eleicao": 2022,
            "sequencial_candidato": "10002",
            "cargo": "Deputado Federal",
            "tipo_bem": "Apartamento",
            "descricao_bem": "Apartamento em São Paulo",
            "valor_bem": 750000.00,
            "data_referencia": "2022-10-01",
        },
    ], "teste")

    cliente.post("/api/recarregar")

    res = cliente.get(f"/api/politicos/{sk_politico}/ficha", params={"ano": 2024}).json()
    assert "patrimonio_historico" in res
    assert "bens_declarados" in res
    assert len(res["patrimonio_historico"]) == 2
    assert res["patrimonio_historico"][0]["ano_eleicao"] == 2018
    assert res["patrimonio_historico"][0]["total_declarado"] == 500000.00
    assert res["patrimonio_historico"][1]["ano_eleicao"] == 2022
    assert res["patrimonio_historico"][1]["total_declarado"] == 750000.00
