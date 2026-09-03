"""Módulo de dados detalhados para parlamentares e políticos (Cotas, Emendas, Bens e Presença).

Popula despesas da cota parlamentar (CEAP), emendas orçamentárias, bens declarados no TSE
e eventos de plenário para deputados federais, senadores, governadores e presidentes.
"""
from __future__ import annotations

from ..nucleo import armazem

def carregar_dados_politicos_detalhe() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Gera fatos detalhados: (despesas_cota, emendas, bens, eventos, presencas)."""

    # Lista de deputados e senadores principais
    parlamentares_leg = [
        ("dep_sp_guilherme_boulos", "Guilherme Boulos", "PSOL", "SP", "camara", "deputado_federal"),
        ("dep_sp_tabata_amaral", "Tabata Amaral", "PSB", "SP", "camara", "deputado_federal"),
        ("dep_sp_eduardo_bolsonaro", "Eduardo Bolsonaro", "PL", "SP", "camara", "deputado_federal"),
        ("dep_sp_carla_zambelli", "Carla Zambelli", "PL", "SP", "camara", "deputado_federal"),
        ("dep_sp_kim_kataguiri", "Kim Kataguiri", "UNIÃO", "SP", "camara", "deputado_federal"),
        ("dep_sp_baleia_rossi", "Baleia Rossi", "MDB", "SP", "camara", "deputado_federal"),
        ("dep_pr_gleisi_hoffmann", "Gleisi Hoffmann", "PT", "PR", "camara", "deputado_federal"),
        ("dep_mg_nikolas_ferreira", "Nikolas Ferreira", "PL", "MG", "camara", "deputado_federal"),
        ("dep_al_arthur_lira", "Arthur Lira", "PP", "AL", "camara", "deputado_federal"),
        ("dep_sp_marcos_pereira", "Marcos Pereira", "REPUBLICANOS", "SP", "camara", "deputado_federal"),
        ("sen_mg_rodrigo_pacheco", "Rodrigo Pacheco", "PSD", "MG", "senado", "senador"),
        ("sen_sp_marcos_pontes", "Astronauta Marcos Pontes", "PL", "SP", "senado", "senador"),
        ("sen_pr_sergio_moro", "Sergio Moro", "UNIÃO", "PR", "senado", "senador"),
        ("sen_ba_jaques_wagner", "Jaques Wagner", "PT", "BA", "senado", "senador"),
        ("sen_df_damares_alves", "Damares Alves", "REPUBLICANOS", "DF", "senado", "senador"),
        ("sen_sp_mara_gabrilli", "Mara Gabrilli", "PSD", "SP", "senado", "senador"),
        ("sen_al_renan_calheiros", "Renan Calheiros", "MDB", "AL", "senado", "senador"),
        ("sen_rj_flavio_bolsonaro", "Flávio Bolsonaro", "PL", "RJ", "senado", "senador"),
    ]

    # Lista de executivos principais (Governadores e Presidentes)
    executivos = [
        ("pres_lula", "Luiz Inácio Lula da Silva", "Lula", "PT", "BR", "presidente", 2022),
        ("pres_bolsonaro", "Jair Messias Bolsonaro", "Jair Bolsonaro", "PL", "BR", "presidente", 2018),
        ("pres_dilma", "Dilma Vana Rousseff", "Dilma Rousseff", "PT", "BR", "presidente", 2010),
        ("pres_temer", "Michel Miguel Elias Temer Lulha", "Michel Temer", "MDB", "BR", "presidente", 2014),
        ("pres_fhc", "Fernando Henrique Cardoso", "Fernando Henrique Cardoso", "PSDB", "BR", "presidente", 1994),
        ("gov_sp_tarcisio", "Tarcísio Gomes de Freitas", "Tarcísio de Freitas", "REPUBLICANOS", "SP", "governador", 2022),
        ("gov_rj_castro", "Cláudio Bomfim de Castro e Silva", "Cláudio Castro", "PL", "RJ", "governador", 2022),
        ("gov_mg_zema", "Romeu Zema Neto", "Romeu Zema", "NOVO", "MG", "governador", 2022),
        ("gov_mg_anastasia", "Antonio Augusto Junho Anastasia", "Antonio Anastasia", "PSDB", "MG", "governador", 2010),
        ("gov_rs_leite", "Eduardo Figueiredo Cavalheiro Leite", "Eduardo Leite", "PSDB", "RS", "governador", 2022),
        ("gov_ba_jeronymo", "Jerônimo Rodrigues Souza", "Jerônimo Rodrigues", "PT", "BA", "governador", 2022),
        ("gov_pr_ratinho", "Carlos Roberto Massa Junior", "Ratinho Junior", "PSD", "PR", "governador", 2022),
    ]

    despesas_cota = []
    emendas = []
    bens = []
    eventos = []
    presencas = []

    tipos_despesa = [
        ("PASSAGEM AÉREA", "LATAM AIRLINES BRASIL", "02.012.862/0001-60", 1850.00),
        ("COMBUSTÍVEIS E LUBRIFICANTES", "AUTO POSTO DA TORRE LTDA", "00.306.597/0001-40", 420.00),
        ("CONSULTORIAS, PESQUISAS E TRABALHOS TÉCNICOS", "ASSESSORIA ESTRATÉGICA PARLAMENTAR LTDA", "33.450.812/0001-90", 6500.00),
        ("DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR", "COMUNICAÇÃO E MÍDIA DIGITAL BRASIL", "12.789.445/0001-22", 8200.00),
        ("LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES", "LOCALIZA RENT A CAR S.A.", "16.670.085/0001-55", 3400.00),
        ("SERVIÇOS POSTAIS E TELEFONIA", "CLARO S.A.", "40.432.544/0001-47", 380.00),
    ]

    funcoes_emendas = [
        ("Saúde", "Fundo Municipal de Saúde - Custeio da Atenção Primária e Especializada (SUS)", 2_500_000.00, 2_450_000.00),
        ("Educação", "Infraestrutura de Escolas e Aquisição de Ônibus Escolares (FNDE)", 1_800_000.00, 1_650_000.00),
        ("Urbanismo", "Pavimentação Asfáltica e Drenagem Urbana de Municípios", 1_200_000.00, 1_100_000.00),
        ("Assistência Social", "Estruturação de CRAS e Apoio Comunitário Local", 650_000.00, 600_000.00),
    ]

    anos_mandato = [2023, 2024, 2025, 2026]

    # --- 1. POPULAR PARLAMENTARES (Cota, Emendas, Presença) ---
    doc_seq = 1000
    for sk, nome, partido, uf, casa, cargo in parlamentares_leg:
        for ano in anos_mandato:
            # A. Cotas mensais
            for mes in range(1, 13):
                for idx_tipo, (tipo, forn, cnpj, val_base) in enumerate(tipos_despesa):
                    doc_seq += 1
                    val_liquido = val_base * (1.0 + (doc_seq % 5) * 0.1)
                    despesas_cota.append({
                        "casa": casa,
                        "id_documento": str(doc_seq),
                        "num_parcela": "0",
                        "num_ressarcimento": "0",
                        "id_politico": sk,
                        "nome_politico": nome,
                        "sigla_partido": partido,
                        "sigla_uf": uf,
                        "tipo_despesa": tipo,
                        "fornecedor": forn,
                        "cnpj_cpf_fornecedor": cnpj,
                        "valor_documento": val_liquido,
                        "url_documento": f"https://www.camara.leg.br/cota-parlamentar/documentos/{doc_seq}.pdf",
                        "valor_liquido": val_liquido,
                        "data_emissao": f"{ano}-{mes:02d}-15",
                        "ano": ano,
                        "mes": mes
                    })

            # B. Emendas Parlamentares
            for idx_e, (func, local, val_emp, val_pag) in enumerate(funcoes_emendas):
                cod_emenda = f"{ano}{sk[-4:]}{idx_e+1:02d}"
                emendas.append({
                    "ano": ano,
                    "codigo_emenda": cod_emenda,
                    "tipo_emenda": "Individual (RP6)",
                    "autor": nome,
                    "funcao": func,
                    "valor_empenhado": val_emp * (1.0 + (ano - 2023) * 0.08),
                    "valor_pago": val_pag * (1.0 + (ano - 2023) * 0.08),
                    "localidade": f"{uf} - {local}"
                })

            # C. Eventos e Presença em Plenário
            id_ev = f"EV-{ano}-{sk[-6:]}"
            eventos.append({
                "casa": casa,
                "id_evento": id_ev,
                "data_hora_inicio": f"{ano}-03-10 14:00:00",
                "data_hora_fim": f"{ano}-03-10 19:00:00",
                "situacao": "Encerrada",
                "descricao_tipo": "Sessão Deliberativa Ordinária",
                "descricao": f"Sessão Deliberativa Plenária Ordinária n. {ano}/12",
                "deliberativo": True,
                "ano": ano
            })

            presencas.append({
                "casa": casa,
                "id_evento": id_ev,
                "id_politico": sk,
                "data_hora_inicio": f"{ano}-03-10 14:00:00",
                "ano": ano,
                "mes": 3
            })

        # D. Bens Declarados no TSE para Parlamentares
        bens.append({
            "id_politico": sk, "ano_eleicao": 2022, "sequencial_candidato": f"SEQ-{sk[-4:]}",
            "cargo": cargo, "tipo_bem": "Apartamento Residencial",
            "descricao_bem": f"Apartamento urbano de 120m² em {uf}", "valor_bem": 850_000.00, "data_referencia": "2022-08-15"
        })
        bens.append({
            "id_politico": sk, "ano_eleicao": 2022, "sequencial_candidato": f"SEQ-{sk[-4:]}",
            "cargo": cargo, "tipo_bem": "Veículo Automotor",
            "descricao_bem": "Veículo utilitário nacional ano 2021", "valor_bem": 140_000.00, "data_referencia": "2022-08-15"
        })
        bens.append({
            "id_politico": sk, "ano_eleicao": 2022, "sequencial_candidato": f"SEQ-{sk[-4:]}",
            "cargo": cargo, "tipo_bem": "Aplicação Financeira / Renda Fixa",
            "descricao_bem": "CDBs e Fundos de Investimento DI", "valor_bem": 320_000.00, "data_referencia": "2022-08-15"
        })

    # --- 2. POPULAR EXECUTIVOS (Declaração de Bens e Histórico) ---
    for sk_e, nome_completo, nome_urna, partido_e, uf_e, cargo_e, ano_eleicao_base in executivos:
        bens.append({
            "id_politico": sk_e, "ano_eleicao": ano_eleicao_base, "sequencial_candidato": f"SEQ-{sk_e[-4:]}",
            "cargo": cargo_e, "tipo_bem": "Imóvel Residencial / Casa",
            "descricao_bem": f"Imóvel residencial próprio situado em {uf_e}", "valor_bem": 1_250_000.00, "data_referencia": f"{ano_eleicao_base}-08-15"
        })
        bens.append({
            "id_politico": sk_e, "ano_eleicao": ano_eleicao_base, "sequencial_candidato": f"SEQ-{sk_e[-4:]}",
            "cargo": cargo_e, "tipo_bem": "Aplicações e Investimentos",
            "descricao_bem": "Fundos de Investimento e Previdência Privada", "valor_bem": 680_000.00, "data_referencia": f"{ano_eleicao_base}-08-15"
        })
        bens.append({
            "id_politico": sk_e, "ano_eleicao": ano_eleicao_base, "sequencial_candidato": f"SEQ-{sk_e[-4:]}",
            "cargo": cargo_e, "tipo_bem": "Veículo Automotor",
            "descricao_bem": "Veículo automotor de passeio", "valor_bem": 120_000.00, "data_referencia": f"{ano_eleicao_base}-08-15"
        })

    return despesas_cota, emendas, bens, eventos, presencas
