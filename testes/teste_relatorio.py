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


# ============ 6. Custos do Governo Federal: API em vez de CSV
# Registro REAL da API, colhido pela verificação de 25/08. Os nomes que eu
# havia suposto a partir do Swagger erraram todos.
_REAL = {
    "co_natureza_juridica": 2, "ds_natureza_juridica": "FUNDACAO PUBLICA",
    "co_organizacao_n0": "000026", "ds_organizacao_n0": "PRESIDENCIA DA REPUBLICA",
    "co_organizacao_n1": "000244", "ds_organizacao_n1": "MINISTERIO DA EDUCACAO",
    "an_lanc": 2025, "me_lanc": 3, "va_custo_de_pessoal": 1500.5,
}


def test_custos_le_o_registro_real_da_api(monkeypatch):
    """Contra o registro que a API devolveu de verdade, não contra o que eu
    supus lendo o Swagger — que documenta os parâmetros, não a resposta."""
    from src.coletores import tesouro

    pedidos = []

    def falso(fonte, url, parametros=None, **k):
        pedidos.append((url, parametros))
        return {"items": [_REAL], "hasMore": False}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    linhas, completo, _ = tesouro.coletar("pessoal_ativo", 2025)

    assert completo
    assert pedidos[0][0].endswith("/pessoal_ativo")
    assert pedidos[0][1]["ano"] == 2025
    assert linhas[0]["orgao_nome"] == "MINISTERIO DA EDUCACAO"
    assert linhas[0]["orgao_codigo"] == "000244"
    assert linhas[0]["valor"] == 1500.5
    assert linhas[0]["mes"] == 3


def test_valor_tem_nome_diferente_em_cada_endpoint():
    """`va_custo_de_pessoal`, `va_custo_pensionistas`, `va_custo`… Uma lista
    de nomes envelheceria a cada recorte novo; o prefixo não."""
    from src.coletores import tesouro

    for campo in ("va_custo_de_pessoal", "va_custo_pessoal_inativo",
                  "va_custo_pensionistas", "va_custo_depreciacao",
                  "va_custo_transferencias", "va_custo"):
        assert tesouro._valor({campo: 7}) == 7, campo
    assert tesouro._valor({"ds_organizacao_n1": "x"}) is None


def test_endpoint_demais_usa_outro_vocabulario():
    """O `demais` fala `co_siorg_n04..n07` em vez de `co_organizacao_n0..n6`,
    e o ministério muda de nível: n1 nos cinco, n05 aqui."""
    from src.coletores import tesouro

    demais = {"ds_siorg_n04": "PRESIDENCIA DA REPUBLICA",
              "ds_siorg_n05": "MINISTERIO DA GESTAO", "co_siorg_n05": "308803",
              "an_referencia": 2025, "me_referencia": 3, "va_custo": 10.0,
              "no_natureza_despesa_deta": "Diárias"}
    assert tesouro._campo(demais, "orgao_nome") == "MINISTERIO DA GESTAO"
    assert tesouro._campo(demais, "ano") == 2025
    assert tesouro._campo(demais, "item_custo") == "Diárias"


def test_custos_agrega_as_dimensoes_que_o_painel_nao_usa(monkeypatch):
    """`pessoal_ativo` vem quebrado por sexo, escolaridade e faixa etária: um
    único mês passou de 100 mil linhas e estourou o teto de páginas. O painel
    pergunta quanto custa o ÓRGÃO — somar na leitura descarta a explosão
    combinatória sem perder a resposta."""
    from src.coletores import tesouro

    monkeypatch.setattr(tesouro.rede, "buscar", lambda *a, **k: {"items": [
        {**_REAL, "in_sexo": "M", "ds_faixa_etaria": "30-39",
         "va_custo_de_pessoal": 100},
        {**_REAL, "in_sexo": "F", "ds_faixa_etaria": "30-39",
         "va_custo_de_pessoal": 150},
        {**_REAL, "in_sexo": "M", "ds_faixa_etaria": "40-49",
         "va_custo_de_pessoal": 200},
    ], "hasMore": False})

    linhas, _, _ = tesouro.coletar("pessoal_ativo", 2025)
    assert len(linhas) == 1, "três recortes do mesmo órgão viram uma linha"
    assert linhas[0]["valor"] == 450


