"""Testes unitários para as rotas e dados do Ministério Público."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.api.servidor import app


def test_sumario_mp():
    """A rota /api/mp/sumario deve retornar os KPIs e distribuição por ramo."""
    cliente = TestClient(app)
    resp = cliente.get("/api/mp/sumario")
    assert resp.status_code == 200
    dados = resp.json()
    assert "kpis" in dados
    assert "por_ramo" in dados
    assert int(dados["kpis"]["total_membros"]) > 0
    assert float(dados["kpis"]["total_folha_mensal"]) > 0


def test_listar_membros_mp():
    """A rota /api/mp/membros deve listar promotores e procuradores."""
    cliente = TestClient(app)
    resp = cliente.get("/api/mp/membros?limite=10")
    assert resp.status_code == 200
    lista = resp.json()
    assert len(lista) > 0
    primeiro = lista[0]
    assert "nome" in primeiro
    assert "cargo" in primeiro
    assert "ramo" in primeiro
    assert "total_liquido" in primeiro


def test_filtrar_membros_mp_por_ramo():
    """Filtro por ramo (Federal) deve retornar membros do MPF."""
    cliente = TestClient(app)
    resp = cliente.get("/api/mp/membros?ramo=Federal")
    assert resp.status_code == 200
    lista = resp.json()
    assert len(lista) > 0
    assert any("Federal" in m["ramo"] or "MPF" in m.get("orgao_mp", "") for m in lista)


def test_detalhar_membro_mp_existente():
    """Ficha do membro do MP deve trazer histórico de remuneração."""
    cliente = TestClient(app)
    lista = cliente.get("/api/mp/membros").json()
    assert len(lista) > 0
    sk = lista[0]["sk"]

    resp = cliente.get(f"/api/mp/membros/{sk}")
    assert resp.status_code == 200
    ficha = resp.json()
    assert ficha["membro"]["sk"] == sk
    assert "historico" in ficha
    assert len(ficha["historico"]) > 0


def test_detalhar_membro_mp_inexistente():
    """Ficha de membro inválido deve retornar 404."""
    cliente = TestClient(app)
    resp = cliente.get("/api/mp/membros/sk_mp_inexistente_999")
    assert resp.status_code == 404
