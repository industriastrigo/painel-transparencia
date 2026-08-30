import duckdb, sys
con = duckdb.connect()
con.execute("CREATE VIEW financas_ente AS SELECT * FROM read_parquet('dados/fato/financas_ente/**/*.parquet', hive_partitioning=1, union_by_name=1)")
con.execute("""CREATE VIEW vw_conta_codigo AS 
        SELECT *,
               regexp_extract(cod_conta, '([0-9][0-9.]*)$', 1) AS codigo_conta
          FROM financas_ente
    """)
con.execute("""CREATE VIEW vw_conta_nivel AS 
        SELECT *,
               CASE WHEN codigo_conta = '' THEN NULL
                    ELSE LEN(list_filter(str_split(codigo_conta, '.'),
                             x -> COALESCE(TRY_CAST(x AS INTEGER), 0) <> 0))
                    END AS nivel_conta,
               COUNT(*) FILTER (WHERE codigo_conta <> '')
                        OVER (PARTITION BY cod_ibge, ano) AS contas_numericas
          FROM vw_conta_codigo
         WHERE estagio ILIKE '%Empenhada%'
    """)
con.execute("""CREATE VIEW vw_despesa_categoria AS 
        SELECT cod_ibge, ano, esfera, codigo_conta AS cod_natureza,
               rotulo_conta AS natureza, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 1 AND codigo_conta <> ''
         GROUP BY ALL
    """)
con.execute("""CREATE VIEW vw_despesa_natureza AS 
        SELECT cod_ibge, ano, esfera, codigo_conta AS cod_natureza,
               rotulo_conta AS natureza, SUM(valor) AS valor
          FROM vw_conta_nivel
         WHERE nivel_conta = 2 AND codigo_conta <> ''
         GROUP BY ALL
    """)
con.execute("""CREATE VIEW vw_conferencia_despesa AS 
        SELECT cod_ibge, ano, esfera,
               SUM(valor) FILTER (WHERE nivel_conta = 1
                                    AND codigo_conta <> '') AS somado,
               MAX(valor) FILTER (WHERE codigo_conta = '')   AS declarado
          FROM vw_conta_nivel
         GROUP BY ALL
    """)
con.execute("""CREATE VIEW vw_despesa_total AS 
        SELECT cod_ibge, ano, esfera,
               COALESCE(somado, declarado) AS despesa_total
          FROM vw_conferencia_despesa
         WHERE COALESCE(somado, declarado) IS NOT NULL
    """)
con.execute("""CREATE VIEW vw_receita_conta AS 
        SELECT *,
               LEN(list_filter(str_split(codigo_conta, '.'),
                               x -> COALESCE(TRY_CAST(x AS INTEGER), 0) <> 0))
                   AS nivel_receita
          FROM vw_conta_codigo
         WHERE estagio ILIKE '%Receitas%Realizadas%'
           AND codigo_conta <> ''
    """)
con.execute("""CREATE VIEW vw_receita_total AS 
        SELECT cod_ibge, ano, esfera, SUM(valor) AS receita_total
          FROM vw_receita_conta
         WHERE nivel_receita = 1
           AND (codigo_conta LIKE '1%' OR codigo_conta LIKE '2%')
         GROUP BY ALL
    """)
con.execute("""CREATE VIEW vw_transferencia_recebida AS 
        SELECT cod_ibge, ano, esfera,
               SUM(valor) AS transferencia_recebida
          FROM vw_receita_conta
         WHERE nivel_receita = 2
           AND (codigo_conta LIKE '1.7%' OR codigo_conta LIKE '2.4%')
         GROUP BY ALL
    """)

print("== BAHIA: em que gasta, por natureza ==")
print(con.execute("SELECT natureza, valor FROM vw_despesa_natureza WHERE cod_ibge='29' ORDER BY valor DESC LIMIT 8").df().to_string(index=False))
print()
print("== conferencia (somado x declarado), 5 estados ==")
print(con.execute("SELECT cod_ibge, somado, declarado, somado-declarado AS dif FROM vw_conferencia_despesa WHERE esfera='estado' ORDER BY cod_ibge LIMIT 5").df().to_string(index=False))
print()
print("== ARRECADACAO: 5 estados ==")
print(con.execute("SELECT cod_ibge, receita_total FROM vw_receita_total WHERE esfera='estado' ORDER BY cod_ibge LIMIT 5").df().to_string(index=False))
print()
print("== TRANSFERENCIAS RECEBIDAS: 5 estados ==")
print(con.execute("SELECT cod_ibge, transferencia_recebida FROM vw_transferencia_recebida WHERE esfera='estado' ORDER BY cod_ibge LIMIT 5").df().to_string(index=False))
print()
print("== municipios com arrecadacao ==")
print(con.execute("SELECT COUNT(*) FROM vw_receita_total WHERE esfera='municipio'").fetchone())
