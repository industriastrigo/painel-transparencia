"""Catálogo e Inventário de Tabelas do Acervo Parquet.

Gera uma tabela física (`dados/dim/dim_catalogo_tabela.parquet`) e view analítica
que lista CADA tabela, CADA ano coletado (uma linha por ano), volume de linhas no acervo,
volume de linhas na origem, fontes oficiais, órgão de origem, endpoint correspondente,
URL parametrizada do GET e regras de autenticação (incluindo chave individual da CGU).
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

METADADOS_TABELAS: dict[str, dict[str, Any]] = {
    "dim_ente": {
        "orgao": "IBGE",
        "recurso": "Cadastro de Municípios, Estados e Regiões do Brasil",
        "endpoint": "GET /agregados/6579 (SIDRA) + Malhas GeoJSON",
        "url_origem": "https://servicodados.ibge.gov.br/api/docs",
        "url_template": "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do IBGE (sem necessidade de chave).",
        "granularidade": "1 ente federativo (cod_ibge)",
        "completude_default": "total",
        "linhas_origem_default": 5599,
    },
    "dim_politico": {
        "orgao": "TSE / Congresso Nacional",
        "recurso": "Candidatos eleitos e parlamentares federais",
        "endpoint": "GET /divulgacandcontas/candidaturas + GET /deputados + GET /senadores",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/api/v2/deputados",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta (sem necessidade de chave).",
        "granularidade": "1 autoridade / parlamentar (fonte_origem, id_origem)",
        "completude_default": "total",
        "linhas_origem_default": 69973,
    },
    "dim_cargo_publico": {
        "orgao": "Constituição Federal / Leis Orgânicas",
        "recurso": "Catálogo canônico de cargos públicos dos 3 Poderes e esferas",
        "endpoint": "referencias/cargos_publicos.csv",
        "url_origem": "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
        "url_template": "referencias/cargos_publicos.csv",
        "exige_chave": False,
        "instrucao_auth": "Tabela canônica normativa transcrita da legislação.",
        "granularidade": "1 cargo público canônico (cod_cargo)",
        "completude_default": "total",
        "linhas_origem_default": 19,
    },
    "dim_cargo": {
        "orgao": "TSE",
        "recurso": "Cargos eletivos do sistema eleitoral brasileiro",
        "endpoint": "TSE DivulgaCandContas",
        "url_origem": "https://dadosabertos.tse.jus.br/",
        "url_template": "https://divulgacandcontas.tse.jus.br/divulga/rest/v1/cargo",
        "exige_chave": False,
        "instrucao_auth": "Tabela oficial do Tribunal Superior Eleitoral.",
        "granularidade": "1 cargo eletivo",
        "completude_default": "total",
        "linhas_origem_default": 13,
    },
    "dim_partido": {
        "orgao": "TSE",
        "recurso": "Partidos políticos com registro ativo no TSE",
        "endpoint": "TSE Partidos",
        "url_origem": "https://www.tse.jus.br/partidos/partidos-registrados-no-tse",
        "url_template": "https://www.tse.jus.br/partidos/partidos-registrados-no-tse",
        "exige_chave": False,
        "instrucao_auth": "Relação oficial de partidos com registro no TSE (30 ativos + 2 incorporados).",
        "granularidade": "1 partido político (sigla)",
        "completude_default": "total",
        "linhas_origem_default": 32,
    },
    "dim_metrica": {
        "orgao": "IBGE / Tesouro Nacional",
        "recurso": "Dicionário de métricas e indicadores socioeconômicos e fiscais",
        "endpoint": "referencias/metricas.csv",
        "url_origem": "https://www.tesourotransparente.gov.br/",
        "url_template": "referencias/metricas.csv",
        "exige_chave": False,
        "instrucao_auth": "Dicionário de métricas e fórmulas do sistema.",
        "granularidade": "1 métrica / indicador",
        "completude_default": "total",
        "linhas_origem_default": 4,
    },
    "dim_de_para_ente": {
        "orgao": "TSE / IBGE",
        "recurso": "Mapeamento de-para entre Unidades Eleitorais (TSE) e Códigos IBGE",
        "endpoint": "TSE + IBGE",
        "url_origem": "https://dadosabertos.tse.jus.br/",
        "url_template": "referencias/de_para_entes.csv",
        "exige_chave": False,
        "instrucao_auth": "Ponte cadastral calculada por cruzamento determinístico (5.568 municípios com prefeitura).",
        "granularidade": "1 de-para ente (fonte_origem, id_origem)",
        "completude_default": "total",
        "linhas_origem_default": 5568,
    },
    "dim_magistrado": {
        "orgao": "CNJ (Conselho Nacional de Justiça)",
        "recurso": "Ministros de Tribunais Superiores e Presidentes de Tribunais (STF, STJ, TST, TRFs, TJs)",
        "endpoint": "Painel de Remuneração dos Magistrados CNJ",
        "url_origem": "https://paineis.cnj.jus.br/QvAJAXZfc/opendoc.htm?document=qvw_l/PainelCNJ.qvw",
        "url_template": "https://paineis.cnj.jus.br/QvAJAXZfc/opendoc.htm?document=qvw_l/PainelCNJ.qvw",
        "exige_chave": False,
        "instrucao_auth": "Painel oficial do Conselho Nacional de Justiça.",
        "granularidade": "1 magistrado / ministro",
        "completude_default": "amostra_cupula",
        "linhas_origem_default": 31,
    },
    "dim_subsidio": {
        "orgao": "Legislação / Diários Oficiais",
        "recurso": "Subsídios fixados em lei por cargo público constitucional",
        "endpoint": "referencias/subsidios.csv",
        "url_origem": "https://www.planalto.gov.br/",
        "url_template": "referencias/subsidios.csv",
        "exige_chave": False,
        "instrucao_auth": "Valores transcritos de normas federais e estaduais com citação legal e vigências históricas.",
        "granularidade": "1 subsídio normativo por cargo e vigência",
        "completude_default": "total",
        "linhas_origem_default": 26,
    },
    "despesa_parlamentar": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Cota para o Exercício da Atividade Parlamentar (CEAP)",
        "endpoint": "GET /cotas/Ano-{ano}.csv.zip (Câmara dos Deputados)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 nota fiscal / documento de reembolso",
        "completude_default": "total",
    },
    "proposicao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Proposições Legislativas (PL, PEC, MP, PDC, REQ)",
        "endpoint": "GET /proposicoes (Arquivos em lote diários)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 proposição legislativa",
        "completude_default": "total",
    },
    "votacao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Sessões deliberativas e votações no Plenário",
        "endpoint": "GET /votacoes (Arquivos em lote diários)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 sessão / votação",
        "completude_default": "total",
    },
    "voto": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Votos nominais de deputados federais",
        "endpoint": "GET /votacoes/{id}/votos (Arquivos em lote diários)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 voto nominal por deputado × votação",
        "completude_default": "total",
    },
    "orientacao_bancada": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Orientação partidária oficial nas votações (Sim, Não, Obstrução)",
        "endpoint": "GET /votacoes/{id}/orientacoes (Arquivos diários)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/csv/votacoesOrientacoes-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 orientação por bancada × votação",
        "completude_default": "total",
    },
    "evento": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Eventos da agenda parlamentar (sessões, comissões, audiências)",
        "endpoint": "GET /eventos (Arquivos diários)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 evento legislativo",
        "completude_default": "total",
    },
    "presenca_evento": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Presença nominal de parlamentares em eventos legislativos",
        "endpoint": "GET /eventosPresencaDeputados-{ano}.csv (Câmara dos Deputados)",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/csv/eventosPresencaDeputados-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 presença nominal por deputado × sessão",
        "completude_default": "total",
    },
    "tramitacao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Etapas de tramitação de proposições legislativas",
        "endpoint": "GET /proposicoes/{id}/tramitacoes",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/2418000/tramitacoes",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta da Câmara dos Deputados (sem chave).",
        "granularidade": "1 etapa de tramitação",
        "completude_default": "amostra",
    },
    "emenda_parlamentar": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Execução orçamentária de emendas parlamentares (Individuais, Bancada, Comissão, PIX)",
        "endpoint": "GET /api-de-dados/emendas-parlamentares",
        "url_origem": "https://api.portaldatransparencia.gov.br/swagger-ui.html",
        "url_template": "https://api.portaldatransparencia.gov.br/api-de-dados/emendas-parlamentares?ano={ano}&pagina=1",
        "exige_chave": True,
        "instrucao_auth": "A API da CGU exige chave individual de acesso no cabeçalho 'chave-api-dados'. Cada usuário deve obter a sua gratuitamente em: portaldatransparencia.gov.br/api-de-dados/cadastrar-email e configurá-la na aba 'Atualizar'.",
        "granularidade": "1 emenda orçamentária / documento",
        "completude_default": "total",
    },
    "financas_ente": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Declaração de Contas Anuais (DCA) - Despesas e Receitas por conta contábil",
        "endpoint": "GET /dca (Tesouro Nacional)",
        "url_origem": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
        "url_template": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/dca?an_exercicio={ano}&no_anexo=DCA-Anexo%20I-C",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do Tesouro Nacional / SICONFI (sem chave).",
        "granularidade": "1 conta contábil por ente × ano",
        "completude_default": "total",
    },
    "despesa_funcao": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Relatório Resumido de Execução Orçamentária (RREO Anexo 02) - Despesa por Função de Governo",
        "endpoint": "GET /rreo (Tesouro Nacional)",
        "url_origem": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
        "url_template": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?an_exercicio={ano}&nr_periodo=6&co_tipo_demonstrativo=RREO&no_anexo=RREO-Anexo%2002",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do Tesouro Nacional / SICONFI (sem chave).",
        "granularidade": "1 função/subfunção por ente × bimestre",
        "completude_default": "parcial",
    },
    "indicador_fiscal": {
        "orgao": "SICONFI (Tesouro Nacional)",
        "recurso": "Relatório de Gestão Fiscal (RGF) - Limites de Pessoal e Dívida Consolidada da LRF",
        "endpoint": "GET /rgf (Tesouro Nacional)",
        "url_origem": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
        "url_template": "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf?an_exercicio={ano}&in_periodicidade=Q&nr_periodo=3&co_tipo_demonstrativo=RGF&no_anexo=RGF-Anexo%2001",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do Tesouro Nacional / SICONFI (sem chave).",
        "granularidade": "1 indicador fiscal por ente × quadrimestre/semestre",
        "completude_default": "parcial",
    },
    "transferencia_uniao": {
        "orgao": "SIAFI / Tesouro Nacional",
        "recurso": "Transferências Constitucionais Obrigatórias (FPM, FPE, FUNDEB, Royalties)",
        "endpoint": "GET /transferencias-constitucionais (Tesouro Transparente)",
        "url_origem": "https://www.tesourotransparente.gov.br/ckan/dataset/transferencias-constitucionais-para-municipios",
        "url_template": "https://www.tesourotransparente.gov.br/ckan/dataset/transferencias-constitucionais-para-municipios",
        "exige_chave": False,
        "instrucao_auth": "Conjunto de dados aberto e público do Tesouro Transparente (sem chave).",
        "granularidade": "1 repasse por ente × modalidade × mês",
        "completude_default": "total",
    },
    "operacao_credito": {
        "orgao": "SADIPEM (Tesouro Nacional)",
        "recurso": "Pedidos de Verificação de Limites (PVL) e Operações de Crédito de Estados e Municípios",
        "endpoint": "GET /pvl (SADIPEM Data Lake)",
        "url_origem": "https://apidatalake.tesouro.gov.br/docs/sadipem/",
        "url_template": "https://apidatalake.tesouro.gov.br/ords/sadipem/tt/pvl",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do SADIPEM / Tesouro Nacional (sem chave).",
        "granularidade": "1 pleito / PVL",
        "completude_default": "total",
    },
    "custo_orgao": {
        "orgao": "Tesouro Nacional",
        "recurso": "Custo apurado por Ministério e Órgão do Poder Executivo Federal (Regime de Competência)",
        "endpoint": "GET /custos/tt/demais?an_lanc={ano} (Portal de Custos do Governo Federal)",
        "url_origem": "https://apidatalake.tesouro.gov.br/docs/custos/",
        "url_template": "https://apidatalake.tesouro.gov.br/ords/custos/tt/demais?an_lanc={ano}",
        "exige_chave": False,
        "instrucao_auth": "API pública aberta do Tesouro Nacional / Data Lake de Custos (sem chave).",
        "granularidade": "1 item de custo por órgão × mês",
        "completude_default": "total",
    },
    "cartao_corporativo": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Faturas e despesas do Cartão de Pagamento do Governo Federal (CPGF)",
        "endpoint": "GET /api-de-dados/cartoes",
        "url_origem": "https://api.portaldatransparencia.gov.br/swagger-ui.html",
        "url_template": "https://api.portaldatransparencia.gov.br/api-de-dados/cartoes?mesExtratoInicio=01%2F{ano}&mesExtratoFim=12%2F{ano}&pagina=1",
        "exige_chave": True,
        "instrucao_auth": "A API da CGU exige chave individual de acesso no cabeçalho 'chave-api-dados'. Cada usuário deve obter a sua gratuitamente em: portaldatransparencia.gov.br/api-de-dados/cadastrar-email e configurá-la na aba 'Atualizar'.",
        "granularidade": "1 transação / portador",
        "completude_default": "total",
    },
    "contrato_governo": {
        "orgao": "Portal da Transparência / ComprasGov",
        "recurso": "Contratos administrativos firmados por órgãos federais",
        "endpoint": "GET /api-de-dados/contratos",
        "url_origem": "https://api.portaldatransparencia.gov.br/swagger-ui.html",
        "url_template": "https://api.portaldatransparencia.gov.br/api-de-dados/contratos?dataInicial=01%2F01%2F{ano}&dataFinal=31%2F12%2F{ano}&pagina=1",
        "exige_chave": True,
        "instrucao_auth": "A API da CGU exige chave individual de acesso no cabeçalho 'chave-api-dados'. Cada usuário deve obter a sua gratuitamente em: portaldatransparencia.gov.br/api-de-dados/cadastrar-email e configurá-la na aba 'Atualizar'.",
        "granularidade": "1 contrato administrativo",
        "completude_default": "amostra",
    },
    "viagem_servico": {
        "orgao": "Portal da Transparência (CGU)",
        "recurso": "Diárias e passagens aéreas concedidas a servidores e autoridades federais",
        "endpoint": "GET /api-de-dados/viagens",
        "url_origem": "https://api.portaldatransparencia.gov.br/swagger-ui.html",
        "url_template": "https://api.portaldatransparencia.gov.br/api-de-dados/viagens?dataIdaDe=01%2F01%2F{ano}&dataIdaAte=31%2F12%2F{ano}&pagina=1",
        "exige_chave": True,
        "instrucao_auth": "A API da CGU exige chave individual de acesso no cabeçalho 'chave-api-dados'. Cada usuário deve obter a sua gratuitamente em: portaldatransparencia.gov.br/api-de-dados/cadastrar-email e configurá-la na aba 'Atualizar'.",
        "granularidade": "1 viagem a serviço",
        "completude_default": "amostra",
    },
    "fato_remuneracao_magistrado": {
        "orgao": "CNJ (Conselho Nacional de Justiça)",
        "recurso": "Folhas de pagamento detalhadas de magistrados (Subsídio, Vantagens, Indenizações, Teto)",
        "endpoint": "Painel de Remuneração dos Magistrados CNJ",
        "url_origem": "https://paineis.cnj.jus.br/QvAJAXZfc/opendoc.htm?document=qvw_l/PainelCNJ.qvw",
        "url_template": "https://paineis.cnj.jus.br/QvAJAXZfc/opendoc.htm?document=qvw_l/PainelCNJ.qvw",
        "exige_chave": False,
        "instrucao_auth": "Painel oficial do Conselho Nacional de Justiça.",
        "granularidade": "1 contracheque por magistrado × mês",
        "completude_default": "total",
    },
    "mandato": {
        "orgao": "TSE",
        "recurso": "Histórico de mandatos eletivos municipais, estaduais e federais",
        "endpoint": "TSE DivulgaCand + Referências Históricas",
        "url_origem": "https://dadosabertos.tse.jus.br/",
        "url_template": "https://divulgacandcontas.tse.jus.br/",
        "exige_chave": False,
        "instrucao_auth": "Dados abertos do Tribunal Superior Eleitoral.",
        "granularidade": "1 mandato por político × ciclo",
        "completude_default": "total",
    },
    "indicador_ente": {
        "orgao": "IBGE",
        "recurso": "Indicadores socioeconômicos dos municípios (População, PIB, etc.)",
        "endpoint": "GET /agregados/6579 e GET /agregados/5938",
        "url_origem": "https://servicodados.ibge.gov.br/api/docs",
        "url_template": "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/{ano}/variaveis/9324?localidades=N6[all]",
        "exige_chave": False,
        "instrucao_auth": "API pública do SIDRA / IBGE.",
        "granularidade": "1 indicador por ente × ano",
        "completude_default": "total",
    },
    "votacao_proposicao": {
        "orgao": "Câmara dos Deputados",
        "recurso": "Associação entre matérias legislativas e suas sessões de votação",
        "endpoint": "Câmara dos Deputados",
        "url_origem": "https://dadosabertos.camara.leg.br/swagger/api.html",
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/votacoesProposicoes/csv/votacoesProposicoes-{ano}.csv",
        "exige_chave": False,
        "instrucao_auth": "API aberta da Câmara dos Deputados.",
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
                "url_origem": "https://dados.gov.br",
                "url_template": "n/a",
                "exige_chave": False,
                "instrucao_auth": "Público.",
                "granularidade": "1 registro",
                "completude_default": "total",
                "linhas_origem_default": 0,
            })
            try:
                df = con.execute(f"SELECT * FROM read_parquet('{f.as_posix()}')").df()
                fontes = df["_fonte"].unique().tolist() if "_fonte" in df.columns else ["n/a"]
                total_linhas = len(df)
            except Exception as erro:
                log.warning("erro ao ler dimensao %s: %s", f.name, erro)
                total_linhas = 0
                fontes = ["desconhecida"]

            linhas_origem = meta.get("linhas_origem_default", total_linhas)
            if not linhas_origem or linhas_origem == 0:
                linhas_origem = total_linhas

            sk_val = hashlib.md5(f"{tabela}_dim_vigente".encode("utf-8")).hexdigest()[:16]
            linhas.append({
                "sk": sk_val,
                "tabela": tabela,
                "camada": "dim",
                "ano_particao": "vigente",
                "ano": None,
                "total_linhas": int(total_linhas),
                "linhas_origem": int(linhas_origem),
                "fontes": ", ".join(str(x) for x in fontes),
                "status_completude": meta["completude_default"],
                "orgao_origem": meta["orgao"],
                "descricao_recurso": meta["recurso"],
                "endpoint_recurso": meta["endpoint"],
                "url_origem": meta.get("url_origem", ""),
                "url_requisicao": meta.get("url_template", ""),
                "exige_chave": bool(meta.get("exige_chave", False)),
                "instrucao_auth": meta.get("instrucao_auth", ""),
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
                "url_origem": "https://dados.gov.br",
                "url_template": "n/a",
                "exige_chave": False,
                "instrucao_auth": "Público.",
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
                    qtd_linhas = int(r["qtd_linhas"])

                    completude = meta["completude_default"]
                    if tabela == "despesa_funcao":
                        completude = "parcial_municipios" if ano_int == 2026 else "total_ufs"
                    elif tabela == "indicador_fiscal":
                        completude = "parcial_municipios" if ano_int == 2026 else "total_ufs"
                    elif tabela in ("proposicao", "votacao") and ano_int == 1998:
                        completude = "amostra_historica"

                    url_req = meta.get("url_template", "").format(ano=ano_str) if ano_str else meta.get("url_template", "")

                    # Estima/calcula linhas na origem oficial
                    linhas_origem = qtd_linhas
                    if tabela == "despesa_funcao" and ano_int == 2026:
                        linhas_origem = 233940  # 5.570 municípios × 42 subfunções
                    elif tabela == "indicador_fiscal" and ano_int == 2026:
                        linhas_origem = 144820  # 5.570 municípios × 26 indicadores

                    sk_val = hashlib.md5(f"{tabela}_fato_{ano_str}".encode("utf-8")).hexdigest()[:16]
                    linhas.append({
                        "sk": sk_val,
                        "tabela": tabela,
                        "camada": "fato",
                        "ano_particao": ano_str,
                        "ano": ano_int,
                        "total_linhas": qtd_linhas,
                        "linhas_origem": int(linhas_origem),
                        "fontes": fontes_str,
                        "status_completude": completude,
                        "orgao_origem": meta["orgao"],
                        "descricao_recurso": meta["recurso"],
                        "endpoint_recurso": meta["endpoint"],
                        "url_origem": meta.get("url_origem", ""),
                        "url_requisicao": url_req,
                        "exige_chave": bool(meta.get("exige_chave", False)),
                        "instrucao_auth": meta.get("instrucao_auth", ""),
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
                        "linhas_origem": int(total),
                        "fontes": "tse_mandato",
                        "status_completude": "total",
                        "orgao_origem": meta["orgao"],
                        "descricao_recurso": meta["recurso"],
                        "endpoint_recurso": meta["endpoint"],
                        "url_origem": meta.get("url_origem", ""),
                        "url_requisicao": meta.get("url_template", ""),
                        "exige_chave": bool(meta.get("exige_chave", False)),
                        "instrucao_auth": meta.get("instrucao_auth", ""),
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
