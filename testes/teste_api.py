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
    resposta = cliente.get("/api/anos").json()
    assert 2024 in [a["ano"] for a in resposta["anos"]]
    # O padrão é o ano mais recente COMPLETO, não o mais recente que alguma
    # tabela tenha. O RREO é bimestral e já publica o exercício corrente; o
    # DCA é anual e só sai no seguinte — sem esta distinção o painel abria
    # num ano com metade dos cartões vazios, parecendo acervo perdido.
    assert resposta["padrao"] is not None
    padrao = next(a for a in resposta["anos"]
                  if a["ano"] == resposta["padrao"])
    completos = [a for a in resposta["anos"] if a["completo"]]
    if completos:
        assert padrao["completo"], "abriu num ano parcial havendo completo"
        assert resposta["padrao"] == max(a["ano"] for a in completos)


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


def test_ficha_traz_a_despesa_por_natureza(cliente):
    """O Anexo I-D do SICONFI é despesa por NATUREZA (pessoal, juros,
    investimentos), não por FUNÇÃO de governo. A ficha diz "natureza" porque
    é o que o dado sustenta — chamar de função prometeria um recorte que este
    anexo não tem."""
    f = cliente.get("/api/ente/35").json()
    assert f["resumo"]["despesa_total"] == 30_000_000_000
    for linha in f["financas"]:
        assert "natureza" in linha, "a ficha deve falar em natureza"
        assert "funcao" not in linha


def test_ficha_de_ente_inexistente_devolve_404(cliente):
    assert cliente.get("/api/ente/0000000").status_code == 404


def test_pendencias_do_de_para_sao_visiveis(cliente):
    r = cliente.get("/api/de-para/pendencias").json()
    assert [p["nome_origem"] for p in r["pendentes"]] == ["LUGAR NENHUM"]
    metodos = {m["metodo"]: m["quantidade"] for m in r["por_metodo"]}
    assert metodos == {"exata": 1, "pendente": 1}


def test_catalogo_descreve_como_cada_fonte_atualiza():
    """"Atualizar" não quer dizer a mesma coisa em duas fontes: a Câmara
    republica o ano corrente todo dia, o SICONFI só fecha o exercício
    anterior, o TSE só muda a cada eleição. A tela precisa dizer isso ANTES
    do clique — senão a pessoa espera dado que ainda não existe."""
    from src.api import tarefas  # noqa: PLC0415

    catalogo = tarefas.catalogo()
    assert catalogo, "catálogo vazio"

    obrigatorios = {"fonte", "rotulo", "cadencia", "periodo",
                    "granularidade", "duracao", "usa_ano"}
    for item in catalogo:
        faltando = obrigatorios - set(item)
        assert not faltando, f"{item.get('fonte')} sem {faltando}"
        for campo in ("rotulo", "cadencia", "periodo", "granularidade",
                      "duracao"):
            assert item[campo].strip(), f"{item['fonte']}: {campo} vazio"


def test_fonte_que_ignora_o_ano_diz_isso():
    """O campo Ano não tem efeito no SADIPEM nem no IBGE. Deixar a pessoa
    preencher achando que recorta é prometer um filtro que não existe."""
    from src.api import tarefas  # noqa: PLC0415

    por_fonte = {i["fonte"]: i for i in tarefas.catalogo()}
    assert por_fonte["sadipem"]["usa_ano"] is False
    assert por_fonte["ibge"]["usa_ano"] is False
    assert por_fonte["camara"]["usa_ano"] is True
    assert por_fonte["siconfi"]["usa_ano"] is True


def test_fonte_que_precisa_de_configuracao_avisa_no_catalogo():
    from src.api import tarefas  # noqa: PLC0415

    por_fonte = {i["fonte"]: i for i in tarefas.catalogo()}
    assert "CGU" in por_fonte["portal_transparencia"]["requer"]
    assert por_fonte["transferencias"]["requer"], (
        "a API de transferências pode exigir liberação — a tela precisa dizer")


def test_catalogo_cobre_todas_as_fontes_do_orquestrador():
    """Uma fonte nova que entre no ORDEM e não no catálogo some da tela sem
    ninguém notar."""
    from src.api import tarefas  # noqa: PLC0415
    from src.coletores import orquestrador  # noqa: PLC0415

    assert [i["fonte"] for i in tarefas.catalogo()] == orquestrador.ORDEM


