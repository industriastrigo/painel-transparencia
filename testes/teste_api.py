"""Teste de integração da API sobre um armazém temporário.

Não usa rede: semeia Parquet mínimos e confere que as views, os filtros de
data e o placar de votação respondem o que o painel espera.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from fastapi.testclient import TestClient  # noqa: E402

from src.nucleo import armazem  # noqa: E402


def _semear():
    armazem.mesclar("dim_ente", [
        {"cod_ibge": "0", "nivel": "pais", "nome": "Brasil", "sigla_uf": None,
         "cod_uf": None, "regiao": None, "cod_regiao": None},
        {"cod_ibge": "35", "nivel": "estado", "nome": "São Paulo", "sigla_uf": "SP",
         "cod_uf": "35", "regiao": "Sudeste", "cod_regiao": "3"},
        {"cod_ibge": "29", "nivel": "estado", "nome": "Bahia", "sigla_uf": "BA",
         "cod_uf": "29", "regiao": "Nordeste", "cod_regiao": "2"},
        {"cod_ibge": "3550308", "nivel": "municipio", "nome": "São Paulo",
         "sigla_uf": "SP", "cod_uf": "35", "regiao": "Sudeste", "cod_regiao": "3"},
    ], "teste")

    armazem.mesclar("indicador_ente", [
        {"cod_ibge": "35", "cod_metrica": "populacao", "ano": 2024,
         "valor": 44_000_000.0, "unidade": "pessoas", "nivel_territorial": "N3",
         "data_referencia": "2024-12-31"},
        {"cod_ibge": "29", "cod_metrica": "populacao", "ano": 2024,
         "valor": 14_000_000.0, "unidade": "pessoas", "nivel_territorial": "N3",
         "data_referencia": "2024-12-31"},
    ], "teste")

    armazem.mesclar("financas_ente", [
        {"cod_ibge": "35", "ano": 2024, "periodo": "anual", "cod_conta": "10",
         "cod_funcao": "10", "funcao": "Saúde", "rotulo_conta": "Saúde",
         "estagio": "Despesas Empenhadas", "valor": 30_000_000_000.0,
         "esfera": "estado", "uf": "SP", "data_referencia": "2024-12-31"},
        {"cod_ibge": "29", "ano": 2024, "periodo": "anual", "cod_conta": "10",
         "cod_funcao": "10", "funcao": "Saúde", "rotulo_conta": "Saúde",
         "estagio": "Despesas Empenhadas", "valor": 9_000_000_000.0,
         "esfera": "estado", "uf": "BA", "data_referencia": "2024-12-31"},
    ], "teste")

    armazem.mesclar("dim_politico", [
        {"fonte_origem": "camara", "id_origem": "1", "nome": "Fulano de Tal",
         "nome_eleitoral": "Fulano", "sigla_partido": "XYZ", "sigla_uf": "SP",
         "id_legislatura": "57", "email": None, "url_foto": None,
         "casa": "camara", "cargo": "deputado_federal"},
    ], "teste")

    # de-para + mandatos: a ponte entre "quem governa" e "quanto gasta"
    armazem.mesclar("dim_de_para_ente", [
        {"fonte_origem": "tse", "id_origem": "71072", "cod_ibge": "3550308",
         "sigla_uf": "SP", "nome_origem": "SAO PAULO",
         "nome_ibge": "São Paulo", "metodo": "exata", "similaridade": 1.0},
        {"fonte_origem": "tse", "id_origem": "99999", "cod_ibge": None,
         "sigla_uf": "SP", "nome_origem": "LUGAR NENHUM", "nome_ibge": None,
         "metodo": "pendente", "similaridade": 0.31},
    ], "teste")

    armazem.mesclar("mandato", [
        {"sk_politico": "p1", "cod_cargo": "11", "cargo": "prefeito",
         "cod_ue": "71072", "cod_ibge": "3550308", "sigla_uf": "SP",
         "nome_ente": "SAO PAULO", "nome": "Prefeito Teste",
         "sigla_partido": "XYZ", "ano_inicio": 2025, "ano_fim": 2029,
         "data_inicio": "2025-01-01", "ano_eleicao": 2024},
        {"sk_politico": "p2", "cod_cargo": "3", "cargo": "governador",
         "cod_ue": "SP", "cod_ibge": "35", "sigla_uf": "SP",
         "nome_ente": "SÃO PAULO", "nome": "Governador Teste",
         "sigla_partido": "ABC", "ano_inicio": 2023, "ano_fim": 2027,
         "data_inicio": "2023-01-01", "ano_eleicao": 2022},
        {"sk_politico": "p3", "cod_cargo": "1", "cargo": "presidente",
         "cod_ue": "BR", "cod_ibge": "0", "sigla_uf": "BR",
         "nome_ente": "BRASIL", "nome": "Presidente Teste",
         "sigla_partido": "DEF", "ano_inicio": 2023, "ano_fim": 2027,
         "data_inicio": "2023-01-01", "ano_eleicao": 2022},
        {"sk_politico": "p4", "cod_cargo": "13", "cargo": "vereador",
         "cod_ue": "71072", "cod_ibge": "3550308", "sigla_uf": "SP",
         "nome_ente": "SAO PAULO", "nome": "Vereador Teste",
         "sigla_partido": "XYZ", "ano_inicio": 2025, "ano_fim": 2029,
         "data_inicio": "2025-01-01", "ano_eleicao": 2024},
    ], "teste")

    armazem.mesclar("proposicao", [
        {"casa": "camara", "id_proposicao": "9001", "sigla_tipo": "PL",
         "numero": "1", "ano_proposicao": "2024", "identificador": "PL 1/2024",
         "ementa": "Dispõe sobre transparência orçamentária.", "tema": None,
         "data_apresentacao": "2024-03-10", "situacao": "Em tramitação",
         "tramitacao_atual": "Recebimento", "orgao_atual": "CCJC",
         "regime": "Ordinária", "data_ultimo_status": "2024-04-01",
         "ultimo_status": None, "url": None, "id_autor": "1",
         "nome_autor": "Fulano", "partido_autor": "XYZ", "uf_autor": "SP",
         "qtd_autores": 1, "ano": 2024},
        {"casa": "camara", "id_proposicao": "9002", "sigla_tipo": "PEC",
         "numero": "2", "ano_proposicao": "2024", "identificador": "PEC 2/2024",
         "ementa": "Altera a Constituição.", "tema": None,
         "data_apresentacao": "2024-04-10", "situacao": "Pronta para Pauta",
         "tramitacao_atual": None, "orgao_atual": "PLEN", "regime": None,
         "data_ultimo_status": None, "ultimo_status": None, "url": None,
         "id_autor": None, "nome_autor": None, "partido_autor": None,
         "uf_autor": None, "qtd_autores": 0, "ano": 2024},
        {"casa": "camara", "id_proposicao": "9003", "sigla_tipo": "PL",
         "numero": "3", "ano_proposicao": "2024", "identificador": "PL 3/2024",
         "ementa": "Sem situação registrada.", "tema": None,
         "data_apresentacao": "2024-05-10", "situacao": None,
         "tramitacao_atual": None, "orgao_atual": None, "regime": None,
         "data_ultimo_status": None, "ultimo_status": None, "url": None,
         "id_autor": None, "nome_autor": None, "partido_autor": None,
         "uf_autor": None, "qtd_autores": 0, "ano": 2024},
    ], "teste")

    armazem.mesclar("votacao", [
        {"casa": "camara", "id_votacao": "V1", "data_hora": "2024-05-02T15:00",
         "sigla_orgao": "PLEN", "descricao": "Aprovação do texto-base",
         "aprovada": "1", "votos_sim": 2, "votos_nao": 1, "votos_outros": 0,
         "id_proposicao": "9001", "url": None, "ano": 2024},
    ], "teste")

    armazem.mesclar("voto", [
        {"casa": "camara", "id_votacao": "V1", "id_politico": "1",
         "nome_politico": "Fulano", "sigla_partido": "XYZ", "sigla_uf": "SP",
         "voto": "Sim", "data_hora": "2024-05-02T15:00", "ano": 2024, "mes": 5},
        {"casa": "camara", "id_votacao": "V1", "id_politico": "2",
         "nome_politico": "Beltrano", "sigla_partido": "ABC", "sigla_uf": "BA",
         "voto": "Não", "data_hora": "2024-05-02T15:00", "ano": 2024, "mes": 5},
        {"casa": "camara", "id_votacao": "V1", "id_politico": "3",
         "nome_politico": "Sicrano", "sigla_partido": "ABC", "sigla_uf": "MG",
         "voto": "Abstenção", "data_hora": "2024-05-02T15:00", "ano": 2024, "mes": 5},
    ], "teste")


@pytest.fixture(scope="module")
def cliente():
    _semear()
    from src.api import servidor  # noqa: PLC0415
    return TestClient(servidor.app)


def test_saude_lista_fontes(cliente):
    corpo = cliente.get("/api/saude").json()
    assert corpo["situacao"] == "ok"


def test_anos_disponiveis(cliente):
    assert 2024 in cliente.get("/api/anos").json()


def test_mapa_do_pais_traz_as_ufs(cliente):
    corpo = cliente.get("/api/mapa", params={"ano": 2024}).json()
    assert corpo["nivel"] == "estado"
    nomes = {e["nome"] for e in corpo["entes"]}
    assert {"São Paulo", "Bahia"} <= nomes


def test_despesa_per_capita_e_calculada(cliente):
    corpo = cliente.get("/api/mapa", params={"ano": 2024}).json()
    sp = next(e for e in corpo["entes"] if e["cod_ibge"] == "35")
    assert round(sp["despesa_per_capita"]) == round(30_000_000_000 / 44_000_000)


def test_drill_down_para_municipios(cliente):
    corpo = cliente.get("/api/mapa", params={"ano": 2024, "uf": "SP"}).json()
    assert corpo["nivel"] == "municipio"
    assert corpo["entes"][0]["cod_ibge"] == "3550308"


def test_ranking_ordena_desc(cliente):
    linhas = cliente.get("/api/ranking",
                         params={"ano": 2024, "metrica": "despesa_total"}).json()
    assert [l["sigla_uf"] for l in linhas] == ["SP", "BA"]


def test_resumo_de_politicos(cliente):
    corpo = cliente.get("/api/politicos/resumo").json()
    assert corpo["total"] >= 1


def test_filtro_de_data_em_proposicoes(cliente):
    dentro = cliente.get("/api/proposicoes",
                         params={"de": "2024-01-01", "ate": "2024-12-31"}).json()
    fora = cliente.get("/api/proposicoes",
                       params={"de": "2025-01-01"}).json()
    assert len(dentro) == 3 and len(fora) == 0


# --------------------------------------------------- filtro de situação
def test_situacoes_vem_do_acervo_com_contagem(cliente):
    linhas = cliente.get("/api/proposicoes/situacoes").json()
    por_situacao = {l["situacao"]: l["quantidade"] for l in linhas}
    assert por_situacao == {"Em tramitação": 1, "Pronta para Pauta": 1}, \
        "proposição sem situação não pode virar uma opção do filtro"


def test_situacoes_ordenadas_por_quantidade(cliente):
    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": "9004", "sigla_tipo": "PL",
        "numero": "4", "ano_proposicao": "2024", "identificador": "PL 4/2024",
        "ementa": "Outra.", "tema": None, "data_apresentacao": "2024-06-01",
        "situacao": "Pronta para Pauta", "tramitacao_atual": None,
        "orgao_atual": None, "regime": None, "data_ultimo_status": None,
        "ultimo_status": None, "url": None, "id_autor": None,
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "ano": 2024}], "teste")
    servidor_recarregado = cliente.post("/api/recarregar")
    assert servidor_recarregado.status_code == 200

    linhas = cliente.get("/api/proposicoes/situacoes").json()
    assert linhas[0]["situacao"] == "Pronta para Pauta"
    assert linhas[0]["quantidade"] == 2


def test_filtrar_por_situacao(cliente):
    linhas = cliente.get("/api/proposicoes",
                         params={"situacao": "Em tramitação"}).json()
    assert [l["identificador"] for l in linhas] == ["PL 1/2024"]


def test_situacao_inexistente_devolve_lista_vazia(cliente):
    assert cliente.get("/api/proposicoes",
                       params={"situacao": "Arquivada"}).json() == []


def test_filtro_de_situacao_combina_com_os_outros(cliente):
    linhas = cliente.get("/api/proposicoes", params={
        "situacao": "Pronta para Pauta", "tipo": "PEC"}).json()
    assert [l["identificador"] for l in linhas] == ["PEC 2/2024"]


def test_tipos_disponiveis(cliente):
    tipos = {l["sigla_tipo"] for l in cliente.get("/api/proposicoes/tipos").json()}
    assert tipos == {"PL", "PEC"}


def test_proposicao_traz_orgao_atual(cliente):
    linhas = cliente.get("/api/proposicoes",
                         params={"situacao": "Em tramitação"}).json()
    assert linhas[0]["orgao_atual"] == "CCJC"


def test_detalhe_traz_etapas_e_placar(cliente):
    corpo = cliente.get("/api/proposicoes/camara/9001").json()
    assert corpo["proposicao"]["identificador"] == "PL 1/2024"
    votacao = corpo["votacoes"][0]
    assert (votacao["sim"], votacao["nao"], votacao["abstencao"]) == (1, 1, 1)


def test_votos_nominais_com_filtro(cliente):
    todos = cliente.get("/api/votacoes/camara/V1/votos").json()
    assert len(todos["votos"]) == 3
    favor = cliente.get("/api/votacoes/camara/V1/votos",
                        params={"voto": "Sim"}).json()
    assert [v["nome_politico"] for v in favor["votos"]] == ["Fulano"]


def test_proposicao_inexistente_devolve_404(cliente):
    assert cliente.get("/api/proposicoes/camara/000").status_code == 404


# ------------------------------------------------------- ficha do ente
def test_ficha_junta_governo_e_gasto(cliente):
    """O teste que só passa porque o de-para existe."""
    f = cliente.get("/api/ente/3550308").json()

    assert f["ente"]["nome"] == "São Paulo"
    cargos = {g["cargo"]: g["nome"] for g in f["governantes"]}
    assert cargos["prefeito"] == "Prefeito Teste"


def test_ficha_traz_a_cadeia_ate_a_uniao(cliente):
    """Município mostra prefeito, governador da UF e presidente."""
    f = cliente.get("/api/ente/3550308").json()
    cargos = [g["cargo"] for g in f["governantes"]]
    assert cargos == ["prefeito", "governador", "presidente"]


def test_ficha_separa_legislativo_do_executivo(cliente):
    f = cliente.get("/api/ente/3550308").json()
    assert [l["cargo"] for l in f["legislativo"]] == ["vereador"]


def test_ficha_de_estado_nao_traz_prefeito(cliente):
    f = cliente.get("/api/ente/35").json()
    cargos = [g["cargo"] for g in f["governantes"]]
    assert "prefeito" not in cargos
    assert "governador" in cargos


def test_ficha_traz_financas_por_funcao(cliente):
    f = cliente.get("/api/ente/35").json()
    assert f["financas"][0]["funcao"] == "Saúde"
    assert f["resumo"]["despesa_total"] == 30_000_000_000


def test_ficha_de_ente_inexistente_devolve_404(cliente):
    assert cliente.get("/api/ente/0000000").status_code == 404


def test_pendencias_do_de_para_sao_visiveis(cliente):
    r = cliente.get("/api/de-para/pendencias").json()
    assert [p["nome_origem"] for p in r["pendentes"]] == ["LUGAR NENHUM"]
    metodos = {m["metodo"]: m["quantidade"] for m in r["por_metodo"]}
    assert metodos == {"exata": 1, "pendente": 1}
