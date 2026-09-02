"""Script para extrair e organizar os APIRouters em src/api/rotas/."""
from pathlib import Path

# 1. rotas/executivo.py
Path("src/api/rotas/executivo.py").write_text("""\"\"\"Rotas do Poder Executivo e Custos Públicos.\"\"\"
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from ..db import _consultar

router = APIRouter(tags=["executivo"])

@router.get("/api/custo/cargos")
def custo_por_cargo(poder: str | None = None):
    condicoes, parametros = [], []
    if poder:
        condicoes.append("poder = ?"); parametros.append(poder)
    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f\"\"\"
        SELECT cod_cargo, cargo, poder, esfera, ramo, ocupantes,
               valor_mensal, custo_anual_estimado, conferido,
               norma, url_norma, observacao
          FROM vw_custo_cargo {onde}
         ORDER BY custo_anual_estimado DESC NULLS LAST, cargo
    \"\"\", parametros)

@router.get("/api/custo/resumo")
def resumo_de_custo(ano: int | None = None, poder: str | None = None):
    cargos = _consultar(\"\"\"
        SELECT poder, SUM(custo_anual_estimado) AS custo_estimado,
               SUM(ocupantes) AS ocupantes,
               SUM(ocupantes) FILTER (WHERE valor_mensal IS NOT NULL) AS ocupantes_com_subsidio,
               COUNT(*) FILTER (WHERE valor_mensal IS NOT NULL AND NOT conferido) AS nao_conferidos
          FROM vw_custo_cargo
         WHERE poder IS NOT NULL
         GROUP BY poder ORDER BY custo_estimado DESC NULLS LAST
    \"\"\")

    def _ultimo_ano(vista: str, coluna: str = "ano") -> int | None:
        linhas = _consultar(f"SELECT MAX({coluna}) AS ano FROM {vista}")
        return (int(linhas[0]["ano"]) if linhas and linhas[0].get("ano") is not None else None)

    ano_pedido = ano
    ano_funcao = ano_pedido or _ultimo_ano("vw_despesa_poder")
    ano_medido = ano_pedido or _ultimo_ano("custo_orgao")
    ano_receita = ano_pedido or _ultimo_ano("vw_receita_total")

    funcao = _consultar(\"\"\"
        SELECT poder, SUM(valor) AS despesa_empenhada
          FROM vw_despesa_poder
         WHERE (ano = ? OR ? IS NULL) AND poder IS NOT NULL
         GROUP BY poder ORDER BY despesa_empenhada DESC NULLS LAST
    \"\"\", [ano_funcao, ano_funcao])

    medido = _consultar(\"\"\"
        SELECT SUM(valor) AS custo_medido
          FROM custo_orgao
         WHERE (ano = ? OR ? IS NULL)
    \"\"\", [ano_medido, ano_medido])

    receita = _consultar(\"\"\"
        SELECT SUM(arrecadacao_bruta) AS receita_total
          FROM vw_receita_total
         WHERE (ano = ? OR ? IS NULL)
    \"\"\", [ano_receita, ano_receita])

    return {
        "ano_pedido": ano_pedido,
        "ano_funcao": ano_funcao,
        "ano_medido": ano_medido,
        "ano_receita": ano_receita,
        "cargos": cargos,
        "despesa_por_funcao": funcao,
        "custo_executivo_federal_medido": medido[0]["custo_medido"] if medido else None,
        "receita_total_entes": receita[0]["receita_total"] if receita else None,
    }

@router.get("/api/custo/orgaos")
def custo_por_orgao(ano: int | None = None, mes: int | None = None, conjunto: str | None = None, limite: int = 50):
    condicoes, parametros = [], []
    if ano:
        condicoes.append("ano = ?"); parametros.append(ano)
    if mes:
        condicoes.append("mes = ?"); parametros.append(mes)
    if conjunto:
        condicoes.append("conjunto = ?"); parametros.append(conjunto)
    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f\"\"\"
        SELECT nome_orgao, conjunto, SUM(valor) AS valor
          FROM custo_orgao {onde}
         GROUP BY nome_orgao, conjunto
         ORDER BY valor DESC NULLS LAST LIMIT {int(limite)}
    \"\"\", parametros)

@router.get("/api/executivo")
def executivo_geral(ano: int | None = None):
    ano_efetivo = ano or 2025
    gastos_orgao = _consultar(\"\"\"
        SELECT nome_orgao, SUM(valor) AS total_gasto
          FROM vw_custo_executivo_orgao
         WHERE ano = ?
         GROUP BY nome_orgao
         ORDER BY total_gasto DESC
    \"\"\", [ano_efetivo])

    gastos_conjunto = _consultar(\"\"\"
        SELECT conjunto, SUM(valor) AS total_gasto
          FROM custo_executivo
         WHERE ano = ?
         GROUP BY conjunto
         ORDER BY total_gasto DESC
    \"\"\", [ano_efetivo])

    serie_anual = _consultar(\"\"\"
        SELECT ano, SUM(valor) AS total_gasto
          FROM custo_executivo
         GROUP BY ano
         ORDER BY ano ASC
    \"\"\")

    total = sum(g["total_gasto"] for g in gastos_orgao if g["total_gasto"] is not None)
    return {
        "ano": ano_efetivo,
        "total_gasto": total,
        "por_orgao": gastos_orgao,
        "por_conjunto": gastos_conjunto,
        "serie_anual": serie_anual,
    }

@router.get("/api/executivo/cartoes")
def cartoes_executivo(ano: int | None = None, orgao: str | None = None):
    ano_efetivo = ano or 2025
    condicoes = ["ano = ?"]
    params = [ano_efetivo]

    if orgao:
        condicoes.append("(nome_orgao ILIKE ? OR codigo_orgao = ?)")
        params.extend([f"%{orgao}%", orgao])

    onde = f"WHERE {' AND '.join(condicoes)}"

    totais = _consultar(f\"\"\"
        SELECT COUNT(*) AS total_transacoes,
               SUM(valor) AS total_gasto,
               SUM(CASE WHEN nome_orgao ILIKE '%Presidência%' OR nome_orgao ILIKE '%Gabinete de Segurança%' THEN valor ELSE 0 END) AS total_presidencia
          FROM vw_cartao_corporativo {onde}
    \"\"\", params)

    por_orgao = _consultar(f\"\"\"
        SELECT nome_orgao, SUM(valor) AS total_gasto, COUNT(*) AS transacoes
          FROM vw_cartao_corporativo {onde}
         GROUP BY nome_orgao ORDER BY total_gasto DESC LIMIT 20
    \"\"\", params)

    por_favorecido = _consultar(f\"\"\"
        SELECT nome_favorecido, cnpj_cpf_favorecido, SUM(valor) AS total_gasto, COUNT(*) AS transacoes
          FROM vw_cartao_corporativo {onde}
         GROUP BY nome_favorecido, cnpj_cpf_favorecido ORDER BY total_gasto DESC LIMIT 20
    \"\"\", params)

    maiores = _consultar(f\"\"\"
        SELECT data_transacao, nome_orgao, nome_portador, nome_favorecido, valor
          FROM vw_cartao_corporativo {onde}
         ORDER BY valor DESC LIMIT 50
    \"\"\", params)

    serie = _consultar(\"\"\"
        SELECT ano, SUM(valor) AS total_gasto, COUNT(*) AS transacoes
          FROM vw_cartao_corporativo
         GROUP BY ano ORDER BY ano ASC
    \"\"\")

    t = totais[0] if totais else {}
    return {
        "ano": ano_efetivo,
        "total_transacoes": t.get("total_transacoes") or 0,
        "total_gasto": t.get("total_gasto") or 0.0,
        "total_presidencia": t.get("total_presidencia") or 0.0,
        "por_orgao": por_orgao,
        "por_favorecido": por_favorecido,
        "maiores_gastos": maiores,
        "serie_anual": serie,
    }

@router.get("/api/executivo/viagens")
def viagens_executivo(ano: int | None = None, orgao: str | None = None):
    ano_efetivo = ano or 2025
    condicoes = ["ano = ?"]
    params = [ano_efetivo]

    if orgao:
        condicoes.append("(nome_orgao ILIKE ? OR codigo_orgao = ?)")
        params.extend([f"%{orgao}%", orgao])

    onde = f"WHERE {' AND '.join(condicoes)}"

    totais = _consultar(f\"\"\"
        SELECT COUNT(*) AS total_viagens,
               SUM(valor_diarias) AS total_diarias,
               SUM(valor_passagens) AS total_passagens,
               SUM(valor_total) AS total_gasto
          FROM vw_viagem_servico {onde}
    \"\"\", params)

    por_orgao = _consultar(f\"\"\"
        SELECT nome_orgao, SUM(valor_total) AS total_gasto, COUNT(*) AS viagens
          FROM vw_viagem_servico {onde}
         GROUP BY nome_orgao ORDER BY total_gasto DESC LIMIT 20
    \"\"\", params)

    por_destino = _consultar(f\"\"\"
        SELECT destino, SUM(valor_total) AS total_gasto, COUNT(*) AS viagens
          FROM vw_viagem_servico {onde}
         GROUP BY destino ORDER BY total_gasto DESC LIMIT 20
    \"\"\", params)

    maiores = _consultar(f\"\"\"
        SELECT nome_orgao, nome_viajante, cargo_viajante, destino, motivo, data_inicio, valor_total
          FROM vw_viagem_servico {onde}
         ORDER BY valor_total DESC LIMIT 50
    \"\"\", params)

    serie = _consultar(\"\"\"
        SELECT ano, SUM(valor_total) AS total_gasto, COUNT(*) AS total_viagens
          FROM vw_viagem_servico
         GROUP BY ano ORDER BY ano ASC
    \"\"\")

    t = totais[0] if totais else {}
    return {
        "ano": ano_efetivo,
        "total_viagens": t.get("total_viagens") or 0,
        "total_diarias": t.get("total_diarias") or 0.0,
        "total_passagens": t.get("total_passagens") or 0.0,
        "total_gasto": t.get("total_gasto") or 0.0,
        "por_orgao": por_orgao,
        "por_destino": por_destino,
        "maiores_viagens": maiores,
        "serie_anual": serie,
    }

@router.get("/api/executivo/contratos")
def contratos_executivo(ano: int | None = None, orgao: str | None = None):
    ano_efetivo = ano or 2025
    condicoes = ["ano = ?"]
    params = [ano_efetivo]

    if orgao:
        condicoes.append("(nome_orgao ILIKE ? OR codigo_orgao = ?)")
        params.extend([f"%{orgao}%", orgao])

    onde = f"WHERE {' AND '.join(condicoes)}"

    totais = _consultar(f\"\"\"
        SELECT COUNT(*) AS total_contratos,
               SUM(valor_atualizado) AS total_contratado
          FROM vw_contrato_governo {onde}
    \"\"\", params)

    por_fornecedor = _consultar(f\"\"\"
        SELECT nome_fornecedor, cnpj_fornecedor, SUM(valor_atualizado) AS total_contratado, COUNT(*) AS contratos
          FROM vw_contrato_governo {onde}
         GROUP BY nome_fornecedor, cnpj_fornecedor ORDER BY total_contratado DESC LIMIT 20
    \"\"\", params)

    por_modalidade = _consultar(f\"\"\"
        SELECT modalidade_licitacao, SUM(valor_atualizado) AS total_contratado, COUNT(*) AS contratos
          FROM vw_contrato_governo {onde}
         GROUP BY modalidade_licitacao ORDER BY total_contratado DESC
    \"\"\", params)

    maiores = _consultar(f\"\"\"
        SELECT numero_contrato, nome_orgao, nome_fornecedor, objeto, valor_atualizado, data_inicio_vigencia
          FROM vw_contrato_governo {onde}
         ORDER BY valor_atualizado DESC LIMIT 50
    \"\"\", params)

    t = totais[0] if totais else {}
    return {
        "ano": ano_efetivo,
        "total_contratos": t.get("total_contratos") or 0,
        "total_contratado": t.get("total_contratado") or 0.0,
        "por_fornecedor": por_fornecedor,
        "por_modalidade": por_modalidade,
        "maiores_contratos": maiores,
    }
""", encoding="utf-8")
print("rotas/executivo.py criado!")
