"""Testes unitários para as rotas e dados do Poder Judiciário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.coletores.judiciario import gerar_bases_judiciario
from src.api.servidor import app


@pytest.fixture(autouse=True)
def semear():
    """Gera a base de teste de magistrados no armazém temporário."""
    from src.api.servidor import recarregar_views, marcar_dados_alterados
    gerar_bases_judiciario()
    marcar_dados_alterados()
    recarregar_views()



def test_sumario_judiciario():
    """A rota /api/judiciario/sumario deve retornar os KPIs e distribuição por ramo."""
    cliente = TestClient(app)
    resp = cliente.get("/api/judiciario/sumario")
    assert resp.status_code == 200
    dados = resp.json()
    assert "kpis" in dados
    assert "por_ramo" in dados
    assert int(dados["kpis"]["total_magistrados"]) > 0


def test_listar_magistrados():
    """A rota /api/judiciario/magistrados deve listar magistrados com remuneração."""
    cliente = TestClient(app)
    resp = cliente.get("/api/judiciario/magistrados")
    assert resp.status_code == 200
    lista = resp.json()
    assert len(lista) > 0
    primeiro = lista[0]
    assert "nome" in primeiro
    assert "cargo" in primeiro
    assert "tribunal" in primeiro
    assert "total_liquido" in primeiro


def test_filtrar_magistrados_por_ramo():
    """Filtro por ramo (Supremo) deve retornar ministros do STF."""
    cliente = TestClient(app)
    resp = cliente.get("/api/judiciario/magistrados?ramo=Supremo")
    assert resp.status_code == 200
    lista = resp.json()
    assert len(lista) > 0
    assert all(m["tribunal"] == "STF" for m in lista)


def test_ficha_magistrado_existente():
    """Ficha do magistrado deve trazer dados e histórico de remuneração."""
    cliente = TestClient(app)
    lista = cliente.get("/api/judiciario/magistrados").json()
    assert len(lista) > 0
    sk = lista[0]["sk"]

    resp = cliente.get(f"/api/judiciario/magistrados/{sk}")
    assert resp.status_code == 200
    ficha = resp.json()
    assert ficha["magistrado"]["sk"] == sk
    assert "historico" in ficha
    assert len(ficha["historico"]) > 0


def test_ficha_magistrado_inexistente():
    """Ficha de magistrado inválido deve retornar 404."""
    cliente = TestClient(app)
    resp = cliente.get("/api/judiciario/magistrados/sk_inexistente_123")
    assert resp.status_code == 404


def test_listar_tribunais():
    """A rota /api/judiciario/tribunais deve agrupar por tribunal."""
    cliente = TestClient(app)
    resp = cliente.get("/api/judiciario/tribunais")
    assert resp.status_code == 200
    tribunais = resp.json()
    assert len(tribunais) > 0
    trib_nomes = {t["tribunal"] for t in tribunais}
    assert "STF" in trib_nomes
