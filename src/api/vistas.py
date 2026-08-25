"""Camada de leitura: uma view por tabela, sobre os Parquet.

A API só enxerga views. Assim o endpoint nunca sabe onde o arquivo está e
trocar o layout físico (particionar por mês, migrar para Delta) não quebra
nenhuma rota.
"""

from __future__ import annotations

import duckdb

from ..nucleo import armazem
from ..nucleo.esquema import TABELAS, selecao_vazia
from ..nucleo.registro import obter as obter_log

log = obter_log("api.vistas")

# Views derivadas, montadas em cima das tabelas físicas.
DERIVADAS = {
    # As contas do DCA são HIERÁRQUICAS: a função ("10") e suas subfunções
    # ("10.301", "10.302") vêm como linhas irmãs no mesmo demonstrativo.
    # Somar todas contava o mesmo gasto duas ou três vezes e inflava a
    # despesa dos estados em ~5× — o Acre aparecia com R$ 66,9 bi contra
    # R$ 12,15 bi da LOA de 2025.
    #
    # O nível é derivado do próprio `cod_conta`, e não de uma coluna nova, de
    # propósito: assim o acervo já coletado é corrigido na leitura, sem
    # depender de recoleta.
    "vw_conta_nivel": """
        SELECT *, LENGTH(cod_conta) - LENGTH(REPLACE(cod_conta, '.', '')) + 1
                  AS nivel_conta
          FROM financas_ente
         WHERE estagio ILIKE '%Empenhada%'
    """,
    "vw_financas_funcao": """
        SELECT cod_ibge, ano, esfera, cod_funcao, funcao,
               SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 1
         GROUP BY ALL
    """,
    # Deixa a subfunção acessível sem contaminar o total.
    "vw_financas_subfuncao": """
        SELECT cod_ibge, ano, esfera, cod_funcao, cod_conta,
               rotulo_conta, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta > 1
         GROUP BY ALL
    """,
    "vw_despesa_total": """
        SELECT cod_ibge, ano, esfera, SUM(valor) AS despesa_total
          FROM vw_financas_funcao
         GROUP BY ALL
    """,
    "vw_populacao": """
        SELECT cod_ibge, ano, valor AS populacao
          FROM indicador_ente
         WHERE cod_metrica = 'populacao'
    """,
    # Anos existentes no armazém, venham de onde vierem.
    "vw_anos": """
        SELECT DISTINCT ano FROM indicador_ente WHERE ano IS NOT NULL
        UNION
        SELECT DISTINCT ano FROM financas_ente WHERE ano IS NOT NULL
    """,
    # A primeira fatia do painel: três fontes, um número, ponta a ponta.
    # O produto ente × ano é deliberado: município sem finanças ainda aparece
    # no mapa, em cinza, em vez de sumir — some é pior que cinza, porque
    # parece que o ente não existe.
    "vw_mapa": """
        SELECT e.cod_ibge, e.nome, e.nivel, e.sigla_uf, e.cod_uf,
               a.ano, d.esfera, d.despesa_total, p.populacao,
               CASE WHEN COALESCE(p.populacao, 0) > 0
                    THEN d.despesa_total / p.populacao END AS despesa_per_capita
          FROM dim_ente e
         CROSS JOIN vw_anos a
          LEFT JOIN vw_despesa_total d
                 ON d.cod_ibge = e.cod_ibge AND d.ano = a.ano
          LEFT JOIN vw_populacao p
                 ON p.cod_ibge = e.cod_ibge AND p.ano = a.ano
    """,
    # Mandato já ligado ao ente pelo de-para. `resolvido` diz se a ponte
    # existe — o painel precisa distinguir "não tem prefeito" de "não
    # consegui casar o nome da cidade".
    "vw_mandato": """
        SELECT m.sk, m.sk_politico, m.cod_cargo, m.cargo, m.cod_ue,
               m.cod_ibge, m.sigla_uf, m.nome, m.sigla_partido,
               m.nome_ente AS nome_ente_tse,
               e.nome      AS nome_ente_ibge,
               e.nivel     AS nivel_ente,
               m.ano_inicio, m.ano_fim, m.data_inicio, m.ano_eleicao,
               m.cod_ibge IS NOT NULL AS resolvido
          FROM mandato m
          LEFT JOIN dim_ente e ON e.cod_ibge = m.cod_ibge
    """,
    # Quem governa cada ente hoje, um por cargo executivo.
    "vw_executivo": """
        SELECT cod_ibge, sigla_uf, cargo, nome, sigla_partido,
               ano_inicio, ano_fim
          FROM vw_mandato
         WHERE cargo IN ('presidente', 'governador', 'prefeito')
           AND cod_ibge IS NOT NULL
    """,
    # Subsídio vigente = a linha de vigência mais recente de cada cargo.
    "vw_subsidio_vigente": """
        SELECT cod_cargo, vigencia_inicio, valor_mensal, norma, url_norma,
               conferido, observacao
          FROM dim_subsidio
         WHERE valor_mensal IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY cod_cargo
                                   ORDER BY vigencia_inicio DESC) = 1
    """,
    # Quantos ocupam cada cargo, com base no que foi coletado.
    "vw_ocupantes": """
        SELECT cargo AS cod_cargo, COUNT(*) AS ocupantes
          FROM dim_politico
         WHERE cargo IS NOT NULL
         GROUP BY cargo
    """,
    # Custo ANUAL ESTIMADO de subsídios: ocupantes × mensal × 13,33
    # (12 meses + 13º + terço de férias). É uma CONTA, não um dado medido —
    # e não inclui gabinete, auxílios, diárias nem encargos. O painel rotula.
    "vw_custo_cargo": """
        SELECT c.cod_cargo, c.cargo, c.poder, c.esfera, c.ramo,
               COALESCE(o.ocupantes, 0)          AS ocupantes,
               s.valor_mensal,
               s.norma, s.url_norma, s.observacao,
               COALESCE(s.conferido, FALSE)      AS conferido,
               CASE WHEN s.valor_mensal IS NOT NULL AND o.ocupantes IS NOT NULL
                    THEN o.ocupantes * s.valor_mensal * 13.33 END
                                                 AS custo_anual_estimado
          FROM dim_cargo_publico c
          LEFT JOIN vw_subsidio_vigente s ON s.cod_cargo = c.cod_cargo
          LEFT JOIN vw_ocupantes o        ON o.cod_cargo = c.cod_cargo
    """,
    # Despesa REAL por função de governo — o que de fato sai dos cofres.
    "vw_despesa_poder": """
        SELECT ano, esfera,
               CASE cod_funcao WHEN '01' THEN 'Legislativa'
                               WHEN '02' THEN 'Judiciária'
                               WHEN '03' THEN 'Essencial à Justiça'
                               WHEN '04' THEN 'Administração'
                               ELSE funcao END   AS funcao,
               SUM(valor)                        AS valor
          FROM vw_financas_funcao
         WHERE cod_funcao IN ('01', '02', '03', '04')
         GROUP BY ALL
    """,
    "vw_voto_detalhe": """
        SELECT v.casa, v.id_votacao, v.id_politico, v.nome_politico,
               v.sigla_partido, v.sigla_uf, v.voto, v.data_hora,
               v.ano, v.mes,
               s.descricao AS descricao_votacao, s.aprovada,
               s.id_proposicao
          FROM voto v
          LEFT JOIN votacao s
            ON s.id_votacao = v.id_votacao AND s.casa = v.casa
    """,
    "vw_placar_votacao": """
        SELECT casa, id_votacao,
               COUNT(*) FILTER (WHERE voto ILIKE 'Sim%')       AS sim,
               COUNT(*) FILTER (WHERE voto ILIKE 'N_o%')       AS nao,
               COUNT(*) FILTER (WHERE voto ILIKE 'Absten%')    AS abstencao,
               COUNT(*) FILTER (WHERE voto NOT ILIKE 'Sim%'
                                  AND voto NOT ILIKE 'N_o%'
                                  AND voto NOT ILIKE 'Absten%') AS outros,
               COUNT(*) AS total
          FROM voto
         GROUP BY ALL
    """,
    "vw_gasto_parlamentar": """
        SELECT id_politico, nome_politico, sigla_partido, sigla_uf, ano, mes,
               SUM(valor_liquido) AS valor_liquido,
               COUNT(*)           AS documentos
          FROM despesa_parlamentar
         GROUP BY ALL
    """,
}


