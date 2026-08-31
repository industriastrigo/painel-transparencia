"""Rotas de Proposições Legislativas e Votações Nominais."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..db import _consultar, reiniciar_conexao
from ...nucleo.registro import obter as obter_log

log = obter_log("api.rotas.legislativo")
router = APIRouter(tags=["legislativo"])

# ------------------------------------------------------------------ proposições
@router.get("/api/proposicoes/situacoes")
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


@router.get("/api/proposicoes/tipos")
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


@router.get("/api/proposicoes")
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


@router.get("/api/proposicoes/{casa}/{id_proposicao}")
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

    # A ligação vem das DUAS pontas. `votacao.id_proposicao` guarda uma
    # proposição só (a da última apresentação) e vem vazia na maioria das
    # linhas; `votacao_proposicao` é a relação N para N publicada pela Câmara
    # em arquivo separado, e é ela que faz a ficha de um projeto mostrar quem
    # votou. Consultar as duas mantém funcionando o acervo já coletado antes
    # de a segunda existir.
    votacoes = _consultar("""
        SELECT DISTINCT v.id_votacao, v.data_hora, v.sigla_orgao, v.descricao,
               v.aprovada, p.sim, p.nao, p.abstencao, p.outros, p.total
          FROM votacao v
          LEFT JOIN vw_placar_votacao p
            ON p.id_votacao = v.id_votacao AND p.casa = v.casa
         WHERE v.casa = ?
           AND (CAST(v.id_proposicao AS VARCHAR) = ?
                OR EXISTS (SELECT 1 FROM votacao_proposicao vp
                            WHERE vp.casa = v.casa
                              AND vp.id_votacao = v.id_votacao
                              AND CAST(vp.id_proposicao AS VARCHAR) = ?))
         ORDER BY v.data_hora
    """, [casa, id_proposicao, id_proposicao])

    return {"proposicao": cabecalho[0], "tramitacoes": etapas,
            "votacoes": votacoes,
            # A tramitação NÃO vem no arquivo em lote: é uma requisição por
            # proposição, e o acervo tem 153.695 delas — mais de 42 h no freio
            # de 1 req/s. Por isso ela é buscada quando alguém abre a ficha, e
            # não numa varredura que ninguém terminaria.
            "tramitacao_sob_demanda": bool(not etapas and casa == "camara")}


@router.post("/api/proposicoes/{casa}/{id_proposicao}/tramitacoes")
def coletar_tramitacao_agora(casa: str, id_proposicao: str):
    """Busca as etapas desta proposição na Câmara, agora, e guarda no acervo.

    Uma requisição para uma proposição. O lote anual da Câmara não traz
    tramitação, e varrer as 153.695 do acervo levaria mais de 42 h — foi por
    isso que `coletar_tramitacoes` existia e nunca era chamada por ninguém, e
    a ficha dizia "não coletadas" para todas, para sempre.
    """
    if casa != "camara":
        raise HTTPException(400, "só a Câmara publica tramitação por proposição")

    from ...coletores import camara  # noqa: PLC0415

    try:
        quantas = camara.coletar_tramitacoes(str(id_proposicao))
    except Exception as erro:  # noqa: BLE001
        log.error("tramitação %s: %s", id_proposicao, erro)
        raise HTTPException(
            502, f"a Câmara não respondeu agora: {str(erro)[:160]}") from None

    reiniciar_conexao()
    etapas = _consultar("""
        SELECT seq_tramitacao, data_hora, orgao, descricao_tramitacao,
               descricao_situacao, despacho
          FROM tramitacao
         WHERE casa = ? AND id_proposicao = ?
         ORDER BY CAST(seq_tramitacao AS INTEGER)
    """, [casa, str(id_proposicao)])
    return {"coletadas": quantas, "tramitacoes": etapas}


@router.get("/api/votacoes/{casa}/{id_votacao}/votos")
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


