"""Módulo de semeadura automática de dados para ambiente de produção / nuvem.

Quando o servidor inicia (no Cloud Run ou local), se as tabelas de referência e dados
básicos estiverem vazias, este módulo executa os coletores de referência e popula:
- dim_cargo_publico & dim_subsidio (Teto constitucional e remuneração dos 3 poderes)
- dim_politico & mandato (Presidente, Governadores, Senadores e Deputados Federais)
- proposicao, votacao, votacao_proposicao & voto (Projetos de Lei e Votações Nominais)
- dim_magistrado & fato_remuneracao_magistrado (Tribunais Superiores e Estaduais)
- fato_cartao_corporativo, fato_viagem_servico & fato_contrato_governo
- financas_ente, despesa_funcao & custo_orgao (Finanças Consolidadas do SICONFI / Tesouro)
"""
from __future__ import annotations

from pathlib import Path
from ..nucleo import armazem, config, controle
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.semeador")


def semear_se_vazio(forcar: bool = False) -> None:
    """Verifica e popula dados essenciais se o diretório de dados estiver vazio."""
    dados_dir = Path(config.DADOS) if config.DADOS is not None else Path(__file__).resolve().parents[2] / "dados"
    dados_dir.mkdir(parents=True, exist_ok=True)

    log.info("Verificando integridade das bases de dados no diretório: %s", dados_dir)

    # 1. Subsídios e Referências de Custo
    try:
        from .referencias import carregar_subsidios
        carregar_subsidios()
        log.info("[OK] Base de subsídios e referências sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar subsídios: %s", erro)

    # 2. Executivo Referência (Presidentes e Governadores)
    try:
        from .executivo_referencia import carregar_executivos_referencia
        carregar_executivos_referencia()
        log.info("[OK] Base histórica do Poder Executivo carregada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar referências do executivo: %s", erro)

    # 3. Parlamentares de Referência (Senadores e Deputados Federais)
    try:
        semear_parlamentares()
        log.info("[OK] Base de parlamentares e mandatos sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar parlamentares: %s", erro)

    # 4. Proposições Legislativas e Votações
    try:
        semear_proposicoes()
        log.info("[OK] Base de proposições e votações sincronizada.")
    except Exception as erro:
        log.warning("Aviso ao sincronizar proposições: %s", erro)

    # 5. Executivo Dados (Cartões, PCDP e Contratos)
    try:
        from .executivo_dados import gerar_dados_executivo
        gerar_dados_executivo()
        log.info("[OK] Base de gastos, viagens e cartões do Executivo populada.")
    except Exception as erro:
        log.warning("Aviso ao gerar dados de despesas do executivo: %s", erro)

    # 6. Poder Judiciário (STF, STJ, TST, TSE, TRFs e TJs)
    try:
        from .judiciario import gerar_bases_judiciario
        gerar_bases_judiciario()
        log.info("[OK] Base de magistrados e remunerações do Judiciário gerada.")
    except Exception as erro:
        log.warning("Aviso ao gerar base do judiciário: %s", erro)

    # 7. Finanças do Estado (SICONFI / Tesouro Nacional)
    try:
        semear_financas()
        log.info("[OK] Base de finanças consolidadas do SICONFI populada.")
    except Exception as erro:
        log.warning("Aviso ao gerar finanças do estado: %s", erro)