def test_custos_pagina_ate_o_fim(monkeypatch):
    """250 itens por página: parar na primeira devolveria um total com cara
    de completo."""
    from src.coletores import tesouro

    paginas = [
        {"items": [{**_REAL, "ds_organizacao_n1": "A", "va_custo": 1}],
         "hasMore": True},
        {"items": [{**_REAL, "ds_organizacao_n1": "B", "va_custo": 2}],
         "hasMore": False},
    ]
    monkeypatch.setattr(tesouro.rede, "buscar",
                        lambda *a, **k: paginas.pop(0))
    assert len(tesouro.coletar("demais_custos", 2025)[0]) == 2


def test_diagnostico_pede_uma_pagina_so(monkeypatch):
    """`descobrir()` quer os NOMES dos campos. Paginar o recorte inteiro
    custou 232 páginas e quatro minutos de rede para responder o que a
    primeira linha responde."""
    from src.coletores import tesouro

    chamadas = []

    def falso(fonte, url, parametros=None, **k):
        chamadas.append(parametros)
        return {"items": [_REAL], "hasMore": True}   # sempre diz que há mais

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    tesouro.descobrir(2025)

    # Seis recortes, uma chamada cada — e nenhuma com offset.
    assert len(chamadas) == len(tesouro.CONJUNTOS), chamadas
    assert all("offset" not in (c or {}) for c in chamadas)


def test_falha_no_meio_da_paginacao_nao_zera_o_que_ja_veio(monkeypatch, caplog):
    """A conexão caiu na página 232 e as 231 anteriores foram perdidas —
    quatro minutos de rede jogados fora. O que chegou volta marcado como
    parcial, e o aviso diz que o total é um piso."""
    from src.coletores import tesouro

    estado = {"n": 0}

    def falso(fonte, url, parametros=None, **k):
        estado["n"] += 1
        if estado["n"] > 2:
            raise RuntimeError("Remote end closed connection without response")
        return {"items": [{**_REAL, "va_custo": estado["n"]}], "hasMore": True}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    with caplog.at_level("WARNING"):
        linhas, completo, _ = tesouro.coletar("demais_custos", 2025)

    assert not completo, "parcial precisa ser declarado"
    assert linhas, "o que já tinha vindo não pode ser descartado"
    assert "PARCIAIS" in caplog.text or "PARCIAL" in caplog.text


def test_primeira_pagina_que_falha_ainda_levanta(monkeypatch):
    """Sem nenhuma linha recebida, engolir o erro seria reportar 'coletei
    nada com sucesso'."""
    import pytest as _pytest

    from src.coletores import tesouro

    def falso(*a, **k):
        raise RuntimeError("DNS falhou")

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    with _pytest.raises(RuntimeError):
        tesouro.coletar("depreciacao", 2025)


def test_custos_sem_valor_nao_vira_linha(monkeypatch):
    """Linha sem valor não é custo zero — é linha que não diz nada."""
    from src.coletores import tesouro
    monkeypatch.setattr(tesouro.rede, "buscar", lambda *a, **k: {
        "items": [{"ds_organizacao_n1": "A"},
                  {"ds_organizacao_n1": "B", "va_custo_depreciacao": 10}],
        "hasMore": False})
    linhas, _, _ = tesouro.coletar("depreciacao", 2025)
    assert [l["orgao_nome"] for l in linhas] == ["B"]


def test_custos_avisa_quando_a_resposta_nao_tem_lista(monkeypatch, caplog):
    """Resposta inesperada precisa mostrar as chaves recebidas: sem isso, a
    próxima execução repete o mesmo mistério — foi o que aconteceu com o
    envelope `registros` das transferências."""
    from src.coletores import tesouro
    monkeypatch.setattr(tesouro.rede, "buscar",
                        lambda *a, **k: {"status": "erro", "mensagem": "x"})
    with caplog.at_level("WARNING"):
        assert tesouro.coletar("pensionista", 2025)[0] == []
    assert "sem lista" in caplog.text
    assert "status" in caplog.text


