"""Testes do terceiro relatório mentiroso, e da evolução do esquema.

O log era este:

    emenda_parlamentar ← portal_transparencia: 3000 novos, 0 alterados
    concluído com problema em 1 de 1 fonte(s): portal_transparencia

Nenhuma linha de erro no painel. Três defeitos independentes ali dentro.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from fastapi.testclient import TestClient  # noqa: E402

from src.api import tarefas, vistas  # noqa: E402
from src.coletores import orquestrador, portal_transparencia  # noqa: E402
from src.nucleo import armazem, config  # noqa: E402
from src.nucleo.registro import ContadorDeErros, obter as obter_log  # noqa: E402


# ============ 1. erro alheio virava problema da fonte
def test_erro_da_api_nao_conta_como_erro_da_coleta():
    """A causa exata: `api.servidor` logou ERROR durante a janela da coleta.

    O painel consulta a API a cada dois segundos enquanto coleta. Com o
    contador pendurado no logger raiz, qualquer erro do processo virava
    "problema" da fonte que estava coletando.
    """
    with ContadorDeErros() as contador:
        obter_log("api.servidor").error("consulta falhou definitivamente: ...")
        obter_log("uvicorn.error").error("algo do servidor")
        obter_log("httpx").error("requisição do painel")

    assert contador.total == 0, "erro de outro subsistema não é da coleta"


def test_erro_do_coletor_continua_contando():
    with ContadorDeErros() as contador:
        obter_log("coletores.camara").error("proposições 2026 falhou")
    assert contador.total == 1


def test_erro_do_nucleo_continua_contando():
    with ContadorDeErros() as contador:
        obter_log("nucleo.armazem").error("partição corrompida")
    assert contador.total == 1


def test_coleta_limpa_com_api_barulhenta_e_ok(monkeypatch):
    """O caso do Johnny: 3.000 linhas gravadas, zero erro do coletor."""
    class ColetorQueFuncionou:
        @staticmethod
        def executar(**kwargs):
            obter_log("coletores.portal").info("3000 novos")
            # a API reclamando em paralelo, como aconteceu de verdade
            obter_log("api.servidor").error(
                'Binder Error: Referenced column "tramitacao_atual" ...')

    monkeypatch.setattr(orquestrador, "_modulo", lambda n: ColetorQueFuncionou)
    resultado = orquestrador.executar_fonte("portal_transparencia",
                                            orquestrador.Opcoes())
    assert resultado.situacao == "ok"


# ============ 2. erro contado mas invisível
class TarefaFalsa:
    def __init__(self):
        self.linhas = []

    def registrar(self, nivel, mensagem):
        self.linhas.append((nivel, mensagem))


def test_espelho_mostra_erro_de_qualquer_modulo():
    """Contar sem mostrar é a pior combinação: 'problema' sem causa visível."""
    tarefa = TarefaFalsa()
    espelho = tarefas.EspelhoDeLog(tarefa)

    for nome, nivel in [("api.servidor", logging.ERROR),
                        ("uvicorn.error", logging.WARNING),
                        ("coletores.camara", logging.INFO)]:
        espelho.emit(logging.LogRecord(nome, nivel, "", 0, "algo", None, None))

    niveis = [n for n, _ in tarefa.linhas]
    assert "ERROR" in niveis, "erro da API tem que aparecer no painel"
    assert "WARNING" in niveis
    assert len(tarefa.linhas) == 3


def test_espelho_continua_filtrando_ruido_de_rotina():
    tarefa = TarefaFalsa()
    espelho = tarefas.EspelhoDeLog(tarefa)
    for nome in ("api.servidor", "uvicorn.access", "httpx"):
        espelho.emit(logging.LogRecord(nome, logging.INFO, "", 0,
                                       "GET /api/coleta 200", None, None))
    assert tarefa.linhas == [], "INFO de rotina da API continua fora"


# ============ 3. coluna nova sobre acervo antigo
def _proposicao_antiga():
    """Como o acervo do Johnny estava: sem as colunas criadas depois."""
    armazem.remover("proposicao")
    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": "1", "sigla_tipo": "PL",
        "identificador": "PL 1/2024", "ementa": "Antiga.",
        "data_apresentacao": "2024-01-10", "situacao": "Em tramitação",
        "nome_autor": "Fulano", "partido_autor": "XYZ", "uf_autor": "SP",
        "qtd_autores": 1, "url": None, "ultimo_status": None, "ano": 2024,
    }], "teste")


def test_coluna_nova_vira_nula_em_vez_de_derrubar_a_rota():
    """`Binder Error: Referenced column "tramitacao_atual" not found`."""
    _proposicao_antiga()
    con = vistas.conexao_leitura()

    linha = con.execute(
        "SELECT situacao, tramitacao_atual, orgao_atual FROM proposicao"
    ).fetchone()

    assert linha[0] == "Em tramitação", "o que existe continua vindo"
    assert linha[1] is None and linha[2] is None, "o que falta vem nulo"


def test_api_responde_com_acervo_antigo():
    _proposicao_antiga()
    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    resposta = cliente.get("/api/proposicoes", params={"limite": 300})
    assert resposta.status_code == 200, "era 500 antes do conserto"
    assert resposta.json()[0]["tramitacao_atual"] is None


def test_filtro_de_situacao_funciona_com_acervo_antigo():
    _proposicao_antiga()
    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    situacoes = cliente.get("/api/proposicoes/situacoes").json()
    assert situacoes[0]["situacao"] == "Em tramitação"


def test_dado_novo_nao_e_mascarado():
    """A view completa o que falta; não sobrescreve o que existe."""
    armazem.remover("proposicao")
    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": "2", "sigla_tipo": "PL",
        "identificador": "PL 2/2026", "ementa": "Nova.",
        "data_apresentacao": "2026-01-10", "situacao": "Pronta para Pauta",
        "tramitacao_atual": "Recebimento", "orgao_atual": "CCJC",
        "regime": "Ordinária", "data_ultimo_status": "2026-02-01",
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "url": None, "ultimo_status": None, "ano": 2026,
    }], "teste")

    con = vistas.conexao_leitura()
    assert con.execute("SELECT orgao_atual FROM proposicao").fetchone()[0] == "CCJC"


# ============ 4. paginação truncada em silêncio
def test_teto_de_paginas_avisa_em_vez_de_parecer_completo(monkeypatch, caplog):
    """3.000 linhas = 200 páginas × 15. Era o teto, não o fim dos dados."""
    monkeypatch.setattr(config, "CHAVE_PORTAL_TRANSPARENCIA", "x" * 32)
    monkeypatch.setattr(portal_transparencia.rede, "buscar",
                        lambda *a, **k: [{"codigoEmenda": "1"}] * 15)
    monkeypatch.setattr(portal_transparencia.armazem, "mesclar",
                        lambda *a, **k: None)
    marcas = {}
    monkeypatch.setattr(portal_transparencia.controle, "gravar_marca",
                        lambda *a, **k: marcas.update(k))

    with caplog.at_level("WARNING"):
        total = portal_transparencia.coletar_emendas(2025, paginas_max=10)

    assert total == 150
    assert "teto de 10 páginas" in caplog.text
    assert marcas.get("situacao") == "truncado"


def test_fim_dos_dados_nao_avisa_nada(monkeypatch, caplog):
    monkeypatch.setattr(config, "CHAVE_PORTAL_TRANSPARENCIA", "x" * 32)
    paginas = {"n": 0}

    def poucas(*a, **k):
        paginas["n"] += 1
        return [{"codigoEmenda": "1"}] if paginas["n"] <= 2 else []

    monkeypatch.setattr(portal_transparencia.rede, "buscar", poucas)
    monkeypatch.setattr(portal_transparencia.armazem, "mesclar",
                        lambda *a, **k: None)
    marcas = {}
    monkeypatch.setattr(portal_transparencia.controle, "gravar_marca",
                        lambda *a, **k: marcas.update(k))

    with caplog.at_level("WARNING"):
        assert portal_transparencia.coletar_emendas(2025, paginas_max=100) == 2
    assert "teto" not in caplog.text
    assert marcas.get("situacao") == "ok"


# ============ 5. a fonte avisa quando o endpoint vai morrer
class RespostaComCabecalho:
    def __init__(self, cabecalhos):
        self.status_code = 200
        self.headers = cabecalhos
        self.text = "{}"
        self.content = b"{}"

    def json(self):
        return {"ok": True}

    def raise_for_status(self):
        pass


def _sessao_com(cabecalhos):
    class Sessao:
        headers: dict = {}

        def get(self, *a, **k):
            return RespostaComCabecalho(cabecalhos)
    return Sessao()


def test_avisa_quando_a_fonte_marca_o_endpoint_como_depreciado(monkeypatch, caplog):
    """O Senado marca com Deprecation/Sunset/Link. Ignorar isso é esperar o
    dia em que o endereço para de responder sem explicação."""
    from src.nucleo import rede

    monkeypatch.setattr(rede, "sessao", lambda f: _sessao_com({
        "Deprecation": "Mon, 10 Mar 2025 00:00:00 GMT",
        "Sunset": "Sun, 01 Feb 2026 00:00:00 GMT",
        "Link": '<https://legis.senado.leg.br/dadosabertos/composicao/lideranca>; rel="successor"',
    }))
    rede.definir_intervalo("senado_teste", 0)
    rede._ja_avisado.clear()

    with caplog.at_level("WARNING"):
        rede.buscar("senado_teste", "http://exemplo/antigo")

    assert "DEPRECIADO" in caplog.text
    assert "01 Feb 2026" in caplog.text
    assert "composicao/lideranca" in caplog.text, "o substituto tem que aparecer"


def test_aviso_de_depreciacao_sai_uma_vez_so(monkeypatch, caplog):
    from src.nucleo import rede

    monkeypatch.setattr(rede, "sessao",
                        lambda f: _sessao_com({"Sunset": "amanhã"}))
    rede.definir_intervalo("senado_teste2", 0)
    rede._ja_avisado.clear()

    with caplog.at_level("WARNING"):
        for _ in range(5):
            rede.buscar("senado_teste2", "http://exemplo/antigo")

    assert caplog.text.count("DEPRECIADO") == 1, "numa varredura viraria ruído"


def test_endpoint_saudavel_nao_gera_aviso(monkeypatch, caplog):
    from src.nucleo import rede

    monkeypatch.setattr(rede, "sessao", lambda f: _sessao_com({}))
    rede.definir_intervalo("senado_teste3", 0)
    rede._ja_avisado.clear()

    with caplog.at_level("WARNING"):
        rede.buscar("senado_teste3", "http://exemplo/atual")
    assert "DEPRECIADO" not in caplog.text


# ============ 6. Tesouro/SIC: catálogo primeiro, colunas detectadas
def test_pergunta_ao_catalogo_em_vez_de_cravar_url(monkeypatch):
    """A cota parlamentar já quebrou por URL fixa. Aqui o catálogo manda."""
    from src.coletores import tesouro

    pedidos = []

    def falso(fonte, url, parametros=None, **k):
        pedidos.append((url, parametros))
        return {"success": True, "result": {"resources": [
            {"name": "custos_2025.csv", "format": "CSV",
             "url": "https://exemplo/custos_2025.csv", "size": 100},
        ]}}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    recursos = tesouro.catalogar("pessoal_ativo")

    assert pedidos[0][0].endswith("/package_show")
    assert pedidos[0][1]["id"] == "custos-por-itens-de-custos-pessoal-ativo"
    assert recursos[0]["url"] == "https://exemplo/custos_2025.csv"


def test_prefere_o_arquivo_do_ano_pedido():
    from src.coletores import tesouro
    recursos = [
        {"nome": "custos_2023.csv", "formato": "CSV", "url": "u23"},
        {"nome": "custos_2025.csv", "formato": "CSV", "url": "u25"},
    ]
    assert tesouro._escolher_recurso(recursos, 2025)["url"] == "u25"


def test_ignora_recurso_que_nao_e_tabela():
    from src.coletores import tesouro
    recursos = [{"nome": "manual.pdf", "formato": "PDF", "url": "u"}]
    assert tesouro._escolher_recurso(recursos, 2025) is None


def test_reconhece_colunas_por_padrao_de_nome():
    from src.coletores import tesouro
    mapa = tesouro._mapear_colunas(
        ["ANO", "MES", "NOME_ORGAO", "COD_UG", "ITEM_CUSTO", "VALOR_CUSTO"])
    assert mapa["ano"] == "ANO"
    assert mapa["orgao_nome"] == "NOME_ORGAO"
    assert mapa["valor"] == "VALOR_CUSTO"


def test_coluna_nao_reconhecida_vira_erro_com_a_lista_real(monkeypatch, caplog):
    """Em vez de gravar coluna vazia, diz o que o arquivo realmente tem —
    foi a falta disso que deixou a Situação em branco por uma semana."""
    from src.coletores import tesouro
    import pandas as pd

    monkeypatch.setattr(tesouro, "catalogar", lambda c: [
        {"nome": "x.csv", "formato": "CSV", "url": "u"}])
    monkeypatch.setattr(tesouro, "_ler_tabela",
                        lambda r: pd.DataFrame([{"foo": "1", "bar": "2"}]))

    with caplog.at_level("ERROR"):
        assert tesouro.coletar_custos("pessoal_ativo", 2025) == 0
    assert "não reconheci as colunas" in caplog.text
    assert "foo" in caplog.text and "bar" in caplog.text


# ============ 7. subsídio: valor sem norma é número indefensável
def _semear_referencias(tmp_path):
    from src.coletores import referencias
    csv = tmp_path / "subsidios.csv"
    csv.write_text(
        "cod_cargo,cargo,poder,esfera,ramo,vigencia_inicio,valor_mensal,"
        "norma,url_norma,conferido,observacao\n"
        "deputado_federal,Deputado Federal,legislativo,federal,,2023-02-01,"
        "1000.00,Decreto X,http://n,nao,rascunho\n"
        "ministro_stf,Ministro do STF,judiciario,federal,supremo,2025-02-01,"
        "2000.00,Lei Y,http://n,sim,\n"
        "juiz_federal,Juiz Federal,judiciario,federal,federal,,,"
        "escalonamento CNJ,,nao,varia por classe\n",
        encoding="utf-8")
    return referencias.carregar_subsidios(csv)


def test_referencia_carrega_cargo_norma_e_conferido(tmp_path):
    assert _semear_referencias(tmp_path) == 3
    df = armazem.ler("dim_subsidio")
    por_cargo = dict(zip(df["cod_cargo"], df["conferido"]))
    assert por_cargo["ministro_stf"] is True or por_cargo["ministro_stf"] == 1
    assert not por_cargo["deputado_federal"]


def test_cargo_sem_valor_nao_vira_zero(tmp_path):
    _semear_referencias(tmp_path)
    df = armazem.ler("dim_subsidio", filtro="cod_cargo = 'juiz_federal'")
    valor = df.iloc[0]["valor_mensal"]
    assert valor is None or valor != valor, "sem valor é nulo, nunca zero"


def test_custo_estimado_so_existe_com_ocupantes_e_subsidio(tmp_path):
    _semear_referencias(tmp_path)
    armazem.mesclar("dim_politico", [{
        "fonte_origem": "camara", "id_origem": str(i), "nome": f"D{i}",
        "nome_eleitoral": f"D{i}", "sigla_partido": "X", "sigla_uf": "SP",
        "id_legislatura": "57", "email": None, "url_foto": None,
        "casa": "camara", "cargo": "deputado_federal"} for i in range(10)], "t")

    con = vistas.conexao_leitura()
    linhas = con.execute("""
        SELECT cod_cargo, ocupantes, custo_anual_estimado
          FROM vw_custo_cargo ORDER BY cod_cargo""").fetchall()
    por_cargo = {l[0]: (l[1], l[2]) for l in linhas}

    assert por_cargo["deputado_federal"] == (10, 10 * 1000.00 * 13.33)
    assert por_cargo["ministro_stf"][1] is None, "sem ocupante, sem custo"
    assert por_cargo["juiz_federal"][1] is None, "sem subsídio, sem custo"


def test_api_de_custo_marca_o_que_nao_foi_conferido(tmp_path):
    _semear_referencias(tmp_path)
    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    cargos = cliente.get("/api/custo/cargos").json()
    por_cargo = {c["cod_cargo"]: c for c in cargos}
    assert por_cargo["deputado_federal"]["conferido"] is False
    assert por_cargo["ministro_stf"]["conferido"] is True
    assert por_cargo["deputado_federal"]["norma"] == "Decreto X"


def test_resumo_de_custo_avisa_sobre_o_que_e_estimativa(tmp_path):
    _semear_referencias(tmp_path)
    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    resumo = cliente.get("/api/custo/resumo").json()
    texto_avisos = " ".join(resumo["avisos"])
    assert "não conferidos" in texto_avisos
    assert "13,33" in texto_avisos, "a fórmula tem que estar visível"
    assert resumo["arrecadacao"] is None, "não coletada, não inventada"


# ============ 8. tipo divergente entre partições
def test_coluna_toda_nula_e_gravada_com_o_tipo_declarado():
    """A raiz do 'Could not convert string ... to INT32'.

    Coluna sem nenhum valor numa partição virava int32 no Parquet — o pandas
    não tem como adivinhar que era texto. Quando outra partição trouxe a
    mesma coluna preenchida, a leitura das duas juntas estourou.
    """
    import glob
    import pyarrow.parquet as pq
    from src.nucleo import config

    armazem.remover("proposicao")
    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": str(i), "sigla_tipo": "PL",
        "identificador": f"PL {i}", "ementa": "x",
        "data_apresentacao": "2024-01-01", "situacao": None,
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "url": None, "ultimo_status": None, "ano": 2024,
    } for i in range(3)], "teste")

    arquivo = glob.glob(str(config.FATO / "proposicao" / "**" / "*.parquet"),
                        recursive=True)[0]
    tipo = str(pq.read_schema(arquivo).field("situacao").type)
    assert tipo == "string", f"situacao gravada como {tipo}, não como texto"


def test_particoes_com_tipos_diferentes_sao_legiveis():
    """Acervo gravado por versões diferentes do projeto tem que abrir."""
    armazem.remover("proposicao")

    comum = {"sigla_tipo": "PL", "ementa": "x", "nome_autor": None,
             "partido_autor": None, "uf_autor": None, "qtd_autores": 0,
             "url": None, "ultimo_status": None, "casa": "camara"}
    armazem.mesclar("proposicao", [{
        **comum, "id_proposicao": "1", "identificador": "PL 1/2024",
        "data_apresentacao": "2024-01-01", "situacao": None, "ano": 2024}],
        "teste")
    armazem.mesclar("proposicao", [{
        **comum, "id_proposicao": "2", "identificador": "PL 2/2026",
        "data_apresentacao": "2026-01-01",
        "situacao": "Aguardando Providências Internas", "ano": 2026}],
        "teste")

    df = armazem.ler("proposicao", colunas=["id_proposicao", "situacao"])
    assert len(df) == 2
    assert "Aguardando Providências Internas" in set(df["situacao"].dropna())


def test_api_le_acervo_com_tipos_divergentes():
    """Era um 500 em /api/proposicoes e /api/proposicoes/situacoes."""
    armazem.remover("proposicao")
    comum = {"sigla_tipo": "PL", "ementa": "x", "nome_autor": None,
             "partido_autor": None, "uf_autor": None, "qtd_autores": 0,
             "url": None, "ultimo_status": None, "casa": "camara"}
    armazem.mesclar("proposicao", [{
        **comum, "id_proposicao": "1", "identificador": "PL 1/2024",
        "data_apresentacao": "2024-01-01", "situacao": None, "ano": 2024}],
        "teste")
    armazem.mesclar("proposicao", [{
        **comum, "id_proposicao": "2", "identificador": "PL 2/2026",
        "data_apresentacao": "2026-01-01", "situacao": "Em tramitação",
        "ano": 2026}], "teste")

    from src.api import servidor  # noqa: PLC0415
    cliente = TestClient(servidor.app)
    cliente.post("/api/recarregar")

    assert cliente.get("/api/proposicoes", params={"limite": 300}).status_code == 200
    situacoes = cliente.get("/api/proposicoes/situacoes")
    assert situacoes.status_code == 200
    assert situacoes.json()[0]["situacao"] == "Em tramitação"


def test_merge_cura_a_particao_de_tipo_errado():
    """Recoletar conserta o acervo — não é preciso apagar nada."""
    import glob
    import pandas as pd
    import pyarrow.parquet as pq
    from src.nucleo import config, esquema

    armazem.remover("proposicao")
    tabela = esquema.obter("proposicao")
    destino = armazem.caminho_particao(tabela, {"ano": 2026})
    destino.parent.mkdir(parents=True, exist_ok=True)
    # grava à moda antiga: situacao sem tipo
    pd.DataFrame([{
        "sk": "a" * 32, "casa": "camara", "id_proposicao": "1",
        "sigla_tipo": "PL", "identificador": "PL 1/2026", "ementa": "velha",
        "data_apresentacao": "2026-01-01", "situacao": None,
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "url": None, "ultimo_status": None, "ano": 2026,
        "_hash_registro": "h", "_fonte": "antigo",
        "_criado_em": pd.Timestamp.now("UTC"),
        "_atualizado_em": pd.Timestamp.now("UTC"),
    }]).to_parquet(destino, index=False)

    armazem.mesclar("proposicao", [{
        "casa": "camara", "id_proposicao": "2", "sigla_tipo": "PL",
        "identificador": "PL 2/2026", "ementa": "nova",
        "data_apresentacao": "2026-02-01", "situacao": "Em tramitação",
        "nome_autor": None, "partido_autor": None, "uf_autor": None,
        "qtd_autores": 0, "url": None, "ultimo_status": None, "ano": 2026,
    }], "novo")

    tipo = str(pq.read_schema(destino).field("situacao").type)
    assert tipo == "string", f"a partição continuou como {tipo}"


def test_cota_avisa_quando_falta_coluna_de_parcela(monkeypatch, caplog):
    """1.307 notas descartadas por mês sem nenhuma explicação no log."""
    import pandas as pd
    from src.coletores import camara

    monkeypatch.setattr(camara, "_csv_da_cota", lambda ano: pd.DataFrame([
        {"ideDocumento": "1", "vlrLiquido": "10", "numAno": "2026",
         "numMes": "1", "txNomeParlamentar": "F"}]))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)
    armazem.remover("despesa_parlamentar")

    with caplog.at_level("WARNING"):
        camara.coletar_despesas(2026)

    assert "numParcela" in caplog.text
    assert "Colunas disponíveis" in caplog.text