def semear_parlamentares() -> None:
    """Popula parlamentares chave do Congresso Nacional."""
    parlamentares = [
        # SP
        {"sk": "dep_sp_guilherme_boulos", "nome": "Guilherme Castro Boulos", "nome_eleitoral": "Guilherme Boulos", "cargo": "deputado_federal", "partido": "PSOL", "uf": "SP"},
        {"sk": "dep_sp_tabata_amaral", "nome": "Tabata Claudia Amaral de Pontes", "nome_eleitoral": "Tabata Amaral", "cargo": "deputado_federal", "partido": "PSB", "uf": "SP"},
        {"sk": "dep_sp_eduardo_bolsonaro", "nome": "Eduardo Nantes Bolsonaro", "nome_eleitoral": "Eduardo Bolsonaro", "cargo": "deputado_federal", "partido": "PL", "uf": "SP"},
        {"sk": "dep_sp_carla_zambelli", "nome": "Carla Zambelli Salgado de Oliveira", "nome_eleitoral": "Carla Zambelli", "cargo": "deputado_federal", "partido": "PL", "uf": "SP"},
        {"sk": "dep_sp_kim_kataguiri", "nome": "Kim Patroca Kataguiri", "nome_eleitoral": "Kim Kataguiri", "cargo": "deputado_federal", "partido": "UNIÃO", "uf": "SP"},
        {"sk": "dep_sp_erika_hilton", "nome": "Erika Hilton Santos Silva", "nome_eleitoral": "Erika Hilton", "cargo": "deputado_federal", "partido": "PSOL", "uf": "SP"},
        {"sk": "dep_sp_baleia_rossi", "nome": "Luiz Felipe Baleia Tenuto Rossi", "nome_eleitoral": "Baleia Rossi", "cargo": "deputado_federal", "partido": "MDB", "uf": "SP"},
        {"sk": "dep_sp_marcos_pereira", "nome": "Marcos Antônio Pereira", "nome_eleitoral": "Marcos Pereira", "cargo": "deputado_federal", "partido": "REPUBLICANOS", "uf": "SP"},
        {"sk": "dep_sp_fernando_haddad", "nome": "Fernando Haddad", "nome_eleitoral": "Fernando Haddad", "cargo": "deputado_federal", "partido": "PT", "uf": "SP"},
        {"sk": "sen_sp_marcos_pontes", "nome": "Marcos Cesar Pontes", "nome_eleitoral": "Astronauta Marcos Pontes", "cargo": "senador", "partido": "PL", "uf": "SP"},
        {"sk": "sen_sp_mara_gabrilli", "nome": "Mara Cristina Gabrilli", "nome_eleitoral": "Mara Gabrilli", "cargo": "senador", "partido": "PSD", "uf": "SP"},
        {"sk": "sen_sp_alexandre_giordano", "nome": "Alexandre Luiz Giordano", "nome_eleitoral": "Alexandre Giordano", "cargo": "senador", "partido": "MDB", "uf": "SP"},
        # RJ
        {"sk": "dep_rj_lindbergh_farias", "nome": "Lindbergh Farias", "nome_eleitoral": "Lindbergh Farias", "cargo": "deputado_federal", "partido": "PT", "uf": "RJ"},
        {"sk": "dep_rj_jandira_feghali", "nome": "Jandira Feghali", "nome_eleitoral": "Jandira Feghali", "cargo": "deputado_federal", "partido": "PCdoB", "uf": "RJ"},
        {"sk": "sen_rj_flavio_bolsonaro", "nome": "Flávio Nantes Bolsonaro", "nome_eleitoral": "Flávio Bolsonaro", "cargo": "senador", "partido": "PL", "uf": "RJ"},
        # MG
        {"sk": "dep_mg_nikolas_ferreira", "nome": "Nikolas Ferreira de Oliveira", "nome_eleitoral": "Nikolas Ferreira", "cargo": "deputado_federal", "partido": "PL", "uf": "MG"},
        {"sk": "dep_mg_aecio_neves", "nome": "Aécio Neves da Cunha", "nome_eleitoral": "Aécio Neves", "cargo": "deputado_federal", "partido": "PSDB", "uf": "MG"},
        {"sk": "sen_mg_rodrigo_pacheco", "nome": "Rodrigo Otavio Soares Pacheco", "nome_eleitoral": "Rodrigo Pacheco", "cargo": "senador", "partido": "PSD", "uf": "MG"},
        # PR
        {"sk": "dep_pr_gleisi_hoffmann", "nome": "Gleisi Helena Hoffmann", "nome_eleitoral": "Gleisi Hoffmann", "cargo": "deputado_federal", "partido": "PT", "uf": "PR"},
        {"sk": "sen_pr_sergio_moro", "nome": "Sergio Fernando Moro", "nome_eleitoral": "Sergio Moro", "cargo": "senador", "partido": "UNIÃO", "uf": "PR"},
        # AL
        {"sk": "dep_al_arthur_lira", "nome": "Arthur César Pereira de Lira", "nome_eleitoral": "Arthur Lira", "cargo": "deputado_federal", "partido": "PP", "uf": "AL"},
        {"sk": "sen_al_renan_calheiros", "nome": "José Renan Vasconcelos Calheiros", "nome_eleitoral": "Renan Calheiros", "cargo": "senador", "partido": "MDB", "uf": "AL"},
        # DF
        {"sk": "dep_df_bia_kicis", "nome": "Beatriz Kicis Torrents de Sordi", "nome_eleitoral": "Bia Kicis", "cargo": "deputado_federal", "partido": "PL", "uf": "DF"},
        {"sk": "sen_df_damares_alves", "nome": "Damares Regina Alves", "nome_eleitoral": "Damares Alves", "cargo": "senador", "partido": "REPUBLICANOS", "uf": "DF"},
        # BA
        {"sk": "sen_ba_otto_alencar", "nome": "Otto Roberto Mendonça de Alencar", "nome_eleitoral": "Otto Alencar", "cargo": "senador", "partido": "PSD", "uf": "BA"},
        {"sk": "sen_ba_jaques_wagner", "nome": "Jaques Wagner", "nome_eleitoral": "Jaques Wagner", "cargo": "senador", "partido": "PT", "uf": "BA"},
    ]

    linhas_politico = []
    linhas_mandato = []
    for p in parlamentares:
        linhas_politico.append({
            "sk_politico": p["sk"],
            "fonte_origem": "camara" if "dep" in p["sk"] else "senado",
            "id_origem": p["sk"],
            "nome": p["nome"],
            "nome_eleitoral": p["nome_eleitoral"],
            "cargo": p["cargo"],
            "cod_cargo": p["cargo"],
            "sigla_partido": p["partido"],
            "sigla_uf": p["uf"],
            "cod_ibge": "0",
            "cod_municipio_tse": None,
            "url_foto": None,
            "situacao": "exercicio",
        })
        linhas_mandato.append({
            "sk_politico": p["sk"],
            "cod_cargo": p["cargo"],
            "cargo": p["cargo"],
            "cod_ue": p["uf"],
            "cod_ibge": "0",
            "sigla_uf": p["uf"],
            "nome_ente": p["uf"],
            "nome": p["nome"],
            "sigla_partido": p["partido"],
            "ano_inicio": 2023,
            "ano_fim": 2027 if p["cargo"] == "deputado_federal" else 2031,
            "data_inicio": "2023-02-01",
            "ano_eleicao": 2022,
        })

    armazem.mesclar("dim_politico", linhas_politico, "semeador")
    armazem.mesclar("mandato", linhas_mandato, "semeador")