def _completar_colunas(con: duckdb.DuckDBPyConnection, tabela,
                       leitura: str) -> str:
    """Acrescenta como NULL as colunas do contrato que o Parquet ainda não tem.

    Dado coletado ontem não conhece a coluna criada hoje. Sem isto, subir uma
    versão com campo novo derruba a rota inteira com "Binder Error:
    Referenced column ... not found" — foi o que aconteceu com
    `tramitacao_atual` num acervo coletado antes de ela existir.

    O contrato de colunas está declarado em `esquema.py`, e é ele que a API
    consulta. A view é o lugar certo para honrá-lo: quem coletou antes vê o
    campo vazio e recoleta quando quiser, em vez de ficar com o painel fora
    do ar até reprocessar tudo.
    """
    if not tabela.colunas:
        return ""

    try:
        descricao = con.execute(f"DESCRIBE SELECT * FROM {leitura}").fetchall()
    except duckdb.Error:
        return ""

    existentes = {linha[0] for linha in descricao}
    faltando = [(n, t) for n, t in tabela.colunas if n not in existentes]
    if not faltando:
        return ""

    log.info("%s: %d coluna(s) do contrato ausentes no acervo (%s) — "
             "expostas como nulas; recolete a fonte para preenchê-las",
             tabela.nome, len(faltando), ", ".join(n for n, _ in faltando))
    return ", " + ", ".join(f"CAST(NULL AS {tipo}) AS {nome}"
                            for nome, tipo in faltando)


