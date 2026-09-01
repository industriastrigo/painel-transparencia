"""Testes unitários para as rotas e dados do Poder Legislativo."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.api.servidor import app


def test_sumario_legislativo_federal():
    """A rota /api/legislativo/sumario deve retornar KPIs do Congresso Nacional."""
    cliente = TestClient(app)
    resp = cliente.get("/api/legislativo/sumario?esfera=federal&ano=2026")
    assert resp.status_code == 200
    dados = resp.json()
    assert "kpis" in dados
    assert "bancadas" in dados
    assert dados["kpis"]["total_parlamentares"] > 0
    assert dados["kpis"]["total_cota_parlamentar"] > 0
    assert dados["kpis"]["total_emendas_empenhadas"] > 0


def test_sumario_legislativo_camara():
    """A rota /api/legislativo/sumario com casa=camara deve retornar dados da Câmara."""
    cliente = TestClient(app)
    resp = cliente.get("/api/legislativo/sumario?esfera=federal&casa=camara&ano=2026")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["kpis"]["total_parlamentares"] >= 513


def test_listar_parlamentares():
    """A rota /api/legislativo/parlamentares deve listar parlamentares."""
    cliente = TestClient(app)
    resp = cliente.get("/api/legislativo/parlamentares?esfera=federal&ano=2026&limite=10")
    assert resp.status_code == 200
    dados = resp.json()
    assert "parlamentares" in dados
    assert len(dados["parlamentares"]) > 0
    primeiro = dados["parlamentares"][0]
    assert "nome_formatado" in primeiro
    assert "cargo" in primeiro


def test_cotas_parlamentares():
    """A rota /api/legislativo/cotas deve retornar categorias e fornecedores."""
    cliente = TestClient(app)
    resp = cliente.get("/api/legislativo/cotas?ano=2026")
    assert resp.status_code == 200
    dados = resp.json()
    assert "categorias" in dados
    assert "fornecedores" in dados
    assert len(dados["categorias"]) > 0
    assert len(dados["fornecedores"]) > 0


def test_emendas_parlamentares():
    """A rota /api/legislativo/emendas deve responder com lista de emendas."""
    cliente = TestClient(app)
    resp = cliente.get("/api/legislativo/emendas?ano=2026&limite=10")
    assert resp.status_code == 200
    dados = resp.json()
    assert "emendas" in dados
    assert "total" in dados