# =================================================================
#  Sprint 2 — visão macro e destaque do Executivo
# =================================================================

def _cenario_executivo():
    """Presidente e governador, com o subsídio do presidente cadastrado."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.mesclar("dim_cargo_publico", [
        dict(cod_cargo="presidente", cargo="Presidente da República",
             poder="executivo", esfera="federal", ramo=None),
        dict(cod_cargo="governador", cargo="Governador", poder="executivo",
             esfera="estadual", ramo=None)], "teste")
    armazem.mesclar("dim_subsidio", [dict(
        cod_cargo="presidente", vigencia_inicio="2019-01-01",
        valor_mensal=30934.70, norma="Lei 13.752/2018",
        url_norma="https://www.planalto.gov.br/x", conferido=False,
        observacao="valor de rascunho", data_referencia="2019-01-01")], "teste")
    armazem.mesclar("mandato", [
        dict(sk_politico="pr1", cod_cargo="presidente", cargo="presidente",
             cod_ue="0", cod_ibge="0", sigla_uf=None, nome_ente="Brasil",
             nome="Fulana de Tal", sigla_partido="XPTO", ano_inicio=2023,
             ano_fim=2026, data_inicio="2023-01-01", ano_eleicao=2022),
        dict(sk_politico="gv35", cod_cargo="governador", cargo="governador",
             cod_ue="35", cod_ibge="35", sigla_uf="SP", nome_ente="São Paulo",
             nome="Beltrano", sigla_partido="ABC", ano_inicio=2023,
             ano_fim=2026, data_inicio="2023-01-01", ano_eleicao=2022)], "teste")


def test_executivo_sem_uf_e_o_presidente(cliente):
    _cenario_executivo()
    cliente.post("/api/recarregar")
    dados = cliente.get("/api/politicos/executivo").json()
    assert len(dados) == 1
    assert dados[0]["cargo"] == "presidente"
    assert dados[0]["nome"] == "Fulana de Tal"


def test_executivo_com_uf_e_o_governador_daquele_estado(cliente):
    _cenario_executivo()
    cliente.post("/api/recarregar")
    dados = cliente.get("/api/politicos/executivo", params={"uf": "sp"}).json()
    assert len(dados) == 1
    assert dados[0]["cargo"] == "governador"
    assert dados[0]["sigla_uf"] == "SP"


def test_o_salario_junta_por_cod_cargo_e_nao_pelo_texto(cliente):
    """`mandato.cargo` é o apelido (`presidente`) e `dim_cargo_publico.cargo`
    é o nome por extenso ("Presidente da República"). As duas colunas existem
    nas duas tabelas e parecem intercambiáveis: casar por texto não encontra
    nada, e o subsídio viria nulo para todos sem erro nenhum."""
    _cenario_executivo()
    cliente.post("/api/recarregar")
    dados = cliente.get("/api/politicos/executivo").json()
    assert dados[0]["salario"] == 30934.70
    assert dados[0]["norma_salario"] == "Lei 13.752/2018"


def test_subsidio_nao_conferido_chega_marcado(cliente):
    """Todo subsídio do acervo é transcrição não verificada. Entregar o
    número sem o aviso seria apresentar rascunho como fato apurado."""
    _cenario_executivo()
    cliente.post("/api/recarregar")
    assert cliente.get("/api/politicos/executivo").json()[0][
        "salario_conferido"] is False


def test_cargo_sem_subsidio_cadastrado_vem_nulo_e_nao_zero(cliente):
    _cenario_executivo()
    cliente.post("/api/recarregar")
    assert cliente.get("/api/politicos/executivo",
                       params={"uf": "SP"}).json()[0]["salario"] is None


def test_uf_sem_governador_devolve_lista_vazia(cliente):
    _cenario_executivo()
    cliente.post("/api/recarregar")
    assert cliente.get("/api/politicos/executivo",
                       params={"uf": "AC"}).json() == []


def test_resumo_de_custo_traz_os_totais_com_a_cobertura(cliente):
    """A soma vale o que a cobertura vale: 27 UFs e 5.570 municípios produzem
    números muito diferentes que se parecem igualmente com "o Brasil". A
    contagem de entes vai junto para a tela poder dizer de onde veio."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("financas_ente")
    linhas = []
    for cod, uf in (("35", "SP"), ("33", "RJ")):
        for conta, rot, estagio, valor in [
            ("DO3.0.00.00.00.00", "Correntes", "Despesas Empenhadas", 8e10),
            ("RO1.0.0.0.00.0.0", "Receitas Correntes",
             "Receitas Brutas Realizadas", 9e10)]:
            linhas.append(dict(
                cod_ibge=cod, ano=2024, periodo="anual", cod_conta=conta,
                cod_funcao=None, funcao=None, rotulo_conta=rot,
                estagio=estagio, valor=valor, esfera="estado", uf=uf,
                data_referencia="2024-12-31"))
    armazem.mesclar("financas_ente", linhas, "teste")
    cliente.post("/api/recarregar")

    r = cliente.get("/api/custo/resumo", params={"ano": 2024}).json()
    assert r["arrecadacao"] == 1.8e11 and r["arrecadacao_entes"] == 2
    assert r["despesa_subnacional"] == 1.6e11 and r["despesa_entes"] == 2
    assert any("União não entra" in a for a in r["avisos"]), (
        "a tela precisa dizer que a União está fora da soma")