def test_custos_respeita_o_limite_publicado():
    """A documentação diz 1 requisição por segundo, e o piso do projeto não
    deixa ninguém pedir menos (armadilha 2r)."""
    from src.nucleo import config
    assert config.INTERVALO_REQUISICOES["tesouro"] >= 1.0


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


def test_toda_coluna_gravada_esta_declarada_no_contrato():
    """`rotulo_conta` e `uf` eram gravados pelo coletor do SICONFI e não
    estavam no contrato de colunas. Com a tabela cheia ninguém notava — o
    Parquet trazia as colunas. Numa instalação NOVA, a view nasce do contrato
    e três views de despesa quebravam com

        Binder Error: Referenced column "rotulo_conta" not found

    Este teste cria o armazém vazio e monta as views: é o estado de quem
    acabou de clonar o projeto.
    """
    from src.api import vistas  # noqa: PLC0415
    from src.nucleo import armazem  # noqa: PLC0415

    armazem.remover("financas_ente")
    con = vistas.conexao_leitura()

    # Não basta "criou": uma view pode existir e estourar ao ser lida.
    for view in ("vw_despesa_categoria", "vw_despesa_natureza",
                 "vw_financas_subfuncao", "vw_despesa_total",
                 "vw_receita_total", "vw_conferencia_despesa"):
        con.execute(f"SELECT * FROM {view} LIMIT 1").fetchall()


def test_contrato_de_financas_cobre_o_que_o_coletor_grava():
    """Guarda de manutenção: uma coluna nova no coletor sem entrada no
    contrato repete o defeito acima, e só aparece para quem instala do zero."""
    from src.nucleo.esquema import _COLUNAS  # noqa: PLC0415

    declaradas = {nome for nome, _ in _COLUNAS["financas_ente"]}
    gravadas = {"cod_ibge", "ano", "periodo", "cod_conta", "cod_funcao",
                "funcao", "rotulo_conta", "estagio", "valor", "esfera", "uf",
                "data_referencia"}
    assert not (gravadas - declaradas), (
        f"o coletor grava colunas fora do contrato: {gravadas - declaradas}")


# ---------- Custos: paginação medida contra a API real (29/08/2026)
# `scripts/medir_paginacao_custos.py` mediu no endpoint de verdade:
#   limit=250 → 208 linhas/s | limit=10000 → 2.857 linhas/s | totalResults: null
# Estes testes travam as três consequências disso no código.

def test_pede_pagina_grande_porque_o_servidor_honra(monkeypatch):
    """250 era o PADRÃO do servidor, não um limite. Pedir 10 mil é o que
    separa horas de minutos: um ano de pessoal_ativo passa de um milhão de
    linhas brutas."""
    from src.coletores import tesouro

    pedidos = []

    def falso(fonte, url, parametros=None, **k):
        pedidos.append(dict(parametros or {}))
        return {"items": [_REAL], "hasMore": False, "limit": parametros["limit"]}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    tesouro.coletar("demais_custos", 2025)

    assert pedidos[0]["limit"] == tesouro.PAGINA == 10_000
    assert "offset" not in pedidos[0], "a primeira página não pede offset"


def test_adota_o_limite_que_o_servidor_aplicou(monkeypatch, caplog):
    """Se o servidor devolver menos do que foi pedido, andar `limit` posições
    pularia registros. Quem manda é o que ele devolveu."""
    from src.coletores import tesouro

    paginas = []

    def falso(fonte, url, parametros=None, **k):
        paginas.append(dict(parametros or {}))
        if len(paginas) == 1:
            return {"items": [_REAL] * 2, "hasMore": True, "limit": 2}
        return {"items": [_REAL], "hasMore": False, "limit": 2}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    with caplog.at_level("INFO"):
        _, completo, alcancado = tesouro.coletar("demais_custos", 2025)

    assert completo and alcancado == 3
    assert paginas[1]["offset"] == 2, "o offset anda pelo que veio, não pelo pedido"
    assert "o servidor aplicou" in caplog.text


