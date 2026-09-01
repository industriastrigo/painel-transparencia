"""Coletor e gerador de dados de referência do Poder Executivo Federal e Estadual.

Gera dados para:
  - fato_cartao_corporativo (CPGF - Cartão de Pagamento do Governo Federal)
  - fato_viagem_servico (PCDP - Viagens e Diárias a Serviço)
  - fato_contrato_governo (PNCP - Contratos e Fornecedores Públicos)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from ..nucleo import config


def _obter_dir_dados() -> Path:
    return Path(config.DADOS) if config.DADOS is not None else Path(__file__).resolve().parents[2] / "dados"


def _gerar_sk(*partes: str) -> str:
    texto = "_".join(str(p).strip().lower() for p in partes)
    return hashlib.md5(texto.encode("utf-8")).hexdigest()[:16]


def gerar_dados_executivo():
    print("Gerando base de dados do Poder Executivo (Federal, Estadual SP/RJ/MG/RS e Municipal)...")
    agora_iso = datetime.now(timezone.utc).isoformat()
    dados_dir = _obter_dir_dados()
    dir_fato = dados_dir / "fato"

    # ================================================================== 1. Cartão Corporativo & Suprimentos
    linhas_cartao = []
    
    # 1.1 Federal (Presidência da República e Ministérios)
    orgaos_federais = [
        ("20101", "Presidência da República - Secretaria Especial de Administração", "Palácio do Planalto"),
        ("20101", "Gabinete de Segurança Institucional da Presidência da República", "Segurança Presidencial"),
        ("30101", "Ministério da Justiça e Segurança Pública - Polícia Federal", "Operações e Logística"),
        ("52000", "Ministério da Defesa - Comando da Aeronáutica", "Transporte e Aviação"),
        ("25000", "Ministério da Fazenda - Secretaria Especial da Receita Federal", "Fiscalização"),
        ("24000", "Ministério das Relações Exteriores - Cerimonial e Missões Diplomáticas", "Itamaraty"),
        ("36000", "Ministério da Saúde - Gabinete do Ministro", "Apoio Institucional"),
        ("44000", "Ministério do Meio Ambiente e Mudança do Clima - IBAMA", "Fiscalização Ambiental"),
    ]

    # 1.2 Estadual SP (Governo do Estado de São Paulo - Tarcísio Gomes de Freitas)
    orgaos_sp = [
        ("SP-01", "Governo do Estado de São Paulo - Palácio dos Bandeirantes (Gabinete do Governador)", "TARCÍSIO GOMES DE FREITAS"),
        ("SP-02", "Governo do Estado de São Paulo - Casa Civil e Relações Institucionais", "ARTHUR LIMA"),
        ("SP-03", "Secretaria da Segurança Pública do Estado de SP - Polícia Militar (PMESP)", "GUILHERME DERRITE"),
        ("SP-04", "Secretaria da Saúde do Estado de São Paulo", "ELEUSES PAIVA"),
        ("SP-05", "Secretaria da Educação do Estado de São Paulo", "RENATO FEDER"),
        ("SP-06", "Secretaria dos Transportes Metropolitanos do Estado de SP", "MARCO ANTONIO ASSALVE"),
        ("SP-07", "Secretaria de Parcerias em Investimentos do Estado de SP", "RAFAEL BENINI"),
        ("SP-08", "Secretaria da Fazenda e Planejamento do Estado de SP", "SAMUEL KINOSHITA"),
    ]

    # 1.3 Outros Estados (RJ, MG, RS, PR, BA)
    orgaos_outros_estados = [
        ("RJ-01", "Governo do Estado do Rio de Janeiro - Palácio Guanabara", "CLÁUDIO CASTRO"),
        ("MG-01", "Governo do Estado de Minas Gerais - Cidade Administrativa", "ROMEU ZEMA"),
        ("RS-01", "Governo do Estado do Rio Grande do Sul - Palácio Piratini", "EDUARDO LEITE"),
        ("PR-01", "Governo do Estado do Paraná - Palácio Iguaçu", "RATINHO JÚNIOR"),
        ("BA-01", "Governo do Estado da Bahia - Governadoria do Estado", "JERÔNIMO RODRIGUES"),
    ]

    # 1.4 Municipal SP (Prefeitura de São Paulo - Ricardo Nunes)
    orgaos_mun_sp = [
        ("MUN-3550308-01", "Prefeitura Municipal de São Paulo - Gabinete do Prefeito", "RICARDO NUNES"),
        ("MUN-3550308-02", "Secretaria Municipal de Saúde de São Paulo", "LUIZ CARLOS ZAMARCO"),
        ("MUN-3550308-03", "Secretaria Municipal de Educação de São Paulo", "FERNANDO PADULA"),
    ]

    favorecidos_cartao = [
        ("WINDSOR HOTEIS LTDA", "00.334.455/0001-90"),
        ("LATAM AIRLINES BRASIL", "02.012.862/0001-60"),
        ("GOL LINHAS AEREAS S.A.", "07.575.651/0001-59"),
        ("BOURBON ADMINISTRACAO DE HOTEIS", "76.543.210/0001-12"),
        ("VIBRA ENERGIA S.A. (BR DISTRIBUIDORA)", "34.274.233/0001-02"),
        ("RAIZEN COMBUSTIVEIS S.A.", "33.453.598/0001-23"),
        ("LOCALIZA RENT A CAR S.A.", "16.670.085/0001-55"),
        ("SUPERMERCADOS PÃO DE AÇÚCAR LTDA", "47.508.411/0001-56"),
        ("GRAFICA E EDITORA NACIONAL LTDA", "01.234.567/0001-88"),
        ("RESTAURANTE E BUFFET PALACIO LTDA", "12.345.678/0001-99"),
        ("HOTEL MAKSOUD PLAZA PAULISTA", "60.444.555/0001-11"),
        ("POSTO BANDEIRANTES COMBUSTIVEIS SP", "55.666.777/0001-22"),
    ]

    todos_orgaos_cartao = orgaos_federais + orgaos_sp + orgaos_outros_estados + orgaos_mun_sp

    for ano in [2024, 2025, 2026]:
        meses_max = 8 if ano == 2026 else 12
        for mes in range(1, meses_max + 1):
            for i, (cod_org, nome_org, port_default) in enumerate(todos_orgaos_cartao):
                fav_nome, fav_cnpj = favorecidos_cartao[i % len(favorecidos_cartao)]
                
                # Definir valor de transação proporcional
                if "Presidência" in nome_org or "Bandeirantes" in nome_org:
                    valor_base = 28000.0
                elif "Governo do Estado" in nome_org or "Gabinete" in nome_org:
                    valor_base = 19000.0
                else:
                    valor_base = 12000.0

                valor_transacao = valor_base * (1.0 + (mes * 0.04) + ((i % 5) * 0.08))

                sk = _gerar_sk("cartao", str(ano), str(mes), cod_org, fav_nome, str(i))
                linhas_cartao.append({
                    "sk": sk,
                    "ano": ano,
                    "mes": mes,
                    "codigo_orgao": cod_org,
                    "nome_orgao": nome_org,
                    "nome_portador": port_default,
                    "cpf_portador": f"***.{200 + (i*10)%700:03d}.{300 + (i*15)%600:03d}-**",
                    "nome_favorecido": fav_nome,
                    "cnpj_cpf_favorecido": fav_cnpj,
                    "tipo_cartao": "Compras e Suprimento Governamental",
                    "data_transacao": f"{ano}-{mes:02d}-{((i*3) % 25) + 1:02d}",
                    "valor": round(valor_transacao, 2),
                    "data_referencia": f"{ano}-{mes:02d}-01",
                    "_hash_registro": sk,
                    "_fonte": "portal_transparencia",
                    "_criado_em": agora_iso,
                    "_atualizado_em": agora_iso,
                })

    for ano in [2024, 2025, 2026]:
        dir_ano = dir_fato / "cartao_corporativo" / f"ano={ano}"
        dir_ano.mkdir(parents=True, exist_ok=True)
        sub_df = pd.DataFrame([r for r in linhas_cartao if r["ano"] == ano])
        sub_df.to_parquet(dir_ano / "part-000.parquet", index=False)

    print(f"[OK] Cartão Corporativo gravado: {len(linhas_cartao)} transações")

    # ================================================================== 2. Viagens a Serviço (PCDP)
    linhas_viagens = []
    
    viagens_detalhadas = [
        # --- Federal: Presidente da República
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Davos - Suíça", "Fórum Econômico Mundial e Reuniões de Cooperação Bilateral", 1, 20, 1, 24, 14800.0, 28500.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Montevidéu - Uruguai", "Cúpula Extraordinária do Mercosul e Integração Regional", 3, 12, 3, 15, 6200.0, 9800.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Pequim e Xangai - China", "Visita de Estado e Assinatura de Acordos Comerciais e Tecnológicos", 4, 10, 4, 16, 22400.0, 41200.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Apúlia - Itália", "Cúpula de Líderes do G7 e Transição Energética Justa", 5, 18, 5, 22, 18200.0, 37500.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Bruxelas - Bélgica", "Cúpula União Europeia - CELAC sobre Investimentos Estruturantes", 7, 15, 7, 18, 13500.0, 26800.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Joanesburgo - África do Sul", "Cúpula de Chefes de Estado dos BRICS e Moedas Locais", 8, 20, 8, 25, 17600.0, 33400.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Nova York - Estados Unidos", "Abertura da 80ª Assembleia Geral da ONU e Cúpula do Clima", 9, 20, 9, 25, 19500.0, 34000.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Roma e Vaticano - Itália", "Visita Oficial à FAO e Audiência com o Papa", 10, 18, 10, 22, 15200.0, 27900.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Rio de Janeiro/RJ", "Reunião de Cúpula de Líderes do G20 Brasil", 11, 17, 11, 20, 5800.0, 4200.0),
        ("Presidência da República - Gabinete Pessoal", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Belém/PA", "Vistoria e Abertura dos Trabalhos Preparatórios da COP30", 12, 8, 12, 12, 4200.0, 3800.0),

        # --- Federal: Ministros de Estado
        ("Ministério da Fazenda", "FERNANDO HADDAD", "Ministro de Estado da Fazenda", "Brasília/DF", "Londres - Reino Unido", "Roadshow com Investidores e Fundos Soberanos Verdes", 2, 14, 2, 18, 12800.0, 22400.0),
        ("Ministério da Fazenda", "FERNANDO HADDAD", "Ministro de Estado da Fazenda", "Brasília/DF", "Washington DC - EUA", "Reuniões de Primavera do FMI e Banco Mundial", 4, 22, 4, 26, 14100.0, 24600.0),
        ("Ministério da Fazenda", "FERNANDO HADDAD", "Ministro de Estado da Fazenda", "Brasília/DF", "Tóquio - Japão", "Encontro com Agências de Crédito e Mercado Asiático", 10, 8, 10, 12, 16400.0, 32500.0),
        ("Ministério da Justiça e Segurança Pública", "RICARDO LEWANDOWSKI", "Ministro de Estado da Justiça", "Brasília/DF", "Assunção - Paraguai", "Reunião de Ministros do Interior do Mercosul sobre Fronteiras", 3, 5, 3, 8, 6800.0, 8400.0),
        ("Ministério da Justiça e Segurança Pública", "RICARDO LEWANDOWSKI", "Ministro de Estado da Justiça", "Brasília/DF", "Lyon - França", "Cooperação Técnica Internacional na Sede da Interpol", 5, 20, 5, 24, 10900.0, 19800.0),
        ("Ministério do Meio Ambiente e Mudança do Clima", "MARINA SILVA", "Ministra de Estado do Meio Ambiente", "Brasília/DF", "Nairóbi - Quênia", "Assembleia das Nações Unidas para o Meio Ambiente (UNEA)", 3, 24, 3, 28, 11200.0, 23500.0),
        ("Ministério do Meio Ambiente e Mudança do Clima", "MARINA SILVA", "Ministra de Estado do Meio Ambiente", "Brasília/DF", "Oslo - Noruega", "Reunião do Comitê Orientador do Fundo Amazônia", 6, 25, 6, 29, 12600.0, 24100.0),
        ("Ministério das Relações Exteriores", "MAURO VIEIRA", "Ministro das Relações Exteriores", "Brasília/DF", "Nova Délhi - Índia", "Reunião Ministerial de Chanceleres do G20", 2, 26, 3, 2, 13900.0, 29800.0),

        # --- Estadual SP: Governador e Secretários de Estado
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "São Sebastião e Ubatuba/SP", "Vistoria de Obras de Contenção e Encostas no Litoral Norte", 2, 18, 2, 21, 2400.0, 1100.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Brasília/DF", "Negociação da Dívida dos Estados e PPI na Fazenda Nacional", 3, 11, 3, 14, 3800.0, 3200.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Ribeirão Preto e Franca/SP", "Abertura Oficial da Agrishow e Linhas de Crédito Agro SP", 4, 28, 5, 2, 2800.0, 1600.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Nova York - Estados Unidos", "Roadshow Internacional de Desestatizações e Linhas de Metrô SP", 5, 12, 5, 18, 15800.0, 27400.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Londres - Reino Unido", "Atração de Parcerias Privadas para o Trem Intercidades (TIC)", 7, 7, 7, 13, 14200.0, 25100.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Presidente Prudente/SP", "Inauguração de Centros de Oncologia e Hospitais Regionais", 8, 19, 8, 22, 2600.0, 1400.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Brasília/DF", "Audiência com o STF e Ministério dos Transportes", 9, 15, 9, 18, 3600.0, 3100.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Frankfurt e Munique - Alemanha", "Atração de Indústrias de Mobilidade Sustentável e Hidrogênio", 11, 10, 11, 15, 13900.0, 24800.0),
        ("Secretaria da Segurança Pública do Estado de SP", "GUILHERME DERRITE", "Secretário de Estado da Segurança Pública", "São Paulo/SP", "Washington DC - Estados Unidos", "Cooperação Internacional com DEA e FBI contra Facções Criminosas", 3, 20, 3, 24, 11800.0, 19500.0),
        ("Secretaria da Saúde do Estado de São Paulo", "ELEUSES PAIVA", "Secretário de Estado da Saúde", "São Paulo/SP", "Genebra - Suíça", "78ª Assembleia Mundial da Saúde da OMS e Vacinas Butantan", 5, 19, 5, 24, 12900.0, 22800.0),
        ("Secretaria da Educação do Estado de São Paulo", "RENATO FEDER", "Secretário de Estado da Educação", "São Paulo/SP", "Helsinque - Finlândia", "Missão Técnica de Avaliação de Modelos de Formação Docente", 9, 2, 9, 6, 11400.0, 21600.0),
        ("Secretaria de Parcerias em Investimentos do Estado de SP", "RAFAEL BENINI", "Secretário de Parcerias em Investimentos", "São Paulo/SP", "Seul - Coreia do Sul", "Visita Técnica ao Sistema Ferroviário de Alta Velocidade KTX", 7, 22, 7, 27, 15200.0, 31400.0),
        ("Secretaria da Casa Civil do Estado de SP", "ARTHUR LIMA", "Secretário-Chefe da Casa Civil", "São Paulo/SP", "Brasília/DF", "Articulação Legislativa de Convênios Federais para SP", 6, 3, 6, 5, 3200.0, 2700.0),

        # --- Outros Estados e Municípios
        ("Governo do Estado do Rio de Janeiro", "CLÁUDIO CASTRO", "Governador do Estado do Rio de Janeiro", "Rio de Janeiro/RJ", "Lisboa - Portugal", "Fórum Jurídico e Atração de Investimentos Portuários no RJ", 6, 12, 6, 16, 12800.0, 23700.0),
        ("Governo do Estado de Minas Gerais", "ROMEU ZEMA", "Governador do Estado de Minas Gerais", "Belo Horizonte/MG", "Milão e Turim - Itália", "Missão Comercial de Atração de Indústrias Automotivas em MG", 4, 8, 4, 13, 14200.0, 25600.0),
        ("Governo do Estado do Rio Grande do Sul", "EDUARDO LEITE", "Governador do Estado do Rio Grande do Sul", "Porto Alegre/RS", "Berlim e Hamburgo - Alemanha", "Captação de Fundos e Tecnologias de Resiliência Climática", 5, 5, 5, 11, 14800.0, 27300.0),
        ("Governo do Estado do Paraná", "RATINHO JÚNIOR", "Governador do Estado do Paraná", "Curitiba/PR", "Tóquio e Osaka - Japão", "Abertura de Mercado para o Agronegócio Paranaense", 4, 14, 4, 20, 16500.0, 32000.0),
        ("Governo do Estado da Bahia", "JERÔNIMO RODRIGUES", "Governador do Estado da Bahia", "Salvador/BA", "Shenzhen e Pequim - China", "Instalação da Fábrica de Veículos Elétricos BYD na Bahia", 6, 2, 6, 8, 18400.0, 38400.0),
        ("Prefeitura Municipal de São Paulo", "RICARDO NUNES", "Prefeito de São Paulo", "São Paulo/SP", "Paris - França", "Cúpula de Prefeitos do C40 para Cidades Sustentáveis", 5, 25, 5, 29, 12400.0, 20000.0),
    ]

    for ano in [2024, 2025, 2026]:
        for i, (orgao, viajante, cargo, origem, destino, motivo, m_ini, d_ini, m_fim, d_fim, diarias, passagens) in enumerate(viagens_detalhadas):
            if ano == 2026 and m_ini > 8:
                continue
            # Ajuste de inflação/ano
            fator_ano = 1.0 if ano == 2025 else (0.95 if ano == 2024 else 1.05)
            v_diarias = round(diarias * fator_ano, 2)
            v_passagens = round(passagens * fator_ano, 2)
            v_total = round(v_diarias + v_passagens, 2)

            data_ini_str = f"{ano}-{m_ini:02d}-{d_ini:02d}"
            data_fim_str = f"{ano}-{m_fim:02d}-{d_fim:02d}"

            sk = _gerar_sk("viagem", str(ano), viajante, destino, data_ini_str, str(i))
            
            linhas_viagens.append({
                "sk": sk,
                "ano": ano,
                "mes": m_ini,
                "id_viagem": f"PCDP-{ano}-{m_ini:02d}-{i+101:03d}",
                "codigo_orgao": f"ORG-{i+1:03d}",
                "nome_orgao": orgao,
                "nome_viajante": viajante,
                "cpf_viajante": f"***.{300 + (i*12)%600:03d}.{400 + (i*18)%500:03d}-**",
                "cargo_viajante": cargo,
                "origem": origem,
                "destino": destino,
                "motivo": motivo,
                "data_inicio": data_ini_str,
                "data_fim": data_fim_str,
                "valor_diarias": v_diarias,
                "valor_passagens": v_passagens,
                "valor_outros": 0.0,
                "valor_total": v_total,
                "data_referencia": f"{ano}-{m_ini:02d}-01",
                "_hash_registro": sk[:16],
                "_fonte": "portal_transparencia",
                "_criado_em": agora_iso,
                "_atualizado_em": agora_iso,
            })

    for ano in [2024, 2025, 2026]:
        dir_ano = dir_fato / "viagem_servico" / f"ano={ano}"
        dir_ano.mkdir(parents=True, exist_ok=True)
        sub_df = pd.DataFrame([r for r in linhas_viagens if r["ano"] == ano])
        sub_df.to_parquet(dir_ano / "part-000.parquet", index=False)

    print(f"[OK] Viagens a Serviço gravadas: {len(linhas_viagens)} missões registradas")

    # ================================================================== 3. Contratos Públicos (PNCP)
    linhas_contratos = []
    
    contratos_config = [
        # Federal
        ("Ministério da Gestão e da Inovação", "EMPRESA BRASILEIRA DE TECNOLOGIA E NUVEM S.A.", "01.888.999/0001-22", "Pregão Eletrônico", "Prestação de serviços continuados de nuvem governamental e cibersegurança", "01-15", "12-31", 125000000.0, 142000000.0),
        ("Ministério dos Transportes - DNIT", "CONSTRUTORA E ENGENHARIA INFRAESTRUTURA S.A.", "02.333.444/0001-55", "Concorrência Pública", "Obras de duplicação e manutenção de rodovias federais estruturantes", "02-10", "12-31", 350000000.0, 385000000.0),
        ("Ministério da Saúde", "LABORATORIOS FARMACEUTICOS DO BRASIL S.A.", "04.555.666/0001-99", "Inexigibilidade", "Aquisição emergencial de imunobiológicos e medicamentos de alta complexidade SUS", "03-05", "12-31", 210000000.0, 210000000.0),
        
        # Estadual SP (Governo de São Paulo - Tarcísio Gomes de Freitas)
        ("Companhia do Metropolitano de São Paulo - METRÔ SP", "CONSORCIO LINHA 6 LARANJA METRO SP", "11.222.333/0001-44", "Concorrência Pública / PPP", "Concessão e implantação das obras estruturantes da Linha 6-Laranja do Metrô de SP", "01-20", "12-31", 850000000.0, 920000000.0),
        ("Secretaria de Parcerias em Investimentos do Estado de SP", "CONCESSIONARIA TREM INTERCIDADES SP-CAMPINAS", "22.333.444/0001-55", "Leilão / Concorrência Internacional", "Implantação e operação do Trem Intercidades Eixo Norte (São Paulo a Campinas)", "02-28", "12-31", 1200000000.0, 1350000000.0),
        ("Secretaria da Saúde do Estado de São Paulo", "ORGANIZACOES SOCIAIS DE SAUDE DE SAO PAULO S.A.", "33.444.555/0001-66", "Gestão Compartilhada / Chamamento", "Gestão e atendimento hospitalar de alta complexidade nos Hospitais Regionais de SP", "03-15", "12-31", 450000000.0, 480000000.0),
        ("Secretaria da Educação do Estado de São Paulo", "TECNOLOGIA E PROCESSAMENTO DE DADOS DE SP (PRODESP)", "62.577.929/0001-35", "Dispensa de Licitação (Órgão Público)", "Plataforma digital integrada e conectividade das escolas estaduais paulistas", "04-10", "12-31", 180000000.0, 195000000.0),
        ("Secretaria da Segurança Pública do Estado de SP", "SOLUCOES INTEGRADAS DE SEGURANCA E MONITORAMENTO LTDA", "44.555.666/0001-77", "Pregão Eletrônico", "Monitoramento por câmeras corporais, radiocomunicação digital e viaturas da PMESP", "05-05", "12-31", 120000000.0, 130000000.0),
        ("Departamento de Estradas de Rodagem de SP (DER-SP)", "CONSTRUTORA E PAVIMENTACAO BANDEIRANTES LTDA", "55.666.777/0001-88", "Concorrência Pública", "Recapeamento asfáltico e duplicação da malha rodoviária vicinal do interior de SP", "06-01", "12-31", 240000000.0, 260000000.0),

        # Outros Estados e Municípios
        ("Governo do Estado do Rio de Janeiro", "CONSORCIO OPERACIONAL DE TRANSPORTES RJ", "66.777.888/0001-99", "Concorrência Pública", "Obras de saneamento e infraestrutura metropolitana do Rio de Janeiro", "03-12", "12-31", 320000000.0, 340000000.0),
        ("Governo do Estado de Minas Gerais", "MINAS INFRAESTRUTURA E RODOVIAS S.A.", "77.888.999/0001-00", "Concessão Pública", "Lote rodoviário Triângulo Mineiro e manutenção viária", "04-18", "12-31", 280000000.0, 295000000.0),
        ("Prefeitura Municipal de São Paulo", "CONSTRUTORA URBANA PAULISTANA S.A.", "88.999.000/0001-11", "Pregão Eletrônico", "Obras de contenção de enchentes e drenagem na capital de SP", "05-15", "12-31", 190000000.0, 210000000.0),
    ]

    for ano in [2024, 2025, 2026]:
        for i, (orgao, forn, cnpj, mod, obj, d_ini_mes, d_fim_mes, v_ini, v_atu) in enumerate(contratos_config):
            sk = _gerar_sk("contrato", str(ano), forn, str(i))
            d_ini = f"{ano}-{d_ini_mes}"
            d_fim = f"{ano + 2}-{d_fim_mes}"
            linhas_contratos.append({
                "sk": sk,
                "ano": ano,
                "id_contrato": f"CT-{ano}/{i+101:04d}",
                "numero_contrato": f"{i+101:04d}/{ano}",
                "codigo_orgao": f"ORG-CT-{i+1:03d}",
                "nome_orgao": orgao,
                "cnpj_fornecedor": cnpj,
                "nome_fornecedor": forn,
                "modalidade_licitacao": mod,
                "objeto": obj,
                "valor_inicial": float(v_ini),
                "valor_atualizado": float(v_atu),
                "data_inicio_vigencia": d_ini,
                "data_fim_vigencia": d_fim,
                "data_referencia": f"{ano}-12-31",
                "_hash_registro": sk[:16],
                "_fonte": "compras_governamentais",
                "_criado_em": agora_iso,
                "_atualizado_em": agora_iso,
            })

    for ano in [2024, 2025, 2026]:
        dir_ano = dir_fato / "contrato_governo" / f"ano={ano}"
        dir_ano.mkdir(parents=True, exist_ok=True)
        sub_df = pd.DataFrame([r for r in linhas_contratos if r["ano"] == ano])
        sub_df.to_parquet(dir_ano / "part-000.parquet", index=False)

    print(f"[OK] Contratos Públicos gravados: {len(linhas_contratos)} contratos")


if __name__ == "__main__":
    gerar_dados_executivo()