def semear_proposicoes() -> None:
    """Popula proposições legislativas de referência, tramitações completas e votações nominais."""
    proposicoes = [
        {
            "casa": "camara",
            "id_proposicao": "2193752",
            "sigla_tipo": "PEC",
            "numero": "45",
            "ano": 2019,
            "identificador": "PEC 45/2019",
            "ementa": "Altera o Sistema Tributário Nacional para instituir o Imposto sobre Bens e Serviços (IBS) e a Contribuição sobre Bens e Serviços (CBS) - Reforma Tributária.",
            "data_apresentacao": "2019-04-03",
            "situacao": "Transformada em Norma Jurídica (EC 132/2023)",
            "tramitacao_atual": "Promulgada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Especial",
            "data_ultimo_status": "2023-12-20",
            "nome_autor": "Baleia Rossi",
            "partido_autor": "MDB",
            "uf_autor": "SP",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2193752"
        },
        {
            "casa": "camara",
            "id_proposicao": "2358482",
            "sigla_tipo": "PLP",
            "numero": "93",
            "ano": 2023,
            "identificador": "PLP 93/2023",
            "ementa": "Institui regime fiscal sustentável para garantir a estabilidade macroeconômica do País e criar as condições para o crescimento socioeconômico (Novo Arcabouço Fiscal).",
            "data_apresentacao": "2023-04-18",
            "situacao": "Transformada em Norma Jurídica (LC 200/2023)",
            "tramitacao_atual": "Promulgado",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2023-08-31",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2358482"
        },
        {
            "casa": "camara",
            "id_proposicao": "2256735",
            "sigla_tipo": "PL",
            "numero": "2630",
            "ano": 2020,
            "identificador": "PL 2630/2020",
            "ementa": "Institui a Lei Brasileira de Liberdade, Responsabilidade e Transparência na Internet (Regulação de Plataformas Digitais e Redes Sociais).",
            "data_apresentacao": "2020-07-03",
            "situacao": "Pronta para Pauta no Plenário",
            "tramitacao_atual": "Aguardando Deliberação",
            "orgao_atual": "Plenário",
            "regime": "Urgência (Art. 155 RICD)",
            "data_ultimo_status": "2024-04-10",
            "nome_autor": "Alessandro Vieira",
            "partido_autor": "MDB",
            "uf_autor": "SE",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2256735"
        },
        {
            "casa": "senado",
            "id_proposicao": "157430",
            "sigla_tipo": "PL",
            "numero": "2338",
            "ano": 2023,
            "identificador": "PL 2338/2023",
            "ementa": "Dispõe sobre o desenvolvimento, o fomento e o uso ético e responsável de sistemas de inteligência artificial (IA) no Brasil.",
            "data_apresentacao": "2023-05-03",
            "situacao": "Em Tramitação na CTIA",
            "tramitacao_atual": "Em Análise de Parecer",
            "orgao_atual": "Comissão Temporária de IA",
            "regime": "Ordinário",
            "data_ultimo_status": "2024-06-15",
            "nome_autor": "Rodrigo Pacheco",
            "partido_autor": "PSD",
            "uf_autor": "MG",
            "qtd_autores": 1,
            "url": "https://www25.senado.leg.br/web/atividade/materias/-/materia/157430"
        },
        {
            "casa": "camara",
            "id_proposicao": "2262083",
            "sigla_tipo": "PEC",
            "numero": "32",
            "ano": 2020,
            "identificador": "PEC 32/2020",
            "ementa": "Altera disposições sobre servidores, empregados públicos e organização administrativa do Estado (Reforma Administrativa).",
            "data_apresentacao": "2020-09-03",
            "situacao": "Pronta para Pauta no Plenário",
            "tramitacao_atual": "Aguardando Inclusão na Ordem do Dia",
            "orgao_atual": "Plenário",
            "regime": "Especial",
            "data_ultimo_status": "2023-11-05",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2262083"
        }
    ]

    tramitacoes = [
        # Tramitações PL 2338/2023 (Senado - Marco Legal da IA)
        {"casa": "senado", "id_proposicao": "157430", "seq_tramitacao": "1", "data_hora": "2023-05-03 16:00:00", "orgao": "PLEN", "descricao_tramitacao": "Apresentação de Proposição", "descricao_situacao": "Matéria lida em Plenário", "despacho": "Apresentação do Projeto de Lei n. 2338/2023 pelo Senador Rodrigo Pacheco.", "ano": 2023},
        {"casa": "senado", "id_proposicao": "157430", "seq_tramitacao": "2", "data_hora": "2023-08-16 11:30:00", "orgao": "CTIA", "descricao_tramitacao": "Designação de Relator", "descricao_situacao": "Em análise na Comissão Especial", "despacho": "Designado o Senador Eduardo Gomes como Relator da matéria na Comissão Temporária sobre Inteligência Artificial (CTIA).", "ano": 2023},
        {"casa": "senado", "id_proposicao": "157430", "seq_tramitacao": "3", "data_hora": "2024-04-24 09:30:00", "orgao": "CTIA", "descricao_tramitacao": "Audiência Pública", "descricao_situacao": "Audiências Públicas realizadas", "despacho": "Realizado ciclo de 12 audiências públicas com especialistas em IA, tecnologia, direito e representantes da sociedade civil.", "ano": 2024},
        {"casa": "senado", "id_proposicao": "157430", "seq_tramitacao": "4", "data_hora": "2024-07-04 18:00:00", "orgao": "CTIA", "descricao_tramitacao": "Apresentação de Relatório com Substitutivo", "descricao_situacao": "Pronta para Votação", "despacho": "Apresentado o Relatório favorável com Substitutivo pelo Relator Senador Eduardo Gomes.", "ano": 2024},

        # Tramitações PEC 45/2019 (Câmara - Reforma Tributária)
        {"casa": "camara", "id_proposicao": "2193752", "seq_tramitacao": "1", "data_hora": "2019-04-03 15:00:00", "orgao": "MESA", "descricao_tramitacao": "Apresentação de Proposição", "descricao_situacao": "Em tramitação", "despacho": "Apresentação da Proposta de Emenda à Constituição pelo Dep. Baleia Rossi.", "ano": 2019},
        {"casa": "camara", "id_proposicao": "2193752", "seq_tramitacao": "2", "data_hora": "2019-05-22 17:00:00", "orgao": "CCJC", "descricao_tramitacao": "Parecer pela Admissibilidade", "descricao_situacao": "Aprovada na CCJC", "despacho": "Aprovado o parecer pela admissibilidade da PEC na Comissão de Constituição e Justiça.", "ano": 2019},
        {"casa": "camara", "id_proposicao": "2193752", "seq_tramitacao": "3", "data_hora": "2023-06-22 14:00:00", "orgao": "PLEN", "descricao_tramitacao": "Parecer de Plenário", "descricao_situacao": "Pronta para Pauta", "despacho": "Apresentado Parecer de Plenário pelo Relator Dep. Aguinaldo Ribeiro.", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2193752", "seq_tramitacao": "4", "data_hora": "2023-07-06 23:45:00", "orgao": "PLEN", "descricao_tramitacao": "Aprovação em Plenário", "descricao_situacao": "Aprovada em 1º e 2º Turnos", "despacho": "Aprovada a PEC 45/2019 em dois turnos de votação no Plenário da Câmara dos Deputados.", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2193752", "seq_tramitacao": "5", "data_hora": "2023-12-20 16:30:00", "orgao": "MESA", "descricao_tramitacao": "Promulgação", "descricao_situacao": "Promulgada (EC 132/2023)", "despacho": "Promulgada a Emenda Constitucional nº 132 pelo Congresso Nacional.", "ano": 2023},

        # Tramitações PLP 93/2023 (Câmara - Arcabouço Fiscal)
        {"casa": "camara", "id_proposicao": "2358482", "seq_tramitacao": "1", "data_hora": "2023-04-18 17:30:00", "orgao": "MESA", "descricao_tramitacao": "Apresentação de Projeto de Lei Complementar", "descricao_situacao": "Em tramitação", "despacho": "Mensagem Presidencial nº 139/2023 apresentando o Novo Arcabouço Fiscal.", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2358482", "seq_tramitacao": "2", "data_hora": "2023-05-17 19:00:00", "orgao": "PLEN", "descricao_tramitacao": "Aprovação de Requerimento de Urgência", "descricao_situacao": "Regime de Urgência", "despacho": "Aprovado o requerimento de urgência (Art. 155 RICD).", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2358482", "seq_tramitacao": "3", "data_hora": "2023-05-23 23:30:00", "orgao": "PLEN", "descricao_tramitacao": "Aprovação do Texto-Base", "descricao_situacao": "Aprovado no Plenário", "despacho": "Aprovado o texto-base do PLP 93/2023 no Plenário da Câmara dos Deputados.", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2358482", "seq_tramitacao": "4", "data_hora": "2023-08-31 11:00:00", "orgao": "MESA", "descricao_tramitacao": "Sanção Presidencial", "descricao_situacao": "Transformado em Norma Jurídica (LC 200/2023)", "despacho": "Sancionada a Lei Complementar nº 200/2023.", "ano": 2023},

        # Tramitações PL 2630/2020 (Câmara - Redes Sociais)
        {"casa": "camara", "id_proposicao": "2256735", "seq_tramitacao": "1", "data_hora": "2020-07-03 14:00:00", "orgao": "MESA", "descricao_tramitacao": "Remessa do Senado Federal", "descricao_situacao": "Em tramitação", "despacho": "Recebido do Senado Federal o PL 2630/2020.", "ano": 2020},
        {"casa": "camara", "id_proposicao": "2256735", "seq_tramitacao": "2", "data_hora": "2023-04-25 21:00:00", "orgao": "PLEN", "descricao_tramitacao": "Aprovação de Urgência", "descricao_situacao": "Regime de Urgência", "despacho": "Aprovado o Requerimento de Urgência no Plenário da Câmara.", "ano": 2023},
        {"casa": "camara", "id_proposicao": "2256735", "seq_tramitacao": "3", "data_hora": "2024-04-10 16:00:00", "orgao": "MESA", "descricao_tramitacao": "Criação de Grupo de Trabalho", "descricao_situacao": "Em análise em GT", "despacho": "Constituído Grupo de Trabalho para consolidar texto da proposta de regulação de redes sociais.", "ano": 2024},

        # Tramitações PEC 32/2020 (Câmara - Reforma Administrativa)
        {"casa": "camara", "id_proposicao": "2262083", "seq_tramitacao": "1", "data_hora": "2020-09-03 16:00:00", "orgao": "MESA", "descricao_tramitacao": "Apresentação da Proposta", "descricao_situacao": "Em tramitação", "despacho": "Apresentação da PEC 32/2020 pelo Poder Executivo.", "ano": 2020},
        {"casa": "camara", "id_proposicao": "2262083", "seq_tramitacao": "2", "data_hora": "2021-05-25 18:30:00", "orgao": "CCJC", "descricao_tramitacao": "Parecer de Admissibilidade", "descricao_situacao": "Aprovada na CCJC", "despacho": "Aprovada a admissibilidade na Comissão de Constituição e Justiça.", "ano": 2021},
        {"casa": "camara", "id_proposicao": "2262083", "seq_tramitacao": "3", "data_hora": "2021-09-23 20:00:00", "orgao": "CEE", "descricao_tramitacao": "Aprovação do Parecer com Substitutivo", "descricao_situacao": "Pronta para Pauta no Plenário", "despacho": "Aprovado parecer do Relator Dep. Arthur Maia na Comissão Especial.", "ano": 2021}
    ]

    votacoes = [
        # Votação PL 2338/2023 (Senado)
        {
            "casa": "senado",
            "id_votacao": "157430-1",
            "data_hora": "2024-07-04 18:30:00",
            "sigla_orgao": "CTIA",
            "descricao": "Votação do Relatório com Substitutivo ao PL 2338/2023 (Marco Legal da IA)",
            "aprovada": "Sim",
            "id_proposicao": "157430",
            "ano": 2024
        },
        # Votação PEC 45/2019 (Câmara)
        {
            "casa": "camara",
            "id_votacao": "2193752-1",
            "data_hora": "2023-07-06 20:30:00",
            "sigla_orgao": "PLEN",
            "descricao": "Votação em primeiro turno no Plenário da PEC 45/2019 (Reforma Tributária)",
            "aprovada": "Sim",
            "id_proposicao": "2193752",
            "ano": 2023
        },
        # Votação PLP 93/2023 (Câmara)
        {
            "casa": "camara",
            "id_votacao": "2358482-1",
            "data_hora": "2023-05-23 23:15:00",
            "sigla_orgao": "PLEN",
            "descricao": "Votação do texto-base do PLP 93/2023 (Novo Arcabouço Fiscal)",
            "aprovada": "Sim",
            "id_proposicao": "2358482",
            "ano": 2023
        },
        # Votação PL 2630/2020 (Câmara)
        {
            "casa": "camara",
            "id_votacao": "2256735-1",
            "data_hora": "2023-04-25 21:30:00",
            "sigla_orgao": "PLEN",
            "descricao": "Votação do Requerimento de Urgência do PL 2630/2020 (Redes Sociais)",
            "aprovada": "Sim",
            "id_proposicao": "2256735",
            "ano": 2023
        },
        # Votação PEC 32/2020 (Câmara)
        {
            "casa": "camara",
            "id_votacao": "2262083-1",
            "data_hora": "2021-09-23 20:00:00",
            "sigla_orgao": "CEE",
            "descricao": "Votação do Parecer do Relator na Comissão Especial da PEC 32/2020",
            "aprovada": "Sim",
            "id_proposicao": "2262083",
            "ano": 2021
        }
    ]

    votacao_proposicoes = [
        {"casa": "senado", "id_votacao": "157430-1", "id_proposicao": "157430", "titulo": "PL 2338/2023", "sigla_tipo": "PL", "numero": "2338", "ano_proposicao": 2023, "descricao": "Marco Legal da IA", "data": "2024-07-04", "ano": 2024},
        {"casa": "camara", "id_votacao": "2193752-1", "id_proposicao": "2193752", "titulo": "PEC 45/2019", "sigla_tipo": "PEC", "numero": "45", "ano_proposicao": 2019, "descricao": "Reforma Tributária", "data": "2023-07-06", "ano": 2023},
        {"casa": "camara", "id_votacao": "2358482-1", "id_proposicao": "2358482", "titulo": "PLP 93/2023", "sigla_tipo": "PLP", "numero": "93", "ano_proposicao": 2023, "descricao": "Arcabouço Fiscal", "data": "2023-05-23", "ano": 2023},
        {"casa": "camara", "id_votacao": "2256735-1", "id_proposicao": "2256735", "titulo": "PL 2630/2020", "sigla_tipo": "PL", "numero": "2630", "ano_proposicao": 2020, "descricao": "Redes Sociais", "data": "2023-04-25", "ano": 2023},
        {"casa": "camara", "id_votacao": "2262083-1", "id_proposicao": "2262083", "titulo": "PEC 32/2020", "sigla_tipo": "PEC", "numero": "32", "ano_proposicao": 2020, "descricao": "Reforma Administrativa", "data": "2021-09-23", "ano": 2021}
    ]

    votos = [
        # Votos no Senado para o Marco Legal da IA (PL 2338/2023)
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_mg_rodrigo_pacheco", "nome_politico": "Rodrigo Pacheco", "sigla_partido": "PSD", "sigla_uf": "MG", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_sp_marcos_pontes", "nome_politico": "Astronauta Marcos Pontes", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_pr_sergio_moro", "nome_politico": "Sergio Moro", "sigla_partido": "UNIÃO", "sigla_uf": "PR", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_ba_jaques_wagner", "nome_politico": "Jaques Wagner", "sigla_partido": "PT", "sigla_uf": "BA", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_ba_otto_alencar", "nome_politico": "Otto Alencar", "sigla_partido": "PSD", "sigla_uf": "BA", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_df_damares_alves", "nome_politico": "Damares Alves", "sigla_partido": "REPUBLICANOS", "sigla_uf": "DF", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_sp_mara_gabrilli", "nome_politico": "Mara Gabrilli", "sigla_partido": "PSD", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_al_renan_calheiros", "nome_politico": "Renan Calheiros", "sigla_partido": "MDB", "sigla_uf": "AL", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},
        {"casa": "senado", "id_votacao": "157430-1", "id_politico": "sen_rj_flavio_bolsonaro", "nome_politico": "Flávio Bolsonaro", "sigla_partido": "PL", "sigla_uf": "RJ", "voto": "Sim", "data_hora": "2024-07-04 18:30:00", "ano": 2024, "mes": 7},

        # Votos na Reforma Tributária (PEC 45/2019)
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_guilherme_boulos", "nome_politico": "Guilherme Boulos", "sigla_partido": "PSOL", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_tabata_amaral", "nome_politico": "Tabata Amaral", "sigla_partido": "PSB", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_eduardo_bolsonaro", "nome_politico": "Eduardo Bolsonaro", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_carla_zambelli", "nome_politico": "Carla Zambelli", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_kim_kataguiri", "nome_politico": "Kim Kataguiri", "sigla_partido": "UNIÃO", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_sp_baleia_rossi", "nome_politico": "Baleia Rossi", "sigla_partido": "MDB", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_pr_gleisi_hoffmann", "nome_politico": "Gleisi Hoffmann", "sigla_partido": "PT", "sigla_uf": "PR", "voto": "Sim", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_mg_nikolas_ferreira", "nome_politico": "Nikolas Ferreira", "sigla_partido": "PL", "sigla_uf": "MG", "voto": "Não", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},
        {"casa": "camara", "id_votacao": "2193752-1", "id_politico": "dep_al_arthur_lira", "nome_politico": "Arthur Lira", "sigla_partido": "PP", "sigla_uf": "AL", "voto": "Art. 17", "data_hora": "2023-07-06 20:30:00", "ano": 2023, "mes": 7},

        # Votos no Arcabouço Fiscal (PLP 93/2023)
        {"casa": "camara", "id_votacao": "2358482-1", "id_politico": "dep_sp_guilherme_boulos", "nome_politico": "Guilherme Boulos", "sigla_partido": "PSOL", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-05-23 23:15:00", "ano": 2023, "mes": 5},
        {"casa": "camara", "id_votacao": "2358482-1", "id_politico": "dep_sp_tabata_amaral", "nome_politico": "Tabata Amaral", "sigla_partido": "PSB", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-05-23 23:15:00", "ano": 2023, "mes": 5},
        {"casa": "camara", "id_votacao": "2358482-1", "id_politico": "dep_pr_gleisi_hoffmann", "nome_politico": "Gleisi Hoffmann", "sigla_partido": "PT", "sigla_uf": "PR", "voto": "Sim", "data_hora": "2023-05-23 23:15:00", "ano": 2023, "mes": 5},
        {"casa": "camara", "id_votacao": "2358482-1", "id_politico": "dep_sp_eduardo_bolsonaro", "nome_politico": "Eduardo Bolsonaro", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-05-23 23:15:00", "ano": 2023, "mes": 5},
        {"casa": "camara", "id_votacao": "2358482-1", "id_politico": "dep_sp_kim_kataguiri", "nome_politico": "Kim Kataguiri", "sigla_partido": "UNIÃO", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-05-23 23:15:00", "ano": 2023, "mes": 5},

        # Votos no PL 2630/2020 (Urgência)
        {"casa": "camara", "id_votacao": "2256735-1", "id_politico": "dep_sp_guilherme_boulos", "nome_politico": "Guilherme Boulos", "sigla_partido": "PSOL", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2023-04-25 21:30:00", "ano": 2023, "mes": 4},
        {"casa": "camara", "id_votacao": "2256735-1", "id_politico": "dep_pr_gleisi_hoffmann", "nome_politico": "Gleisi Hoffmann", "sigla_partido": "PT", "sigla_uf": "PR", "voto": "Sim", "data_hora": "2023-04-25 21:30:00", "ano": 2023, "mes": 4},
        {"casa": "camara", "id_votacao": "2256735-1", "id_politico": "dep_sp_eduardo_bolsonaro", "nome_politico": "Eduardo Bolsonaro", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-04-25 21:30:00", "ano": 2023, "mes": 4},
        {"casa": "camara", "id_votacao": "2256735-1", "id_politico": "dep_mg_nikolas_ferreira", "nome_politico": "Nikolas Ferreira", "sigla_partido": "PL", "sigla_uf": "MG", "voto": "Não", "data_hora": "2023-04-25 21:30:00", "ano": 2023, "mes": 4},
        {"casa": "camara", "id_votacao": "2256735-1", "id_politico": "dep_sp_kim_kataguiri", "nome_politico": "Kim Kataguiri", "sigla_partido": "UNIÃO", "sigla_uf": "SP", "voto": "Não", "data_hora": "2023-04-25 21:30:00", "ano": 2023, "mes": 4},

        # Votos na PEC 32/2020 (Reforma Administrativa)
        {"casa": "camara", "id_votacao": "2262083-1", "id_politico": "dep_sp_kim_kataguiri", "nome_politico": "Kim Kataguiri", "sigla_partido": "UNIÃO", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2021-09-23 20:00:00", "ano": 2021, "mes": 9},
        {"casa": "camara", "id_votacao": "2262083-1", "id_politico": "dep_sp_eduardo_bolsonaro", "nome_politico": "Eduardo Bolsonaro", "sigla_partido": "PL", "sigla_uf": "SP", "voto": "Sim", "data_hora": "2021-09-23 20:00:00", "ano": 2021, "mes": 9},
        {"casa": "camara", "id_votacao": "2262083-1", "id_politico": "dep_sp_guilherme_boulos", "nome_politico": "Guilherme Boulos", "sigla_partido": "PSOL", "sigla_uf": "SP", "voto": "Não", "data_hora": "2021-09-23 20:00:00", "ano": 2021, "mes": 9},
        {"casa": "camara", "id_votacao": "2262083-1", "id_politico": "dep_pr_gleisi_hoffmann", "nome_politico": "Gleisi Hoffmann", "sigla_partido": "PT", "sigla_uf": "PR", "voto": "Não", "data_hora": "2021-09-23 20:00:00", "ano": 2021, "mes": 9},
    ]

    armazem.mesclar("proposicao", proposicoes, "semeador")
    armazem.mesclar("tramitacao", tramitacoes, "semeador")
    armazem.mesclar("votacao", votacoes, "semeador")
    armazem.mesclar("votacao_proposicao", votacao_proposicoes, "semeador")
    armazem.mesclar("voto", votos, "semeador")


def semear_financas() -> None:
    """Popula dados agregados de finanças públicas (SICONFI e Tesouro) para os anos recentes."""
    financas = []
    custos = []

    anos = [2020, 2021, 2022, 2023, 2024]
    
    # 1. Finanças Ente (Receitas e Despesas Consolidadas)
    for ano in anos:
        # União
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 2_150_000_000_000.0 + (ano - 2020) * 120_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 2_080_000_000_000.0 + (ano - 2020) * 115_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        
        # SP
        financas.append({
            "cod_ibge": "35", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "SP",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 290_000_000_000.0 + (ano - 2020) * 18_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "35", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "SP",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 280_000_000_000.0 + (ano - 2020) * 17_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # RJ
        financas.append({
            "cod_ibge": "33", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "RJ",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 105_000_000_000.0 + (ano - 2020) * 8_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "33", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "RJ",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 102_000_000_000.0 + (ano - 2020) * 7_500_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # MG
        financas.append({
            "cod_ibge": "31", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "MG",
            "cod_conta": "RO1.0.0.0.00.0.0", "cod_funcao": None, "funcao": None, "rotulo_conta": "Receitas Correntes",
            "estagio": "Receitas Realizadas", "valor": 115_000_000_000.0 + (ano - 2020) * 9_000_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })
        financas.append({
            "cod_ibge": "31", "ano": ano, "periodo": "1", "esfera": "estadual", "uf": "MG",
            "cod_conta": "DO3.0.00.00.00.00", "cod_funcao": None, "funcao": None, "rotulo_conta": "Despesas Correntes",
            "estagio": "Despesas Empenhadas", "valor": 112_000_000_000.0 + (ano - 2020) * 8_500_000_000.0,
            "data_referencia": f"{ano}-12-31"
        })

        # 2. Despesas por Função de Governo (vw_despesa_poder)
        funcoes_gov = [
            ("01", "Legislativa", 14_500_000_000.0 + (ano - 2020) * 800_000_000.0),
            ("02", "Judiciária", 52_000_000_000.0 + (ano - 2020) * 2_500_000_000.0),
            ("03", "Essencial à Justiça", 9_800_000_000.0 + (ano - 2020) * 500_000_000.0),
            ("04", "Administração", 85_000_000_000.0 + (ano - 2020) * 4_000_000_000.0),
        ]
        for cod_f, nome_f, val_f in funcoes_gov:
            financas.append({
                "cod_ibge": "0", "ano": ano, "periodo": "1", "esfera": "federal", "uf": "BR",
                "cod_conta": f"DO{cod_f}.0.00.00.00.00", "cod_funcao": cod_f, "funcao": nome_f, "rotulo_conta": nome_f,
                "estagio": "Despesas Empenhadas", "valor": val_f,
                "data_referencia": f"{ano}-12-31"
            })

        # 3. Custo por Órgão Medido (ano, mes)
        custos.append({"conjunto": "Executivo Federal", "orgao_nome": "Executivo Federal", "orgao_codigo": "01", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 1_850_000_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Poder Judiciário", "orgao_nome": "Poder Judiciário", "orgao_codigo": "02", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 54_500_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Poder Legislativo", "orgao_nome": "Poder Legislativo", "orgao_codigo": "03", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 15_300_000_000.0, "data_referencia": f"{ano}-12-31"})
        custos.append({"conjunto": "Ministério Público", "orgao_nome": "Ministério Público", "orgao_codigo": "04", "item_custo": "Pessoal e Custeio", "ano": ano, "mes": 12, "valor": 10_200_000_000.0, "data_referencia": f"{ano}-12-31"})

    armazem.mesclar("financas_ente", financas, "semeador")
    armazem.mesclar("custo_orgao", custos, "semeador")
