"""Rotas do Poder Executivo, Custos, Cartões, Viagens e Contratos."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..db import _consultar
from ...nucleo import controle

router = APIRouter(tags=["executivo"])

# ------------------------------------------------------------------ custo
@router.get("/api/custo/cargos")
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


@router.get("/api/custo/resumo")
def resumo_de_custo(ano: int | None = None, poder: str | None = None):
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

    ano_pedido = ano
    ano_funcao = ano_pedido or _ultimo_ano("vw_despesa_poder")
    ano_medido = ano_pedido or _ultimo_ano("custo_orgao")
    ano_receita = ano_pedido or _ultimo_ano("vw_receita_total")
    ano_despesa = ano_pedido or _ultimo_ano("vw_despesa_total")
    ano = ano_pedido or max(
        [a for a in (ano_funcao, ano_medido, ano_receita, ano_despesa)
         if a is not None], default=None)

    despesa = _consultar("""
        SELECT funcao, esfera, SUM(valor) AS valor
          FROM vw_despesa_poder WHERE ano = ?
         GROUP BY ALL ORDER BY valor DESC
    """, [ano_funcao]) if ano_funcao else []

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

    # Big Number da Competência da Presidência da República e Executivo Federal
    presid_rows = _consultar("""
        SELECT SUM(valor) AS total_presidencia
          FROM custo_orgao
         WHERE ano = ? AND (orgao_nome ILIKE '%Presidência da República%' OR orgao_nome ILIKE '%Presidencia da Republica%')
    """, [ano_medido]) if ano_medido else []
    custo_presidencia = float(presid_rows[0]["total_presidencia"]) if presid_rows and presid_rows[0].get("total_presidencia") is not None else None

    total_fed_rows = _consultar("""
        SELECT SUM(valor) AS total_executivo_federal
          FROM custo_orgao WHERE ano = ?
    """, [ano_medido]) if ano_medido else []
    custo_executivo_federal = float(total_fed_rows[0]["total_executivo_federal"]) if total_fed_rows and total_fed_rows[0].get("total_executivo_federal") is not None else None

    cargos_filtrados = [c for c in cargos if c.get("poder", "").lower() == poder.lower()] if poder else cargos
    nao_conferidos = sum(int(c["nao_conferidos"] or 0) for c in cargos_filtrados)

    anos_disponiveis = [
        int(l["ano"]) for l in _consultar("""
            SELECT DISTINCT ano FROM vw_anos WHERE ano IS NOT NULL ORDER BY ano DESC
        """)
    ]

    return {
        "ano": ano,
        "ano_pedido": ano_pedido,
        "poder_selecionado": poder,
        "anos_disponiveis": anos_disponiveis,
        "estimado_por_poder": cargos_filtrados,
        "estimado_todos_poderes": cargos,
        "despesa_por_funcao": despesa,
        "custo_medido_federal": medido,
        "custo_presidencia_republica": custo_presidencia,
        "custo_executivo_federal": custo_executivo_federal,
        "arrecadacao": valor_receita,
        "arrecadacao_entes": entes_receita,
        "ano_arrecadacao": ano_receita,
        "ano_despesa_subnacional": ano_despesa,
        "ano_despesa_funcao": ano_funcao,
        "ano_custo_medido": ano_medido,
        "despesa_subnacional": valor_despesa_agregada,
        "despesa_entes": entes_despesa,
        "avisos": [
            aviso for aviso in [
                f"{nao_conferidos} valor(es) de subsídio ainda não conferidos contra a norma." if nao_conferidos else None,
                "Custo estimado = ocupantes × subsídio × 13,33. Não inclui gabinete, auxílios, diárias nem encargos." if cargos_filtrados else None,
                "Despesa por função é o valor que de fato saiu dos cofres (SICONFI) — não confundir com a estimativa de subsídios." if despesa else None,
                (f"Custo medido federal de {ano_medido}: {', '.join(incompletos)} com coleta incompleta (paginação interrompida). Os valores desses recortes são PISO, não total apurado.") if incompletos else None,
                f"Arrecadação e despesa somam {entes_despesa} ente(s) do acervo — estados e municípios já coletados. O orçamento da União não entra: ele não está no SICONFI." if entes_despesa else None,
                (f"Arrecadação e despesa agregadas não existem para {ano_pedido}: elas vêm do DCA, que é anual e só é publicado no exercício seguinte. O último disponível é {ano_receita or ano_despesa or 'nenhum'}.") if ano_pedido and not entes_despesa else None,
            ] if aviso
        ],
    }



# ------------------------------------------------------------------ executivo & políticos
@router.get("/api/politicos/executivo")
def executivo_em_destaque(uf: str | None = None, cargo: str | None = None,
                          cod_ibge: str | None = None, ano: int | None = None):
    """Quem chefia o Executivo do recorte em que o usuário está."""
    parametros: list[Any] = []
    if cod_ibge:
        onde = "m.cargo = 'prefeito' AND m.cod_ibge = ?"
        parametros.append(str(cod_ibge))
    elif cargo == "prefeito" and uf:
        onde = "m.cargo = 'prefeito' AND m.sigla_uf = ?"
        parametros.append(uf.strip().upper())
    elif uf:
        onde = "m.cargo = 'governador' AND m.sigla_uf = ?"
        parametros.append(uf.strip().upper())
    else:
        onde = "m.cargo = 'presidente'"

    filtro_ano = ""
    if ano:
        filtro_ano = "AND (m.ano_inicio <= ? AND (m.ano_fim >= ? OR m.ano_fim IS NULL))"
        parametros.extend([ano, ano])

    res = _consultar(f"""
        SELECT m.cargo, m.nome, m.sigla_partido, m.sigla_uf,
               m.ano_inicio, m.ano_fim, m.data_inicio,
               p.url_foto,
               COALESCE(s_especifico.valor_mensal, s_geral.valor_mensal) AS salario,
               COALESCE(s_especifico.norma, s_geral.norma)               AS norma_salario,
               COALESCE(s_especifico.url_norma, s_geral.url_norma)       AS url_norma_salario,
               COALESCE(s_especifico.conferido, s_geral.conferido)       AS salario_conferido
          FROM vw_mandato m
          LEFT JOIN dim_politico p
                 ON p.id_origem = m.sk_politico
           LEFT JOIN dim_cargo_publico c_especifico
                  ON c_especifico.cod_cargo = (m.cargo || '_' || LOWER(COALESCE(m.sigla_uf, '')))
           LEFT JOIN vw_subsidio_vigente s_especifico
                  ON s_especifico.cod_cargo = c_especifico.cod_cargo
           LEFT JOIN dim_cargo_publico c_geral
                  ON (c_geral.cod_cargo = m.cod_cargo OR c_geral.cod_cargo = m.cargo)
           LEFT JOIN vw_subsidio_vigente s_geral
                  ON s_geral.cod_cargo = c_geral.cod_cargo
          WHERE {onde} {filtro_ano}
          ORDER BY m.ano_inicio DESC
          LIMIT 1
    """, parametros)

    return res


@router.get("/api/executivo/municipios")
def executivo_municipios(uf: str):
    """Municípios de uma UF para o seletor do Poder Executivo."""
    return _consultar("""
        SELECT e.cod_ibge, e.nome, e.sigla_uf, p.populacao
          FROM dim_ente e
          LEFT JOIN vw_populacao p
                 ON p.cod_ibge = e.cod_ibge
                AND p.ano = (SELECT MAX(ano) FROM vw_populacao WHERE populacao IS NOT NULL)
         WHERE e.nivel = 'municipio' AND e.sigla_uf = ?
         ORDER BY p.populacao DESC NULLS LAST, e.nome
    """, [uf.upper()])


@router.get("/api/executivo/mandato")
def executivo_mandato(esfera: str = "estadual", sigla_uf: str = "SP",
                      cod_ibge: str | None = None, ano: int | None = None):
    """Dados consolidados do mandato do Executivo (Presidente, Governador ou Prefeito)."""
    uf_busca = sigla_uf.upper() if sigla_uf else "SP"

    if esfera == "federal":
        cod_ibge_busca = "0"
        uf_busca = "BR"
        ente_nome = "Governo Federal (Brasil)"
        mandato_sql = "m.cargo = 'presidente'"
        params_gov: list[Any] = []
    elif esfera == "estadual":
        ente_res = _consultar("SELECT cod_ibge, nome FROM dim_ente WHERE nivel = 'estado' AND sigla_uf = ?", [uf_busca])
        cod_ibge_busca = ente_res[0]["cod_ibge"] if ente_res else "35"
        ente_nome = ente_res[0]["nome"] if ente_res else f"Estado de {uf_busca}"
        mandato_sql = "m.cargo = 'governador' AND m.sigla_uf = ?"
        params_gov = [uf_busca]
    else: # municipal
        if not cod_ibge and sigla_uf:
            muns = _consultar("SELECT cod_ibge, nome FROM dim_ente WHERE nivel = 'municipio' AND sigla_uf = ? ORDER BY populacao DESC LIMIT 1", [uf_busca])
            cod_ibge_busca = muns[0]["cod_ibge"] if muns else "3550308"
            ente_nome = muns[0]["nome"] if muns else "São Paulo"
        else:
            cod_ibge_busca = str(cod_ibge or "3550308")
            ente_res = _consultar("SELECT nome, sigla_uf FROM dim_ente WHERE cod_ibge = ?", [cod_ibge_busca])
            ente_nome = ente_res[0]["nome"] if ente_res else "Município"
            uf_busca = ente_res[0]["sigla_uf"] if ente_res else "SP"
        mandato_sql = "m.cargo = 'prefeito' AND m.cod_ibge = ?"
        params_gov = [cod_ibge_busca]

    # Série Histórica de Receitas, Despesas e Saldo
    if esfera == "federal":
        serie_rows = _consultar("""
            SELECT ano, SUM(valor) AS despesa_total, NULL AS receita_total, NULL AS populacao
              FROM custo_orgao GROUP BY ano ORDER BY ano DESC
        """)
    else:
        serie_rows = _consultar("""
            SELECT a.ano, r.receita_total, d.despesa_total, p.populacao,
                   (r.receita_total - d.despesa_total) AS saldo_orcamentario
              FROM vw_anos a
              LEFT JOIN vw_receita_total r ON r.cod_ibge = ? AND r.ano = a.ano
              LEFT JOIN vw_despesa_total d ON d.cod_ibge = ? AND d.ano = a.ano
              LEFT JOIN vw_populacao p ON p.cod_ibge = ? AND p.ano = a.ano
             WHERE (r.receita_total IS NOT NULL OR d.despesa_total IS NOT NULL)
             ORDER BY a.ano DESC
        """, [cod_ibge_busca, cod_ibge_busca, cod_ibge_busca])

    serie_anual = []
    for s in serie_rows:
        ano_item = int(s["ano"])
        desp = float(s["despesa_total"]) if s.get("despesa_total") is not None else None
        rec = float(s["receita_total"]) if s.get("receita_total") is not None else None
        pop = float(s["populacao"]) if s.get("populacao") is not None else None
        saldo = (rec - desp) if (rec is not None and desp is not None) else None
        situacao = "superavit" if (saldo is not None and saldo >= 0) else ("deficit" if saldo is not None else None)
        serie_anual.append({
            "ano": ano_item, "receita": rec, "despesa": desp, "saldo": saldo,
            "situacao": situacao, "populacao": pop,
            "despesa_per_capita": (desp / pop) if (desp is not None and pop) else None
        })

    ano_alvo = ano or (serie_anual[0]["ano"] if serie_anual else 2025)
    item_ano = next((x for x in serie_anual if x["ano"] == ano_alvo), (serie_anual[0] if serie_anual else None))

    # Governante ativo no ano solicitado
    filtro_ano_gov = "AND (m.ano_inicio <= ? AND (m.ano_fim >= ? OR m.ano_fim IS NULL))"
    params_gov_ano = list(params_gov) + [ano_alvo, ano_alvo]

    gov_rows = _consultar(f"""
        SELECT m.cargo, m.nome, m.sigla_partido, m.sigla_uf, m.ano_inicio, m.ano_fim, m.data_inicio,
               COALESCE(s_especifico.valor_mensal, s_geral.valor_mensal) AS salario,
               COALESCE(s_especifico.norma, s_geral.norma)               AS norma_salario,
               COALESCE(s_especifico.url_norma, s_geral.url_norma)       AS url_norma_salario,
               COALESCE(s_especifico.conferido, s_geral.conferido)       AS salario_conferido
          FROM vw_mandato m
          LEFT JOIN dim_cargo_publico c_especifico
                 ON c_especifico.cod_cargo = (m.cargo || '_' || LOWER(COALESCE(m.sigla_uf, '')))
          LEFT JOIN vw_subsidio_vigente s_especifico
                 ON s_especifico.cod_cargo = c_especifico.cod_cargo
          LEFT JOIN dim_cargo_publico c_geral
                 ON (c_geral.cod_cargo = m.cod_cargo OR c_geral.cod_cargo = m.cargo)
          LEFT JOIN vw_subsidio_vigente s_geral
                 ON s_geral.cod_cargo = c_geral.cod_cargo
         WHERE {mandato_sql} {filtro_ano_gov}
         ORDER BY m.ano_inicio DESC LIMIT 1
    """, params_gov_ano)

    governante = gov_rows[0] if gov_rows else None

    # Mandatos Históricos Disponíveis para este Ente
    mandatos_hist = _consultar(f"""
        SELECT DISTINCT m.nome, m.sigla_partido, m.ano_inicio, m.ano_fim, m.data_inicio
          FROM vw_mandato m
         WHERE {mandato_sql}
         ORDER BY m.ano_inicio DESC
    """, params_gov)

    mandatos_disponiveis = []
    for mh in mandatos_hist:
        ini = int(mh["ano_inicio"]) if mh.get("ano_inicio") else 2023
        fim = int(mh["ano_fim"]) if mh.get("ano_fim") else (ini + 4)
        rotulo = f"Mandato {ini}–{fim} ({mh.get('nome', '')})"
        anos_mandato = [a for a in range(ini, fim) if a in [s["ano"] for s in serie_anual]] or list(range(ini, fim))
        mandatos_disponiveis.append({
            "ano_inicio": ini,
            "ano_fim": fim,
            "nome": mh.get("nome"),
            "partido": mh.get("sigla_partido"),
            "rotulo": rotulo,
            "anos": sorted(anos_mandato, reverse=True)
        })

    # Funções de Governo no ano
    if esfera == "federal":
        funcoes = _consultar("""
            SELECT orgao_codigo AS cod_funcao, orgao_nome AS funcao, SUM(valor) AS valor
              FROM custo_orgao WHERE ano = ?
             GROUP BY ALL ORDER BY valor DESC LIMIT 15
        """, [ano_alvo])
    else:
        funcoes = _consultar("""
            SELECT cod_funcao, funcao, SUM(valor) AS valor
              FROM vw_despesa_por_funcao WHERE cod_ibge = ? AND ano = ?
             GROUP BY ALL ORDER BY valor DESC LIMIT 15
        """, [cod_ibge_busca, ano_alvo])

    total_funcoes = sum(float(f["valor"]) for f in funcoes if f.get("valor"))
    for f in funcoes:
        v = float(f.get("valor") or 0)
        f["percentual"] = round((v / total_funcoes * 100), 2) if total_funcoes else 0

    # LRF & Pessoal
    lrf_res = _consultar("""
        SELECT percentual_pessoal, limite_maximo, limite_prudencial, limite_alerta,
               acima_do_limite, acima_do_prudencial
          FROM vw_lrf_pessoal WHERE cod_ibge = ? AND ano = ? AND poder = 'E'
    """, [cod_ibge_busca, ano_alvo])
    lrf = lrf_res[0] if lrf_res else None

    # Anos disponíveis
    anos_disponiveis = [s["ano"] for s in serie_anual]

    return {
        "esfera": esfera,
        "cod_ibge": cod_ibge_busca,
        "ente_nome": ente_nome,
        "sigla_uf": uf_busca,
        "ano": ano_alvo,
        "anos_disponiveis": anos_disponiveis,
        "mandatos_disponiveis": mandatos_disponiveis,
        "governante": governante,
        "resultado_ano": item_ano,
        "gastos_por_funcao": funcoes,
        "serie_anual": serie_anual,
        "lrf": lrf
    }


@router.get("/api/executivo/cartoes")
def executivo_cartoes(ano: int | None = None, orgao: str | None = None, limite: int = 50):
    """Gastos do Cartão de Pagamento do Governo Federal (CPGF)."""
    if ano is None:
        ultimo = _consultar("SELECT MAX(ano) AS ano FROM vw_cartao_corporativo")
        ano = int(ultimo[0]["ano"]) if ultimo and ultimo[0].get("ano") is not None else None

    condicoes = []
    parametros: list[Any] = []
    if ano:
        condicoes.append("ano = ?")
        parametros.append(ano)
    if orgao:
        condicoes.append("nome_orgao ILIKE ?")
        parametros.append(f"%{orgao}%")

    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    totais = _consultar(f"""
        SELECT COUNT(*) AS total_transacoes,
               SUM(valor) AS total_gasto,
               SUM(valor) FILTER (
                 WHERE nome_orgao ILIKE '%Presidência da República%'
                    OR nome_orgao ILIKE '%Presidencia da Republica%'
                    OR nome_orgao ILIKE '%Gabinete de Segurança Institucional%'
               ) AS total_presidencia
          FROM vw_cartao_corporativo {onde}
    """, parametros)

    por_orgao = _consultar(f"""
        SELECT nome_orgao, COUNT(*) AS transacoes, SUM(valor) AS total_gasto
          FROM vw_cartao_corporativo {onde}
         GROUP BY nome_orgao ORDER BY total_gasto DESC LIMIT 15
    """, parametros)

    por_favorecido = _consultar(f"""
        SELECT nome_favorecido, cnpj_cpf_favorecido,
               COUNT(*) AS transacoes, SUM(valor) AS total_gasto
          FROM vw_cartao_corporativo {onde}
         GROUP BY nome_favorecido, cnpj_cpf_favorecido
         ORDER BY total_gasto DESC LIMIT 20
    """, parametros)

    maiores_gastos = _consultar(f"""
        SELECT data_transacao, nome_orgao, nome_portador,
               nome_favorecido, cnpj_cpf_favorecido, tipo_cartao, valor
          FROM vw_cartao_corporativo {onde}
         ORDER BY valor DESC LIMIT {int(limite)}
    """, parametros)

    serie_anual = _consultar("""
        SELECT ano, total_gasto, total_presidencia, transacoes
          FROM vw_cartao_serie_anual
         ORDER BY ano DESC
    """)

    anos_disponiveis = [int(l["ano"]) for l in _consultar("""
        SELECT DISTINCT ano FROM vw_cartao_corporativo WHERE ano IS NOT NULL ORDER BY ano DESC
    """)]

    tot = totais[0] if totais else {}
    return {
        "ano": ano,
        "anos_disponiveis": anos_disponiveis,
        "total_gasto": float(tot.get("total_gasto") or 0.0),
        "total_presidencia": float(tot.get("total_presidencia") or 0.0),
        "total_transacoes": int(tot.get("total_transacoes") or 0),
        "por_orgao": por_orgao,
        "por_favorecido": por_favorecido,
        "maiores_gastos": maiores_gastos,
        "serie_anual": serie_anual,
    }


@router.get("/api/executivo/viagens")
def executivo_viagens(ano: int | None = None, orgao: str | None = None, limite: int = 50):
    """Viagens a serviço, diárias e passagens do Governo Federal (PCDP / CGU)."""
    if ano is None:
        ultimo = _consultar("SELECT MAX(ano) AS ano FROM vw_viagem_servico")
        ano = int(ultimo[0]["ano"]) if ultimo and ultimo[0].get("ano") is not None else None

    condicoes = []
    parametros: list[Any] = []
    if ano:
        condicoes.append("ano = ?")
        parametros.append(ano)
    if orgao:
        condicoes.append("nome_orgao ILIKE ?")
        parametros.append(f"%{orgao}%")

    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    totais = _consultar(f"""
        SELECT COUNT(*) AS total_viagens,
               SUM(valor_diarias) AS total_diarias,
               SUM(valor_passagens) AS total_passagens,
               SUM(valor_total) AS total_gasto
          FROM vw_viagem_servico {onde}
    """, parametros)

    por_orgao = _consultar(f"""
        SELECT nome_orgao, COUNT(*) AS viagens,
               SUM(valor_diarias) AS total_diarias,
               SUM(valor_passagens) AS total_passagens,
               SUM(valor_total) AS total_gasto
          FROM vw_viagem_servico {onde}
         GROUP BY nome_orgao ORDER BY total_gasto DESC LIMIT 15
    """, parametros)

    por_destino = _consultar(f"""
        SELECT destino, COUNT(*) AS viagens, SUM(valor_total) AS total_gasto
          FROM vw_viagem_servico {onde}
         GROUP BY destino ORDER BY total_gasto DESC LIMIT 20
    """, parametros)

    maiores_viagens = _consultar(f"""
        SELECT data_inicio, data_fim, nome_orgao, nome_viajante, cargo_viajante,
               origem, destino, motivo, valor_diarias, valor_passagens, valor_total
          FROM vw_viagem_servico {onde}
         ORDER BY valor_total DESC LIMIT {int(limite)}
    """, parametros)

    serie_anual = _consultar("""
        SELECT ano, viagens, total_diarias, total_passagens, total_gasto
          FROM vw_viagem_serie_anual
         ORDER BY ano DESC
    """)

    anos_disponiveis = [int(l["ano"]) for l in _consultar("""
        SELECT DISTINCT ano FROM vw_viagem_servico WHERE ano IS NOT NULL ORDER BY ano DESC
    """)]

    tot = totais[0] if totais else {}
    return {
        "ano": ano,
        "anos_disponiveis": anos_disponiveis,
        "total_viagens": int(tot.get("total_viagens") or 0),
        "total_diarias": float(tot.get("total_diarias") or 0.0),
        "total_passagens": float(tot.get("total_passagens") or 0.0),
        "total_gasto": float(tot.get("total_gasto") or 0.0),
        "por_orgao": por_orgao,
        "por_destino": por_destino,
        "maiores_viagens": maiores_viagens,
        "serie_anual": serie_anual,
    }


@router.get("/api/executivo/contratos")
def executivo_contratos(ano: int | None = None, orgao: str | None = None, limite: int = 50):
    """Contratos públicos, licitações, dispensas e fornecedores (PNCP / CGU)."""
    if ano is None:
        ultimo = _consultar("SELECT MAX(ano) AS ano FROM vw_contrato_governo")
        ano = int(ultimo[0]["ano"]) if ultimo and ultimo[0].get("ano") is not None else None

    condicoes = []
    parametros: list[Any] = []
    if ano:
        condicoes.append("ano = ?")
        parametros.append(ano)
    if orgao:
        condicoes.append("nome_orgao ILIKE ?")
        parametros.append(f"%{orgao}%")

    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    totais = _consultar(f"""
        SELECT COUNT(*) AS total_contratos,
               SUM(valor_atualizado) AS total_contratado,
               SUM(valor_inicial) AS total_inicial
          FROM vw_contrato_governo {onde}
    """, parametros)

    por_modalidade = _consultar(f"""
        SELECT modalidade_licitacao, COUNT(*) AS contratos,
               SUM(valor_atualizado) AS total_contratado
          FROM vw_contrato_governo {onde}
         GROUP BY modalidade_licitacao ORDER BY total_contratado DESC
    """, parametros)

    por_fornecedor = _consultar(f"""
        SELECT nome_fornecedor, cnpj_fornecedor, COUNT(*) AS contratos,
               SUM(valor_atualizado) AS total_contratado
          FROM vw_contrato_governo {onde}
         GROUP BY nome_fornecedor, cnpj_fornecedor ORDER BY total_contratado DESC LIMIT 20
    """, parametros)

    maiores_contratos = _consultar(f"""
        SELECT id_contrato, numero_contrato, nome_orgao, nome_fornecedor, cnpj_fornecedor,
               modalidade_licitacao, objeto, valor_inicial, valor_atualizado,
               data_inicio_vigencia, data_fim_vigencia
          FROM vw_contrato_governo {onde}
         ORDER BY valor_atualizado DESC LIMIT {int(limite)}
    """, parametros)

    anos_disponiveis = [int(l["ano"]) for l in _consultar("""
        SELECT DISTINCT ano FROM vw_contrato_governo WHERE ano IS NOT NULL ORDER BY ano DESC
    """)]

    tot = totais[0] if totais else {}
    return {
        "ano": ano,
        "anos_disponiveis": anos_disponiveis,
        "total_contratos": int(tot.get("total_contratos") or 0),
        "total_contratado": float(tot.get("total_contratado") or 0.0),
        "total_inicial": float(tot.get("total_inicial") or 0.0),
        "por_modalidade": por_modalidade,
        "por_fornecedor": por_fornecedor,
        "maiores_contratos": maiores_contratos,
    }


