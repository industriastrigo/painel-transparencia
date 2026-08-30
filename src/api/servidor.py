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
               -- Quantos ocupantes REALMENTE entram na soma. Sem esta coluna
               -- a tela dizia "64.323 ocupantes × subsídio × 13,33" ao lado de
               -- R$ 329,79 mi, e a divisão dava R$ 385/mês por ocupante: só
               -- 594 dos 64.323 têm subsídio cadastrado. Número certo com
               -- rótulo errado é indefensável — e é a conta que qualquer
               -- crítico refaz em dez segundos.
               SUM(ocupantes) FILTER (WHERE valor_mensal IS NOT NULL)
                                                 AS ocupantes_com_subsidio,
               COUNT(*) FILTER (WHERE valor_mensal IS NOT NULL
                                  AND NOT conferido) AS nao_conferidos
          FROM vw_custo_cargo
         WHERE poder IS NOT NULL
         GROUP BY poder ORDER BY custo_estimado DESC NULLS LAST
    """)

    def _ultimo_ano(vista: str, coluna: str = "ano") -> int | None:
        """O ano mais recente em que ESTA vista tem dado."""
        linhas = _consultar(f"SELECT MAX({coluna}) AS ano FROM {vista}")
        return (int(linhas[0]["ano"])
                if linhas and linhas[0].get("ano") is not None else None)

    # CADA BLOCO NO ANO EM QUE ELE EXISTE.
    #
    # Duas correções erradas em cima do mesmo lugar, em direções opostas:
    #
    # 1. Antes o ano saía de `vw_despesa_poder` sozinha. Com a despesa por
    #    função vazia e a receita cheia, o exercício vinha nulo e os totais
    #    agregados sumiam da tela — estando no disco.
    # 2. A correção foi tirar o ano de `vw_anos`, que reúne TUDO. Aí bastou a
    #    despesa por função ter 2026 (o RREO é bimestral) para o ano virar
    #    2026 — e a arrecadação, que é do DCA e só existe até 2025, sumir da
    #    tela. Estando no disco. De novo.
    #
    # O erro comum às duas é supor que existe UM ano certo para a tela
    # inteira. Não existe: as fontes têm calendários diferentes. A saída é
    # cada bloco usar o ano mais recente em que ele tem dado, e a tela dizer
    # de que ano é cada número — mostrar a arrecadação de 2025 rotulada como
    # 2025 é melhor que esconder um número que existe.
    ano_pedido = ano
    ano_funcao = ano_pedido or _ultimo_ano("vw_despesa_poder")
    ano_medido = ano_pedido or _ultimo_ano("custo_orgao")
    ano_receita = ano_pedido or _ultimo_ano("vw_receita_total")
    ano_despesa = ano_pedido or _ultimo_ano("vw_despesa_total")
    # `ano` continua sendo o rótulo geral da aba: o mais recente que existe.
    ano = ano_pedido or max(
        [a for a in (ano_funcao, ano_medido, ano_receita, ano_despesa)
         if a is not None], default=None)

    despesa = _consultar("""
        SELECT funcao, esfera, SUM(valor) AS valor
          FROM vw_despesa_poder WHERE ano = ?
         GROUP BY ALL ORDER BY valor DESC
    """, [ano_funcao]) if ano_funcao else []

    # A soma vem com a MARCA DA COLETA colada nela. Sem isto, um recorte cujo
    # `_ctl/ingestao` diz `parcial — paginação interrompida` chega à tela como
    # valor apurado: `pessoal_ativo` de 2025 publicava R$ 9,04 bi apoiado em 24
    # linhas, quando a própria documentação do coletor fala em mais de 100 mil
    # linhas por mês. O acervo sabia que estava truncado; a tela é que não
    # dizia. Número parcial não é errado — é PISO — e a diferença entre as duas
    # leituras é o rótulo, não o dado.
    medido = _consultar("""
        SELECT conjunto, SUM(valor) AS valor, COUNT(*) AS linhas
          FROM custo_orgao WHERE ano = ?
         GROUP BY conjunto ORDER BY valor DESC
    """, [ano_medido]) if ano_medido else []

    if medido:
        marcas = controle.situacao()
        por_recurso = ({str(l["recurso"]): str(l.get("situacao") or "")
                        for _, l in marcas.iterrows()}
                       if not marcas.empty else {})
        for linha in medido:
            situacao_coleta = por_recurso.get(
                f'{linha["conjunto"]}_{ano_medido}', "desconhecida")
            linha["situacao_coleta"] = situacao_coleta
            linha["completo"] = situacao_coleta == "ok"
    incompletos = [l["conjunto"] for l in medido if not l["completo"]]

    # Os dois totais agregados. `COUNT(*)` junto NÃO é enfeite: a soma vale o
    # que a cobertura vale. Com 27 UFs coletadas e nenhum município, o número
    # sai bem formado e pequeno demais — e ninguém vê a diferença olhando só
    # para ele. O painel mostra a soma E de quantos entes ela veio.
    receita = _consultar("""
        SELECT SUM(receita_total) AS total, COUNT(*) AS entes
          FROM vw_receita_total WHERE ano = ?
    """, [ano_receita]) if ano_receita else []

    despesa_agregada = _consultar("""
        SELECT SUM(despesa_total) AS total, COUNT(*) AS entes
          FROM vw_despesa_total WHERE ano = ?
    """, [ano_despesa]) if ano_despesa else []

    def _total(linhas: list[dict]) -> tuple[float | None, int]:
        """(valor, entes) — nunca 0 no lugar de "não sei"."""
        if not linhas:
            return None, 0
        bruto = linhas[0].get("total")
        return (float(bruto) if bruto is not None else None,
                int(linhas[0].get("entes") or 0))

    valor_receita, entes_receita = _total(receita)
    valor_despesa_agregada, entes_despesa = _total(despesa_agregada)

    nao_conferidos = sum(int(c["nao_conferidos"] or 0) for c in cargos)

    return {
        "ano": ano,
        "estimado_por_poder": cargos,
        "despesa_por_funcao": despesa,
        "custo_medido_federal": medido,
        "arrecadacao": valor_receita,
        "arrecadacao_entes": entes_receita,
        # De que ano é cada número. Sem isto a tela juntaria exercícios
        # diferentes sem dizer — que é pior do que mostrar um só.
        "ano_arrecadacao": ano_receita,
        "ano_despesa_subnacional": ano_despesa,
        "ano_despesa_funcao": ano_funcao,
        "ano_custo_medido": ano_medido,
        # NÃO é "nacional": é a soma dos entes SUBNACIONAIS que o acervo tem.
        # O orçamento da União não está no SICONFI e portanto não está aqui.
        # Chamar de nacional seria afirmar uma cobertura que o número não tem.
        "despesa_subnacional": valor_despesa_agregada,
        "despesa_entes": entes_despesa,
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
                # O aviso nomeia os recortes: "alguns dados podem estar
                # incompletos" é a frase que ninguém age em cima.
                (f"Custo medido federal de {ano_medido}: "
                 f"{', '.join(incompletos)} com coleta incompleta "
                 f"(paginação interrompida). Os valores desses recortes são "
                 f"PISO, não total apurado.")
                if incompletos else None,
                f"Arrecadação e despesa somam {entes_despesa} ente(s) do "
                f"acervo — estados e municípios já coletados. O orçamento da "
                f"União não entra: ele não está no SICONFI."
                if entes_despesa else None,
                # O aviso antigo dizia "nenhum ente com dado neste exercício"
                # e parecia acervo perdido. Quando o pedido é por um ano
                # específico e ele não tem DCA, a causa é o calendário da
                # fonte — e é isso que a frase precisa dizer.
                (f"Arrecadação e despesa agregadas não existem para "
                 f"{ano_pedido}: elas vêm do DCA, que é anual e só é "
                 f"publicado no exercício seguinte. O último disponível é "
                 f"{ano_receita or ano_despesa or 'nenhum'}.")
                if ano_pedido and not entes_despesa else None,
                ("Arrecadação e despesa agregadas indisponíveis: nenhum ente "
                 "com dado no acervo.")
                if not ano_pedido and not entes_despesa else None,
            ] if aviso
        ],
    }


@app.get("/api/metricas")
def metricas():
    return _consultar("SELECT cod_metrica, rotulo, unidade, fonte_origem "
                      "FROM dim_metrica ORDER BY rotulo")


@app.get("/api/anos")
def anos():
    """Os anos do acervo, com quanto de cada um o painel consegue mostrar.

    Devolve objeto, não número, por um motivo concreto: as fontes têm
    calendários diferentes. O RREO é bimestral e já publica o exercício
    corrente; o DCA é ANUAL e só sai no seguinte. Existe portanto sempre um
    ano com despesa por função e sem arrecadação.

    O painel abria nesse ano — escolhia o mais recente que QUALQUER tabela
    tivesse — e metade dos cartões dizia "não coletado". Parecia acervo
    perdido; era ano ainda incompleto. `padrao` marca o ano mais recente
    COMPLETO, e é nele que a tela abre; os parciais continuam na lista, com
    o que falta dito por extenso.
    """
    linhas = _consultar("""
        SELECT a.ano,
               COALESCE(c.blocos_com_dado, 0) AS blocos_com_dado,
               COALESCE(c.blocos_no_total, 5) AS blocos_no_total,
               COALESCE(c.completo, FALSE)    AS completo,
               c.blocos
          FROM vw_anos a
          LEFT JOIN vw_cobertura_ano c USING (ano)
         WHERE a.ano IS NOT NULL
         ORDER BY a.ano DESC
    """)

    completos = [l for l in linhas if l.get("completo")]
    # Sem nenhum ano completo, o mais recente é o melhor que há — abrir numa
    # tela vazia por preciosismo seria pior que abrir numa tela parcial.
    padrao = int((completos or linhas)[0]["ano"]) if linhas else None

    return {
        "anos": [{
            "ano": int(l["ano"]),
            "completo": bool(l.get("completo")),
            "blocos_com_dado": int(l.get("blocos_com_dado") or 0),
            "blocos_no_total": int(l.get("blocos_no_total") or 5),
            "blocos": str(l.get("blocos") or "").split(",") if l.get("blocos")
                      else [],
        } for l in linhas],
        "padrao": padrao,
    }


@app.post("/api/recarregar")
def recarregar():
    return {"views": recarregar_views()}


# ------------------------------------------------------------------ mapa
@app.get("/api/mapa")
def mapa(
    ano: int = Query(..., description="Ano de referência"),
    uf: str | None = Query(None, description="Sigla da UF para descer ao município"),
    metrica: str = Query(
        "despesa_per_capita",
        pattern="^(despesa_per_capita|despesa_total|populacao"
                "|receita_total|receita_per_capita|transferencia_recebida"
                "|transferencia_uniao|dependencia_transferencia"
                "|despesa_saude|saude_per_capita|despesa_educacao"
                "|educacao_per_capita|percentual_pessoal|divida_liquida)$"),
):
    """País → estado → município. Sem UF devolve as 27 UFs; com UF, os municípios."""
    # As mesmas colunas nos dois recortes: o tooltip do painel lê uma estrutura
    # só, e uma diferença entre os dois SELECTs viraria campo vazio conforme o
    # nível — o tipo de falha silenciosa que o item 2d do catálogo descreve.
    COLUNAS = """
        cod_ibge, nome, sigla_uf, ano, despesa_total, populacao,
        despesa_per_capita, receita_total, receita_per_capita,
        transferencia_recebida, transferencia_uniao,
        dependencia_transferencia, despesa_saude, despesa_educacao,
        saude_per_capita, educacao_per_capita,
        percentual_pessoal, acima_do_limite, divida_liquida
    """
    if uf:
        linhas = _consultar(
            f"SELECT {COLUNAS} FROM vw_mapa"
            "  WHERE nivel = 'municipio' AND sigla_uf = ? AND ano = ?"
            "  ORDER BY nome", [uf.upper(), ano])
        nivel = "municipio"
    else:
        linhas = _consultar(
            f"SELECT {COLUNAS} FROM vw_mapa"
            "  WHERE nivel = 'estado' AND ano = ?"
            "  ORDER BY nome", [ano])
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
@app.get("/api/politicos/executivo")
def executivo_em_destaque(uf: str | None = None):
    """Quem chefia o Executivo do recorte em que o usuário está.

    Sem UF é o presidente; com UF, o governador daquele estado. É a pergunta
    que a aba Políticos não respondia: ela listava 69 mil nomes em ordem
    alfabética, e o primeiro da lista era um vereador qualquer.

    **O join com o cargo é por `cod_cargo`, não por `cargo`.** As duas colunas
    existem nas duas tabelas e parecem intercambiáveis, mas guardam coisas
    diferentes: `mandato.cargo` é o apelido (`presidente`) e
    `dim_cargo_publico.cargo` é o nome por extenso ("Presidente da
    República"). Casar por texto não encontra nada — e o salário viria nulo
    para todo mundo, sem erro nenhum no log.
    """
    if uf:
        onde = "m.cargo = 'governador' AND m.sigla_uf = ?"
        parametros: list[Any] = [uf.strip().upper()]
    else:
        onde = "m.cargo = 'presidente'"
        parametros = []

    return _consultar(f"""
        SELECT m.cargo, m.nome, m.sigla_partido, m.sigla_uf,
               m.ano_inicio, m.ano_fim,
               p.url_foto,
               s.valor_mensal AS salario,
               s.norma        AS norma_salario,
               s.url_norma    AS url_norma_salario,
               -- Vem junto de propósito: os subsídios do acervo estão
               -- marcados `conferido = false` ("valor de rascunho"), e o
               -- painel tem de dizer isso ao lado do número em vez de
               -- apresentá-lo como fato apurado.
               s.conferido    AS salario_conferido
          FROM vw_mandato m
          LEFT JOIN dim_politico p
                 ON p.id_origem = m.sk_politico
          LEFT JOIN dim_cargo_publico c
                 ON c.cod_cargo = m.cod_cargo
          LEFT JOIN vw_subsidio_vigente s
                 ON s.cod_cargo = c.cod_cargo
         WHERE {onde}
         ORDER BY m.ano_inicio DESC
         LIMIT 1
    """, parametros)


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

    # O subsídio vem junto para a dica ao passar o mouse não precisar de uma
    # requisição por linha. São 300 linhas por consulta: uma chamada por
    # `mouseenter` seria 300 requisições e uma corrida a cada movimento do
    # ponteiro. O join é por CARGO, que é o grão em que o subsídio existe —
    # o acervo não tem remuneração individual, e fingir que tem seria pior
    # que não mostrar nada.
    return _consultar(f"""
        SELECT p.sk, p.id_origem, p.nome, p.nome_eleitoral, p.cargo,
               p.sigla_partido, p.sigla_uf, p.casa, p.url_foto,
               p.fonte_origem,
               c.cargo        AS cargo_extenso,
               c.poder, c.esfera,
               s.valor_mensal AS subsidio_cargo,
               s.norma        AS norma_subsidio,
               s.conferido    AS subsidio_conferido
          FROM dim_politico p
          LEFT JOIN dim_cargo_publico c ON c.cod_cargo = p.cargo
          LEFT JOIN vw_subsidio_vigente s ON s.cod_cargo = c.cod_cargo
        {onde.replace("sigla_uf", "p.sigla_uf").replace("cargo = ?", "p.cargo = ?")
             .replace("sigla_partido", "p.sigla_partido")
             .replace("nome ILIKE", "p.nome ILIKE")}
         ORDER BY p.nome LIMIT {int(limite)}
    """, parametros)


@app.get("/api/politicos/{sk}/ficha")
def ficha_do_politico(sk: str, ano: int | None = None):
    """Tudo o que o acervo sabe sobre um parlamentar, numa chamada.

    **O que existe e o que não existe** — a distinção importa mais aqui do
    que em qualquer outra tela do painel, porque a página oficial da Câmara
    mostra coisas que a API de dados abertos **não publica**:

    | O quê | Onde está |
    |---|---|
    | Cota parlamentar, nota a nota | arquivos em lote da Câmara — **temos** |
    | Subsídio do cargo | norma, em `referencias/` — **temos** |
    | Presença em sessão deliberativa | arquivo `eventosPresencaDeputados` — **temos** |
    | Fidelidade à orientação da bancada | arquivo `votacoesOrientacoes` — **temos** |
    | Verba de gabinete | só na página HTML — **não temos** |
    | Pessoal de gabinete | só na página HTML — **não temos** |
    | Justificativa de falta | só na página HTML — **não temos** |

    Sobre presença, uma correção registrada: por um tempo este projeto
    afirmou que frequência não existia em dado aberto, porque a rota
    `/deputados/{id}` não a expõe. Existe — em outro lugar, o arquivo em
    lote `eventosPresencaDeputados`, um registro por (evento, deputado).
    A lição não é sobre a Câmara, é sobre o método: "consultei o endpoint
    óbvio e não achei" não é o mesmo que "não existe".

    O que continua não existindo é a JUSTIFICATIVA da falta. A fonte publica
    quem esteve e nunca quem faltou; a ausência é subtração nossa, e uma
    falta abonada por missão oficial fica igual a uma falta seca. A tela diz
    isso ao lado do número.

    Para o que não temos, a resposta traz o ENDEREÇO da página oficial: o
    painel manda o cidadão à fonte em vez de raspar HTML — raspagem quebra
    em silêncio quando a página muda, que é o oposto do que este projeto
    promete.
    """
    politico = _consultar("""
        SELECT p.sk, p.id_origem, p.nome, p.nome_eleitoral, p.cargo,
               p.sigla_partido, p.sigla_uf, p.casa, p.url_foto,
               p.fonte_origem,
               c.cargo AS cargo_extenso, c.poder, c.esfera,
               s.valor_mensal AS subsidio_cargo, s.norma AS norma_subsidio,
               s.url_norma AS url_norma_subsidio,
               s.conferido AS subsidio_conferido
          FROM dim_politico p
          LEFT JOIN dim_cargo_publico c ON c.cod_cargo = p.cargo
          LEFT JOIN vw_subsidio_vigente s ON s.cod_cargo = c.cod_cargo
         WHERE p.sk = ?
    """, [sk])
    if not politico:
        raise HTTPException(404, "político não encontrado")
    politico = politico[0]

    # A cota é indexada pelo id da Câmara, não pelo `sk` do painel.
    id_camara = politico.get("id_origem")
    da_camara = politico.get("fonte_origem") == "camara"

    por_ano = _consultar("""
        SELECT ano, valor, notas FROM vw_cota_por_ano
         WHERE id_politico = ? ORDER BY ano DESC
    """, [str(id_camara)]) if id_camara else []

    if ano is None and por_ano:
        ano = int(por_ano[0]["ano"])

    por_mes = _consultar("""
        SELECT mes, SUM(valor_liquido) AS valor, COUNT(*) AS notas
          FROM vw_cota_parlamentar
         WHERE CAST(id_politico AS VARCHAR) = ? AND ano = ?
         GROUP BY mes ORDER BY mes
    """, [str(id_camara), ano]) if id_camara and ano else []

    por_tipo = _consultar("""
        SELECT tipo_despesa, valor, notas FROM vw_cota_por_tipo
         WHERE id_politico = ? AND ano = ?
         ORDER BY valor DESC
    """, [str(id_camara), ano]) if id_camara and ano else []

    fornecedores = _consultar("""
        SELECT fornecedor, cnpj_cpf_fornecedor, valor, notas
          FROM vw_cota_por_fornecedor
         WHERE id_politico = ? AND ano = ?
         ORDER BY valor DESC LIMIT 20
    """, [str(id_camara), ano]) if id_camara and ano else []

    notas = _consultar("""
        SELECT data_emissao, tipo_despesa, fornecedor, cnpj_cpf_fornecedor,
               valor_liquido, url_documento
          FROM vw_cota_parlamentar
         WHERE CAST(id_politico AS VARCHAR) = ? AND ano = ?
         ORDER BY valor_liquido DESC LIMIT 50
    """, [str(id_camara), ano]) if id_camara and ano else []

    presenca = _consultar("""
        SELECT ano, presencas, sessoes_possiveis, ausencias, taxa_presenca,
               sessoes_no_ano, primeiro_dia, ultimo_dia, janela_aproximada
          FROM vw_presenca_deputado
         WHERE id_politico = ? ORDER BY ano DESC
    """, [str(id_camara)]) if id_camara else []

    # A RESSALVA VIAJA COM O NÚMERO, e não só no HTML do painel.
    #
    # O aviso existia na tela e estava bem escrito. Só que esta API é aberta:
    # quem consome o JSON — outro painel, uma planilha, um jornalista com
    # `curl` — recebia `ausencias: 13` ao lado do nome de uma pessoa real e
    # nada mais. A ressalva morava no cliente, e ausência sem justificativa
    # publicada como número seco é acusação, não informação.
    #
    # Aqui ela é parte do dado. Só existe quando há presença para qualificar,
    # e `teste_presenca.py` falha se um dia deixar de existir.
    presenca_ressalva = [
        "A Câmara publica QUEM ESTEVE, nunca quem faltou: a ausência é "
        "subtração nossa.",
        "Não há justificativa no dado aberto. Missão oficial, licença médica "
        "e licença-maternidade aparecem iguais a falta seca.",
        "Entram só sessões deliberativas encerradas DO PLENÁRIO; audiência "
        "pública e seminário não são obrigação de comparecimento.",
        "Reunião de comissão fica de fora: a Câmara publica quem esteve, mas "
        "não quem é membro de cada comissão, e sem isso não há como saber a "
        "quem aquela reunião era obrigação.",
        "O denominador é a janela em que o parlamentar esteve em exercício, "
        "não o ano inteiro.",
    ] if presenca else []

    # POR QUE NÃO HÁ PRESENÇA, quando não há. São dois motivos diferentes e a
    # tela dizia a mesma frase para os dois: "sem registro no acervo" faz o
    # vereador parecer um dado que falta coletar, quando na verdade ele é um
    # dado que não existe de forma estruturada em lugar nenhum.
    #
    # Confundir "ainda não coletei" com "a fonte não publica" é o mesmo erro
    # de sempre, na direção contrária: aqui a tela estaria prometendo que um
    # dia mostra o que nunca vai poder mostrar.
    # Cargos cuja casa legislativa não publica presença em dado aberto. A
    # lista existe porque `esfera` vem de `dim_cargo_publico`, que nasce do
    # CSV de referências: num acervo em que ele não foi carregado, o campo é
    # nulo e a mensagem cairia no genérico — justamente o que este trecho
    # existe para não fazer. O cargo, esse, sempre está lá.
    CARGOS_SEM_FONTE_DE_PRESENCA = {
        "vereador", "prefeito", "vice_prefeito", "deputado_estadual",
        "deputado_distrital", "governador", "vice_governador",
    }

    presenca_indisponivel = None
    if not presenca:
        esfera = str(politico.get("esfera") or "").lower()
        casa = str(politico.get("casa") or "").lower()
        cargo = str(politico.get("cargo") or "").lower()
        if esfera in ("municipal", "estadual") or cargo in CARGOS_SEM_FONTE_DE_PRESENCA:
            presenca_indisponivel = (
                "Presença e voto nominal só existem de forma estruturada no "
                "Congresso Nacional. São 27 assembleias e 5.570 câmaras "
                "municipais, cada uma com o seu site: para este cargo o painel "
                "mostra cadastro e finanças, e não afirma o que não pôde "
                "verificar.")
        elif casa == "senado":
            presenca_indisponivel = (
                "O painel coleta as votações do Senado, mas ainda não a "
                "presença em sessão. Enquanto não coletar, não há número aqui "
                "— e número que não existe não vira zero.")
        elif casa == "camara":
            presenca_indisponivel = (
                "A Câmara publica a presença deste parlamentar, mas o acervo "
                "ainda não tem o ano coletado. Marque a Câmara na aba "
                "Atualizar para preencher.")
        else:
            presenca_indisponivel = (
                "Sem registro de presença no acervo para este cargo.")

    fidelidade = _consultar("""
        SELECT ano, votos_com_orientacao, votos_divergentes, taxa_divergencia
          FROM vw_fidelidade_partidaria
         WHERE id_politico = ? ORDER BY ano DESC
    """, [str(id_camara)]) if id_camara else []

    # As votações em que ele votou contra a própria bancada, com a descrição
    # da matéria: sem ela o número é uma acusação sem objeto.
    divergencias = _consultar("""
        SELECT d.id_votacao, d.voto, d.orientacao, d.sigla_bancada,
               v.data_hora, v.descricao, v.sigla_orgao
          FROM vw_voto_contra_orientacao d
          LEFT JOIN votacao v
                 ON v.casa = d.casa AND v.id_votacao = d.id_votacao
         WHERE d.id_politico = ? AND d.ano = ? AND d.divergiu
         ORDER BY v.data_hora DESC LIMIT 50
    """, [str(id_camara), ano]) if id_camara and ano else []

    return {
        "politico": politico,
        "ano": ano,
        "anos": [int(a["ano"]) for a in por_ano],
        "presenca": presenca,
        "presenca_ressalva": presenca_ressalva,
        "presenca_indisponivel": presenca_indisponivel,
        "fidelidade": fidelidade,
        "divergencias": divergencias,
        "cota_por_ano": por_ano,
        "cota_por_mes": por_mes,
        "cota_por_tipo": por_tipo,
        "fornecedores": fornecedores,
        "maiores_notas": notas,
        # O que o painel NÃO tem, dito com todas as letras e com o caminho
        # para quem quiser conferir na fonte.
        "so_na_pagina_oficial": ([
            {"item": "Verba de gabinete",
             "porque": "a Câmara publica o valor mensal só em HTML"},
            {"item": "Pessoal de gabinete",
             "porque": "nomes e cargos dos secretários, só em HTML"},
            {"item": "Justificativa das faltas",
             "porque": "a fonte publica quem esteve, nunca por que faltou — "
                       "missão oficial e falta seca ficam iguais aqui"},
        ] if da_camara else []),
        "url_oficial": (f"https://www.camara.leg.br/deputados/{id_camara}"
                        if da_camara and id_camara else None),
    }


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
        "SELECT ano, despesa_total, populacao, despesa_per_capita, "
        "       receita_total, transferencia_recebida, transferencia_uniao, "
        "       dependencia_transferencia, despesa_saude, despesa_educacao, "
        "       saude_per_capita, educacao_per_capita, "
        "       percentual_pessoal, acima_do_limite, divida_liquida "
        "FROM vw_mapa WHERE cod_ibge = ? AND ano = ?",
        [cod_ibge, ano]) if ano else []

    credito = _consultar("""
        SELECT pleitos, valor_pleiteado, valor_deferido, valor_contratado
          FROM vw_credito_ente WHERE cod_ibge = ? AND ano = ?
    """, [cod_ibge, ano]) if ano else []

    credito_finalidade = _consultar("""
        SELECT finalidade, credor, tipo_credor, valor
          FROM vw_credito_finalidade
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY valor DESC LIMIT 15
    """, [cod_ibge, ano]) if ano else []

    # Por modalidade, não só o total: o total responde "quanto", a modalidade
    # responde "de onde" — e é a segunda que explica a dependência do FPM.
    transferencias_uniao = _consultar("""
        SELECT cod_transferencia, transferencia, valor
          FROM vw_transferencia_modalidade
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY valor DESC LIMIT 20
    """, [cod_ibge, ano]) if ano else []

    # NATUREZA, não função. O Anexo I-D do DCA traz pessoal, juros e
    # investimentos — não saúde e educação. Chamar de "função" na tela seria
    # prometer um recorte que este anexo não tem.
    financas = _consultar("""
        SELECT cod_natureza, natureza, valor
          FROM vw_despesa_natureza
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY valor DESC LIMIT 15
    """, [cod_ibge, ano]) if ano else []

    conferencia = _consultar("""
        SELECT somado, declarado FROM vw_conferencia_despesa
         WHERE cod_ibge = ? AND ano = ?
    """, [cod_ibge, ano]) if ano else []

    # FUNÇÃO — saúde, educação, segurança. Vem do RREO, não do DCA, e por
    # isso mora ao lado de `financas` em vez de dentro. São dois recortes do
    # mesmo dinheiro: quem somar os dois dobra a despesa do ente.
    funcoes = _consultar("""
        SELECT cod_funcao, funcao, periodo, valor
          FROM vw_despesa_por_funcao
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY valor DESC LIMIT 20
    """, [cod_ibge, ano]) if ano else []

    # Mesma conferência do DCA, aplicada às funções. Vale ainda mais aqui,
    # porque a regra de nível é por NOME de função — e nome é mais frágil que
    # código. A view existia e nenhuma rota a expunha.
    conferencia_funcao = _consultar("""
        SELECT somado, declarado FROM vw_conferencia_funcao
         WHERE cod_ibge = ? AND ano = ?
    """, [cod_ibge, ano]) if ano else []

    lrf = _consultar("""
        SELECT poder, periodo, despesa_pessoal_liquida,
               receita_corrente_liquida, percentual_pessoal, limite_maximo,
               limite_prudencial, acima_do_limite, acima_do_prudencial,
               divida_liquida
          FROM vw_lrf_pessoal
         WHERE cod_ibge = ? AND ano = ?
         ORDER BY poder
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
        "funcoes": funcoes,
        "lrf": lrf,
        "conferencia_despesa": conferencia[0] if conferencia else None,
        "conferencia_funcao": (conferencia_funcao[0]
                               if conferencia_funcao else None),
        "transferencias_uniao": transferencias_uniao,
        "credito": credito[0] if credito else None,
        "credito_finalidade": credito_finalidade,
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