def test_pagina_vazia_com_hasmore_nao_vira_laco_infinito(monkeypatch, caplog):
    """Página vazia com hasMore verdadeiro girava em falso até bater o teto:
    1.500 requisições para não trazer nada."""
    from src.coletores import tesouro

    def falso(fonte, url, parametros=None, **k):
        return {"items": [], "hasMore": True, "limit": 10_000}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    with caplog.at_level("WARNING"):
        linhas, completo, _ = tesouro.coletar("demais_custos", 2025)

    assert linhas == [] and not completo
    assert "girar em falso" in caplog.text


def test_retomada_continua_do_offset_e_soma_ao_que_ja_havia(monkeypatch):
    """O defeito que fez 24 h de carga não terminarem nada: toda execução
    recomeçava do offset zero, rebaixava o mesmo prefixo e parava no mesmo
    lugar. Agora a segunda execução continua de onde a primeira parou, e o
    valor gravado é a soma dos dois trechos — não o segundo sozinho."""
    from src.nucleo import armazem  # noqa: PLC0415
    from src.coletores import tesouro

    armazem.remover("custo_orgao")
    armazem.mesclar("custo_orgao", [{
        "conjunto": "demais_custos", "orgao_nome": "MINISTERIO DA EDUCACAO",
        # `item_custo` sai de ds_natureza_juridica no registro real: a
        # semente precisa cair na MESMA chave, senão vira linha nova.
        "orgao_codigo": "000244", "item_custo": "FUNDACAO PUBLICA",
        "ano": 2025, "mes": 3, "valor": 100.0,
        "data_referencia": "2025-03-01"}], "teste")

    pedidos = []

    def falso(fonte, url, parametros=None, **k):
        pedidos.append(dict(parametros or {}))
        return {"items": [_REAL], "hasMore": False, "limit": 10_000}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    linhas, completo, _ = tesouro.coletar("demais_custos", 2025,
                                          offset=250, retomar=True)

    assert pedidos[0]["offset"] == 250, "tem de continuar de onde parou"
    assert completo
    assert len(linhas) == 1
    assert linhas[0]["valor"] == 1600.5, (   # 100 já gravado + 1500,5 do trecho novo
        "o trecho novo soma ao que já estava gravado; sem isso a tela passaria "
        "a mostrar MENOS do que mostrava antes da retomada")


def test_marca_guarda_a_posicao_quando_fica_pela_metade(monkeypatch):
    """A marca precisa dizer ONDE parou. Guardando só o ano, a execução
    seguinte não tem como retomar e recomeça do zero."""
    from src.coletores import tesouro
    from src.nucleo import controle  # noqa: PLC0415

    estado = {"n": 0}

    def falso(fonte, url, parametros=None, **k):
        estado["n"] += 1
        if estado["n"] > 1:
            raise RuntimeError("Remote end closed connection")
        return {"items": [_REAL] * 3, "hasMore": True, "limit": 10_000}

    monkeypatch.setattr(tesouro.rede, "buscar", falso)
    tesouro.executar(anos=[2025], conjuntos=["demais_custos"], refazer=True)

    assert controle.ler_marca("tesouro", "demais_custos_2025") == "offset=3"
    assert tesouro._retomada("demais_custos", 2025) == 3


def test_marca_antiga_nao_e_confundida_com_posicao():
    """Marca de versão anterior guardava o ANO. Lê-la como offset pularia o
    começo do recorte — dado perdido em silêncio."""
    from src.coletores import tesouro
    from src.nucleo import controle  # noqa: PLC0415

    controle.gravar_marca("tesouro", "pensionista_2019", "2019", 10,
                          situacao="parcial")
    assert tesouro._retomada("pensionista", 2019) == 0
