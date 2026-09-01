"""Rotas do Poder Judiciário (Magistrados, Ministros e Remunerações)."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..db import _consultar

router = APIRouter(prefix="/api/judiciario", tags=["judiciario"])


@router.get("/sumario")
def judiciario_sumario():
    """Resumo geral do Poder Judiciário com totais, médias e distribuição por ramo."""
    totais = _consultar("""
        SELECT COUNT(DISTINCT m.sk) AS total_magistrados,
               COUNT(DISTINCT m.tribunal) AS total_tribunais,
               AVG(r.total_liquido) AS media_liquida,
               SUM(r.total_liquido) AS total_folha_mensal,
               AVG(r.indenizacoes + r.gratificacoes) AS media_penduricalhos
          FROM dim_magistrado m
          LEFT JOIN (
              SELECT sk_magistrado, total_liquido, indenizacoes, gratificacoes
                FROM fato_remuneracao_magistrado
               WHERE ano = 2026 AND mes = (SELECT MAX(mes) FROM fato_remuneracao_magistrado WHERE ano = 2026)
          ) r ON r.sk_magistrado = m.sk
    """)

    por_ramo = _consultar("""
        SELECT m.ramo,
               COUNT(DISTINCT m.sk) AS quantidade,
               COALESCE(AVG(r.total_liquido), 0) AS media_liquida,
               COALESCE(SUM(r.total_liquido), 0) AS total_liquido
          FROM dim_magistrado m
          LEFT JOIN (
              SELECT sk_magistrado, total_liquido
                FROM fato_remuneracao_magistrado
               WHERE ano = 2026 AND mes = (SELECT MAX(mes) FROM fato_remuneracao_magistrado WHERE ano = 2026)
          ) r ON r.sk_magistrado = m.sk
         GROUP BY m.ramo
         ORDER BY total_liquido DESC
    """)

    return {
        "kpis": totais[0] if totais else {},
        "por_ramo": por_ramo,
    }


@router.get("/magistrados")
def listar_magistrados(
    ramo: str | None = None,
    tribunal: str | None = None,
    cargo: str | None = None,
    grau: str | None = None,
    uf: str | None = None,
    busca: str | None = None,
    ordenar: str = "remuneracao",  # 'remuneracao' ou 'nome'
    limite: int = Query(100, le=1000),
):
    """Lista de magistrados com dados cadastrais e última remuneração apurada."""
    condicoes = []
    parametros: list[Any] = []

    if ramo:
        condicoes.append("m.ramo ILIKE ?")
        parametros.append(f"%{ramo}%")
    if tribunal:
        condicoes.append("m.tribunal = ?")
        parametros.append(tribunal.upper())
    if cargo:
        condicoes.append("m.cargo = ?")
        parametros.append(cargo)
    if grau:
        condicoes.append("m.grau = ?")
        parametros.append(grau.upper())
    if uf:
        condicoes.append("m.sigla_uf = ?")
        parametros.append(uf.upper())
    if busca:
        condicoes.append("(m.nome ILIKE ? OR m.cargo_descricao ILIKE ? OR m.orgao_lotacao ILIKE ?)")
        termo = f"%{busca}%"
        parametros.extend([termo, termo, termo])

    clausula_where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    ordem_sql = "ORDER BY r.total_liquido DESC NULLS LAST" if ordenar == "remuneracao" else "ORDER BY m.nome ASC"

    return _consultar(f"""
        SELECT m.sk,
               m.cod_magistrado_interno,
               m.cod_cargo_interno,
               m.nome_extraido,
               m.nome_formatado,
               m.nome,
               m.cargo,
               m.cargo_descricao,
               m.tribunal,
               m.ramo,
               m.grau,
               m.sigla_uf,
               m.orgao_lotacao,
               m.data_posse,
               m.situacao,
               m.url_foto,
               COALESCE(r.ano, 2026) AS ano_ref,
               COALESCE(r.mes, 1) AS mes_ref,
               COALESCE(r.subsidio, 0) AS subsidio,
               COALESCE(r.vantagens_pessoais, 0) AS vantagens_pessoais,
               COALESCE(r.indenizacoes, 0) AS indenizacoes,
               COALESCE(r.gratificacoes, 0) AS gratificacoes,
               COALESCE(r.total_bruto, 0) AS total_bruto,
               COALESCE(r.retencao_teto, 0) AS retencao_teto,
               COALESCE(r.descontos_legais, 0) AS descontos_legais,
               COALESCE(r.total_liquido, 0) AS total_liquido,
               COALESCE(r.total_penduricalhos, (COALESCE(r.indenizacoes, 0) + COALESCE(r.gratificacoes, 0))) AS total_penduricalhos
          FROM vw_magistrado m
          LEFT JOIN (
              SELECT DISTINCT ON (sk_magistrado)
                     sk_magistrado, ano, mes, subsidio, vantagens_pessoais,
                     indenizacoes, gratificacoes, total_bruto, retencao_teto,
                     descontos_legais, total_liquido,
                     (indenizacoes + gratificacoes) AS total_penduricalhos
                FROM fato_remuneracao_magistrado
               ORDER BY sk_magistrado, ano DESC, mes DESC
          ) r ON r.sk_magistrado = m.sk
         {clausula_where}
         {ordem_sql}
         LIMIT {int(limite)}
    """, parametros)


@router.get("/magistrados/{sk}")
def ficha_magistrado(sk: str):
    """Ficha detalhada com histórico de remuneração e dados de lotação."""
    magistrado = _consultar("""
        SELECT m.sk,
               m.nome,
               m.cargo,
               m.cargo_descricao,
               m.tribunal,
               m.ramo,
               m.grau,
               m.sigla_uf,
               m.orgao_lotacao,
               m.data_posse,
               m.situacao,
               m.url_foto
          FROM dim_magistrado m
         WHERE m.sk = ?
    """, [sk])

    if not magistrado:
        raise HTTPException(404, "Magistrado não encontrado")

    folhas = _consultar("""
        SELECT ano, mes, subsidio, vantagens_pessoais, indenizacoes,
               gratificacoes, total_bruto, retencao_teto, descontos_legais,
               total_liquido
          FROM fato_remuneracao_magistrado
         WHERE sk_magistrado = ?
         ORDER BY ano DESC, mes DESC
    """, [sk])

    totais = _consultar("""
        SELECT AVG(total_liquido) AS media_mensal_liquida,
               SUM(total_bruto) AS total_acumulado_bruto,
               SUM(total_liquido) AS total_acumulado_liquido,
               SUM(indenizacoes + gratificacoes) AS total_penduricalhos
          FROM fato_remuneracao_magistrado
         WHERE sk_magistrado = ?
    """, [sk])

    return {
        "magistrado": magistrado[0],
        "historico": folhas,
        "totais": totais[0] if totais else {},
        "teto_stf_referencia": 46366.19,
    }


@router.get("/tribunais")
def listar_tribunais():
    """Lista agregada de tribunais do Poder Judiciário."""
    return _consultar("""
        SELECT m.tribunal,
               m.ramo,
               COUNT(DISTINCT m.sk) AS quantidade_magistrados,
               COALESCE(AVG(r.total_liquido), 0) AS media_liquida,
               COALESCE(SUM(r.total_liquido), 0) AS total_mensal
          FROM dim_magistrado m
          LEFT JOIN (
              SELECT sk_magistrado, total_liquido
                FROM fato_remuneracao_magistrado
               WHERE ano = 2026 AND mes = (SELECT MAX(mes) FROM fato_remuneracao_magistrado WHERE ano = 2026)
          ) r ON r.sk_magistrado = m.sk
         GROUP BY m.tribunal, m.ramo
         ORDER BY quantidade_magistrados DESC, total_mensal DESC
    """)