def test_o_ano_do_resumo_nao_depende_de_um_recorte_so(cliente):
    """O exercício vinha de `vw_despesa_poder`. Com a despesa por função
    vazia e a receita cheia, o ano vinha nulo e os totais sumiam da tela como
    se não existissem — estando no disco."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("financas_ente")
    armazem.mesclar("financas_ente", [dict(
        cod_ibge="35", ano=2024, periodo="anual",
        cod_conta="RO1.0.0.0.00.0.0", cod_funcao=None, funcao=None,
        rotulo_conta="Receitas Correntes",
        estagio="Receitas Brutas Realizadas", valor=5e10, esfera="estado",
        uf="SP", data_referencia="2024-12-31")], "teste")
    cliente.post("/api/recarregar")

    r = cliente.get("/api/custo/resumo").json()
    assert r["ano"] == 2024, "o ano sumiu porque outro recorte estava vazio"
    assert r["arrecadacao"] == 5e10


def test_a_lista_de_politicos_traz_o_subsidio_do_cargo(cliente):
    """A dica ao passar o mouse mostra o subsídio, e ele vem JUNTO da lista.

    Uma chamada por `mouseenter` seriam 300 requisições por busca e uma
    corrida a cada movimento do ponteiro.
    """
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.mesclar("dim_cargo_publico", [dict(
        cod_cargo="deputado_federal", cargo="Deputado Federal",
        poder="legislativo", esfera="federal", ramo=None)], "teste")
    armazem.mesclar("dim_subsidio", [dict(
        cod_cargo="deputado_federal", vigencia_inicio="2023-02-01",
        valor_mensal=41650.92, norma="Decreto Legislativo da Mesa",
        url_norma=None, conferido=False, observacao=None,
        data_referencia="2023-02-01")], "teste")
    armazem.mesclar("dim_politico", [dict(
        fonte_origem="camara", id_origem="204536", nome="FULANO DE TAL",
        nome_eleitoral="Fulano", sigla_partido="ABC", sigla_uf="SP",
        casa="camara", cargo="deputado_federal", url_foto=None)], "teste")
    cliente.post("/api/recarregar")

    linha = cliente.get("/api/politicos", params={"busca": "FULANO"}).json()[0]
    assert linha["subsidio_cargo"] == 41650.92
    assert linha["cargo_extenso"] == "Deputado Federal"
    assert linha["poder"] == "legislativo"
    # O aviso viaja junto com o número: sem ele a dica apresentaria
    # transcrição não verificada como fato apurado.
    assert linha["subsidio_conferido"] is False


def test_os_filtros_de_politicos_continuam_funcionando(cliente):
    """O `WHERE` passou a qualificar as colunas com `p.` por causa do join.
    Um filtro que deixasse de casar sairia como 'sem resultados'."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("dim_politico")
    armazem.mesclar("dim_politico", [
        dict(fonte_origem="tse", id_origem="a", nome="ANA SILVA",
             nome_eleitoral="Ana", sigla_partido="AAA", sigla_uf="SP",
             casa=None, cargo="vereador", url_foto=None),
        dict(fonte_origem="tse", id_origem="b", nome="BRUNO SOUZA",
             nome_eleitoral="Bruno", sigla_partido="BBB", sigla_uf="MG",
             casa=None, cargo="prefeito", url_foto=None)], "teste")
    cliente.post("/api/recarregar")

    pedir = lambda **p: cliente.get("/api/politicos", params=p).json()
    assert len(pedir(uf="SP")) == 1
    assert len(pedir(cargo="prefeito")) == 1
    assert len(pedir(partido="bbb")) == 1
    assert len(pedir(busca="silva")) == 1
    assert len(pedir(uf="SP", cargo="prefeito")) == 0


