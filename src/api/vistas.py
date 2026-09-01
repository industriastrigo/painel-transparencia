"""Camada de leitura: uma view por tabela, sobre os Parquet.

A API só enxerga views. Assim o endpoint nunca sabe onde o arquivo está e
trocar o layout físico (particionar por mês, migrar para Delta) não quebra
nenhuma rota.
"""

from __future__ import annotations

import duckdb

from ..nucleo import armazem
from ..nucleo.esquema import TABELAS, selecao_vazia
from ..nucleo.normalizadores import (
    normalizar_nome_proprio,
    gerar_slug_codigo,
    gerar_cod_politico_interno,
    gerar_cod_magistrado_interno,
    gerar_cod_cargo_interno,
    gerar_cod_ministro_estado_interno,
)
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
    # O `cod_conta` do SICONFI vem com PREFIXO de letras: a receita chega como
    # `RO1.0.0.0.00.0.0`, não `1.0.0.0.00.0.0`. Só se descobriu isso vendo o
    # log de uma coleta real. Todo cálculo de nível parte do código NUMÉRICO,
    # extraído do fim da string — nunca da string inteira.
    "vw_conta_codigo": """
        SELECT *,
               regexp_extract(cod_conta, '([0-9][0-9.]*)$', 1) AS codigo_conta
          FROM financas_ente
    """,
    # O NÍVEL NÃO SAI DA CONTAGEM DE PONTOS. As contas do DCA têm número fixo
    # de segmentos e a hierarquia está nos ZEROS:
    #
    #     DO3.0.00.00.00.00  Despesas Correntes          nível 1
    #     DO3.1.00.00.00.00  Pessoal e Encargos          nível 2
    #     DO3.1.90.00.00.00  Aplicações Diretas          nível 3
    #     DO3.1.90.11.00.00  Vencimentos e Vantagens     nível 4
    #
    # As quatro têm CINCO pontos. Contar pontos dava nível 6 para todas, e
    # nenhuma passava no filtro de primeiro nível — a despesa da Bahia vinha
    # inteira de uma linha textual `TotalDespesas` que sobrava por acaso.
    #
    # Contando segmentos diferentes de zero, a soma do nível 1 bate com o
    # total declarado pelo próprio ente, com diferença zero nos 27 estados.
    "vw_conta_nivel": """
        SELECT *,
               CASE WHEN codigo_conta = '' THEN NULL
                    ELSE LEN(list_filter(str_split(codigo_conta, '.'),
                             x -> COALESCE(TRY_CAST(x AS INTEGER), 0) <> 0))
                    END AS nivel_conta,
               COUNT(*) FILTER (WHERE codigo_conta <> '')
                        OVER (PARTITION BY cod_ibge, ano) AS contas_numericas
          FROM vw_conta_codigo
         WHERE estagio ILIKE '%Empenhada%'
    """,
    # ATENÇÃO AO NOME: o Anexo I-D traz despesa por NATUREZA (pessoal, juros,
    # investimentos), não por FUNÇÃO de governo (saúde, educação). O campo
    # `cod_funcao` gravado pelo coletor antigo saía de `cod_conta.split('.')`
    # e virava "DO3" — não é função de coisa nenhuma.
    #
    # Nível 1 são as duas categorias econômicas: Correntes e Capital.
    "vw_despesa_categoria": """
        SELECT cod_ibge, ano, esfera, codigo_conta AS cod_natureza,
               rotulo_conta AS natureza, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 1 AND codigo_conta <> ''
         GROUP BY ALL
    """,
    # Nível 2 é o grupo, e é onde a leitura fica interessante: Pessoal e
    # Encargos, Juros e Encargos da Dívida, Outras Despesas Correntes,
    # Investimentos, Inversões Financeiras, Amortização da Dívida.
    "vw_despesa_natureza": """
        SELECT cod_ibge, ano, esfera, codigo_conta AS cod_natureza,
               rotulo_conta AS natureza, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 2 AND codigo_conta <> ''
         GROUP BY ALL
    """,
    "vw_financas_subfuncao": """
        SELECT cod_ibge, ano, esfera, cod_funcao, cod_conta,
               rotulo_conta, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta > 1
         GROUP BY ALL
    """,
    # A despesa total é a soma do nível 1. O ente também declara um total
    # explícito numa linha textual, e ele fica de fora da soma — mas serve de
    # CONFERÊNCIA, que é para o que `vw_conferencia_despesa` existe.
    # Duas medidas do mesmo número por caminhos diferentes: a soma das
    # categorias e o total que o próprio ente declara numa linha à parte. Se
    # divergirem, alguma regra de agregação quebrou — é a checagem que teria
    # pego a despesa inflada em 5× no dia em que ela apareceu.
    "vw_conferencia_despesa": """
        SELECT cod_ibge, ano, esfera,
               SUM(valor) FILTER (WHERE nivel_conta = 1
                                    AND codigo_conta <> '') AS somado,
               MAX(valor) FILTER (WHERE codigo_conta = '')   AS declarado
          FROM vw_conta_nivel
         GROUP BY ALL
    """,
    # A soma das categorias é a medida preferida. O total declarado entra só
    # quando não há conta numérica nenhuma — ente que entregou apenas o total
    # tem despesa conhecida, e deixá-lo cinza no mapa seria dizer "não sei"
    # sobre um número que está publicado.
    "vw_despesa_total": """
        SELECT cod_ibge, ano, esfera,
               COALESCE(somado, declarado) AS despesa_total
          FROM vw_conferencia_despesa
         WHERE COALESCE(somado, declarado) IS NOT NULL
    """,
    # Mantida para o dia em que o anexo de FUNÇÃO for coletado: só aceita
    # conta cujo código de função seja de fato uma função de governo, e não a
    # natureza da despesa que o I-D traz.
    "vw_financas_funcao": """
        SELECT cod_ibge, ano, esfera, cod_funcao, funcao,
               SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 1 AND codigo_conta <> ''
           AND cod_funcao IS NOT NULL
           AND regexp_matches(cod_funcao, '^[0-9]{2}$')
         GROUP BY ALL
    """,
    # ------------------------------------------- despesa por FUNÇÃO (RREO)
    # Recorte que o DCA não tem. Vem de tabela própria porque é OUTRO corte
    # do mesmo dinheiro: somar função com natureza daria o dobro do real.
    #
    # AQUI A HIERARQUIA NÃO ESTÁ NO CÓDIGO. Ao contrário do DCA e da receita,
    # o `cod_conta` do RREO Anexo 02 é a mesma string em todas as linhas
    # (`RREO2TotalDespesas`): função, subfunção e totais. Contar segmentos não
    # zerados — a regra que vale nos outros dois — aqui não separa nada.
    #
    # Quem separa é o nome: o coletor casa o texto da conta contra as 28
    # funções da Portaria MOG 42/1999 e grava `cod_funcao` quando casa. Então
    # **`cod_funcao IS NOT NULL` é o nível 1**, e não há como uma linha de
    # total entrar na soma: "TOTAL (III) = (I + II)" não é nome de função.
    "vw_funcao_conta": """
        SELECT * FROM despesa_funcao
         WHERE estagio ILIKE '%EMPENHADAS%'
    """,
    # O bimestre mais recente de cada ente e ano: o RREO é acumulado no
    # exercício, então somar os seis bimestres contaria janeiro seis vezes.
    "vw_funcao_ultimo_periodo": """
        SELECT cod_ibge, ano, MAX(periodo) AS periodo
          FROM despesa_funcao
         GROUP BY ALL
    """,
    # Soma os blocos do demonstrativo (exceto intra + intra), que são dois
    # universos somáveis, e nunca duas linhas do mesmo bloco.
    "vw_despesa_por_funcao": """
        SELECT n.cod_ibge, n.ano, n.esfera, n.cod_funcao, n.funcao,
               n.periodo, SUM(n.valor) AS valor
          FROM vw_funcao_conta n
          JOIN vw_funcao_ultimo_periodo u
            ON u.cod_ibge = n.cod_ibge AND u.ano = n.ano
           AND u.periodo = n.periodo
         WHERE n.cod_funcao IS NOT NULL
         GROUP BY ALL
    """,
    # O que NÃO casou com função oficial: subfunção ou linha de total. Fica
    # acessível para quem quiser olhar, e fora de toda soma.
    "vw_despesa_por_subfuncao": """
        SELECT n.cod_ibge, n.ano, n.esfera, n.rotulo_conta, n.bloco,
               n.periodo, SUM(n.valor) AS valor
          FROM vw_funcao_conta n
          JOIN vw_funcao_ultimo_periodo u
            ON u.cod_ibge = n.cod_ibge AND u.ano = n.ano
           AND u.periodo = n.periodo
         WHERE n.cod_funcao IS NULL
         GROUP BY ALL
    """,
    # Conferência: a soma das funções contra o total que o próprio
    # demonstrativo declara. É a mesma checagem que pegou a despesa inflada em
    # 5× no DCA — aqui ela vale ainda mais, porque a regra de nível é por
    # NOME, e nome é mais frágil que código.
    "vw_conferencia_funcao": """
        SELECT n.cod_ibge, n.ano,
               SUM(n.valor) FILTER (WHERE n.cod_funcao IS NOT NULL) AS somado,
               SUM(n.valor) FILTER (
                   WHERE n.cod_funcao IS NULL
                     AND n.rotulo_conta ILIKE 'TOTAL%')             AS declarado
          FROM vw_funcao_conta n
          JOIN vw_funcao_ultimo_periodo u
            ON u.cod_ibge = n.cod_ibge AND u.ano = n.ano
           AND u.periodo = n.periodo
         GROUP BY ALL
    """,
    # As duas perguntas que o painel prometia e não respondia.
    "vw_saude_educacao": """
        SELECT cod_ibge, ano, esfera,
               SUM(valor) FILTER (WHERE cod_funcao = '10') AS saude,
               SUM(valor) FILTER (WHERE cod_funcao = '12') AS educacao,
               SUM(valor)                                  AS total_funcoes
          FROM vw_despesa_por_funcao
         GROUP BY ALL
    """,
    # ------------------------------------------------ cota parlamentar
    # A MESMA nota chegou DUAS vezes ao acervo, e o merge não viu.
    #
    # A chave é `(casa, id_documento, num_parcela, num_ressarcimento)`. Uma
    # versão antiga do coletor deixava parcela e ressarcimento NULOS quando a
    # fonte mandava vazio; a versão atual grava `"0"`. Nulo e "0" são chaves
    # diferentes, então cada nota coletada nas duas épocas virou duas linhas
    # — 96.407 documentos, e a despesa de 2026 saltou de R$ 121,5 mi para
    # R$ 242,2 mi. O dobro exato.
    #
    # A desduplicação fica AQUI, na leitura, e não só no coletor consertado,
    # porque o acervo já existente continuaria dobrado. Normalizar o vazio
    # para "0" e ficar com uma linha por documento devolve o número que a
    # própria Câmara publica: conferido contra a página oficial de um
    # deputado, R$ 67.682,76 contra R$ 67.682,70 — a diferença é
    # arredondamento de exibição.
    "vw_cota_parlamentar": """
        SELECT * REPLACE (
                 COALESCE(NULLIF(CAST(num_parcela AS VARCHAR), ''), '0')
                   AS num_parcela,
                 COALESCE(NULLIF(CAST(num_ressarcimento AS VARCHAR), ''), '0')
                   AS num_ressarcimento)
          FROM despesa_parlamentar
         QUALIFY ROW_NUMBER() OVER (
                   PARTITION BY casa, CAST(id_documento AS VARCHAR),
                     COALESCE(NULLIF(CAST(num_parcela AS VARCHAR), ''), '0'),
                     COALESCE(NULLIF(CAST(num_ressarcimento AS VARCHAR), ''), '0')
                   ORDER BY _atualizado_em DESC) = 1
    """,
    # Quanto cada parlamentar gastou, por ano.
    "vw_cota_por_ano": """
        SELECT casa, CAST(id_politico AS VARCHAR) AS id_politico,
               nome_politico, sigla_partido, sigla_uf, ano,
               SUM(valor_liquido) AS valor, COUNT(*) AS notas
          FROM vw_cota_parlamentar
         GROUP BY ALL
    """,
    # E EM QUÊ. É a pergunta que a linha "cota parlamentar" não responde:
    # divulgação da atividade parlamentar sozinha é o maior item do país.
    "vw_cota_por_tipo": """
        SELECT casa, CAST(id_politico AS VARCHAR) AS id_politico, ano,
               tipo_despesa, SUM(valor_liquido) AS valor, COUNT(*) AS notas
          FROM vw_cota_parlamentar
         GROUP BY ALL
    """,
    "vw_cota_por_fornecedor": """
        SELECT casa, CAST(id_politico AS VARCHAR) AS id_politico, ano,
               fornecedor, cnpj_cpf_fornecedor,
               SUM(valor_liquido) AS valor, COUNT(*) AS notas
          FROM vw_cota_parlamentar
         GROUP BY ALL
    """,
    # Conferência: o acervo cru contra o desduplicado. Se um dia divergirem
    # de novo, é porque a chave voltou a descrever um grão mais fino que o
    # dado — e a tela mostra isso em vez de somar o dobro em silêncio.
    # ------------------------------------------------------- presença
    # Só sessões DELIBERATIVAS DO PLENÁRIO entram no denominador. Audiência
    # pública e seminário são trabalho, não obrigação de comparecimento;
    # contá-los faria de quem prioriza o Plenário um faltoso.
    #
    # E o `deliberativo` sozinho NÃO basta, o que só apareceu quando medi o
    # acervo: em 2026 ele marca 566 eventos, dos quais 499 são "Reunião
    # Deliberativa" DE COMISSÃO e apenas 67 são sessão do Plenário. Um
    # deputado participa de duas ou três comissões, não de todas — contar as
    # 499 como obrigação dele fabricava, em média, **483 faltas por
    # deputado**, contra 12 na conta correta. Eram 573 pessoas nomeadas a um
    # clique de receber uma acusação inventada pelo denominador.
    #
    # A Câmara publica a presença em reunião de comissão, mas não a lista de
    # membros de cada comissão: sem saber a quem aquela reunião era
    # obrigação, não há como transformá-la em falta de ninguém. Fica de fora,
    # e a ressalva na tela diz por quê.
    "vw_sessao_deliberativa": """
        SELECT casa, id_evento, ano,
               CAST(SUBSTR(data_hora_inicio, 1, 10) AS DATE) AS dia
          FROM evento
         WHERE deliberativo
           AND descricao_tipo ILIKE 'sess_o deliberativa%'
           AND lower(situacao) LIKE 'encerrada%'
    """,
    # A fonte publica QUEM ESTEVE e nunca quem faltou. A falta é uma
    # subtração nossa, e só é honesta dentro da janela em que o deputado
    # estava em exercício: quem tomou posse em março não faltou às sessões
    # de fevereiro, e quem morreu em agosto não faltou às de outubro.
    # Como não temos a data de posse por deputado, a janela é aproximada
    # pela primeira e última atividade dele no ano — e o fato de ser
    # aproximação sai junto com o número, no campo `janela_aproximada`.
    "vw_janela_exercicio": """
        WITH atividade AS (
            SELECT casa, id_politico, ano,
                   CAST(SUBSTR(data_hora_inicio, 1, 10) AS DATE) AS dia
              FROM presenca_evento
             UNION ALL
            SELECT casa, id_politico, ano,
                   CAST(SUBSTR(data_hora, 1, 10) AS DATE) AS dia
              FROM voto
        )
        SELECT casa, CAST(id_politico AS VARCHAR) AS id_politico, ano,
               MIN(dia) AS primeiro_dia, MAX(dia) AS ultimo_dia
          FROM atividade
         WHERE dia IS NOT NULL
         GROUP BY ALL
    """,
    "vw_presenca_deputado": """
        WITH janela AS (SELECT * FROM vw_janela_exercicio),
        possiveis AS (
            SELECT j.casa, j.id_politico, j.ano,
                   COUNT(s.id_evento) AS sessoes_possiveis
              FROM janela j
              LEFT JOIN vw_sessao_deliberativa s
                     ON s.casa = j.casa AND s.ano = j.ano
                    AND s.dia BETWEEN j.primeiro_dia AND j.ultimo_dia
             GROUP BY ALL
        ),
        comparecimentos AS (
            SELECT p.casa, CAST(p.id_politico AS VARCHAR) AS id_politico,
                   p.ano, COUNT(DISTINCT p.id_evento) AS presencas
              FROM presenca_evento p
              JOIN vw_sessao_deliberativa s
                ON s.casa = p.casa AND s.id_evento = p.id_evento
             GROUP BY ALL
        ),
        total_ano AS (
            SELECT casa, ano, COUNT(*) AS sessoes_no_ano
              FROM vw_sessao_deliberativa GROUP BY ALL
        )
        SELECT po.casa, po.id_politico, po.ano,
               COALESCE(c.presencas, 0) AS presencas,
               po.sessoes_possiveis,
               GREATEST(po.sessoes_possiveis - COALESCE(c.presencas, 0), 0)
                   AS ausencias,
               CASE WHEN po.sessoes_possiveis > 0
                    THEN COALESCE(c.presencas, 0) * 1.0 / po.sessoes_possiveis
               END AS taxa_presenca,
               t.sessoes_no_ano,
               j.primeiro_dia, j.ultimo_dia,
               -- Verdadeiro quando o deputado não esteve ativo o ano todo:
               -- a taxa cobre só parte do ano e não se compara com a dos
               -- demais sem essa ressalva.
               po.sessoes_possiveis < t.sessoes_no_ano AS janela_aproximada
          FROM possiveis po
          JOIN janela j USING (casa, id_politico, ano)
          JOIN total_ano t ON t.casa = po.casa AND t.ano = po.ano
          LEFT JOIN comparecimentos c USING (casa, id_politico, ano)
    """,
    # ------------------------------------------- fidelidade partidária
    # Cruza o voto do deputado com o que a liderança recomendou. É o dado
    # que quase nenhum painel mostra, e o único aqui que descreve
    # comportamento em vez de dinheiro.
    "vw_voto_contra_orientacao": """
        SELECT v.casa, v.id_votacao,
               CAST(v.id_politico AS VARCHAR) AS id_politico,
               v.nome_politico, v.sigla_partido, v.ano,
               v.voto, o.orientacao, o.sigla_bancada,
               CASE
                 WHEN o.orientacao IS NULL THEN NULL
                 WHEN lower(o.orientacao) IN ('liberado', 'liberada') THEN NULL
                 WHEN upper(trim(v.voto)) NOT IN ('SIM', 'NÃO', 'NAO')
                      THEN NULL
                 ELSE upper(trim(v.voto)) <> upper(trim(o.orientacao))
               END AS divergiu
          FROM voto v
          JOIN orientacao_bancada o
            ON o.casa = v.casa AND o.id_votacao = v.id_votacao
           AND upper(trim(o.sigla_bancada)) = upper(trim(v.sigla_partido))
    """,
    "vw_fidelidade_partidaria": """
        SELECT casa, id_politico, nome_politico, sigla_partido, ano,
               COUNT(*) FILTER (WHERE divergiu IS NOT NULL) AS votos_com_orientacao,
               COUNT(*) FILTER (WHERE divergiu) AS votos_divergentes,
               CASE WHEN COUNT(*) FILTER (WHERE divergiu IS NOT NULL) > 0
                    THEN COUNT(*) FILTER (WHERE divergiu) * 1.0
                         / COUNT(*) FILTER (WHERE divergiu IS NOT NULL)
               END AS taxa_divergencia
          FROM vw_voto_contra_orientacao
         GROUP BY ALL
    """,
    "vw_conferencia_cota": """
        SELECT ano,
               (SELECT COUNT(*) FROM despesa_parlamentar b
                 WHERE b.ano = a.ano)              AS linhas_no_acervo,
               COUNT(*)                            AS linhas_distintas
          FROM vw_cota_parlamentar a
         GROUP BY ano
    """,
    # ------------------------------------------------- indicadores da LRF
    # O RGF publica os dois lados e o percentual: a resposta é do próprio
    # ente, não conta nossa. `acima_do_limite` compara com o limite que a
    # fonte também informa — nada é chutado aqui.
    "vw_fiscal_ente": """
        SELECT cod_ibge, ano, periodo, poder, esfera,
               -- Cada conceito é um par (conta, MEDIDA). No RGF a mesma conta
               -- aparece em R$ e em % sobre a RCL, e é a coluna que decide o
               -- significado — ver armadilha 2ai.
               MAX(valor) FILTER (
                   WHERE indicador = 'DespesaComPessoalBruta'
                     AND medida = 'valor')            AS despesa_pessoal_bruta,
               MAX(valor) FILTER (
                   WHERE indicador IN ('DespesaComPessoalLiquida',
                                       'DespesaLiquidaComPessoal')
                     AND medida = 'valor')          AS despesa_pessoal_liquida,
               MAX(valor) FILTER (
                   WHERE indicador = 'DespesaComPessoalTotal'
                     AND medida = 'valor')            AS despesa_pessoal_total,
               MAX(valor) FILTER (
                   WHERE indicador IN ('ReceitaCorrenteLiquidaAjustada',
                                       'ReceitaCorrenteLiquidaLimiteLegal',
                                       'RGF2ReceitaCorrenteLiquida')
                     AND medida = 'valor')        AS receita_corrente_liquida,
               -- O percentual da folha é a DespesaComPessoalTotal lida na
               -- coluna de percentual — não é uma conta própria.
               MAX(valor) FILTER (
                   WHERE indicador = 'DespesaComPessoalTotal'
                     AND medida = 'percentual')          AS percentual_pessoal,
               MAX(valor) FILTER (
                   WHERE indicador IN ('LimiteMaximoDespesaComPessoalTotal',
                                       'LimiteMaximo')
                     AND medida = 'percentual')               AS limite_maximo,
               MAX(valor) FILTER (
                   WHERE indicador IN ('LimitePrudencialDespesaComPessoalTotal',
                                       'LimitePrudencial')
                     AND medida = 'percentual')           AS limite_prudencial,
               MAX(valor) FILTER (
                   WHERE indicador = 'LimiteDeAlertaDespesaComPessoalTotal'
                     AND medida = 'percentual')               AS limite_alerta,
               -- Anexo 02. `medida = 'saldo'` é o saldo DO quadrimestre
               -- pedido: o coletor descarta as colunas dos outros períodos,
               -- que antes podiam gravar o saldo do ano passado como se
               -- fosse o de agora.
               MAX(valor) FILTER (
                   WHERE indicador = 'DividaConsolidadaLiquida'
                     AND medida = 'saldo')                    AS divida_liquida,
               MAX(valor) FILTER (
                   WHERE indicador = 'DividaConsolidada'
                     AND medida = 'saldo')               AS divida_consolidada,
               MAX(valor) FILTER (
                   WHERE indicador = 'LimiteDefinidoPorResolucaoDoSenadoFederal'
                     AND medida = 'saldo')                    AS limite_divida,
               MAX(valor) FILTER (
                   WHERE indicador = 'PercentualDaDCLSobreARCL'
                     AND medida = 'saldo')                 AS percentual_divida
          FROM indicador_fiscal
         GROUP BY ALL
    """,
    "vw_lrf_pessoal": """
        SELECT f.*,
               CASE WHEN f.percentual_pessoal IS NOT NULL
                     AND f.limite_maximo IS NOT NULL
                    THEN f.percentual_pessoal > f.limite_maximo END
                    AS acima_do_limite,
               CASE WHEN f.percentual_pessoal IS NOT NULL
                     AND f.limite_prudencial IS NOT NULL
                    THEN f.percentual_pessoal > f.limite_prudencial END
                    AS acima_do_prudencial,
               CASE WHEN f.divida_liquida IS NOT NULL
                     AND f.limite_divida IS NOT NULL
                    THEN f.divida_liquida > f.limite_divida END
                    AS divida_acima_do_limite
          FROM vw_fiscal_ente f
         QUALIFY ROW_NUMBER() OVER (PARTITION BY f.cod_ibge, f.ano, f.poder
                                    ORDER BY f.periodo DESC) = 1
    """,
    # ---------------------------------------------------------- receita
    # As contas de receita são hierárquicas como as de despesa, e o mesmo
    # erro é possível: `1.0.0.0.00.0.0` (Receitas Correntes) é o pai de
    # `1.1.0.0.00.0.0`, e somar os dois conta o mesmo real duas vezes.
    #
    # O nível sai do próprio código. Os segmentos zerados são sempre os
    # finais, então contar quantos segmentos são diferentes de zero dá a
    # profundidade da conta: `1.0.0.0.00.0.0` → 1, `1.7.0.0.00.0.0` → 2.
    "vw_receita_conta": """
        SELECT *,
               LEN(list_filter(str_split(codigo_conta, '.'),
                               x -> COALESCE(TRY_CAST(x AS INTEGER), 0) <> 0))
                   AS nivel_receita
          FROM vw_conta_codigo
         WHERE estagio ILIKE '%Receitas%Realizadas%'
           AND codigo_conta <> ''
    """,
    # Arrecadação = receitas correntes (1) + receitas de capital (2), no
    # primeiro nível. As deduções (grupo 9, FUNDEB e restituições) ficam de
    # fora: a coluna da fonte é BRUTA, e misturar dedução aqui produziria um
    # número que não é nem bruto nem líquido.
    "vw_receita_total": """
        SELECT cod_ibge, ano, esfera, SUM(valor) AS receita_total
          FROM vw_receita_conta
         WHERE nivel_receita = 1
           AND (codigo_conta LIKE '1%' OR codigo_conta LIKE '2%')
         GROUP BY ALL
    """,
    # Transferências RECEBIDAS de outros entes: correntes (1.7) e de capital
    # (2.4). Segundo nível, porque é onde a conta "Transferências" vive.
    "vw_transferencia_recebida": """
        SELECT cod_ibge, ano, esfera,
               SUM(valor) AS transferencia_recebida
          FROM vw_receita_conta
         WHERE nivel_receita = 2
           AND (codigo_conta LIKE '1.7%' OR codigo_conta LIKE '2.4%')
         GROUP BY ALL
    """,
    # ------------------------------------- transferências pagas pela União
    # Outra MEDIDA, não outro recorte da mesma: aqui quem declara é quem
    # pagou (Tesouro/SIAFI, regime de caixa) e só cobre as obrigatórias da
    # União. `vw_transferencia_recebida`, acima, é o que o ente declarou ter
    # recebido de qualquer origem. As duas não batem e não deveriam — o que o
    # estado repassa aos municípios dele (ICMS, IPVA) entra lá e nunca aqui.
    "vw_transferencia_uniao": """
        SELECT cod_ibge, nivel, uf, ano,
               SUM(valor) AS transferencia_uniao
          FROM transferencia_uniao
         GROUP BY ALL
    """,
    "vw_transferencia_modalidade": """
        SELECT cod_ibge, ano, cod_transferencia, transferencia,
               SUM(valor) AS valor
          FROM transferencia_uniao
         GROUP BY ALL
    """,
    "vw_transferencia_historico_ente": """
        SELECT cod_ibge, ano,
               SUM(valor) AS total_transferencias,
               SUM(valor) FILTER (WHERE transferencia = 'FPM' OR transferencia LIKE 'FPM%') AS fpm,
               SUM(valor) FILTER (WHERE transferencia = 'FPE') AS fpe,
               SUM(valor) FILTER (WHERE transferencia LIKE 'FUNDEB%') AS fundeb,
               SUM(valor) FILTER (WHERE transferencia LIKE 'Royalties%') AS royalties
          FROM transferencia_uniao
         GROUP BY ALL
    """,
    # ----------------------------------------------- emendas parlamentares
    "vw_emenda_parlamentar": """
        SELECT ano, codigo_emenda, tipo_emenda,
               autor AS autor_extraido,
               normalizar_nome(autor) AS autor_formatado,
               normalizar_nome(autor) AS autor,
               funcao,
               COALESCE(
                   TRY_CAST(valor_empenhado AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_empenhado AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               ) AS valor_empenhado,
               COALESCE(
                   TRY_CAST(valor_pago AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_pago AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               ) AS valor_pago,
               localidade
          FROM emenda_parlamentar
    """,
    "vw_emenda_por_autor": """
        SELECT autor, ano, tipo_emenda, funcao,
               COUNT(*) AS emendas,
               SUM(COALESCE(
                   TRY_CAST(valor_empenhado AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_empenhado AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS valor_empenhado,
               SUM(COALESCE(
                   TRY_CAST(valor_pago AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_pago AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS valor_pago
          FROM vw_emenda_parlamentar
         GROUP BY ALL
    """,
    "vw_emenda_por_municipio": """
        SELECT localidade, ano, autor, tipo_emenda, funcao,
               COUNT(*) AS emendas,
               SUM(COALESCE(
                   TRY_CAST(valor_empenhado AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_empenhado AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS valor_empenhado,
               SUM(COALESCE(
                   TRY_CAST(valor_pago AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor_pago AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS valor_pago
          FROM vw_emenda_parlamentar
         GROUP BY ALL
    """,
    # ------------------------------------------------- cartões corporativos
    "vw_cartao_corporativo": """
        SELECT ano, mes, codigo_orgao, nome_orgao,
               nome_portador AS nome_portador_extraido,
               normalizar_nome(nome_portador) AS nome_portador_formatado,
               normalizar_nome(nome_portador) AS nome_portador,
               cpf_portador,
               nome_favorecido AS nome_favorecido_extraido,
               normalizar_nome(nome_favorecido) AS nome_favorecido_formatado,
               normalizar_nome(nome_favorecido) AS nome_favorecido,
               cnpj_cpf_favorecido,
               tipo_cartao, data_transacao,
               COALESCE(
                   TRY_CAST(valor AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               ) AS valor,
               data_referencia
          FROM cartao_corporativo
    """,
    "vw_cartao_por_orgao": """
        SELECT ano, codigo_orgao, nome_orgao,
               COUNT(*) AS transacoes,
               SUM(COALESCE(
                   TRY_CAST(valor AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS total_gasto
          FROM cartao_corporativo
         GROUP BY ALL
    """,
    "vw_cartao_por_favorecido": """
        SELECT ano, nome_favorecido, cnpj_cpf_favorecido,
               COUNT(*) AS transacoes,
               SUM(COALESCE(
                   TRY_CAST(valor AS DOUBLE),
                   TRY_CAST(REPLACE(REPLACE(CAST(valor AS VARCHAR), '.', ''), ',', '.') AS DOUBLE),
                   0.0
               )) AS total_gasto
          FROM vw_cartao_corporativo
         GROUP BY ALL
    """,
    "vw_cartao_serie_anual": """
        SELECT ano,
               COUNT(*)                                          AS transacoes,
               SUM(COALESCE(TRY_CAST(valor AS DOUBLE), 0.0))    AS total_gasto,
               SUM(COALESCE(TRY_CAST(valor AS DOUBLE), 0.0)) FILTER (
                 WHERE nome_orgao ILIKE '%Presidência da República%'
                    OR nome_orgao ILIKE '%Presidencia da Republica%'
                    OR nome_orgao ILIKE '%Gabinete de Segurança Institucional%'
               ) AS total_presidencia
          FROM cartao_corporativo
         GROUP BY ALL
    """,
    # ----------------------------------------------- viagens e diárias PCDP
    "vw_viagem_servico": """
        SELECT ano, mes, id_viagem, codigo_orgao, nome_orgao,
               nome_viajante AS nome_viajante_extraido,
               normalizar_nome(nome_viajante) AS nome_viajante_formatado,
               normalizar_nome(nome_viajante) AS nome_viajante,
               cpf_viajante,
               cargo_viajante AS cargo_viajante_extraido,
               normalizar_nome(cargo_viajante) AS cargo_viajante_formatado,
               normalizar_nome(cargo_viajante) AS cargo_viajante,
               origem, destino, motivo, data_inicio, data_fim,
               COALESCE(TRY_CAST(valor_diarias AS DOUBLE), 0.0)    AS valor_diarias,
               COALESCE(TRY_CAST(valor_passagens AS DOUBLE), 0.0)  AS valor_passagens,
               COALESCE(TRY_CAST(valor_outros AS DOUBLE), 0.0)     AS valor_outros,
               COALESCE(TRY_CAST(valor_total AS DOUBLE), 0.0)      AS valor_total,
               data_referencia
          FROM viagem_servico
    """,
    "vw_viagem_por_orgao": """
        SELECT ano, codigo_orgao, nome_orgao,
               COUNT(*)                                                AS viagens,
               SUM(COALESCE(TRY_CAST(valor_diarias AS DOUBLE), 0.0))   AS total_diarias,
               SUM(COALESCE(TRY_CAST(valor_passagens AS DOUBLE), 0.0)) AS total_passagens,
               SUM(COALESCE(TRY_CAST(valor_total AS DOUBLE), 0.0))     AS total_gasto
          FROM viagem_servico
         GROUP BY ALL
    """,
    "vw_viagem_por_destino": """
        SELECT ano, destino,
               COUNT(*)                                                AS viagens,
               SUM(COALESCE(TRY_CAST(valor_total AS DOUBLE), 0.0))     AS total_gasto
          FROM viagem_servico
         GROUP BY ALL
    """,
    "vw_viagem_serie_anual": """
        SELECT ano,
               COUNT(*)                                                AS viagens,
               SUM(COALESCE(TRY_CAST(valor_diarias AS DOUBLE), 0.0))   AS total_diarias,
               SUM(COALESCE(TRY_CAST(valor_passagens AS DOUBLE), 0.0)) AS total_passagens,
               SUM(COALESCE(TRY_CAST(valor_total AS DOUBLE), 0.0))     AS total_gasto
          FROM viagem_servico
         GROUP BY ALL
    """,
    # --------------------------------- declaração de bens e patrimônio (TSE)
    "vw_bem_declarado": """
        SELECT id_politico, ano_eleicao, sequencial_candidato, cargo,
               tipo_bem, descricao_bem,
               COALESCE(TRY_CAST(valor_bem AS DOUBLE), 0.0) AS valor_bem,
               data_referencia
          FROM bem_declarado
    """,
    "vw_patrimonio_politico": """
        SELECT id_politico, ano_eleicao, cargo,
               COUNT(*)                                              AS total_bens,
               SUM(COALESCE(TRY_CAST(valor_bem AS DOUBLE), 0.0))    AS total_declarado
          FROM bem_declarado
         GROUP BY ALL
    """,
    # --------------------------------- contratos públicos e licitações (PNCP)
    "vw_contrato_governo": """
        SELECT ano, id_contrato, numero_contrato, codigo_orgao, nome_orgao,
               cnpj_fornecedor,
               nome_fornecedor AS nome_fornecedor_extraido,
               normalizar_nome(nome_fornecedor) AS nome_fornecedor_formatado,
               normalizar_nome(nome_fornecedor) AS nome_fornecedor,
               modalidade_licitacao, objeto,
               COALESCE(TRY_CAST(valor_inicial AS DOUBLE), 0.0)    AS valor_inicial,
               COALESCE(TRY_CAST(valor_atualizado AS DOUBLE), 0.0) AS valor_atualizado,
               data_inicio_vigencia, data_fim_vigencia, data_referencia
          FROM contrato_governo
    """,
    "vw_contrato_por_fornecedor": """
        SELECT ano, cnpj_fornecedor, nome_fornecedor,
               COUNT(*)                                                AS contratos,
               SUM(COALESCE(TRY_CAST(valor_atualizado AS DOUBLE), 0.0)) AS total_contratado
          FROM vw_contrato_governo
         GROUP BY ALL
    """,
    "vw_contrato_por_modalidade": """
        SELECT ano, modalidade_licitacao,
               COUNT(*)                                                AS contratos,
               SUM(COALESCE(TRY_CAST(valor_atualizado AS DOUBLE), 0.0)) AS total_contratado
          FROM vw_contrato_governo
         GROUP BY ALL
    """,
    # ------------------------------------------------ operações de crédito
    # Três medidas, e a diferença entre elas é a informação:
    #   pedido    — tudo que foi protocolado, inclusive o que foi negado
    #   deferido  — o que o Tesouro autorizou
    #   contratado— o que virou contrato com o credor
    #
    # Nenhuma delas é "dívida". O valor é o do PLEITO, não o saldo devedor de
    # hoje, que anos de amortização já reduziram. Ver armadilha 2o.
    "vw_credito_ente": """
        SELECT cod_ibge, uf, ano,
               COUNT(*)                                   AS pleitos,
               SUM(valor)                                 AS valor_pleiteado,
               SUM(valor) FILTER (WHERE status ILIKE 'Deferido%')
                                                          AS valor_deferido,
               SUM(valor) FILTER (WHERE contratado = 1)   AS valor_contratado
          FROM operacao_credito
         WHERE cod_ibge IS NOT NULL
         GROUP BY ALL
    """,
    "vw_credito_finalidade": """
        SELECT cod_ibge, ano, finalidade, tipo_credor, credor,
               COUNT(*) AS pleitos, SUM(valor) AS valor
          FROM operacao_credito
         WHERE status ILIKE 'Deferido%'
         GROUP BY ALL
    """,
    "vw_populacao": """
        SELECT cod_ibge, ano, valor AS populacao
          FROM indicador_ente
         WHERE cod_metrica = 'populacao'
    """,
    # Anos existentes no armazém, venham de onde vierem.
    # Os anos que o mapa oferece. Toda tabela de fato sobre ENTE entra aqui:
    # o `vw_mapa` faz produto de ente × ano, então um ano que falte nesta
    # lista simplesmente não existe para o painel — o ente que só entregou o
    # RREO sumiria do mapa em vez de aparecer cinza, e sumir é pior que
    # cinza, porque parece que o ente não existe.
    "vw_anos": """
        SELECT DISTINCT ano FROM indicador_ente WHERE ano IS NOT NULL
        UNION
        SELECT DISTINCT ano FROM financas_ente WHERE ano IS NOT NULL
        UNION
        SELECT DISTINCT ano FROM despesa_funcao WHERE ano IS NOT NULL
        UNION
        SELECT DISTINCT ano FROM indicador_fiscal WHERE ano IS NOT NULL
        UNION
        SELECT DISTINCT ano FROM transferencia_uniao WHERE ano IS NOT NULL
    """,
    # QUANTO de cada ano o painel consegue mostrar.
    #
    # As fontes têm calendários diferentes e isso não é detalhe: o RREO é
    # bimestral e já publica o ano corrente, enquanto o DCA é ANUAL e só sai
    # no exercício seguinte. Então existe sempre um ano — o corrente — em que
    # há despesa por função e indicador fiscal, mas não há arrecadação nem
    # despesa total.
    #
    # O painel abria nesse ano, porque escolhia o mais recente que QUALQUER
    # tabela tivesse. Metade dos cartões dizia "não coletado" e parecia que o
    # acervo tinha se perdido. Não tinha: o ano é que ainda não existe
    # inteiro. Esta view é o que permite a tela dizer isso.
    "vw_cobertura_ano": """
        WITH tudo AS (
            SELECT ano, 'financas'      AS bloco FROM financas_ente
             UNION ALL
            SELECT ano, 'populacao'          FROM indicador_ente
             UNION ALL
            SELECT ano, 'despesa_funcao'     FROM despesa_funcao
             UNION ALL
            SELECT ano, 'indicador_fiscal'   FROM indicador_fiscal
             UNION ALL
            SELECT ano, 'transferencias'     FROM transferencia_uniao
        )
        SELECT ano,
               COUNT(DISTINCT bloco) AS blocos_com_dado,
               5 AS blocos_no_total,
               -- Texto separado por vírgula, não `list()`: a camada que
               -- converte a consulta em JSON trata cada célula com um teste
               -- booleano, e um array levanta "truth value of an array is
               -- ambiguous". O tipo mais simples que atravessa é string.
               string_agg(DISTINCT bloco, ',' ORDER BY bloco) AS blocos,
               COUNT(DISTINCT bloco) = 5 AS completo
          FROM tudo WHERE ano IS NOT NULL GROUP BY ano
    """,
    # A primeira fatia do painel: três fontes, um número, ponta a ponta.
    # O produto ente × ano é deliberado: município sem finanças ainda aparece
    # no mapa, em cinza, em vez de sumir — some é pior que cinza, porque
    # parece que o ente não existe.
    "vw_mapa": """
        SELECT e.cod_ibge, e.nome, e.nivel, e.sigla_uf, e.cod_uf,
               a.ano, d.esfera, d.despesa_total, p.populacao,
               r.receita_total, t.transferencia_recebida,
               u.transferencia_uniao,
               se.saude AS despesa_saude, se.educacao AS despesa_educacao,
               lrf.percentual_pessoal, lrf.acima_do_limite,
               lrf.divida_liquida,
               CASE WHEN COALESCE(p.populacao, 0) > 0
                    THEN d.despesa_total / p.populacao END AS despesa_per_capita,
               CASE WHEN COALESCE(p.populacao, 0) > 0
                    THEN r.receita_total / p.populacao END AS receita_per_capita,
               -- Saúde e educação por habitante: é assim que a comparação
               -- entre uma capital e uma cidade de 3 mil pessoas faz sentido.
               CASE WHEN COALESCE(p.populacao, 0) > 0
                    THEN se.saude / p.populacao END AS saude_per_capita,
               CASE WHEN COALESCE(p.populacao, 0) > 0
                    THEN se.educacao / p.populacao END AS educacao_per_capita,
               -- Fatia da arrecadação que veio de transferência em vez de
               -- tributo próprio. Num município pequeno costuma passar de 90%,
               -- e é o número que explica por que ele depende do FPM.
               CASE WHEN COALESCE(r.receita_total, 0) > 0
                    THEN 100 * t.transferencia_recebida / r.receita_total END
                    AS dependencia_transferencia
          FROM dim_ente e
         CROSS JOIN vw_anos a
          LEFT JOIN vw_despesa_total d
                 ON d.cod_ibge = e.cod_ibge AND d.ano = a.ano
          LEFT JOIN vw_populacao p
                 ON p.cod_ibge = e.cod_ibge AND p.ano = a.ano
          LEFT JOIN vw_receita_total r
                 ON r.cod_ibge = e.cod_ibge AND r.ano = a.ano
          LEFT JOIN vw_transferencia_recebida t
                 ON t.cod_ibge = e.cod_ibge AND t.ano = a.ano
          LEFT JOIN vw_transferencia_uniao u
                 ON u.cod_ibge = e.cod_ibge AND u.ano = a.ano
          LEFT JOIN vw_saude_educacao se
                 ON se.cod_ibge = e.cod_ibge AND se.ano = a.ano
          LEFT JOIN vw_lrf_pessoal lrf
                 ON lrf.cod_ibge = e.cod_ibge AND lrf.ano = a.ano
                AND lrf.poder = 'E'
    """,
    # Mandato já ligado ao ente pelo de-para. `resolvido` diz se a ponte
    # existe — o painel precisa distinguir "não tem prefeito" de "não
    # consegui casar o nome da cidade".
    "vw_mandato": """
        SELECT m.sk,
               COALESCE(m.sk_politico, gerar_cod_politico(m.nome)) AS cod_politico_interno,
               m.sk_politico,
               COALESCE(m.cod_cargo, gerar_cod_cargo(m.cargo)) AS cod_cargo_interno,
               m.cod_cargo,
               m.cargo,
               m.cod_ue,
               m.cod_ibge,
               m.sigla_uf,
               m.nome AS nome_extraido,
               normalizar_nome(m.nome) AS nome_formatado,
               normalizar_nome(m.nome) AS nome,
               m.sigla_partido,
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
        SELECT cod_ibge, sigla_uf, cargo, cod_cargo_interno, cod_politico_interno,
               nome_extraido, nome_formatado, nome,
               sigla_partido, ano_inicio, ano_fim
          FROM vw_mandato
         WHERE cargo IN ('presidente', 'governador', 'prefeito')
           AND cod_ibge IS NOT NULL
    """,
    # Magistrados e Ministros dos Tribunais Brasileiros (Painel CNJ)
    "vw_magistrado": """
        SELECT m.sk,
               COALESCE(gerar_cod_magistrado(m.nome, m.tribunal), m.sk) AS cod_magistrado_interno,
               COALESCE(gerar_cod_cargo(m.cargo), m.cargo) AS cod_cargo_interno,
               m.id_origem,
               m.nome AS nome_extraido,
               normalizar_nome(m.nome) AS nome_formatado,
               normalizar_nome(m.nome) AS nome,
               m.cargo,
               normalizar_nome(m.cargo_descricao) AS cargo_descricao,
               m.tribunal,
               m.ramo,
               m.grau,
               m.sigla_uf,
               normalizar_nome(m.orgao_lotacao) AS orgao_lotacao,
               m.data_posse,
               m.situacao,
               m.url_foto
          FROM dim_magistrado m
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


def _udf_normalizar_nome(texto: str) -> str:
    return normalizar_nome_proprio(texto)


def _udf_gerar_slug(texto: str) -> str:
    return gerar_slug_codigo(texto)


def _udf_gerar_cod_politico(nome: str) -> str:
    return gerar_cod_politico_interno(nome)


def _udf_gerar_cod_magistrado(nome: str, tribunal: str) -> str:
    return gerar_cod_magistrado_interno(nome, tribunal)


def _udf_gerar_cod_cargo(cargo: str) -> str:
    return gerar_cod_cargo_interno(cargo)


def _udf_gerar_cod_ministro(pasta: str, nome: str) -> str:
    return gerar_cod_ministro_estado_interno(pasta, nome)


def criar(con: duckdb.DuckDBPyConnection) -> list[str]:
    criadas = []

    # Registrar UDFs de normalização de texto e códigos internos
    try:
        con.create_function("normalizar_nome", _udf_normalizar_nome)
        con.create_function("gerar_slug_codigo", _udf_gerar_slug)
        con.create_function("gerar_cod_politico", _udf_gerar_cod_politico)
        con.create_function("gerar_cod_magistrado", _udf_gerar_cod_magistrado)
        con.create_function("gerar_cod_cargo", _udf_gerar_cod_cargo)
        con.create_function("gerar_cod_ministro", _udf_gerar_cod_ministro)
    except Exception as erro_udf:
        log.debug("UDFs já registradas ou aviso: %s", erro_udf)

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