def criar(con: duckdb.DuckDBPyConnection) -> list[str]:
    criadas = []

    for nome, tabela in TABELAS.items():
        if tabela.camada == "_ctl":
            continue
        padrao = armazem.padrao_leitura(tabela)
        # union_by_name combina o esquema de TODOS os arquivos, em vez de
        # tirá-lo do primeiro. É o que permite ler um acervo cujas partições
        # foram gravadas em versões diferentes do projeto — sem ele, uma
        # coluna que mudou de tipo derruba a view inteira.
        hive = (", hive_partitioning=1, union_by_name=1"
                if tabela.camada == "fato" else "")
        leitura = f"read_parquet('{padrao}'{hive})"
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW {nome} AS "
                f"SELECT *{_completar_colunas(con, tabela, leitura)} "
                f"FROM {leitura}"
            )
            con.execute(f"SELECT 1 FROM {nome} LIMIT 1")
            criadas.append(nome)
        except duckdb.Error:
            # Ainda não coletada: view VAZIA e TIPADA, com o contrato de
            # colunas do esquema. O painel abre e mostra "sem dados" em vez
            # de estourar 500 na primeira execução.
            con.execute(
                f"CREATE OR REPLACE VIEW {nome} AS {selecao_vazia(tabela)}")

    for nome, sql in DERIVADAS.items():
        try:
            con.execute(f"CREATE OR REPLACE VIEW {nome} AS {sql}")
            criadas.append(nome)
        except duckdb.Error as erro:
            log.warning("view %s indisponível: %s", nome, str(erro)[:120])

    log.info("%d views prontas", len(criadas))
    return criadas


def conexao_leitura() -> duckdb.DuckDBPyConnection:
    con = armazem.conectar()
    criar(con)
    return con