# =================================================================
#  Cota parlamentar — a nota que chegou duas vezes
# =================================================================

def _nota(doc, valor, parcela, ano=2026, mes=1, tipo="DIVULGAÇÃO",
          fornecedor="AGENCIA LTDA"):
    return dict(
        casa="camara", id_documento=str(doc), num_parcela=parcela,
        num_ressarcimento=parcela, id_politico="204536",
        nome_politico="Fulano", sigla_partido="ABC", sigla_uf="SP",
        tipo_despesa=tipo, fornecedor=fornecedor,
        cnpj_cpf_fornecedor="10.111.222/0001-00", valor_documento=valor,
        url_documento=f"https://exemplo/{doc}.pdf", valor_liquido=valor,
        data_emissao=f"{ano}-{mes:02d}-15T00:00:00", ano=ano, mes=mes)


def test_a_mesma_nota_com_parcela_nula_e_zero_conta_UMA_vez(cliente):
    """O defeito que dobrou a cota parlamentar do acervo.

    A chave é `(casa, id_documento, num_parcela, num_ressarcimento)`. Uma
    versão antiga do coletor deixava parcela NULA quando a fonte mandava
    vazio; a atual grava "0". Nulo e "0" são chaves diferentes, então cada
    nota coletada nas duas épocas virou duas linhas — 96.407 documentos, e a
    despesa de 2026 saltou de R$ 121,5 mi para R$ 242,2 mi. O dobro exato.

    Conferido contra a página oficial de um deputado: R$ 67.682,76 do acervo
    limpo contra R$ 67.682,70 publicados pela Câmara.
    """
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("despesa_parlamentar")
    armazem.mesclar("despesa_parlamentar", [
        _nota(1, 1000.0, None), _nota(1, 1000.0, "0")], "teste")
    cliente.post("/api/recarregar")

    bruto = cliente.get("/api/politicos", params={"limite": 1})  # aquece as views
    assert bruto.status_code == 200

    from src.api import servidor  # noqa: PLC0415
    total = servidor._consultar(
        "SELECT SUM(valor_liquido) v FROM vw_cota_parlamentar")[0]["v"]
    assert total == 1000.0, f"a nota foi contada duas vezes: {total}"


def test_parcelas_DE_VERDADE_continuam_separadas(cliente):
    """A desduplicação não pode engolir parcelamento real: reembolso
    parcelado repete o mesmo documento com números de parcela diferentes, e
    cada parcela é um pagamento. Foi por isso que os campos entraram na
    chave — 1.307 notas eram descartadas sem eles."""
    from src.nucleo import armazem  # noqa: PLC0415
    from src.api import servidor  # noqa: PLC0415

    armazem.remover("despesa_parlamentar")
    armazem.mesclar("despesa_parlamentar", [
        _nota(2, 500.0, "1"), _nota(2, 500.0, "2"), _nota(2, 500.0, "3")], "teste")
    cliente.post("/api/recarregar")

    total = servidor._consultar(
        "SELECT SUM(valor_liquido) v, COUNT(*) n FROM vw_cota_parlamentar")[0]
    assert total["n"] == 3 and total["v"] == 1500.0


