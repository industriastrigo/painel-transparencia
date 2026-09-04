# -*- coding: utf-8 -*-
"""
Executor e Gerador do Relatório de Auditoria Técnica de QA - Indústrias Trigo.

Executa a suíte de testes de ponta a ponta (UI, Lógica, API, Banco de Dados e Batch)
e consolida os resultados no arquivo standalone 'relatorio_auditoria_qa.html'.
"""
from __future__ import annotations

import html
import inspect
import json
import math
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from testes.qa_audit import (
    test_ui_contracts,
    test_business_logic,
    test_api_integration,
    test_database_duckdb,
    test_batch_routines,
)

def extrair_descricao(func) -> str:
    doc = inspect.getdoc(func)
    if doc:
        return doc.strip().split("\n")[0]
    return func.__name__.replace("test_", "").replace("_", " ").capitalize()

def executar_teste(func, args=()):
    inicio = time.perf_counter()
    try:
        func(*args)
        duracao = (time.perf_counter() - inicio) * 1000
        return {
            "status": "Aprovado",
            "duracao_ms": round(duracao, 2),
            "onde_barrou": "N/A — Execução em total conformidade",
            "traceback": "",
        }
    except Exception as erro:
        duracao = (time.perf_counter() - inicio) * 1000
        tb = traceback.format_exc()
        tipo_erro = type(erro).__name__
        msg_erro = str(erro).strip().split("\n")[0] if str(erro) else "Falha de asserção"
        onde_barrou = f"{tipo_erro}: {msg_erro}"
        return {
            "status": "Reprovado",
            "duracao_ms": round(duracao, 2),
            "onde_barrou": onde_barrou,
            "traceback": tb,
        }

