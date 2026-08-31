"""Testes para o módulo de autenticação Google OAuth e middleware de proteção."""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from src.api.auth import emails_permitidos
from src.api.servidor import app


def test_emails_permitidos_com_variavel(monkeypatch):
    """Testa a extração e normalização de e-mails da whitelist."""
    monkeypatch.setenv("EMAILS_PERMITIDOS", "  Admin@Empresa.com, teste@GMAIL.COM , OUTRO@GOV.BR  ")
    permitidos = emails_permitidos()
    assert permitidos == {"admin@empresa.com", "teste@gmail.com", "outro@gov.br"}


def test_emails_permitidos_vazio(monkeypatch):
    """Quando não há lista configurada, deve retornar conjunto vazio."""
    monkeypatch.setenv("EMAILS_PERMITIDOS", "")
    assert emails_permitidos() == set()


def test_rota_saude_publica():
    """A rota /saude deve responder 200 sem necessidade de autenticação."""
    cliente = TestClient(app)
    resp = cliente.get("/saude")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["status"] == "ok"


def test_usuario_nao_autenticado_me():
    """Rota /auth/me sem sessão ativa deve indicar autenticado=False."""
    cliente = TestClient(app)
    resp = cliente.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"autenticado": False, "usuario": None}


def test_logout_redireciona():
    """Rota /auth/logout deve redirecionar com código 303."""
    cliente = TestClient(app)
    resp = cliente.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers.get("location", "")


def test_middleware_bloqueio_quando_exige_auth(monkeypatch):
    """Quando EXIGE_AUTH=1, rota de API sem login deve retornar 401 e página HTML deve redirecionar."""
    monkeypatch.setenv("EXIGE_AUTH", "1")
    cliente = TestClient(app)

    # Chamada de API sem login -> 401
    resp_api = cliente.get("/api/controle/sumario")
    assert resp_api.status_code == 401
    assert resp_api.json().get("erro") == "Não autenticado"

    # Navegação sem login -> redirecionamento 307/302 para /auth/login
    resp_web = cliente.get("/", follow_redirects=False)
    assert resp_web.status_code in (302, 307)
    assert "/auth/login" in resp_web.headers.get("location", "")


def test_middleware_liberado_quando_nao_exige_auth(monkeypatch):
    """Quando EXIGE_AUTH=0, as rotas devem responder normalmente."""
    monkeypatch.setenv("EXIGE_AUTH", "0")
    cliente = TestClient(app)
    resp = cliente.get("/saude")
    assert resp.status_code == 200
    assert resp.json()["auth_ativa"] is False