def test_a_ficha_do_parlamentar_junta_tudo(cliente):
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("despesa_parlamentar")
    armazem.mesclar("dim_cargo_publico", [dict(
        cod_cargo="deputado_federal", cargo="Deputado Federal",
        poder="legislativo", esfera="federal", ramo=None)], "teste")
    armazem.mesclar("dim_subsidio", [dict(
        cod_cargo="deputado_federal", vigencia_inicio="2023-02-01",
        valor_mensal=41650.92, norma="Decreto da Mesa", url_norma=None,
        conferido=False, observacao=None, data_referencia="2023-02-01")], "teste")
    armazem.mesclar("dim_politico", [dict(
        fonte_origem="camara", id_origem="204536", nome="FULANO DE TAL",
        nome_eleitoral="Fulano", sigla_partido="ABC", sigla_uf="SP",
        casa="camara", cargo="deputado_federal", url_foto=None)], "teste")
    armazem.mesclar("despesa_parlamentar", [
        _nota(10, 3000.0, "0", mes=1, tipo="DIVULGAÇÃO", fornecedor="AGENCIA"),
        _nota(11, 1000.0, "0", mes=2, tipo="TELEFONIA", fornecedor="TELECOM"),
        # a duplicata de novo, para a ficha não somar o dobro
        _nota(10, 3000.0, None, mes=1, tipo="DIVULGAÇÃO", fornecedor="AGENCIA"),
    ], "teste")
    cliente.post("/api/recarregar")

    sk = cliente.get("/api/politicos", params={"busca": "FULANO"}).json()[0]["sk"]
    f = cliente.get(f"/api/politicos/{sk}/ficha").json()

    assert f["ano"] == 2026
    assert f["cota_por_ano"][0]["valor"] == 4000.0, "somou a duplicata"
    assert {t["tipo_despesa"] for t in f["cota_por_tipo"]} == {"DIVULGAÇÃO", "TELEFONIA"}
    assert len(f["fornecedores"]) == 2
    assert f["politico"]["subsidio_cargo"] == 41650.92
    assert f["url_oficial"] == "https://www.camara.leg.br/deputados/204536"