def rodar_suite_completa() -> list[dict]:
    resultados = []

    # 1. UI Contracts
    html_c = test_ui_contracts.INDEX_HTML.read_text(encoding="utf-8")
    css_c = test_ui_contracts.ESTILO_CSS.read_text(encoding="utf-8")

    ui_tests = [
        (test_ui_contracts.test_html_document_structure, (html_c,)),
        (test_ui_contracts.test_topbar_elements_and_buttons, (html_c,)),
        (test_ui_contracts.test_drawer_navigation_items, (html_c,)),
        (test_ui_contracts.test_section_tabpanels_existence, (html_c,)),
        (test_ui_contracts.test_dialog_modals_integrity, (html_c,)),
        (test_ui_contracts.test_search_inputs_and_filters, (html_c,)),
        (test_ui_contracts.test_css_and_js_asset_links, (html_c,)),
        (test_ui_contracts.test_outline_svg_standardization, (html_c, css_c)),
        (test_ui_contracts.test_no_emojis_in_headings_and_badges, (html_c,)),
        (test_ui_contracts.test_table_headers_and_accessibility, (html_c,)),
    ]

    for func, args in ui_tests:
        res = executar_teste(func, args)
        resultados.append({
            "nome_funcao": func.__name__,
            "o_que_foi_testado": extrair_descricao(func),
            "tipo_teste": "UI",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    # 2. Business Logic
    exemplos_numero = [
        (None, None), ("", None), ("   ", None), (float("nan"), None),
        (123, 123.0), (45.67, 45.67), ("100", 100.0), ("1.234,56", 1234.56),
        ("1.234.567,89", 1234567.89), ("R$ 50.000,00", 50000.0), ("  R$ 1.500,50 ", 1500.50),
        ("1234567.89", 1234567.89), ("1.234.567", 1234567.0), ("-150,25", -150.25),
        ("texto_invalido", None), ("12a34", None),
    ]
    for ent, esp in exemplos_numero:
        desc = f"Parsing numérico defensivo: '{ent}' -> {esp}"
        res = executar_teste(test_business_logic.test_valores_numero_parsing_precisao, (ent, esp))
        resultados.append({
            "nome_funcao": f"test_valores_numero_parsing_precisao[{ent}]",
            "o_que_foi_testado": desc,
            "tipo_teste": "Lógica",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    exemplos_inteiro = [
        (None, 0, 0), ("", 10, 10), ("123", None, 123),
        ("1.250,90", None, 1250), ("invalido", -1, -1),
    ]
    for ent, pad, esp in exemplos_inteiro:
        desc = f"Conversão inteiro com fallback: '{ent}' (padrão={pad}) -> {esp}"
        res = executar_teste(test_business_logic.test_valores_inteiro_fallback, (ent, pad, esp))
        resultados.append({
            "nome_funcao": f"test_valores_inteiro_fallback[{ent}]",
            "o_que_foi_testado": desc,
            "tipo_teste": "Lógica",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    exemplos_data = [
        (None, None), ("", None), ("2024-05-18", "2024-05-18"),
        ("2023-12-31T23:59:59Z", "2023-12-31"), ("14/08/2022", "2022-08-14"),
        ("14/08/22", "2022-08-14"), ("01/01/75", "1975-01-01"),
        ("01/01/69", "2069-01-01"), ("31/02/2023", "2023-02-31"),
        ("99/99/9999", None), ("invalido", None),
    ]
    for ent, esp in exemplos_data:
        desc = f"Conversão data padrão BR/SADIPEM: '{ent}' -> {esp}"
        res = executar_teste(test_business_logic.test_valores_data_br_boundary_resolution, (ent, esp))
        resultados.append({
            "nome_funcao": f"test_valores_data_br_boundary_resolution[{ent}]",
            "o_que_foi_testado": desc,
            "tipo_teste": "Lógica",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    outros_logica = [
        test_business_logic.test_valores_texto_e_opcional,
        test_business_logic.test_remover_acentos,
        test_business_logic.test_geradores_de_codigos_internos_entidades,
        test_business_logic.test_lrf_thresholds_math,
        test_business_logic.test_calculo_resultado_primario_e_nominal,
        test_business_logic.test_reconciliacao_pib_demanda_e_oferta,
        test_business_logic.test_schema_tables_minimum_contract,
    ]
    for func in outros_logica:
        res = executar_teste(func)
        resultados.append({
            "nome_funcao": func.__name__,
            "o_que_foi_testado": extrair_descricao(func),
            "tipo_teste": "Lógica",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    # 3. API Integration
    api_tests = [
        test_api_integration.test_api_saude_endpoint,
        test_api_integration.test_api_anos_e_cobertura,
        test_api_integration.test_api_configuracao,
        test_api_integration.test_api_mapa_com_parametros,
        test_api_integration.test_api_mapa_sem_ano_rejeicao_422,
        test_api_integration.test_api_metricas_catalogo,
        test_api_integration.test_api_entes_especifico_ibge,
        test_api_integration.test_api_executivo_esferas,
        test_api_integration.test_api_politicos_listagem,
        test_api_integration.test_api_proposicoes_listagem,
        test_api_integration.test_api_custo_reparticao,
        test_api_integration.test_api_judiciario_e_mp,
        test_api_integration.test_api_catalogo_e_explorador_arvore,
        test_api_integration.test_auth_endpoints_status,
        test_api_integration.test_explorador_consulta_select_valida,
        test_api_integration.test_explorador_consulta_vazia,
        test_api_integration.test_rota_inexistente_404,
    ]
    for func in api_tests:
        res = executar_teste(func)
        resultados.append({
            "nome_funcao": func.__name__,
            "o_que_foi_testado": extrair_descricao(func),
            "tipo_teste": "API",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    payloads_seguranca = [
        "DROP TABLE dim_ente",
        "DELETE FROM dim_ente WHERE 1=1",
        "INSERT INTO dim_ente VALUES (1, 2, 3)",
        "UPDATE dim_ente SET nome = 'Hacked'",
        "ALTER TABLE dim_ente ADD COLUMN hacked TEXT",
        "TRUNCATE TABLE dim_ente",
        "CREATE TABLE backdoor (id INT)",
        "GRANT ALL PRIVILEGES ON ALL TABLES TO PUBLIC",
        "REVOKE ALL PRIVILEGES ON ALL TABLES FROM PUBLIC",
        "SELECT * FROM dim_ente; DROP TABLE dim_ente;",
        "/* comentário */ DROP TABLE dim_ente",
        "select * from dim_ente; delete from dim_ente;",
    ]
    for payload in payloads_seguranca:
        desc = f"Segurança SQL / Bloqueio de DDL/DML: '{payload}'"
        res = executar_teste(test_api_integration.test_explorador_bloqueio_injecao_ddl_dml, (payload,))
        resultados.append({
            "nome_funcao": f"test_explorador_bloqueio_injecao_ddl_dml[{payload[:25]}...]",
            "o_que_foi_testado": desc,
            "tipo_teste": "API",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    # 4. DuckDB
    db_tests = [
        test_database_duckdb.test_duckdb_conexao_e_cursor,
        test_database_duckdb.test_duckdb_concorrencia_multiplas_threads,
        test_database_duckdb.test_duckdb_views_declaradas_criacao,
        test_database_duckdb.test_duckdb_resiliencia_query_invalida,
        test_database_duckdb.test_duckdb_parametrizacao_defensiva,
        test_database_duckdb.test_duckdb_tipagem_e_valores_nulos,
    ]
    for func in db_tests:
        res = executar_teste(func)
        resultados.append({
            "nome_funcao": func.__name__,
            "o_que_foi_testado": extrair_descricao(func),
            "tipo_teste": "DB",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    # 5. Batch
    batch_tests = [
        test_batch_routines.test_orquestrador_catalogo_fontes_metadados,
        test_batch_routines.test_contador_de_erros_registro_fiel,
        test_batch_routines.test_contador_de_erros_ignora_logs_alheios,
        test_batch_routines.test_armazem_deduplicacao_de_dados,
        test_batch_routines.test_estrutura_particionamento_parquet,
    ]
    for func in batch_tests:
        res = executar_teste(func)
        resultados.append({
            "nome_funcao": func.__name__,
            "o_que_foi_testado": extrair_descricao(func),
            "tipo_teste": "Batch",
            "status": res["status"],
            "duracao_ms": res["duracao_ms"],
            "onde_barrou": res["onde_barrou"],
            "traceback": res["traceback"],
        })

    return resultados

def gerar_relatorio_html(resultados: list[dict], arquivo_saida: Path):
    total = len(resultados)
    aprovados = sum(1 for r in resultados if r["status"] == "Aprovado")
    reprovados = sum(1 for r in resultados if r["status"] == "Reprovado")
    taxa_sucesso = (aprovados / total * 100) if total > 0 else 0
    tempo_total = sum(r["duracao_ms"] for r in resultados)

    tipos_contagem = {}
    for r in resultados:
        t = r["tipo_teste"]
        tipos_contagem[t] = tipos_contagem.get(t, 0) + 1

    agora = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")

    linhas_html = []
    for idx, r in enumerate(resultados, 1):
        status_classe = "badge-aprovado" if r["status"] == "Aprovado" else "badge-reprovado"
        tipo_classe = f"badge-tipo badge-{r['tipo_teste'].lower()}"
        
        if r["status"] == "Aprovado":
            onde_barrou_html = f'<span class="texto-conforme">{html.escape(r["onde_barrou"])}</span>'
        else:
            onde_barrou_html = f'''
                <div class="falha-resumo">
                    <strong class="texto-erro">{html.escape(r["onde_barrou"])}</strong>
                    <button class="btn-detalhes" onclick="abrirModalDetalhes({idx})">Ver Detalhes do Erro</button>
                    <script id="tb-data-{idx}" type="application/json">{json.dumps(r["traceback"])}</script>
                </div>
            '''

        linhas_html.append(f"""
        <tr class="linha-teste" data-tipo="{r['tipo_teste']}" data-status="{r['status']}">
            <td class="col-componente">
                <div class="nome-teste-principal">{html.escape(r['o_que_foi_testado'])}</div>
                <div class="nome-codigo-teste"><code>{html.escape(r['nome_funcao'])}</code></div>
            </td>
            <td class="col-tipo">
                <span class="{tipo_classe}">{r['tipo_teste']}</span>
            </td>
            <td class="col-status">
                <span class="badge-status {status_classe}">{r['status']}</span>
                <span class="duracao-teste">{r['duracao_ms']} ms</span>
            </td>
            <td class="col-barrou">
                {onde_barrou_html}
            </td>
        </tr>
        """)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Relatório de Auditoria Técnica de QA · Indústrias Trigo</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --fundo-base: #0B0E14;
            --fundo-card: #141824;
            --fundo-hover: #1E2336;
            --fundo-subtil: #1A1F2C;
            --borda-base: #2A3143;
            --borda-suave: #202738;
            --dourado-trigo: #E5A93C;
            --dourado-brilho: #F5C767;
            --dourado-fundo: rgba(229, 169, 60, 0.12);
            --texto-principal: #F0F2F8;
            --texto-secundario: #A2ACC3;
            --texto-mutado: #6B7694;
            --verde-sucesso: #10B981;
            --verde-fundo: rgba(16, 185, 129, 0.15);
            --vermelho-erro: #EF4444;
            --vermelho-fundo: rgba(239, 68, 68, 0.15);
            --azul-info: #3B82F6;
            --azul-fundo: rgba(59, 130, 246, 0.15);
            --roxo-tag: #8B5CF6;
            --roxo-fundo: rgba(139, 92, 246, 0.15);
            --laranja-tag: #F97316;
            --laranja-fundo: rgba(249, 115, 22, 0.15);
            --sombra-card: 0 10px 30px rgba(0, 0, 0, 0.35);
            --raio-borda: 10px;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--fundo-base);
            color: var(--texto-principal);
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            line-height: 1.5;
            padding: 30px 20px;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .cabecalho-auditoria {{
            background: linear-gradient(135deg, #141824 0%, #1A2035 100%);
            border: 1px solid var(--borda-base);
            border-radius: var(--raio-borda);
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: var(--sombra-card);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }}

        .marca-bloco {{
            display: flex;
            align-items: center;
            gap: 18px;
        }}

        .logo-icone {{
            width: 48px;
            height: 48px;
            background: var(--dourado-fundo);
            border: 1px solid var(--dourado-trigo);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--dourado-trigo);
        }}

        .titulo-auditoria {{
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--texto-principal);
            letter-spacing: -0.02em;
        }}

        .titulo-auditoria span {{
            color: var(--dourado-trigo);
        }}

        .subtitulo-auditoria {{
            font-size: 0.9rem;
            color: var(--texto-secundario);
            margin-top: 4px;
        }}

        .meta-info {{
            text-align: right;
            font-size: 0.85rem;
            color: var(--texto-mutado);
        }}

        .meta-badge {{
            display: inline-block;
            background: rgba(229, 169, 60, 0.15);
            border: 1px solid rgba(229, 169, 60, 0.3);
            color: var(--dourado-brilho);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 6px;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 25px;
        }}

        .kpi-card {{
            background-color: var(--fundo-card);
            border: 1px solid var(--borda-base);
            border-radius: var(--raio-borda);
            padding: 20px;
            box-shadow: var(--sombra-card);
            transition: transform 0.2s, border-color 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--dourado-trigo);
        }}

        .kpi-rotulo {{
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--texto-mutado);
            margin-bottom: 8px;
        }}

        .kpi-valor {{
            font-size: 2rem;
            font-weight: 800;
            color: var(--texto-principal);
            font-family: 'JetBrains Mono', monospace;
        }}

        .kpi-valor.sucesso {{ color: var(--verde-sucesso); }}
        .kpi-valor.erro {{ color: var(--vermelho-erro); }}
        .kpi-valor.destaque {{ color: var(--dourado-trigo); }}

        .kpi-rodape {{
            font-size: 0.78rem;
            color: var(--texto-secundario);
            margin-top: 6px;
        }}

        .painel-controles {{
            background-color: var(--fundo-card);
            border: 1px solid var(--borda-base);
            border-radius: var(--raio-borda);
            padding: 16px 20px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .grupo-filtros {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .btn-filtro {{
            background-color: var(--fundo-subtil);
            border: 1px solid var(--borda-base);
            color: var(--texto-secundario);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .btn-filtro:hover {{
            background-color: var(--fundo-hover);
            color: var(--texto-principal);
        }}

        .btn-filtro.ativo {{
            background-color: var(--dourado-trigo);
            color: #0B0E14;
            border-color: var(--dourado-trigo);
            font-weight: 700;
        }}

        .busca-container {{
            position: relative;
            min-width: 280px;
        }}

        .input-busca {{
            width: 100%;
            background-color: var(--fundo-base);
            border: 1px solid var(--borda-base);
            border-radius: 8px;
            padding: 8px 14px 8px 36px;
            color: var(--texto-principal);
            font-size: 0.85rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .input-busca:focus {{
            border-color: var(--dourado-trigo);
        }}

        .icone-lupa {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--texto-mutado);
            pointer-events: none;
        }}

        .tabela-container {{
            background-color: var(--fundo-card);
            border: 1px solid var(--borda-base);
            border-radius: var(--raio-borda);
            overflow: hidden;
            box-shadow: var(--sombra-card);
        }}

        .tabela-auditoria {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        .tabela-auditoria th {{
            background-color: #10141F;
            color: var(--texto-secundario);
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 14px 18px;
            border-bottom: 2px solid var(--borda-base);
        }}

        .tabela-auditoria td {{
            padding: 14px 18px;
            border-bottom: 1px solid var(--borda-suave);
            font-size: 0.88rem;
            vertical-align: middle;
        }}

        .linha-teste:hover {{
            background-color: var(--fundo-hover);
        }}

        .nome-teste-principal {{
            font-weight: 600;
            color: var(--texto-principal);
            margin-bottom: 4px;
        }}

        .nome-codigo-teste code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.76rem;
            color: var(--texto-mutado);
            background: rgba(255, 255, 255, 0.04);
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .badge-status {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }}

        .badge-aprovado {{
            background-color: var(--verde-fundo);
            color: var(--verde-sucesso);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-reprovado {{
            background-color: var(--vermelho-fundo);
            color: var(--vermelho-erro);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .duracao-teste {{
            display: block;
            font-size: 0.72rem;
            color: var(--texto-mutado);
            font-family: 'JetBrains Mono', monospace;
            margin-top: 4px;
        }}

        .badge-tipo {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
        }}

        .badge-ui {{ background: var(--azul-fundo); color: var(--azul-info); border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-lógica {{ background: var(--roxo-fundo); color: var(--roxo-tag); border: 1px solid rgba(139, 92, 246, 0.3); }}
        .badge-api {{ background: var(--dourado-fundo); color: var(--dourado-trigo); border: 1px solid rgba(229, 169, 60, 0.3); }}
        .badge-db {{ background: rgba(14, 165, 233, 0.15); color: #0EA5E9; border: 1px solid rgba(14, 165, 233, 0.3); }}
        .badge-batch {{ background: var(--laranja-fundo); color: var(--laranja-tag); border: 1px solid rgba(249, 115, 22, 0.3); }}

        .texto-conforme {{
            color: var(--texto-mutado);
            font-size: 0.82rem;
            font-style: italic;
        }}

        .falha-resumo {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .texto-erro {{
            color: var(--vermelho-erro);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
        }}

        .btn-detalhes {{
            align-self: flex-start;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #F87171;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .btn-detalhes:hover {{
            background: rgba(239, 68, 68, 0.25);
            color: #FFF;
        }}

        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(4px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            padding: 20px;
        }}

        .modal-corpo {{
            background-color: var(--fundo-card);
            border: 1px solid var(--borda-base);
            border-radius: var(--raio-borda);
            width: 100%;
            max-width: 900px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6);
            overflow: hidden;
        }}

        .modal-cabecalho {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--borda-base);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .modal-titulo {{
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--vermelho-erro);
        }}

        .btn-fechar-modal {{
            background: transparent;
            border: none;
            color: var(--texto-secundario);
            font-size: 1.4rem;
            cursor: pointer;
        }}

        .modal-conteudo {{
            padding: 20px;
            overflow-y: auto;
        }}

        .codigo-traceback {{
            background-color: #07090E;
            border: 1px solid var(--borda-suave);
            border-radius: 6px;
            padding: 16px;
            color: #F87171;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            white-space: pre-wrap;
            overflow-x: auto;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="cabecalho-auditoria">
            <div class="marca-bloco">
                <div class="logo-icone">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                </div>
                <div>
                    <h1 class="titulo-auditoria">Indústrias Trigo · <span>Auditoria Técnica de QA</span></h1>
                    <p class="subtitulo-auditoria">Suíte de Testes Automatizados de Ponta a Ponta: UI, Lógica, API, Banco de Dados & Processamento Batch</p>
                </div>
            </div>
            <div class="meta-info">
                <div class="meta-badge">RELATÓRIO TÉCNICO OFICIAL</div>
                <div>Executado em: <strong>{agora}</strong></div>
                <div>Ambiente: <strong>Produção / Homologação (Python 3.12)</strong></div>
            </div>
        </header>

        <section class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-rotulo">Total de Testes</div>
                <div class="kpi-valor">{total}</div>
                <div class="kpi-rodape">100% dos fluxos auditados</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-rotulo">Aprovados</div>
                <div class="kpi-valor sucesso">{aprovados}</div>
                <div class="kpi-rodape">Conformidade total assegurada</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-rotulo">Reprovados / Falhas</div>
                <div class="kpi-valor erro">{reprovados}</div>
                <div class="kpi-rodape">Gargalos e bloqueios identificados</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-rotulo">Taxa de Sucesso</div>
                <div class="kpi-valor destaque">{taxa_sucesso:.1f}%</div>
                <div class="kpi-rodape">Índice geral de aprovação</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-rotulo">Duração Total</div>
                <div class="kpi-valor">{tempo_total:.0f} ms</div>
                <div class="kpi-rodape">Tempo de execução dos testes</div>
            </div>
        </section>

        <section class="painel-controles">
            <div class="grupo-filtros">
                <button class="btn-filtro ativo" onclick="filtrar('todos')">Todos ({total})</button>
                <button class="btn-filtro" onclick="filtrar('Aprovado')">Aprovados ({aprovados})</button>
                <button class="btn-filtro" onclick="filtrar('Reprovado')">Reprovados ({reprovados})</button>
                <button class="btn-filtro" onclick="filtrar('UI')">UI ({tipos_contagem.get('UI', 0)})</button>
                <button class="btn-filtro" onclick="filtrar('Lógica')">Lógica ({tipos_contagem.get('Lógica', 0)})</button>
                <button class="btn-filtro" onclick="filtrar('API')">API ({tipos_contagem.get('API', 0)})</button>
                <button class="btn-filtro" onclick="filtrar('DB')">DB ({tipos_contagem.get('DB', 0)})</button>
                <button class="btn-filtro" onclick="filtrar('Batch')">Batch ({tipos_contagem.get('Batch', 0)})</button>
            </div>
            <div class="busca-container">
                <svg class="icone-lupa" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <input type="text" id="input-busca" class="input-busca" placeholder="Buscar testes, métodos ou erros..." onkeyup="buscarTestes()">
            </div>
        </section>

        <section class="tabela-container">
            <table class="tabela-auditoria" id="tabela-auditoria">
                <thead>
                    <tr>
                        <th style="width: 42%;">O que foi testado</th>
                        <th style="width: 12%;">Tipo de Teste</th>
                        <th style="width: 14%;">Status</th>
                        <th style="width: 32%;">Onde Barrou</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(linhas_html)}
                </tbody>
            </table>
        </section>
    </div>

    <div class="modal-overlay" id="modal-traceback" onclick="fecharModalDetalhes(event)">
        <div class="modal-corpo" onclick="event.stopPropagation()">
            <div class="modal-cabecalho">
                <h3 class="modal-titulo" id="modal-titulo-erro">Detalhes da Falha / Traceback Técnico</h3>
                <button class="btn-fechar-modal" onclick="fecharModalDetalhes()">&times;</button>
            </div>
            <div class="modal-conteudo">
                <pre class="codigo-traceback" id="modal-traceback-conteudo"></pre>
            </div>
        </div>
    </div>

    <script>
        let filtroAtivo = 'todos';

        function filtrar(tipo) {{
            filtroAtivo = tipo;
            document.querySelectorAll('.btn-filtro').forEach(btn => {{
                btn.classList.toggle('ativo', btn.innerText.toLowerCase().startsWith(tipo.toLowerCase()));
            }});
            aplicarFiltros();
        }}

        function buscarTestes() {{
            aplicarFiltros();
        }}

        function aplicarFiltros() {{
            const termo = document.getElementById('input-busca').value.toLowerCase();
            const linhas = document.querySelectorAll('.linha-teste');

            linhas.forEach(linha => {{
                const tipo = linha.getAttribute('data-tipo');
                const status = linha.getAttribute('data-status');
                const texto = linha.innerText.toLowerCase();

                let bateTipo = (filtroAtivo === 'todos') || (status === filtroAtivo) || (tipo === filtroAtivo);
                let bateBusca = !termo || texto.includes(termo);

                if (bateTipo && bateBusca) {{
                    linha.style.display = '';
                }} else {{
                    linha.style.display = 'none';
                }}
            }});
        }}

        function abrirModalDetalhes(idx) {{
            const scriptTag = document.getElementById('tb-data-' + idx);
            if (scriptTag) {{
                try {{
                    const traceback = JSON.parse(scriptTag.textContent);
                    document.getElementById('modal-traceback-conteudo').textContent = traceback || 'Sem detalhes de traceback gravados.';
                    document.getElementById('modal-traceback').style.display = 'flex';
                }} catch (e) {{
                    console.error('Erro ao abrir modal:', e);
                }}
            }}
        }}

        function fecharModalDetalhes() {{
            document.getElementById('modal-traceback').style.display = 'none';
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') fecharModalDetalhes();
        }});
    </script>
</body>
</html>
"""
    arquivo_saida.write_text(html_template, encoding="utf-8")
    print(f"[OK] Relatório de Auditoria QA gerado com sucesso em: {arquivo_saida}")

def main():
    print("=" * 70)
    print("INICIANDO SUÍTE DE AUDITORIA TÉCNICA DE QA - INDÚSTRIAS TRIGO")
    print("=" * 70)
    resultados = rodar_suite_completa()
    print(f"Total de testes executados: {len(resultados)}")
    aprovados = sum(1 for r in resultados if r["status"] == "Aprovado")
    reprovados = sum(1 for r in resultados if r["status"] == "Reprovado")
    print(f"Aprovados: {aprovados} | Reprovados: {reprovados}")

    destino_html = RAIZ / "relatorio_auditoria_qa.html"
    gerar_relatorio_html(resultados, destino_html)
    print("=" * 70)

if __name__ == "__main__":
    main()
