"""Rotas de Políticos, Ficha do Parlamentar e Gastos."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..db import _consultar

router = APIRouter(tags=["politicos"])

@router.get("/api/politicos/resumo")
def politicos_resumo(uf: str | None = None):
    filtro = "WHERE sigla_uf = ?" if uf else ""
    linhas = _consultar(f"""
        SELECT cargo, COUNT(*) AS quantidade
          FROM dim_politico {filtro}
         GROUP BY cargo ORDER BY quantidade DESC
    """, [uf.upper()] if uf else [])
    return {"uf": uf, "cargos": linhas,
            "total": sum(int(l["quantidade"]) for l in linhas)}


@router.get("/api/politicos")
def politicos(uf: str | None = None, cargo: str | None = None,
              partido: str | None = None, busca: str | None = None,
              ano: int | None = None,
              limite: int = Query(200, le=2000)):
    condicoes, parametros = [], []
    if uf:
        if cargo == "presidente":
            condicoes.append("(p.sigla_uf = ? OR p.sigla_uf = 'BR')")
            parametros.append(uf.upper())
        else:
            condicoes.append("p.sigla_uf = ?")
            parametros.append(uf.upper())
    if cargo:
        condicoes.append("p.cargo = ?"); parametros.append(cargo)
    if partido:
        condicoes.append("p.sigla_partido = ?"); parametros.append(partido.upper())
    if busca:
        condicoes.append("p.nome ILIKE ?"); parametros.append(f"%{busca}%")
    if ano:
        condicoes.append("""(
            (p.casa = 'camara' AND ? >= 2023 AND ? <= 2027)
            OR (p.casa = 'senado' AND ? >= 2019 AND ? <= 2031)
            OR (m.ano_inicio <= ? AND (m.ano_fim >= ? OR m.ano_fim IS NULL))
            OR EXISTS (SELECT 1 FROM despesa_parlamentar dp WHERE CAST(dp.id_politico AS VARCHAR) = p.id_origem AND dp.ano = ?)
            OR EXISTS (SELECT 1 FROM voto v WHERE CAST(v.id_politico AS VARCHAR) = p.id_origem AND v.ano = ?)
        )""")
        parametros.extend([ano, ano, ano, ano, ano, ano, ano, ano])

    onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    return _consultar(f"""
        SELECT p.sk, p.id_origem, p.nome, p.nome_eleitoral, p.cargo,
               p.sigla_partido, p.sigla_uf, p.casa, p.url_foto,
               p.fonte_origem,
               c.cargo        AS cargo_extenso,
               c.poder, c.esfera,
               s.valor_mensal AS subsidio_cargo,
               s.norma        AS norma_subsidio,
               s.conferido    AS subsidio_conferido,
               COALESCE(m.ano_inicio, CASE WHEN p.casa = 'camara' THEN 2023 WHEN p.casa = 'senado' THEN 2023 ELSE NULL END) AS ano_inicio,
               COALESCE(m.ano_fim, CASE WHEN p.casa = 'camara' THEN 2027 WHEN p.casa = 'senado' THEN 2031 ELSE NULL END) AS ano_fim,
               COALESCE(m.data_inicio, CASE WHEN p.casa = 'camara' THEN '2023-02-01' WHEN p.casa = 'senado' THEN '2023-02-01' ELSE NULL END) AS data_inicio
          FROM dim_politico p
          LEFT JOIN dim_cargo_publico c ON c.cod_cargo = p.cargo
          LEFT JOIN vw_subsidio_vigente s ON s.cod_cargo = c.cod_cargo
          LEFT JOIN (
              SELECT sk_politico, MIN(ano_inicio) AS ano_inicio, MAX(ano_fim) AS ano_fim, MIN(data_inicio) AS data_inicio
                FROM mandato GROUP BY sk_politico
          ) m ON m.sk_politico = p.id_origem
        {onde}
         ORDER BY p.nome LIMIT {int(limite)}
    """, parametros)


@router.get("/api/politicos/{sk}/ficha")
def ficha_do_politico(sk: str, ano: int | None = None):
    """Tudo o que o acervo sabe sobre um parlamentar, numa chamada."""
    politico = _consultar("""
        SELECT p.sk, p.id_origem, p.nome, p.nome_eleitoral, p.cargo,
               p.sigla_partido, p.sigla_uf, p.casa, p.url_foto,
               p.fonte_origem,
               c.cargo AS cargo_extenso, c.poder, c.esfera,
               s.valor_mensal AS subsidio_cargo, s.norma AS norma_subsidio,
               s.url_norma AS url_norma_subsidio,
               s.conferido AS subsidio_conferido,
               COALESCE(m.ano_inicio, CASE WHEN p.casa = 'camara' THEN 2023 WHEN p.casa = 'senado' THEN 2023 ELSE NULL END) AS ano_inicio,
               COALESCE(m.ano_fim, CASE WHEN p.casa = 'camara' THEN 2027 WHEN p.casa = 'senado' THEN 2031 ELSE NULL END) AS ano_fim,
               COALESCE(m.data_inicio, CASE WHEN p.casa = 'camara' THEN '2023-02-01' WHEN p.casa = 'senado' THEN '2023-02-01' ELSE NULL END) AS data_inicio
          FROM dim_politico p
          LEFT JOIN dim_cargo_publico c ON c.cod_cargo = p.cargo
          LEFT JOIN vw_subsidio_vigente s ON s.cod_cargo = c.cod_cargo
          LEFT JOIN (
              SELECT sk_politico, MIN(ano_inicio) AS ano_inicio, MAX(ano_fim) AS ano_fim, MIN(data_inicio) AS data_inicio
                FROM mandato GROUP BY sk_politico
          ) m ON m.sk_politico = p.id_origem
         WHERE p.sk = ?
    """, [sk])
    if not politico:
        raise HTTPException(404, "político não encontrado")
    politico = politico[0]

    id_camara = str(politico.get("id_origem") or "")
    id_sk = str(sk)
    da_camara = politico.get("fonte_origem") == "camara"

    por_ano = _consultar("""
        SELECT ano, valor, notas FROM vw_cota_por_ano
         WHERE id_politico = ? OR id_politico = ?
         ORDER BY ano DESC
    """, [id_camara, id_sk])

    mandatos = _consultar("""
        SELECT cod_cargo, cargo, sigla_uf, nome_ente,
               ano_inicio, ano_fim, data_inicio, sigla_partido
          FROM mandato
         WHERE sk_politico = ? OR sk_politico = ?
         ORDER BY ano_inicio DESC
    """, [id_camara, id_sk])

    id_politico_oficial = str(politico.get("id_origem") or sk)
    patrimonio_historico = _consultar("""
        SELECT ano_eleicao, cargo, total_bens, total_declarado
          FROM vw_patrimonio_politico
         WHERE id_politico = ? OR id_politico = ?
         ORDER BY ano_eleicao ASC
    """, [id_sk, id_politico_oficial])

    bens_declarados = _consultar("""
        SELECT ano_eleicao, cargo, tipo_bem, descricao_bem, valor_bem
          FROM vw_bem_declarado
         WHERE id_politico = ? OR id_politico = ?
         ORDER BY ano_eleicao DESC, valor_bem DESC
    """, [id_sk, id_politico_oficial])

    anos_set = {int(a["ano"]) for a in por_ano}
    for m in mandatos:
        ini = m.get("ano_inicio")
        fim = m.get("ano_fim")
        if ini:
            fim_ano = int(fim) if fim else int(ini) + 3
            for y in range(int(ini), min(fim_ano + 1, 2027)):
                anos_set.add(y)
    for b in bens_declarados:
        if b.get("ano_eleicao"):
            anos_set.add(int(b["ano_eleicao"]))
    if not anos_set:
        anos_set = {2024, 2023}
    anos_ordenados = sorted(list(anos_set), reverse=True)

    if ano is None or int(ano) not in anos_set:
        ano = anos_ordenados[0]
    else:
        ano = int(ano)

    por_mes = _consultar("""
        SELECT mes, SUM(valor_liquido) AS valor, COUNT(*) AS notas
          FROM vw_cota_parlamentar
         WHERE (CAST(id_politico AS VARCHAR) = ? OR CAST(id_politico AS VARCHAR) = ?) AND ano = ?
         GROUP BY mes ORDER BY mes
    """, [id_camara, id_sk, ano])

    por_tipo = _consultar("""
        SELECT tipo_despesa, valor, notas FROM vw_cota_por_tipo
         WHERE (id_politico = ? OR id_politico = ?) AND ano = ?
         ORDER BY valor DESC
    """, [id_camara, id_sk, ano])

    fornecedores = _consultar("""
        SELECT fornecedor, cnpj_cpf_fornecedor, valor, notas
          FROM vw_cota_por_fornecedor
         WHERE (id_politico = ? OR id_politico = ?) AND ano = ?
         ORDER BY valor DESC LIMIT 20
    """, [id_camara, id_sk, ano])

    notas = _consultar("""
        SELECT data_emissao, tipo_despesa, fornecedor, cnpj_cpf_fornecedor,
               valor_liquido, url_documento
          FROM vw_cota_parlamentar
         WHERE (CAST(id_politico AS VARCHAR) = ? OR CAST(id_politico AS VARCHAR) = ?) AND ano = ?
         ORDER BY valor_liquido DESC LIMIT 50
    """, [id_camara, id_sk, ano])

    presenca = _consultar("""
        SELECT ano, presencas, sessoes_possiveis, ausencias, taxa_presenca,
               sessoes_no_ano, primeiro_dia, ultimo_dia, janela_aproximada
          FROM vw_presenca_deputado
         WHERE id_politico = ? OR id_politico = ?
         ORDER BY ano DESC
    """, [id_camara, id_sk])

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
    ] if presenca else None

    presenca_indisponivel = None
    if not presenca:
        if politico.get("fonte_origem") == "tse":
            presenca_indisponivel = (
                "Presença e voto nominal só existem de forma estruturada no "
                "Congresso Nacional. São 27 assembleias e 5.570 câmaras "
                "municipais, cada uma com o seu site: para este cargo o painel "
                "mostra cadastro e finanças, e não afirma o que não pôde "
                "verificar.")
        elif politico.get("casa") == "senado":
            presenca_indisponivel = (
                "O painel coleta as votações do Senado, mas ainda não a "
                "presença em sessão. Enquanto não coletar, não há número aqui "
                "— e número que não existe não vira zero.")
        elif da_camara:
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
         WHERE id_politico = ? OR id_politico = ?
         ORDER BY ano DESC
    """, [id_camara, id_sk])

    divergencias = _consultar("""
        SELECT d.id_votacao, d.voto, d.orientacao, d.sigla_bancada,
               v.data_hora, v.descricao, v.sigla_orgao
          FROM vw_voto_contra_orientacao d
          LEFT JOIN votacao v
                 ON v.casa = d.casa AND v.id_votacao = d.id_votacao
         WHERE (d.id_politico = ? OR d.id_politico = ?) AND d.ano = ? AND d.divergiu
         ORDER BY v.data_hora DESC LIMIT 50
    """, [id_camara, id_sk, ano])

    votos_ano = _consultar("""
        SELECT v.data_hora, v.id_votacao, v.voto, v.descricao_votacao,
               v.aprovada, v.id_proposicao,
               o.orientacao, o.sigla_bancada,
               CASE WHEN o.orientacao IS NOT NULL AND upper(trim(v.voto)) IN ('SIM', 'NÃO', 'NAO')
                    THEN upper(trim(v.voto)) <> upper(trim(o.orientacao)) ELSE FALSE END AS divergiu
          FROM vw_voto_detalhe v
          LEFT JOIN orientacao_bancada o
            ON o.casa = v.casa AND o.id_votacao = v.id_votacao
           AND upper(trim(o.sigla_bancada)) = upper(trim(v.sigla_partido))
         WHERE (CAST(v.id_politico AS VARCHAR) = ? OR CAST(v.id_politico AS VARCHAR) = ?)
           AND (v.ano = ? OR ? IS NULL)
         ORDER BY v.data_hora DESC LIMIT 100
    """, [id_camara, id_sk, ano, ano])

    nome_politico = politico.get("nome_eleitoral") or politico.get("nome") or ""
    proposicoes_ano = _consultar("""
        SELECT casa, id_proposicao, sigla_tipo, numero, ano,
               ementa, data_apresentacao, situacao, url
          FROM proposicao
         WHERE nome_autor ILIKE ?
           AND (ano = ? OR ? IS NULL)
         ORDER BY data_apresentacao DESC LIMIT 50
    """, [f"%{nome_politico}%", ano, ano]) if nome_politico else []

    nome_busca = politico.get("nome") or ""
    nome_eleitoral_busca = politico.get("nome_eleitoral") or ""

    emendas = _consultar("""
        SELECT ano, codigo_emenda, tipo_emenda, funcao,
               valor_empenhado, valor_pago, localidade
          FROM vw_emenda_parlamentar
         WHERE (upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?)))
                OR upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?))))
           AND (ano = ? OR ? IS NULL)
         ORDER BY valor_empenhado DESC LIMIT 100
    """, [f"%{nome_busca}%", f"%{nome_eleitoral_busca}%", ano, ano]) if (nome_busca or nome_eleitoral_busca) else []

    total_empenhado = sum(float(e["valor_empenhado"] or 0) for e in emendas)
    total_pago = sum(float(e["valor_pago"] or 0) for e in emendas)

    emendas_por_funcao = _consultar("""
        SELECT funcao,
               SUM(valor_empenhado) AS empenhado,
               SUM(valor_pago)      AS pago,
               COUNT(*)             AS quantidade
          FROM vw_emenda_parlamentar
         WHERE (upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?)))
                OR upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?))))
           AND (ano = ? OR ? IS NULL)
         GROUP BY funcao ORDER BY empenhado DESC
    """, [f"%{nome_busca}%", f"%{nome_eleitoral_busca}%", ano, ano]) if (nome_busca or nome_eleitoral_busca) else []

    emendas_por_localidade = _consultar("""
        SELECT localidade,
               SUM(valor_empenhado) AS empenhado,
               SUM(valor_pago)      AS pago,
               COUNT(*)             AS quantidade
          FROM vw_emenda_parlamentar
         WHERE (upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?)))
                OR upper(strip_accents(trim(autor))) ILIKE upper(strip_accents(trim(?))))
           AND (ano = ? OR ? IS NULL)
         GROUP BY localidade ORDER BY empenhado DESC LIMIT 25
    """, [f"%{nome_busca}%", f"%{nome_eleitoral_busca}%", ano, ano]) if (nome_busca or nome_eleitoral_busca) else []

    sigla_uf_pol = politico.get("sigla_uf") or ("BR" if politico.get("cargo") == "presidente" else None)
    financas_gestao = _consultar("""
        SELECT f.cod_ibge, f.ano, f.esfera, f.uf,
               SUM(f.valor) FILTER (WHERE f.cod_conta LIKE 'RO1%') AS receita_total,
               SUM(f.valor) FILTER (WHERE f.cod_conta LIKE 'DO3%') AS despesa_total
          FROM financas_ente f
         WHERE (f.uf = ? OR (? = 'BR' AND f.cod_ibge = '0'))
           AND (f.ano = ? OR ? IS NULL)
         GROUP BY f.cod_ibge, f.ano, f.esfera, f.uf
    """, [sigla_uf_pol, sigla_uf_pol, ano, ano]) if sigla_uf_pol else []

    return {
        "politico": politico,
        "ano": ano,
        "anos": anos_ordenados,
        "presenca": presenca,
        "presenca_ressalva": presenca_ressalva,
        "presenca_indisponivel": presenca_indisponivel,
        "fidelidade": fidelidade,
        "divergencias": divergencias,
        "votos": votos_ano,
        "proposicoes": proposicoes_ano,
        "mandatos": mandatos,
        "patrimonio_historico": patrimonio_historico,
        "bens_declarados": bens_declarados,
        "emendas": emendas,
        "emendas_total_empenhado": total_empenhado,
        "emendas_total_pago": total_pago,
        "emendas_por_funcao": emendas_por_funcao,
        "emendas_por_localidade": emendas_por_localidade,
        "financas_gestao": financas_gestao[0] if financas_gestao else None,
        "cota_por_ano": por_ano,
        "cota_por_mes": por_mes,
        "cota_por_tipo": por_tipo,
        "fornecedores": fornecedores,
        "maiores_notas": notas,
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


@router.get("/api/politicos/{sk}/gastos")
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


