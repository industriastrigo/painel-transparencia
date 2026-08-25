"""API de leitura do Painel da Transparência.

FastAPI só lê as views DuckDB sobre os Parquet — nenhuma rota chama API
externa em tempo de renderização. Se a fonte estiver fora do ar, o painel
continua respondendo com o último dado coletado, e o rodapé mostra a data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..coletores import ibge as coletor_ibge
from ..coletores import orquestrador
from ..nucleo import armazem, config, controle, segredos
from ..nucleo.registro import obter as obter_log
from . import tarefas, vistas

log = obter_log("api.servidor")

app = FastAPI(
    title="Painel da Transparência",
    description="Dados políticos, socioeconômicos e orçamentários do Brasil",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_con = None
_dados_mudaram = False
_trava_con = __import__("threading").Lock()


def marcar_dados_alterados() -> None:
    """Sinaliza que o armazém mudou; as views serão refeitas na próxima leitura.

    A coleta roda em outra thread. Ela NÃO recria as views ali mesmo: mexer no
    catálogo enquanto requisições leem dele é corrida — e foi o que travou o
    processo em teste. Aqui só levanta a bandeira; quem reconstrói é a próxima
    requisição, na sua própria thread.
    """
    global _dados_mudaram
    _dados_mudaram = True


def con():
    global _con, _dados_mudaram
    with _trava_con:
        if _con is None:
            _con = vistas.conexao_leitura()
            _dados_mudaram = False
        elif _dados_mudaram:
            vistas.criar(_con)
            _dados_mudaram = False
        return _con


def reiniciar_conexao() -> None:
    """Descarta a conexão em cache.

    A conexão guarda as views, que guardam os CAMINHOS dos Parquet. Trocar
    `PAINEL_DADOS` sem passar por aqui deixa a API lendo o armazém anterior —
    era o que fazia os testes darem resultados diferentes conforme a ordem
    dos arquivos, mesmo cada um tendo sua pasta.
    """
    global _con
    if _con is not None:
        try:
            _con.close()
        except Exception:  # noqa: BLE001
            pass
    _con = None


def recarregar_views() -> list[str]:
    """Recria as views. Necessário depois de uma coleta nova: a view de uma
    tabela que ainda não existia foi criada vazia e precisa passar a apontar
    para os Parquet recém-escritos."""
    return vistas.criar(con())


def _registros(df) -> list[dict]:
    """NaN e infinito não são JSON válido — viram null, que o painel já sabe
    desenhar como 'sem dado'."""
    if df.empty:
        return []
    limpo = df.replace([float("inf"), float("-inf")], pd.NA)
    return limpo.astype(object).where(limpo.notna(), None).to_dict("records")


def _consultar(sql: str, parametros: list[Any] | None = None) -> list[dict]:
    """Cada consulta usa seu próprio cursor.

    A conexão DuckDB guarda o resultado corrente, e `execute()` + `.df()` são
    duas etapas. Com a conexão compartilhada entre requisições — e o FastAPI
    roda rotas síncronas num pool de threads — uma requisição podia buscar o
    resultado de OUTRA, ou receber `None`.

    Foi assim que o filtro de Situação apareceu com 90 opções `undefined`: ele
    recebeu a resposta de `/api/proposicoes/tipos`. Intermitente, some ao
    recarregar, e afeta qualquer rota — não só aquele seletor.

    `cursor()` cria uma conexão-filha com estado próprio, enxergando as mesmas
    views. É o isolamento que faltava.
    """
    cursor = con().cursor()
    try:
        return _registros(cursor.execute(sql, parametros or []).df())
    except Exception as erro:  # noqa: BLE001
        # Pode ser simplesmente uma tabela que passou a existir depois que a
        # API subiu. Recria as views e tenta de novo, uma única vez.
        log.warning("consulta falhou (%s) — recriando views e repetindo", erro)
        try:
            recarregar_views()
            return _registros(con().cursor().execute(sql, parametros or []).df())
        except Exception as erro2:  # noqa: BLE001
            log.error("consulta falhou definitivamente: %s", erro2)
            raise HTTPException(500, f"consulta falhou: {erro2}") from erro2
    finally:
        try:
            cursor.close()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ meta
@app.get("/api/saude")
def saude():
    df = controle.situacao()
    return {
        "situacao": "ok",
        "data": date.today().isoformat(),
        "fontes": [] if df.empty else json.loads(df.to_json(orient="records")),
    }


# ------------------------------------------------------------------ coleta
class PedidoDeColeta(BaseModel):
    """O que o botão Atualizar manda."""
    fontes: list[str] = Field(..., min_length=1)
    ano: int | None = None
    anos: list[int] | None = None
    nivel: str = "estado"
    uf: str | None = None
    trabalhadores: int = Field(6, ge=1, le=16)
    intervalo: float = Field(0.15, ge=0.0, le=5.0)
    sem_malhas: bool = False
    refazer_vazios: bool = False
    refazer_tudo: bool = False


class ChaveDeApi(BaseModel):
    chave: str = Field(..., min_length=1, max_length=500)


@app.get("/api/config")
def configuracao():
    """O que está configurado — nunca o valor em si.

    A chave volta mascarada (`a1b2…f9e8`): dá para conferir que é a certa,
    não dá para usar. Segredo não trafega de volta por rota de leitura.
    """
    chave = config.CHAVE_PORTAL_TRANSPARENCIA
    return {
        "portal_transparencia": {
            "configurada": bool(chave),
            "mascara": segredos.mascarar(chave),
            "onde_obter": "portaldatransparencia.gov.br/api-de-dados/"
                          "cadastrar-email",
        }
    }


@app.post("/api/config/chave-portal")
def salvar_chave_portal(corpo: ChaveDeApi):
    """Grava a chave da CGU no .env e passa a valer na hora.

    Aceita tanto a chave pura quanto o bloco de exemplo que a CGU mostra na
    tela — colar o JSON inteiro é o caminho natural e recusar seria
    implicância.
    """
    try:
        chave = segredos.aplicar_chave_portal(corpo.chave)
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro

    aceita, mensagem = segredos.testar_chave_portal(chave)
    return {
        "salva": True,
        "mascara": segredos.mascarar(chave),
        "validada": aceita,
        "mensagem": mensagem,
    }


@app.get("/api/coleta/catalogo")
def catalogo_de_coleta():
    return tarefas.catalogo()


@app.post("/api/coleta", status_code=202)
def iniciar_coleta(pedido: PedidoDeColeta):
    desconhecidas = [f for f in pedido.fontes if f not in orquestrador.ORDEM]
    if desconhecidas:
        raise HTTPException(400, f"fonte desconhecida: {desconhecidas}")

    opcoes = orquestrador.Opcoes(
        ano=pedido.ano, anos=pedido.anos, nivel=pedido.nivel, uf=pedido.uf,
        trabalhadores=pedido.trabalhadores, intervalo=pedido.intervalo,
        sem_malhas=pedido.sem_malhas, refazer_vazios=pedido.refazer_vazios,
        refazer_tudo=pedido.refazer_tudo,
    )
    try:
        tarefa = tarefas.iniciar(pedido.fontes, opcoes)
    except tarefas.TarefaEmAndamento as erro:
        # 409: já existe uma coleta rodando. Enfileirar em silêncio faria duas
        # varreduras disputarem o mesmo freio de rede e a mesma partição.
        raise HTTPException(409, str(erro)) from erro
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro
    return tarefa.como_dicionario()


@app.get("/api/coleta")
def coleta_corrente():
    tarefa = tarefas.ultima()
    return tarefa.como_dicionario() if tarefa else {"situacao": "nenhuma"}


@app.get("/api/coleta/{id_tarefa}")
def coleta_por_id(id_tarefa: int):
    tarefa = tarefas.por_id(id_tarefa)
    if not tarefa:
        raise HTTPException(404, "tarefa não encontrada")
    return tarefa.como_dicionario()


# ------------------------------------------------------------------ custo
@app.get("/api/custo/cargos")
def custo_por_cargo(poder: str | None = None):
    condicoes, parametros = [], []
    if poder:
        condicoes.append("poder = ?"); parametros.append(poder)
    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f"""
        SELECT cod_cargo, cargo, poder, esfera, ramo, ocupantes,
               valor_mensal, custo_anual_estimado, conferido,
               norma, url_norma, observacao
          FROM vw_custo_cargo {onde}
         ORDER BY custo_anual_estimado DESC NULLS LAST, cargo
    """, parametros)


@app.get("/api/custo/resumo")
def resumo_de_custo(ano: int | None = None):
    """As três medidas, separadas de propósito.

    Somar subsídio e chamar de "custo da função" subestima muito o real.
    Cada bloco vem rotulado com o que é e de onde veio, e a resposta carrega
    os avisos que o painel tem obrigação de mostrar.
    """
    cargos = _consultar("""
        SELECT poder, SUM(custo_anual_estimado) AS custo_estimado,
               SUM(ocupantes) AS ocupantes,
               COUNT(*) FILTER (WHERE valor_mensal IS NOT NULL
                                  AND NOT conferido) AS nao_conferidos
          FROM vw_custo_cargo
         WHERE poder IS NOT NULL
         GROUP BY poder ORDER BY custo_estimado DESC NULLS LAST
    """)

    if ano is None:
        anos = _consultar("SELECT MAX(ano) AS ano FROM vw_despesa_poder")
        ano = int(anos[0]["ano"]) if anos and anos[0].get("ano") else None

    despesa = _consultar("""
        SELECT funcao, esfera, SUM(valor) AS valor
          FROM vw_despesa_poder WHERE ano = ?
         GROUP BY ALL ORDER BY valor DESC
    """, [ano]) if ano else []

    medido = _consultar("""
        SELECT conjunto, SUM(valor) AS valor
          FROM custo_orgao WHERE ano = ?
         GROUP BY conjunto ORDER BY valor DESC
    """, [ano]) if ano else []

    nao_conferidos = sum(int(c["nao_conferidos"] or 0) for c in cargos)

    return {
        "ano": ano,
        "estimado_por_poder": cargos,
        "despesa_por_funcao": despesa,
        "custo_medido_federal": medido,
        "arrecadacao": None,   # ainda não coletada — ver roteiro
        "avisos": [
            aviso for aviso in [
                f"{nao_conferidos} valor(es) de subsídio ainda não conferidos "
                f"contra a norma." if nao_conferidos else None,
                "Custo estimado = ocupantes × subsídio × 13,33. Não inclui "
                "gabinete, auxílios, diárias nem encargos."
                if cargos else None,
                "Despesa por função é o valor que de fato saiu dos cofres "
                "(SICONFI) — não confundir com a estimativa de subsídios."
                if despesa else None,
                "Arrecadação ainda não coletada." if True else None,
            ] if aviso
        ],
    }


@app.get("/api/metricas")
def metricas():
    return _consultar("SELECT cod_metrica, rotulo, unidade, fonte_origem "
                      "FROM dim_metrica ORDER BY rotulo")


@app.get("/api/anos")
def anos():
    linhas = _consultar(
        "SELECT ano FROM vw_anos WHERE ano IS NOT NULL ORDER BY ano DESC")
    return [int(l["ano"]) for l in linhas]


@app.post("/api/recarregar")
def recarregar():
    return {"views": recarregar_views()}


# ------------------------------------------------------------------ mapa
@app.get("/api/mapa")
def mapa(
    ano: int = Query(..., description="Ano de referência"),
    uf: str | None = Query(None, description="Sigla da UF para descer ao município"),
    metrica: str = Query("despesa_per_capita",
                         pattern="^(despesa_per_capita|despesa_total|populacao)$"),
):
    """País → estado → município. Sem UF devolve as 27 UFs; com UF, os municípios."""
    if uf:
        sql = """
            SELECT cod_ibge, nome, sigla_uf, ano, despesa_total, populacao,
                   despesa_per_capita
              FROM vw_mapa
             WHERE nivel = 'municipio' AND sigla_uf = ? AND ano = ?
             ORDER BY nome
        """
        linhas = _consultar(sql, [uf.upper(), ano])
        nivel = "municipio"
    else:
        sql = """
            SELECT cod_ibge, nome, sigla_uf, ano, despesa_total, populacao,
                   despesa_per_capita
              FROM vw_mapa
             WHERE nivel = 'estado' AND ano = ?
             ORDER BY nome
        """
        linhas = _consultar(sql, [ano])
        nivel = "estado"

    com_dado = [l for l in linhas if l.get(metrica) is not None]
    return {
        "nivel": nivel,
        "uf": uf,
        "ano": ano,
        "metrica": metrica,
        "total_entes": len(linhas),
        "entes_com_dado": len(com_dado),
        "entes": linhas,
    }


@app.get("/api/malha/{escopo}")
def malha(escopo: str):
    """GeoJSON. `escopo` = 'brasil' ou a sigla da UF.

    A malha do Brasil por UF é carregada no boot do painel; a de cada UF, sob
    demanda no clique. Nunca as dos 5.570 municípios de uma vez — centenas de MB.
    """
    if escopo.lower() == "brasil":
        arquivo = config.MALHAS / "brasil-uf.json"
        if not arquivo.exists():
            coletor_ibge.coletar_malha_brasil()
    else:
        arquivo = config.MALHAS / f"uf-{escopo.upper()}.json"
        if not arquivo.exists():
            coletor_ibge.coletar_malha_uf(escopo)

    if not arquivo.exists():
        raise HTTPException(404, f"malha indisponível: {escopo}")
    return FileResponse(arquivo, media_type="application/geo+json")


# ------------------------------------------------------------------ políticos
@app.get("/api/politicos/resumo")
def politicos_resumo(uf: str | None = None):
    filtro = "WHERE sigla_uf = ?" if uf else ""
    linhas = _consultar(f"""
        SELECT cargo, COUNT(*) AS quantidade
          FROM dim_politico {filtro}
         GROUP BY cargo ORDER BY quantidade DESC
    """, [uf.upper()] if uf else [])
    return {"uf": uf, "cargos": linhas,
            "total": sum(int(l["quantidade"]) for l in linhas)}


@app.get("/api/politicos")
def politicos(uf: str | None = None, cargo: str | None = None,
              partido: str | None = None, busca: str | None = None,
              limite: int = Query(200, le=2000)):
    condicoes, parametros = [], []
    if uf:
        condicoes.append("sigla_uf = ?"); parametros.append(uf.upper())
    if cargo:
        condicoes.append("cargo = ?"); parametros.append(cargo)
    if partido:
        condicoes.append("sigla_partido = ?"); parametros.append(partido.upper())
    if busca:
        condicoes.append("nome ILIKE ?"); parametros.append(f"%{busca}%")
    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f"""
        SELECT sk, id_origem, nome, nome_eleitoral, cargo, sigla_partido,
               sigla_uf, casa, url_foto, fonte_origem
          FROM dim_politico {onde}
         ORDER BY nome LIMIT {int(limite)}
    """, parametros)


@app.get("/api/politicos/{sk}/gastos")
def gastos_politico(sk: str, ano: int | None = None):
    parametros: list[Any] = [sk]
    filtro_ano = ""
    if ano:
        filtro_ano = "AND g.ano = ?"; parametros.append(ano)
    return _consultar(f"""
        SELECT g.ano, g.mes, g.valor_liquido, g.documentos
          FROM vw_gasto_parlamentar g
          JOIN dim_politico p ON p.id_origem = g.id_politico
         WHERE p.sk = ? {filtro_ano}
         ORDER BY g.ano DESC, g.mes DESC
    """, parametros)


# ------------------------------------------------------------------ proposições
@app.get("/api/proposicoes/situacoes")
def situacoes_de_proposicoes(ano: int | None = None):
    """Valores de situação existentes no acervo, com quantas proposições cada
    um tem. O filtro do painel é montado a partir daqui — em vez de uma lista
    fixa que envelhece quando a Câmara cria uma situação nova."""
    condicoes = ["situacao IS NOT NULL", "situacao <> ''"]
    parametros: list[Any] = []
    if ano:
        condicoes.append("ano = ?"); parametros.append(ano)
    return _consultar(f"""
        SELECT situacao, COUNT(*) AS quantidade
          FROM proposicao WHERE {' AND '.join(condicoes)}
         GROUP BY situacao ORDER BY quantidade DESC
    """, parametros)


@app.get("/api/proposicoes/tipos")
def tipos_de_proposicoes(ano: int | None = None):
    condicoes = ["sigla_tipo IS NOT NULL"]
    parametros: list[Any] = []
    if ano:
        condicoes.append("ano = ?"); parametros.append(ano)
    return _consultar(f"""
        SELECT sigla_tipo, COUNT(*) AS quantidade
          FROM proposicao WHERE {' AND '.join(condicoes)}
         GROUP BY sigla_tipo ORDER BY quantidade DESC
    """, parametros)


@app.get("/api/proposicoes")
def proposicoes(ano: int | None = None, tipo: str | None = None,
                situacao: str | None = None,
                autor: str | None = None, busca: str | None = None,
                de: str | None = Query(None, description="AAAA-MM-DD"),
                ate: str | None = Query(None, description="AAAA-MM-DD"),
                limite: int = Query(100, le=1000)):
    condicoes, parametros = [], []
    if ano:
        condicoes.append("ano = ?"); parametros.append(ano)
    if tipo:
        condicoes.append("sigla_tipo = ?"); parametros.append(tipo.upper())
    if situacao:
        # Igualdade exata: os valores vêm do próprio acervo, pelo endpoint
        # /situacoes, então não há por que abrir para busca parcial aqui.
        condicoes.append("situacao = ?"); parametros.append(situacao)
    if autor:
        condicoes.append("nome_autor ILIKE ?"); parametros.append(f"%{autor}%")
    if busca:
        condicoes.append("(ementa ILIKE ? OR identificador ILIKE ?)")
        parametros += [f"%{busca}%", f"%{busca}%"]
    if de:
        condicoes.append("CAST(data_apresentacao AS DATE) >= ?"); parametros.append(de)
    if ate:
        condicoes.append("CAST(data_apresentacao AS DATE) <= ?"); parametros.append(ate)
    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f"""
        SELECT casa, id_proposicao, identificador, sigla_tipo, ementa,
               data_apresentacao, situacao, tramitacao_atual, orgao_atual,
               nome_autor, partido_autor, uf_autor, qtd_autores, url
          FROM proposicao {onde}
         ORDER BY CAST(data_apresentacao AS DATE) DESC
         LIMIT {int(limite)}
    """, parametros)


@app.get("/api/proposicoes/{casa}/{id_proposicao}")
def proposicao_detalhe(casa: str, id_proposicao: str):
    """A proposição, todas as etapas e o placar de cada votação."""
    cabecalho = _consultar(
        "SELECT * FROM proposicao WHERE casa = ? AND id_proposicao = ?",
        [casa, id_proposicao])
    if not cabecalho:
        raise HTTPException(404, "proposição não encontrada")

    etapas = _consultar("""
        SELECT seq_tramitacao, data_hora, orgao, descricao_tramitacao,
               descricao_situacao, despacho
          FROM tramitacao
         WHERE casa = ? AND id_proposicao = ?
         ORDER BY CAST(seq_tramitacao AS INTEGER)
    """, [casa, id_proposicao])

    votacoes = _consultar("""
        SELECT v.id_votacao, v.data_hora, v.sigla_orgao, v.descricao,
               v.aprovada, p.sim, p.nao, p.abstencao, p.outros, p.total
          FROM votacao v
          LEFT JOIN vw_placar_votacao p
            ON p.id_votacao = v.id_votacao AND p.casa = v.casa
         WHERE v.casa = ? AND CAST(v.id_proposicao AS VARCHAR) = ?
         ORDER BY v.data_hora
    """, [casa, id_proposicao])

    return {"proposicao": cabecalho[0], "tramitacoes": etapas,
            "votacoes": votacoes}


@app.get("/api/votacoes/{casa}/{id_votacao}/votos")
def votos(casa: str, id_votacao: str, voto: str | None = None,
          partido: str | None = None, uf: str | None = None):
    """Quem votou a favor e contra — nominal, por parlamentar."""
    condicoes = ["casa = ?", "id_votacao = ?"]
    parametros: list[Any] = [casa, id_votacao]
    if voto:
        condicoes.append("voto ILIKE ?"); parametros.append(f"{voto}%")
    if partido:
        condicoes.append("sigla_partido = ?"); parametros.append(partido.upper())
    if uf:
        condicoes.append("sigla_uf = ?"); parametros.append(uf.upper())

    linhas = _consultar(f"""
        SELECT id_politico, nome_politico, sigla_partido, sigla_uf, voto
          FROM voto WHERE {' AND '.join(condicoes)}
         ORDER BY sigla_uf, sigla_partido, nome_politico
    """, parametros)

    placar = _consultar(
        "SELECT * FROM vw_placar_votacao WHERE casa = ? AND id_votacao = ?",
        [casa, id_votacao])
    return {"placar": placar[0] if placar else None, "votos": linhas}


# ------------------------------------------------------------------ ranking
@app.get("/api/ranking")
def ranking(ano: int, metrica: str = "despesa_per_capita",
            nivel: str = "estado", uf: str | None = None,
            ordem: str = Query("desc", pattern="^(asc|desc)$"),
            limite: int = Query(30, le=200)):
    if metrica not in ("despesa_per_capita", "despesa_total", "populacao"):
        raise HTTPException(400, "métrica inválida")
    condicoes = ["nivel = ?", "ano = ?", f"{metrica} IS NOT NULL"]
    parametros: list[Any] = [nivel, ano]
    if uf:
        condicoes.append("sigla_uf = ?"); parametros.append(uf.upper())
    return _consultar(f"""
        SELECT cod_ibge, nome, sigla_uf, {metrica} AS valor
          FROM vw_mapa WHERE {' AND '.join(condicoes)}
         ORDER BY valor {ordem.upper()} LIMIT {int(limite)}
    """, parametros)


@app.get("/api/ente/{cod_ibge}")
def ficha_do_ente(cod_ibge: str, ano: int | None = None):
    """Tudo sobre um ente numa chamada: quem governa, quanto gasta, e em quê.

    É a rota que só existe porque o de-para TSE → IBGE existe. Sem ele o
    painel sabia o gasto e sabia o prefeito, e não conseguia dizer que eram
    a mesma cidade.
    """
    ente = _consultar(
        "SELECT cod_ibge, nome, nivel, sigla_uf, cod_uf, regiao "
        "FROM dim_ente WHERE cod_ibge = ?", [cod_ibge])
    if not ente:
        raise HTTPException(404, "ente não encontrado")
    ente = ente[0]

    if ano is None:
        anos_disponiveis = _consultar(
            "SELECT ano FROM vw_mapa WHERE cod_ibge = ? "
            "AND despesa_total IS NOT NULL ORDER BY ano DESC LIMIT 1",
            [cod_ibge])
        ano = int(anos_disponiveis[0]["ano"]) if anos_disponiveis else None

    resumo = _consultar(
        "SELECT ano, despesa_total, populacao, despesa_per_capita "
        "FROM vw_mapa WHERE cod_ibge = ? AND ano = ?",
        [cod_ibge, ano]) if ano else []

    financas = _consultar("""
        SELECT cod_funcao, funcao, valor
          FROM vw_financas_funcao
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY valor DESC LIMIT 15
    """, [cod_ibge, ano]) if ano else []

    indicadores = _consultar("""
        SELECT i.cod_metrica, m.rotulo, m.unidade, i.ano, i.valor
          FROM indicador_ente i
          LEFT JOIN dim_metrica m ON m.cod_metrica = i.cod_metrica
         WHERE i.cod_ibge = ?
         QUALIFY ROW_NUMBER() OVER (PARTITION BY i.cod_metrica
                                    ORDER BY i.ano DESC) = 1
         ORDER BY m.rotulo
    """, [cod_ibge])

    # Quem governa: o próprio ente, a UF a que pertence, e a União.
    cadeia = [cod_ibge, "0"]
    if ente.get("cod_uf") and str(ente["cod_uf"]) != str(cod_ibge):
        cadeia.append(str(ente["cod_uf"]))
    marcadores = ", ".join("?" for _ in cadeia)
    governantes = _consultar(f"""
        SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
          FROM vw_executivo
         WHERE cod_ibge IN ({marcadores})
         ORDER BY CASE cargo WHEN 'prefeito' THEN 1 WHEN 'governador' THEN 2
                             ELSE 3 END, ano_inicio DESC
    """, cadeia)

    legislativo = _consultar("""
        SELECT cargo, COUNT(*) AS quantidade
          FROM vw_mandato
         WHERE cod_ibge = ? AND cargo NOT IN
               ('presidente', 'governador', 'prefeito')
         GROUP BY cargo ORDER BY quantidade DESC
    """, [cod_ibge])

    return {
        "ente": ente,
        "ano": ano,
        "resumo": resumo[0] if resumo else None,
        "financas": financas,
        "indicadores": indicadores,
        "governantes": governantes,
        "legislativo": legislativo,
    }


@app.get("/api/de-para/pendencias")
def pendencias_de_para(fonte: str = "tse"):
    """Unidades eleitorais que não casaram com nenhum município.

    Existe para a lacuna ser visível e virar exceção escrita à mão, em vez
    de sumir num JOIN que não bate.
    """
    total = _consultar(
        "SELECT metodo, COUNT(*) AS quantidade FROM dim_de_para_ente "
        "WHERE fonte_origem = ? GROUP BY metodo ORDER BY quantidade DESC",
        [fonte])
    abertas = _consultar("""
        SELECT sigla_uf, id_origem, nome_origem, metodo, similaridade
          FROM dim_de_para_ente
         WHERE fonte_origem = ? AND cod_ibge IS NULL
         ORDER BY sigla_uf, nome_origem
    """, [fonte])
    aproximadas = _consultar("""
        SELECT sigla_uf, nome_origem, nome_ibge, similaridade
          FROM dim_de_para_ente
         WHERE fonte_origem = ? AND metodo = 'aproximada'
         ORDER BY similaridade
    """, [fonte])
    return {"por_metodo": total, "pendentes": abertas,
            "aproximadas_para_conferir": aproximadas}


@app.get("/api/financas/{cod_ibge}")
def financas(cod_ibge: str, ano: int | None = None):
    parametros: list[Any] = [cod_ibge]
    filtro = ""
    if ano:
        filtro = "AND ano = ?"; parametros.append(ano)
    return _consultar(f"""
        SELECT ano, cod_funcao, funcao, valor
          FROM vw_financas_funcao
         WHERE cod_ibge = ? {filtro}
         ORDER BY ano DESC, valor DESC
    """, parametros)


# ------------------------------------------------------------------ estáticos
PUBLICO = Path(config.RAIZ) / "publico"
if PUBLICO.exists():
    app.mount("/", StaticFiles(directory=PUBLICO, html=True), name="publico")


@app.exception_handler(404)
def nao_encontrado(request, exc):  # noqa: ARG001
    return JSONResponse({"erro": "recurso não encontrado"}, status_code=404)
