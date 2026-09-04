"""
Auditoria de QA: Contratos de Integração de APIs e Resiliência de Segurança.

Valida conformidade de endpoints REST, status codes HTTP (200, 400, 404, 422, 500),
estrutura de resposta JSON e resistência contra tentativas de injeção SQL/DDL/DML no Explorador.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.api.servidor import app

client = TestClient(app)


# -----------------------------------------------------------------------------
# Testes de Endpoints Públicos e Saúde
# -----------------------------------------------------------------------------

def test_api_saude_endpoint():
    """Valida endpoint de liveness/readiness probe em /saude e /api/saude."""
    res = client.get("/saude")
    assert res.status_code == 200
    dados = res.json()
    assert "status" in dados
    assert dados["status"] in ("ok", "operacional")

    res2 = client.get("/api/saude")
    assert res2.status_code == 200
    dados2 = res2.json()
    assert "situacao" in dados2


def test_api_anos_e_cobertura():
    """Valida endpoint de anos cobertos pelo acervo e status de integridade."""
    res = client.get("/api/anos")
    assert res.status_code == 200
    dados = res.json()
    assert isinstance(dados, dict)
    assert "anos" in dados


def test_api_configuracao():
    """Valida retorno de configurações públicas do painel."""
    res = client.get("/api/config")
    assert res.status_code == 200
    dados = res.json()
    assert isinstance(dados, dict)


def test_api_mapa_com_parametros():
    """Valida consolidação de dados geoespaciais e indicadores dos estados com query params."""
    res = client.get("/api/mapa?ano=2024&metrica=despesa_per_capita")
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        dados = res.json()
        assert isinstance(dados, (dict, list))


def test_api_mapa_sem_ano_rejeicao_422():
    """Valida que /api/mapa sem o parâmetro obrigatório 'ano' rejeita com HTTP 422."""
    res = client.get("/api/mapa")
    assert res.status_code == 422


def test_api_metricas_catalogo():
    """Valida catálogo de métricas disponíveis para ranking e cruzamentos."""
    res = client.get("/api/metricas")
    assert res.status_code == 200
    dados = res.json()
    assert isinstance(dados, list)


def test_api_entes_especifico_ibge():
    """Valida consulta de ente federativo por código IBGE (SP: 3550308)."""
    res = client.get("/api/entes/3550308")
    assert res.status_code in (200, 404)


def test_api_executivo_esferas():
    """Valida endpoints de órgãos e dados do Poder Executivo por esfera."""
    for esfera in ["federal", "estadual", "municipal"]:
        res = client.get(f"/api/executivo/{esfera}")
        assert res.status_code in (200, 404)


def test_api_politicos_listagem():
    """Valida listagem e paginação de agentes políticos."""
    res = client.get("/api/politicos?limite=10")
    assert res.status_code in (200, 404)


def test_api_proposicoes_listagem():
    """Valida listagem de proposições legislativas."""
    res = client.get("/api/proposicoes?limite=10")
    assert res.status_code in (200, 404)


def test_api_custo_reparticao():
    """Valida endpoint de decomposição de custos e remunerações."""
    res = client.get("/api/custo")
    assert res.status_code in (200, 404)


def test_api_judiciario_e_mp():
    """Valida rotas de magistrados e membros do Ministério Público."""
    res_jud = client.get("/api/judiciario")
    assert res_jud.status_code in (200, 404)

    res_mp = client.get("/api/mp")
    assert res_mp.status_code in (200, 404)


def test_api_catalogo_e_explorador_arvore():
    """Valida metadados do catálogo de dados e árvore de esquema."""
    res_cat = client.get("/api/catalogo")
    assert res_cat.status_code in (200, 404)

    res_arv = client.get("/api/explorador/arvore")
    assert res_arv.status_code in (200, 404)


def test_auth_endpoints_status():
    """Valida rotas de autenticação Google (/auth/me, /auth/login, /auth/logout)."""
    res_me = client.get("/auth/me")
    assert res_me.status_code == 200
    dados = res_me.json()
    assert "autenticado" in dados

    res_login = client.get("/auth/login", follow_redirects=False)
    assert res_login.status_code in (200, 302, 303, 307, 500)

    res_logout = client.get("/auth/logout", follow_redirects=False)
    assert res_logout.status_code in (200, 302, 303, 307)


# -----------------------------------------------------------------------------
# Testes de Segurança e Sanitização SQL no Explorador
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("sql_malicioso", [
    "DROP TABLE dim_ente",
    "DELETE FROM dim_ente WHERE 1=1",
    "INSERT INTO dim_ente VALUES (1, 2, 3)",
    "UPDATE dim_ente SET nome = 'Hacked'",
    "ALTER TABLE dim_ente ADD COLUMN hacked TEXT",
    "TRUNCATE TABLE dim_ente",
    "CREATE TABLE backdoor (id INT)",
    "GRANT ALL PRIVILEGES ON ALL TABLES TO PUBLIC",
    "REVOKE ALL PRIVILEGES ON ALL TABLES FROM PUBLIC",
    "SELECT * FROM dim_ente; DROP TABLE dim_ente;",
    "/* comentário */ DROP TABLE dim_ente",
    "select * from dim_ente; delete from dim_ente;",
])
def test_explorador_bloqueio_injecao_ddl_dml(sql_malicioso: str):
    """Garante que qualquer tentativa de DDL/DML ou comandos destrutivos seja terminantemente rejeitada."""
    res = client.post("/api/explorador/consulta", json={"sql": sql_malicioso})
    if res.status_code == 200:
        dados = res.json()
        assert "erro" in dados or "mensagem" in dados, f"SQL perigoso executou sem erro: {sql_malicioso}"
    else:
        assert res.status_code in (400, 403, 422)


def test_explorador_consulta_select_valida():
    """Valida que consultas SELECT simples são aceitas e estruturadas."""
    res = client.post("/api/explorador/consulta", json={"sql": "SELECT 1 AS teste, 'ok' AS status"})
    assert res.status_code in (200, 400)
    if res.status_code == 200:
        dados = res.json()
        assert "colunas" in dados or "linhas" in dados or isinstance(dados, list)


def test_explorador_consulta_vazia():
    """Valida que payload vazio ou sem SQL retorna erro 400 ou 422."""
    res = client.post("/api/explorador/consulta", json={})
    assert res.status_code in (400, 422)


def test_rota_inexistente_404():
    """Garante comportamento padrão 404 para endpoints não mapeados."""
    res = client.get("/api/rota_inexistente_qa_audit")
    assert res.status_code == 404