def test_a_ficha_declara_o_que_o_painel_NAO_tem(cliente):
    """Verba de gabinete, pessoal e presença existem só em HTML na página da
    Câmara. O painel não raspa página — raspagem quebra em silêncio quando o
    site muda — e diz isso na tela, com o link para conferir na fonte."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.mesclar("dim_politico", [dict(
        fonte_origem="camara", id_origem="204536", nome="FULANO DE TAL",
        nome_eleitoral="Fulano", sigla_partido="ABC", sigla_uf="SP",
        casa="camara", cargo="deputado_federal", url_foto=None)], "teste")
    cliente.post("/api/recarregar")

    sk = cliente.get("/api/politicos", params={"busca": "FULANO"}).json()[0]["sk"]
    f = cliente.get(f"/api/politicos/{sk}/ficha").json()
    itens = {x["item"] for x in f["so_na_pagina_oficial"]}
    assert "Verba de gabinete" in itens
    assert "Pessoal de gabinete" in itens
    # Presença SAIU desta lista em 2026-08-28. Ela estava aqui por um erro
    # meu: procurei frequência em `/deputados/{id}` e nos endpoints por
    # deputado, não achei, e concluí que não existia em dado aberto. Existe
    # — no arquivo em lote `eventosPresencaDeputados`. Enquanto isso a tela
    # dizia ao cidadão que o dado não era público. Um item nesta lista é uma
    # afirmação sobre o mundo, e envelhece como qualquer outra.
    assert "Presença em plenário e comissões" not in itens
    # O que continua faltando é a justificativa: a fonte diz quem esteve,
    # nunca por quê faltou.
    assert "Justificativa das faltas" in itens


def test_quem_nao_e_da_camara_nao_ganha_avisos_da_camara(cliente):
    """Um vereador do TSE não tem cota parlamentar nem página na Câmara."""
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("dim_politico")
    armazem.mesclar("dim_politico", [dict(
        fonte_origem="tse", id_origem="v9", nome="BELTRANO",
        nome_eleitoral="Beltrano", sigla_partido="XYZ", sigla_uf="MA",
        casa=None, cargo="vereador", url_foto=None)], "teste")
    cliente.post("/api/recarregar")

    sk = cliente.get("/api/politicos", params={"busca": "BELTRANO"}).json()[0]["sk"]
    f = cliente.get(f"/api/politicos/{sk}/ficha").json()
    assert f["so_na_pagina_oficial"] == []
    assert f["url_oficial"] is None
    assert f["cota_por_ano"] == []


def test_custo_nao_esconde_arrecadacao_por_causa_de_ano_parcial(cliente):
    """O incidente, em forma de teste.

    As fontes têm calendários diferentes: o RREO é bimestral e já publica o
    exercício corrente; o DCA, de onde vêm arrecadação e despesa total, é
    anual e só sai no seguinte.

    A aba fixava UM ano para tudo — `MAX(ano)` de todas as tabelas. Bastou a
    despesa por função ganhar 2026 para a arrecadação de 2025 sumir da tela,
    com o número intacto no disco. Duas correções erradas em cima do mesmo
    lugar, em direções opostas; esta prende as duas.
    """
    from src.nucleo import armazem  # noqa: PLC0415

    # DCA (arrecadação e despesa) só até 2025.
    armazem.mesclar("financas_ente", [dict(
        cod_ibge="35", ano=2025, periodo="anual",
        cod_conta=conta, cod_funcao=None, funcao=None, rotulo_conta="x",
        estagio=estagio, valor=1_000_000.0, esfera="estado", uf="SP",
        data_referencia="2025-12-31")
        for conta, estagio in (("DO3.0.00.00.00.00", "Despesas Empenhadas"),
                               ("RO1.0.0.0.00.0.0", "Receitas Realizadas"))],
        "teste")
    # RREO (despesa por função) já com 2026 — é ele que empurra `vw_anos`
    # para 2026 e fazia a aba inteira migrar para um ano sem DCA.
    armazem.mesclar("despesa_funcao", [dict(
        cod_ibge="35", ano=2026, periodo="bimestre_6",
        cod_conta="exceto_intra|10|Saúde", cod_funcao="10",
        cod_funcao_mae="10", funcao="Saúde", funcao_mae="Saúde",
        rotulo_conta="Saúde", bloco="exceto_intra", descricao_bloco=None,
        estagio="DESPESAS EMPENHADAS ATÉ O BIMESTRE (B)", valor=500.0,
        esfera="estado", uf="SP", data_referencia="2026-12-01")], "teste")
    cliente.post("/api/recarregar")

    assert 2026 in [a["ano"] for a in cliente.get("/api/anos").json()["anos"]]

    resumo = cliente.get("/api/custo/resumo").json()
    assert resumo["arrecadacao"] is not None, (
        "a arrecadação de 2025 sumiu porque 2026 existe pela metade")
    assert resumo["ano_arrecadacao"] == 2025, (
        "o cartão precisa dizer de que ano é o número que mostra")
    assert resumo["despesa_subnacional"] is not None
    assert resumo["ano_despesa_subnacional"] == 2025


def test_custo_com_ano_pedido_explica_por_que_falta(cliente):
    """Pedir 2026 é legítimo — mas a tela tem de dizer por que está vazio."""
    resumo = cliente.get("/api/custo/resumo", params={"ano": 2026}).json()
    if resumo["arrecadacao"] is None:
        assert any("DCA" in a and "anual" in a for a in resumo["avisos"]), (
            "o aviso precisa explicar o calendário da fonte, não só dizer "
            "'nenhum ente com dado'")


def test_custo_medido_carrega_a_marca_da_coleta(cliente):
    """`pessoal_ativo` de 2025 publicava R$ 9,04 bi apoiado em 24 linhas: a
    paginação tinha sido interrompida, `_ctl/ingestao` sabia disso e a tela
    apresentava o piso como valor apurado. A marca da coleta agora viaja
    colada ao número."""
    from src.nucleo import armazem, controle  # noqa: PLC0415

    armazem.remover("custo_orgao")
    armazem.mesclar("custo_orgao", [
        {"conjunto": "demais_custos", "orgao_nome": "Órgão A",
         "item_custo": "diárias", "ano": 2025, "mes": 1, "valor": 100.0,
         "data_referencia": "2025-01-31"},
        {"conjunto": "pessoal_ativo", "orgao_nome": "Órgão B",
         "item_custo": "vencimentos", "ano": 2025, "mes": 1, "valor": 50.0,
         "data_referencia": "2025-01-31"},
    ], "teste")
    controle.gravar_marca("tesouro", "demais_custos_2025", 2025, 1,
                          situacao="ok")
    controle.gravar_marca("tesouro", "pessoal_ativo_2025", 2025, 1,
                          situacao="parcial",
                          detalhe="paginação interrompida — total é um piso")
    cliente.post("/api/recarregar")

    r = cliente.get("/api/custo/resumo", params={"ano": 2025}).json()
    por_conjunto = {l["conjunto"]: l for l in r["custo_medido_federal"]}

    assert por_conjunto["demais_custos"]["completo"] is True
    assert por_conjunto["pessoal_ativo"]["completo"] is False
    assert por_conjunto["pessoal_ativo"]["situacao_coleta"] == "parcial"
    assert por_conjunto["pessoal_ativo"]["linhas"] == 1
    assert any("PISO" in a and "pessoal_ativo" in a for a in r["avisos"]), (
        "o aviso precisa NOMEAR o recorte incompleto — 'alguns dados podem "
        "estar incompletos' é a frase que ninguém age em cima")
