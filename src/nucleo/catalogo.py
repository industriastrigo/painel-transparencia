"""Catálogo e Inventário de Tabelas do Acervo Parquet.

Gera uma tabela física (`dados/dim/dim_catalogo_tabela.parquet`) e view analítica
que lista CADA tabela, CADA ano coletado (uma linha por ano), volume de linhas,
fontes oficiais, órgão de origem, endpoint correspondente e status de completude.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import config
from .registro import obter as obter_log

log = obter_log("nucleo.catalogo")

METADADOS_TABELAS: dict[str, dict[str, str]] = {
    "dim_ente": {
        "orgao": "IBGE",
        "recurso": "Cadastro de Municípios, Estados e Regiões do Brasil",
        "endpoint": "GET /agregados/6579 (SIDRA) + Malhas GeoJSON",
        "granularidade": "1 ente federativo (cod_ibge)",
        "completude_default": "total",
    },
    "dim_politico": {
        "orgao": "TSE / Congresso Nacional",
        "recurso": "Candidatos eleitos e parlamentares federais",
        "endpoint": "GET /divulgacandcontas/candidaturas + GET /deputados + GET /senadores",
        "granularidade": "1 autoridade / parlamentar (fonte_origem, id_origem)",
        "completude_default": "total",
    },
    "dim_cargo_publico": {
        "orgao": "Constituição Federal / Leis Orgânicas",
        "recurso": "Catálogo canônico de cargos públicos dos 3 Poderes e esferas",
        "endpoint": "referencias/cargos_publicos.csv",
        "granularidade": "1 cargo público canônico (cod_cargo)",
        "completude_default": "total",
    },
    "dim_cargo": {
        "orgao": "TSE",
        "recurso": "Cargos eletivos do sistema eleitoral brasileiro",
        "endpoint": "TSE DivulgaCandContas",
        "granularidade": "1 cargo eletivo",
        "completude_default": "total",
    },
    "dim_partido": {
        "orgao": "TSE",
        "recurso": "Partidos políticos com registro ativo no TSE",
        "endpoint": "TSE Partidos",
        "granularidade": "1 partido político (sigla)",
        "completude_default": "total",
    },
    "dim_metrica": {
        "orgao": "IBGE / Tesouro Nacional",
        "recurso": "Dicionário de métricas e indicadores socioeconômicos e fiscais",
        "endpoint": "referencias/metricas.csv",
        "granularidade": "1 métrica / indicador",
        "completude_default": "total",
    },
    "dim_de_para_ente": {
        "orgao": "TSE / IBGE",
        "recurso": "Mapeamento de-para entre Unidades Eleitorais (TSE) e Códigos IBGE",
        "endpoint": "TSE + IBGE",
        "granularidade": "1 de-para ente (fonte_origem, id_origem)",
        "completude_default": "total",
    },
    "dim_magistrado": {
        "orgao": "CNJ (Conselho Nacional de Justiça)",
        "recurso": "Ministros de Tribunais Superiores e Presidentes de Tribunais (STF, STJ, TST, TRFs, TJs)",
        "endpoint": "Painel de Remuneração dos Magistrados CNJ",
        "granularidade": "1 magistrado / ministro",
        "completude_default": "amostra_cupula",
    },
    "dim_subsidio": {
        "orgao": "Legislação / Diários Oficiais",
        "recurso": "Subsídios fixados em lei por cargo público constitucional",
        "endpoint": "referencias/subsidios.csv",
        "granularidade": "1 subsídio normativo por cargo e vigência",
        "completude_default": "total",
    },
    "despesa_parlamentar": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Cota para o Exercício da Atividade Parlamentar (CEAP)",
        "endpoint": "GET /cotas/Ano-{ano}.csv.zip (Arquivos diários)",
        "granularidade": "1 nota fiscal / documento de reembolso",
        "completude_default": "total",
    },
    "proposicao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Proposições Legislativas (PL, PEC, MP, PDC, REQ)",
        "endpoint": "GET /proposicoes (Arquivos em lote diários)",
        "granularidade": "1 proposição legislativa",
        "completude_default": "total",
    },
    "votacao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Sessões deliberativas e votações no Plenário",
        "endpoint": "GET /votacoes (Arquivos em lote diários)",
        "granularidade": "1 sessão / votação",
        "completude_default": "total",
    },
    "voto": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Votos nominais de deputados federais",
        "endpoint": "GET /votacoes/{id}/votos (Arquivos em lote diários)",
        "granularidade": "1 voto nominal por deputado × votação",
        "completude_default": "total",
    },
    "orientacao_bancada": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Orientação partidária oficial nas votações (Sim, Não, Obstrução)",
        "endpoint": "GET /votacoes/{id}/orientacoes (Arquivos diários)",
        "granularidade": "1 orientação por bancada × votação",
        "completude_default": "total",
    },
    "evento": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Eventos da agenda parlamentar (sessões, comissões, audiências)",
        "endpoint": "GET /eventos (Arquivos diários)",
        "granularidade": "1 evento legislativo",
        "completude_default": "total",
    },
    "presenca_evento": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Presença nominal de parlamentares em eventos legislativos",
        "endpoint": "GET /eventos/{id}/deputados (Arquivos diários)",
        "granularidade": "1 presença nominal por deputado × sessão",
        "completude_default": "total",
    },
    "tramitacao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Etapas de tramitação de proposições legislativas",
        "endpoint": "GET /proposicoes/{id}/tramitacoes",
        "granularidade": "1 etapa de tramitação",
        "completude_default": "amostra",
    },
    "emenda_parlamentar": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Execução orçamentária de emendas parlamentares (Individuais, Bancada, Comissão, PIX)",
        "endpoint": "GET /api-de-dados/emendas-parlamentares",
        "granularidade": "1 emenda orçamentária / documento",
        "completude_default": "total",
    },
    "financas_ente": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Declaração de Contas Anuais (DCA) - Despesas e Receitas por conta contábil",
        "endpoint": "GET /dca (Tesouro Nacional)",
        "granularidade": "1 conta contábil por ente × ano",
        "completude_default": "total",
    },
    "despesa_funcao": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Relatório Resumido de Execução Orçamentária (RREO Anexo 02) - Despesa por Função de Governo",
        "endpoint": "GET /rreo (Tesouro Nacional)",
        "granularidade": "1 função/subfunção por ente × bimestre",
        "completude_default": "parcial",
    },
    "indicador_fiscal": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Relatório de Gestão Fiscal (RGF) - Limites de Pessoal e Dívida Consolidada da LRF",
        "endpoint": "GET /rgf (Tesouro Nacional)",
        "granularidade": "1 indicador fiscal por ente × quadrimestre/semestre",
        "completude_default": "parcial",
    },
    "transferencia_uniao": {
        "orgao": "SIAFI / Tesouro Nacional",
        "recurso": "Transferências Constitucionais Obrigatórias (FPM, FPE, FUNDEB, Royalties)",
        "endpoint": "GET /transferencias-constitucionais (Tesouro Aria)",
        "granularidade": "1 repasse por ente × modalidade × mês",
        "completude_default": "total",
    },
    "operacao_credito": {
        "orgao": "SADIPEM (Tesouro Nacional)",
        "recurso": "Pedidos de Verificação de Limites (PVL) e Operações de Crédito de Estados e Municípios",
        "endpoint": "GET /pvl (SADIPEM Data Lake)",
        "granularidade": "1 pleito / PVL",
        "completude_default": "total",
    },
    "custo_orgao": {
        "orgao": "Tesouro Nacional",
        "recurso": "Custo apurado por Ministério e Órgão do Poder Executivo Federal (Regime de Competência)",
        "endpoint": "GET /custo-orgao-federal",
        "granularidade": "1 item de custo por órgão × mês",
        "completude_default": "total",
    },
    "cartao_corporativo": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Faturas e despesas do Cartão de Pagamento do Governo Federal (CPGF)",
        "endpoint": "GET /api-de-dados/cartoes",
        "granularidade": "1 transação / portador",
        "completude_default": "total",
    },
    "contrato_governo": {
        "orgao": "Portal da Transparência / ComprasGov",
        "recurso": "Contratos administrativos firmados por órgãos federais",
        "endpoint": "GET /api-de-dados/contratos",
        "granularidade": "1 contrato administrativo",
        "completude_default": "amostra",
    },
    "viagem_servico": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Diárias e passagens aéreas concedidas a servidores e autoridades federais",
        "endpoint": "GET /api-de-dados/viagens",
        "granularidade": "1 viagem a serviço",
        "completude_default": "amostra",
    },
    "fato_remuneracao_magistrado": {
        "orgao": "CNJ (Conselho Nacional de Justiça)",
        "recurso": "Folhas de pagamento detalhadas de magistrados (Subsídio, Vantagens, Indenizações, Teto)",
        "endpoint": "Painel de Remuneração dos Magistrados CNJ",
        "granularidade": "1 contracheque por magistrado × mês",
        "completude_default": "total",
    },
    "mandato": {
        "orgao": "TSE",
        "recurso": "Histórico de mandatos eletivos municipais, estaduais e federais",
        "endpoint": "TSE DivulgaCand + Referências Históricas",
        "granularidade": "1 mandato por político × ciclo",
        "completude_default": "total",
    },
    "indicador_ente": {
        "orgao": "IBGE",
        "recurso": "Indicadores socioeconômicos dos municípios (População, PIB, etc.)",
        "endpoint": "GET /agregados/6579 e GET /agregados/5938",
        "granularidade": "1 indicador por ente × ano",
        "completude_default": "total",
    },
    "votacao_proposicao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Associação entre matérias legislativas e suas sessões de votação",
        "endpoint": "Câmara dos Deputados",
        "granularidade": "1 vínculo votação × proposição",
        "completude_default": "total",
    },
}


def construir_catalogo() -> pd.DataFrame:
    """Audita todas as tabelas em dados/dim e dados/fato e retorna DataFrame normalizado."""
    con = duckdb.connect()
    linhas: list[dict[str, Any]] = []
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Tabelas de Dimensão
    dim_dir = Path(config.DIM) if config.DIM is not None else Path("dados/dim")
    if dim_dir.exists():
        for f in sorted(dim_dir.glob("*.parquet")):
            if f.stem == "dim_catalogo_tabela":
                continue
            tabela = f.stem
            meta = METADADOS_TABELAS.get(tabela, {
                "orgao": "Oficial",
                "recurso": f"Dimensão {tabela}",
                "endpoint": "n/a",
                "granularidade": "1 registro",
                "completude_default": "total",
            })
            try:
                df = con.execute(f"SELECT * FROM read_parquet('{f.as_posix()}')").df()
                fontes = df["_fonte"].unique().tolist() if "_fonte" in df.columns else ["n/a"]
                total_linhas = len(df)
            except Exception as erro:
                log.warning("erro ao ler dimensao %s: %s", f.name, erro)
                total_linhas = 0
                fontes = ["desconhecida"]

            sk_val = hashlib.md5(f"{tabela}_dim_vigente".encode("utf-8")).hexdigest()[:16]
            linhas.append({
                "sk": sk_val,
                "tabela": tabela,
                "camada": "dim",
                "ano_particao": "vigente",
                "ano": None,
                "total_linhas": int(total_linhas),
                "fontes": ", ".join(str(x) for x in fontes),
                "status_completude": meta["completude_default"],
                "orgao_origem": meta["orgao"],
                "descricao_recurso": meta["recurso"],
                "endpoint_recurso": meta["endpoint"],
                "granularidade": meta["granularidade"],
                "data_atualizacao": agora,
                "_hash_registro": sk_val,
                "_fonte": "catalogo_sistema",
                "_criado_em": agora,
                "_atualizado_em": agora,
            })

    # 2. Tabelas de Fato
    fato_dir = Path(config.FATO) if config.FATO is not None else Path("dados/fato")
    if fato_dir.exists():
        for d in sorted(fato_dir.iterdir()):
            if not d.is_dir():
                continue
            tabela = d.name
            meta = METADADOS_TABELAS.get(tabela, {
                "orgao": "Oficial",
                "recurso": f"Fato {tabela}",
                "endpoint": "n/a",
                "granularidade": "1 registro",
                "completude_default": "total",
            })
            padrao = f"{d.as_posix()}/**/*.parquet"

            try:
                df_anos = con.execute(f"""
                    SELECT 
                        COALESCE(TRY_CAST(ano AS VARCHAR), 'sem_ano') AS ano_ref,
                        COUNT(*) AS qtd_linhas,
                        LIST(DISTINCT _fonte) AS fontes_list
                    FROM read_parquet('{padrao}', hive_partitioning=1, union_by_name=1)
                    GROUP BY 1
                    ORDER BY 1
                """).df()

                for _, r in df_anos.iterrows():
                    ano_str = str(r["ano_ref"])
                    ano_int = int(ano_str) if ano_str.isdigit() else None
                    fontes_str = ", ".join(str(x) for x in r["fontes_list"])

                    completude = meta["completude_default"]
                    if tabela == "despesa_funcao":
                        completude = "parcial_municipios" if ano_int == 2026 else "total_ufs"
                    elif tabela == "indicador_fiscal":
                        completude = "parcial_municipios" if ano_int == 2026 else "total_ufs"
                    elif tabela in ("proposicao", "votacao") and ano_int == 1998:
                        completude = "amostra_historica"

                    sk_val = hashlib.md5(f"{tabela}_fato_{ano_str}".encode("utf-8")).hexdigest()[:16]
                    linhas.append({
                        "sk": sk_val,
                        "tabela": tabela,
                        "camada": "fato",
                        "ano_particao": ano_str,
                        "ano": ano_int,
                        "total_linhas": int(r["qtd_linhas"]),
                        "fontes": fontes_str,
                        "status_completude": completude,
                        "orgao_origem": meta["orgao"],
                        "descricao_recurso": meta["recurso"],
                        "endpoint_recurso": meta["endpoint"],
                        "granularidade": meta["granularidade"],
                        "data_atualizacao": agora,
                        "_hash_registro": sk_val,
                        "_fonte": "catalogo_sistema",
                        "_criado_em": agora,
                        "_atualizado_em": agora,
                    })
            except Exception:
                # Fatos sem partição explícita de ano (ex: mandato)
                try:
                    total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{padrao}', hive_partitioning=1, union_by_name=1)").fetchone()[0]
                    sk_val = hashlib.md5(f"{tabela}_fato_geral".encode("utf-8")).hexdigest()[:16]
                    linhas.append({
                        "sk": sk_val,
                        "tabela": tabela,
                        "camada": "fato",
                        "ano_particao": "serie_historica",
                        "ano": None,
                        "total_linhas": int(total),
                        "fontes": "tse_mandato",
                        "status_completude": "total",
                        "orgao_origem": meta["orgao"],
                        "descricao_recurso": meta["recurso"],
                        "endpoint_recurso": meta["endpoint"],
                        "granularidade": meta["granularidade"],
                        "data_atualizacao": agora,
                        "_hash_registro": sk_val,
                        "_fonte": "catalogo_sistema",
                        "_criado_em": agora,
                        "_atualizado_em": agora,
                    })
                except Exception as erro_fato:
                    log.warning("falha ao catalogar fato %s: %s", tabela, erro_fato)

    return pd.DataFrame(linhas)


def salvar_catalogo() -> Path:
    """Constrói o catálogo e grava como Parquet em dados/dim/dim_catalogo_tabela.parquet."""
    df = construir_catalogo()
    destino_dim = (Path(config.DIM) if config.DIM is not None else Path("dados/dim")) / "dim_catalogo_tabela.parquet"
    destino_ctl = (Path(config.CTL) if config.CTL is not None else Path("dados/_ctl")) / "catalogo_tabelas.parquet"

    destino_dim.parent.mkdir(parents=True, exist_ok=True)
    destino_ctl.parent.mkdir(parents=True, exist_ok=True)

    tabela_arrow = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(tabela_arrow, destino_dim, compression="zstd")
    pq.write_table(tabela_arrow, destino_ctl, compression="zstd")

    log.info("catálogo de tabelas gerado com sucesso: %d registros em %s", len(df), destino_dim)
    return destino_dim
