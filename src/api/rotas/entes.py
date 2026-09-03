"""Rotas de Entes Federativos, Indicadores, Rankings, Mapas e Malhas."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from ..db import _consultar
from ...nucleo import config
from ...coletores import ibge as coletor_ibge

router = APIRouter(tags=["entes"])

@router.get("/api/metricas")
def metricas():
    return _consultar("SELECT cod_metrica, rotulo, unidade, fonte_origem "
                      "FROM dim_metrica ORDER BY rotulo")


@router.get("/api/anos")
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



# ------------------------------------------------------------------ mapa
@router.get("/api/mapa")
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


@router.get("/api/malha/{escopo}")
def malha(escopo: str):
    """GeoJSON. `escopo` = 'brasil' ou a sigla da UF.

    A malha do Brasil por UF é carregada no boot do painel; a de cada UF é
    resolvida instantaneamente a partir das geometrias oficiais empacotadas.
    """
    escopo_limpo = escopo.strip().upper()
    HEADERS_CACHE = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if escopo_limpo in ("BRASIL", "BR"):
        arquivo = config.MALHAS / "brasil-uf.json"
        if not arquivo.exists():
            ref = config.RAIZ / "referencias" / "malhas" / "brasil-uf.json"
            if ref.exists():
                import shutil
                shutil.copy(ref, arquivo)
        if arquivo.exists():
            return FileResponse(arquivo, media_type="application/geo+json", headers=HEADERS_CACHE)
        ref = config.RAIZ / "referencias" / "malhas" / "brasil-uf.json"
        if ref.exists():
            return FileResponse(ref, media_type="application/geo+json", headers=HEADERS_CACHE)
        raise HTTPException(404, "malha do Brasil indisponível")

    # Escopo é uma UF específica (ex: 'SP', 'RJ', 'MG', 'BA')
    arquivo_uf = config.MALHAS / f"uf-{escopo_limpo}.json"
    if arquivo_uf.exists():
        return FileResponse(arquivo_uf, media_type="application/geo+json", headers=HEADERS_CACHE)

    # Busca no diretório de referências embutidas
    ref = config.RAIZ / "referencias" / "malhas" / f"uf-{escopo_limpo}.json"
    if ref.exists():
        import shutil
        config.MALHAS.mkdir(parents=True, exist_ok=True)
        shutil.copy(ref, arquivo_uf)
        return FileResponse(arquivo_uf, media_type="application/geo+json", headers=HEADERS_CACHE)

    raise HTTPException(404, f"malha municipal indisponível: {escopo_limpo}")



# ------------------------------------------------------------------ ranking
@router.get("/api/ranking")
def ranking(ano: int, metrica: str = "despesa_per_capita",
            nivel: str = "estado", uf: str | None = None,
            porte: str | None = None,
            ordem: str = Query("desc", pattern="^(asc|desc)$"),
            limite: int = Query(30, le=200)):
    if metrica not in ("despesa_per_capita", "despesa_total", "receita_total",
                       "receita_per_capita", "populacao", "despesa_saude",
                       "despesa_educacao", "saude_per_capita", "educacao_per_capita"):
        raise HTTPException(400, "métrica inválida")
    condicoes = ["nivel = ?", "ano = ?", f"{metrica} IS NOT NULL"]
    parametros: list[Any] = [nivel, ano]
    if uf:
        condicoes.append("sigla_uf = ?"); parametros.append(uf.upper())
    if porte == "pequeno":
        condicoes.append("populacao <= 20000")
    elif porte == "medio":
        condicoes.append("populacao > 20000 AND populacao <= 100000")
    elif porte == "grande":
        condicoes.append("populacao > 100000")
    elif porte == "capitais":
        condicoes.append("cod_ibge IN ('1100205','1200401','1302603','1400100','1501402','1600303','1721000','2111300','2211001','2304400','2408102','2507507','2611606','2704302','2800308','2927408','3106200','3205309','3304557','3550308','4106902','4205407','4314902','5002704','5103403','5208707','5300108')")

    return _consultar(f"""
        SELECT cod_ibge, nome, sigla_uf, populacao, {metrica} AS valor
          FROM vw_mapa WHERE {' AND '.join(condicoes)}
         ORDER BY valor {ordem.upper()} LIMIT {int(limite)}
    """, parametros)


@router.get("/api/ente/{cod_ibge}")
def ficha_do_ente(cod_ibge: str, ano: int | None = None):
    """Tudo sobre um ente numa chamada: quem governa, quanto gasta, e em quê.

    É a rota que só existe porque o de-para TSE → IBGE existe. Sem ele o
    painel sabia o gasto e sabia o prefeito, e não conseguia dizer que eram
    a mesma cidade.
    """
    cod_ibge_limpo = cod_ibge.strip()
    ente = _consultar(
        "SELECT cod_ibge, nome, nivel, sigla_uf, cod_uf, regiao "
        "FROM dim_ente WHERE cod_ibge = ? OR (sigla_uf = ? AND nivel = 'estado')",
        [cod_ibge_limpo, cod_ibge_limpo.upper()])
    if not ente:
        raise HTTPException(404, "ente não encontrado")
    ente = ente[0]
    cod_ibge = str(ente["cod_ibge"])

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

    credito_historico = _consultar("""
        SELECT ano, COUNT(*) AS pleitos,
               SUM(valor) AS valor_pleiteado,
               SUM(valor) FILTER (WHERE status ILIKE 'Deferido%') AS valor_deferido,
               SUM(valor) FILTER (WHERE contratado = 1) AS valor_contratado
          FROM operacao_credito
         WHERE cod_ibge = ?
         GROUP BY ano ORDER BY ano DESC
    """, [cod_ibge])

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
         ORDER BY CASE poder WHEN 'E' THEN 1 WHEN 'L' THEN 2 WHEN 'J' THEN 3 WHEN 'M' THEN 4 WHEN 'D' THEN 5 ELSE 6 END
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

    # Quem governa:
    # 1. Ente País: presidentes (se ano informado, contemporâneo; se sem ano, histórico)
    # 2. Ente Estado: governadores do estado + presidente contemporâneo (1 registro)
    # 3. Ente Município: prefeitos do município + governador contemporâneo da UF (1) + presidente contemporâneo (1)
    if ente.get("nivel") == "pais" or cod_ibge == "0":
        cond_gov = "cod_ibge = '0'"
        params_gov = []
        if ano:
            cond_gov += " AND ano_inicio <= ? AND ano_fim >= ?"
            params_gov.extend([ano, ano])
        governantes = _consultar(f"""
            SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
              FROM vw_executivo
             WHERE {cond_gov}
             ORDER BY ano_inicio DESC
        """, params_gov)
    elif ente.get("nivel") == "estado":
        gov_estado = _consultar("""
            SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
              FROM vw_executivo
             WHERE cod_ibge = ?
             ORDER BY ano_inicio DESC
        """, [cod_ibge])
        if ano:
            gov_filtrado = [g for g in gov_estado if (g.get("ano_inicio") or 0) <= ano <= (g.get("ano_fim") or 9999)]
            if gov_filtrado:
                gov_estado = gov_filtrado

        if ano:
            pres = _consultar("""
                SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                  FROM vw_executivo
                 WHERE cod_ibge = '0' AND ano_inicio <= ? AND ano_fim >= ?
                 ORDER BY ano_inicio DESC LIMIT 1
            """, [ano, ano])
        else:
            pres = _consultar("""
                SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                  FROM vw_executivo
                 WHERE cod_ibge = '0'
                 ORDER BY ano_inicio DESC LIMIT 1
            """)
        governantes = gov_estado + (pres or [])
    else:
        # Município
        cod_uf = str(ente.get("cod_uf") or "")
        pref = _consultar("""
            SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
              FROM vw_executivo
             WHERE cod_ibge = ?
             ORDER BY ano_inicio DESC
        """, [cod_ibge])
        if ano:
            pref_filtrado = [p for p in pref if (p.get("ano_inicio") or 0) <= ano <= (p.get("ano_fim") or 9999)]
            if pref_filtrado:
                pref = pref_filtrado

        gov = []
        if cod_uf:
            if ano:
                gov = _consultar("""
                    SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                      FROM vw_executivo
                     WHERE cod_ibge = ? AND ano_inicio <= ? AND ano_fim >= ?
                     ORDER BY ano_inicio DESC LIMIT 1
                """, [cod_uf, ano, ano])
            if not gov:
                gov = _consultar("""
                    SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                      FROM vw_executivo
                     WHERE cod_ibge = ?
                     ORDER BY ano_inicio DESC LIMIT 1
                """, [cod_uf])

        if ano:
            pres = _consultar("""
                SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                  FROM vw_executivo
                 WHERE cod_ibge = '0' AND ano_inicio <= ? AND ano_fim >= ?
                 ORDER BY ano_inicio DESC LIMIT 1
            """, [ano, ano])
        else:
            pres = _consultar("""
                SELECT cargo, nome, sigla_partido, sigla_uf, ano_inicio, ano_fim
                  FROM vw_executivo
                 WHERE cod_ibge = '0'
                 ORDER BY ano_inicio DESC LIMIT 1
            """)
        governantes = pref + (gov or []) + (pres or [])

    legislativo = _consultar("""
        SELECT cargo, COUNT(*) AS quantidade
          FROM vw_mandato
         WHERE cod_ibge = ? AND cargo NOT IN
               ('presidente', 'governador', 'prefeito')
         GROUP BY cargo ORDER BY quantidade DESC
    """, [cod_ibge])

    transferencias_historico = _consultar("""
        SELECT ano, total_transferencias, fpm, fpe, fundeb, royalties
          FROM vw_transferencia_historico_ente
         WHERE cod_ibge = ?
         ORDER BY ano DESC
    """, [cod_ibge])

    nome_ente = str(ente.get("nome") or "").upper()
    uf_ente = str(ente.get("sigla_uf") or "").upper()
    localidade_busca = f"{nome_ente} - {uf_ente}"

    emendas_recebidas = _consultar("""
        SELECT ano, autor, tipo_emenda, funcao,
               valor_empenhado, valor_pago
          FROM vw_emenda_parlamentar
         WHERE upper(strip_accents(trim(localidade))) = upper(strip_accents(trim(?)))
            OR upper(strip_accents(trim(localidade))) LIKE upper(strip_accents(trim(?))) || '%'
         ORDER BY valor_empenhado DESC LIMIT 50
    """, [localidade_busca, nome_ente]) if nome_ente else []

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
        "transferencias_historico": transferencias_historico,
        "emendas_recebidas": emendas_recebidas,
        "credito": credito[0] if credito else None,
        "credito_historico": credito_historico,
        "credito_finalidade": credito_finalidade,
        "indicadores": indicadores,
        "governantes": governantes,
        "legislativo": legislativo,
    }


@router.get("/api/de-para/pendencias")
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


@router.get("/api/financas/{cod_ibge}")
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


