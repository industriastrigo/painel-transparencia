"""Módulo de dados detalhados para parlamentares e políticos (Cotas, Emendas, Bens e Presença).

Popula despesas da cota parlamentar (CEAP), emendas orçamentárias, bens declarados no TSE
e eventos de plenário para deputados federais, senadores, governadores e presidentes.
"""
from __future__ import annotations

import hashlib

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

    catalogo_ceap = [
        ("COMBUSTÍVEIS E LUBRIFICANTES", (3, 6), [
            ("AUTO POSTO DA TORRE LTDA", "00.306.597/0001-40", 250.0, 480.0),
            ("CASCOL COMBUSTÍVEIS PARA VEÍCULOS LTDA", "00.306.597/0002-21", 220.0, 450.0),
            ("POSTO IPIRANGA MONUMENTAL LTDA", "03.490.112/0001-85", 240.0, 490.0),
            ("POSTO PETROBRAS ASA SUL", "00.000.000/0001-91", 210.0, 430.0),
            ("SHELL AUTO POSTO AEROPORTO", "04.552.123/0001-33", 280.0, 520.0),
        ]),
        ("PASSAGEM AÉREA", (2, 4), [
            ("LATAM AIRLINES BRASIL", "02.012.862/0001-60", 950.0, 2800.0),
            ("GOL LINHAS AÉREAS S.A.", "07.575.651/0001-59", 850.0, 2600.0),
            ("AZUL LINHAS AÉREAS BRASILEIRAS S.A.", "09.296.295/0001-60", 900.0, 2750.0),
            ("VOEPASS LINHAS AÉREAS", "00.512.441/0001-72", 650.0, 1600.0),
        ]),
        ("DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR", (1, 2), [
            ("COMUNICAÇÃO E MÍDIA DIGITAL BRASIL", "12.789.445/0001-22", 4500.0, 11500.0),
            ("GRÁFICA E EDITORA BRASÍLIA LTDA", "01.442.981/0001-19", 2800.0, 7200.0),
            ("AGÊNCIA FOCO COMUNICAÇÃO E MARKETING", "24.110.892/0001-44", 3500.0, 9000.0),
            ("IMPULSIONA MÍDIA E REDES SOCIAIS", "38.991.205/0001-88", 1800.0, 5500.0),
            ("PRODUÇÕES E CONTEÚDO AUDIOVISUAL LTDA", "19.330.412/0001-77", 3800.0, 10500.0),
        ]),
        ("HOSPEDAGEM E ALIMENTAÇÃO", (1, 3), [
            ("B HOTEL BRASÍLIA", "26.330.142/0001-99", 450.0, 980.0),
            ("HOTEL NACIONAL DE BRASÍLIA", "00.123.884/0001-15", 380.0, 750.0),
            ("WINDSOR PLAZA HOTEL BRASÍLIA", "09.112.445/0001-66", 420.0, 890.0),
            ("RESTAURANTE SENAC PLENÁRIO", "03.709.814/0001-98", 85.0, 210.0),
        ]),
        ("LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES", (0, 1), [
            ("LOCALIZA RENT A CAR S.A.", "16.670.085/0001-55", 3200.0, 6800.0),
            ("MOVIDA LOCAÇÃO DE VEÍCULOS S.A.", "07.976.147/0001-60", 2900.0, 6200.0),
            ("UNIDAS LOCADORA DE VEÍCULOS S.A.", "04.981.822/0001-12", 3100.0, 6500.0),
        ]),
        ("CONSULTORIAS, PESQUISAS E TRABALHOS TÉCNICOS", (0, 1), [
            ("ASSESSORIA ESTRATÉGICA PARLAMENTAR LTDA", "33.450.812/0001-90", 5500.0, 12000.0),
            ("INSTITUTO BRASILEIRO DE ANÁLISE PÚBLICA", "18.300.914/0001-55", 4800.0, 11000.0),
            ("FRANCO & ASSOCIADOS CONSULTORIA JURÍDICA", "29.881.042/0001-11", 6000.0, 14000.0),
        ]),
        ("SERVIÇOS POSTAIS E TELEFONIA", (1, 1), [
            ("CLARO S.A.", "40.432.544/0001-47", 280.0, 650.0),
            ("VIVO TELEFÔNICA BRASIL S.A.", "02.558.157/0001-62", 310.0, 720.0),
            ("EMPRESA BRASILEIRA DE CORREIOS E TELÉGRAFOS", "34.028.316/0001-03", 150.0, 850.0),
        ]),
        ("MANUTENÇÃO DE ESCRITÓRIO DE APOIO", (0, 1), [
            ("KALUNGA COMÉRCIO E PAPELARIA LTDA", "43.214.055/0001-07", 350.0, 1400.0),
            ("IMOBILIÁRIA CENTRAL DO DF", "05.119.822/0001-33", 1800.0, 3800.0),
        ]),
    ]

    catalogo_emendas = [
        ("Saúde", [
            ("Fundo Municipal de Saúde - Custeio da Atenção Primária e Especializada (SUS)", 1_500_000.00, 1_450_000.00),
            ("Aquisição de Equipamentos Hospitalares e Ambulatoriais para Santa Casa", 1_200_000.00, 1_180_000.00),
            ("Reforma e Modernização de Unidades Básicas de Saúde (UBS)", 850_000.00, 820_000.00),
            ("Suporte a Tratamentos de Alta Complexidade e Oncologia", 950_000.00, 920_000.00),
        ]),
        ("Educação", [
            ("Infraestrutura de Escolas Municipais e Aquisição de Ônibus Escolares (FNDE)", 1_400_000.00, 1_320_000.00),
            ("Apoio e Modernização de Laboratórios em Universidades e Institutos Federais", 1_100_000.00, 1_050_000.00),
            ("Construção e Ampliação de Creches e Educação Infantil", 900_000.00, 850_000.00),
        ]),
        ("Urbanismo", [
            ("Pavimentação Asfáltica, Recapeamento e Drenagem Urbana de Municípios", 1_200_000.00, 1_100_000.00),
            ("Revitalização de Praças Públicas e Espaços de Convivência Urbana", 600_000.00, 560_000.00),
        ]),
        ("Assistência Social", [
            ("Estruturação de CRAS, CREAS e Apoio a Famílias em Vulnerabilidade", 650_000.00, 600_000.00),
            ("Equipamentos para Casas de Acolhimento e Centros Comunitários", 450_000.00, 420_000.00),
        ]),
        ("Segurança Pública", [
            ("Aquisição de Viaturas e Equipamentos de Proteção para Guarda Municipal", 750_000.00, 710_000.00),
            ("Implantação de Sistema de Monitoramento e Câmeras de Vigilância", 550_000.00, 520_000.00),
        ]),
        ("Agricultura", [
            ("Aquisição de Tratores e Patrulha Mecanizada para Agricultura Familiar", 680_000.00, 650_000.00),
        ]),
        ("Esporte e Lazer", [
            ("Construção de Complexo Esportivo Comunitário e Arenas Multiuso", 500_000.00, 480_000.00),
        ]),
    ]

    anos_mandato = [2023, 2024, 2025, 2026]

    # --- 1. POPULAR PARLAMENTARES (Cota, Emendas, Presença) ---
    doc_seq = 10000
    for sk, nome, partido, uf, casa, cargo in parlamentares_leg:
        for ano in anos_mandato:
            # A. Cotas com distribuições realistas por tipo de despesa e fornecedor
            for mes in range(1, 13):
                for cat_nome, (min_f, max_f), fornecedores in catalogo_ceap:
                    # Variação determinística baseada no político, ano, mês e categoria
                    hash_cat = int(hashlib.md5(f"{sk}_{ano}_{mes}_{cat_nome}".encode()).hexdigest(), 16)
                    qtd_notas = min_f + (hash_cat % (max_f - min_f + 1))
                    for i in range(qtd_notas):
                        doc_seq += 1
                        hash_forn = int(hashlib.md5(f"{sk}_{ano}_{mes}_{cat_nome}_{i}".encode()).hexdigest(), 16)
                        forn_nome, cnpj, val_min, val_max = fornecedores[hash_forn % len(fornecedores)]
                        val_pct = (hash_forn % 1000) / 1000.0
                        val_liquido = round(val_min + val_pct * (val_max - val_min), 2)
                        dia_emissao = 1 + (hash_forn % 28)

                        despesas_cota.append({
                            "casa": casa,
                            "id_documento": str(doc_seq),
                            "num_parcela": "0",
                            "num_ressarcimento": "0",
                            "id_politico": sk,
                            "nome_politico": nome,
                            "sigla_partido": partido,
                            "sigla_uf": uf,
                            "tipo_despesa": cat_nome,
                            "fornecedor": forn_nome,
                            "cnpj_cpf_fornecedor": cnpj,
                            "valor_documento": val_liquido,
                            "url_documento": f"https://www.camara.leg.br/cota-parlamentar/documentos/{doc_seq}.pdf",
                            "valor_liquido": val_liquido,
                            "data_emissao": f"{ano}-{mes:02d}-{dia_emissao:02d}",
                            "ano": ano,
                            "mes": mes
                        })

            # B. Emendas Parlamentares
            seq_emenda = 0
            for func_nome, itens in catalogo_emendas:
                hash_f = int(hashlib.md5(f"{sk}_{ano}_{func_nome}".encode()).hexdigest(), 16)
                if func_nome == "Saúde":
                    qtd_func = 3 + (hash_f % 2)  # 3 a 4
                elif func_nome == "Educação":
                    qtd_func = 2 + (hash_f % 2)  # 2 a 3
                elif func_nome == "Urbanismo":
                    qtd_func = 1 + (hash_f % 2)  # 1 a 2
                elif func_nome == "Assistência Social":
                    qtd_func = 1
                else:
                    qtd_func = hash_f % 2        # 0 ou 1

                for i in range(min(qtd_func, len(itens))):
                    seq_emenda += 1
                    local, val_emp, val_pag = itens[i]
                    cod_emenda = f"{ano}{sk[-4:]}{seq_emenda:02d}"
                    emendas.append({
                        "ano": ano,
                        "codigo_emenda": cod_emenda,
                        "tipo_emenda": "Individual (RP6)",
                        "autor": nome,
                        "funcao": func_nome,
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
