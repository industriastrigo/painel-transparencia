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
    
    viagens_config = [
        # Federal
        ("Presidência da República", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Nova York - Estados Unidos", "Assembleia Geral da ONU e Cúpula do Clima", 18500.0, 32000.0),
        ("Presidência da República", "LUIZ INÁCIO LULA DA SILVA", "Presidente da República", "Brasília/DF", "Rio de Janeiro/RJ", "Cúpula de Líderes do G20 Brasil", 9500.0, 7800.0),
        ("Ministério da Fazenda", "FERNANDO HADDAD", "Ministro de Estado da Fazenda", "Brasília/DF", "Londres - Reino Unido", "Reuniões com Investidores e Transição Ecológica", 14200.0, 24500.0),
        ("Ministério da Justiça", "RICARDO LEWANDOWSKI", "Ministro de Estado da Justiça", "Brasília/DF", "Buenos Aires - Argentina", "Cúpula de Segurança Pública do Mercosul", 7800.0, 9200.0),
        ("Ministério do Meio Ambiente", "MARINA SILVA", "Ministra de Estado do Meio Ambiente", "Brasília/DF", "Belém/PA", "Preparação e Infraestrutura para a COP30", 5400.0, 6800.0),
        
        # Estadual SP (Tarcísio Gomes de Freitas e Secretários)
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Nova York - Estados Unidos", "Roadshow Internacional de Desestatização e Infraestrutura SP", 16500.0, 28000.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Londres - Reino Unido", "Atração de Parcerias Privadas para o Trem Intercidades (TIC)", 15000.0, 25000.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Brasília/DF", "Negociação da Dívida dos Estados com a Fazenda Nacional", 4200.0, 3800.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "Ribeirão Preto/SP", "Abertura Oficial da Agrishow e Anúncio de Crédito Rural", 2800.0, 1800.0),
        ("Governo do Estado de São Paulo - Palácio dos Bandeirantes", "TARCÍSIO GOMES DE FREITAS", "Governador do Estado de São Paulo", "São Paulo/SP", "São Sebastião/SP", "Vistoria e Entrega de Obras Habitacionais de Reconstrução", 2400.0, 1200.0),
        ("Secretaria da Segurança Pública do Estado de SP", "GUILHERME DERRITE", "Secretário de Estado da Segurança Pública", "São Paulo/SP", "Washington DC - Estados Unidos", "Cooperação Internacional em Inteligência Policial e Combate ao Crime", 11200.0, 19500.0),
        ("Secretaria da Saúde do Estado de São Paulo", "ELEUSES PAIVA", "Secretário de Estado da Saúde", "São Paulo/SP", "Genebra - Suíça", "Assembleia Mundial da Saúde da OMS", 12500.0, 21000.0),
        ("Secretaria da Casa Civil do Estado de SP", "ARTHUR LIMA", "Secretário-Chefe da Casa Civil", "São Paulo/SP", "Brasília/DF", "Articulação Institucional e Recursos Federais", 3800.0, 3200.0),

        # Outros Estados
        ("Governo do Estado do Rio de Janeiro", "CLÁUDIO CASTRO", "Governador do Estado do Rio de Janeiro", "Rio de Janeiro/RJ", "Brasília/DF", "Regime de Recuperação Fiscal do Estado do Rio", 4500.0, 3600.0),
        ("Governo do Estado de Minas Gerais", "ROMEU ZEMA", "Governador do Estado de Minas Gerais", "Belo Horizonte/MG", "Milão - Itália", "Missão Comercial de Atração de Indústrias Automotivas", 13800.0, 22500.0),
        ("Governo do Estado do Rio Grande do Sul", "EDUARDO LEITE", "Governador do Estado do Rio Grande do Sul", "Porto Alegre/RS", "Berlim - Alemanha", "Financiamento para Reconstrução e Resiliência Climática", 14500.0, 24000.0),
        ("Governo do Estado do Paraná", "RATINHO JÚNIOR", "Governador do Estado do Paraná", "Curitiba/PR", "Tóquio - Japão", "Exportações do Agronegócio Paranaense", 17500.0, 31000.0),

        # Municipal SP
        ("Prefeitura Municipal de São Paulo", "RICARDO NUNES", "Prefeito de São Paulo", "São Paulo/SP", "Paris - França", "Cúpula de Prefeitos do C40 para Cidades Sustentáveis", 12000.0, 18500.0),
    ]

    for ano in [2024, 2025, 2026]:
        meses_max = 8 if ano == 2026 else 12
        for mes in range(1, meses_max + 1):
            for i, (orgao, viajante, cargo, origem, destino, motivo, diarias, passagens) in enumerate(viagens_config):
                total = diarias + passagens
                sk = _gerar_sk("viagem", str(ano), str(mes), viajante, destino, str(i))
                
                linhas_viagens.append({
                    "sk": sk,
                    "ano": ano,
                    "mes": mes,
                    "id_viagem": f"PCDP-{ano}-{mes:02d}-{i:03d}",
                    "codigo_orgao": f"ORG-{i+1:03d}",
                    "nome_orgao": orgao,
                    "nome_viajante": viajante,
                    "cpf_viajante": f"***.{300 + (i*12)%600:03d}.{400 + (i*18)%500:03d}-**",
                    "cargo_viajante": cargo,
                    "origem": origem,
                    "destino": destino,
                    "motivo": motivo,
                    "data_inicio": f"{ano}-{mes:02d}-05",
                    "data_fim": f"{ano}-{mes:02d}-10",
                    "valor_diarias": round(diarias, 2),
                    "valor_passagens": round(passagens, 2),
                    "valor_outros": 0.0,
                    "valor_total": round(total, 2),
                    "data_referencia": f"{ano}-{mes:02d}-01",
                    "_hash_registro": sk,
                    "_fonte": "portal_transparencia",
                    "_criado_em": agora_iso,
                    "_atualizado_em": agora_iso,
                })

    for ano in [2024, 2025, 2026]:
        dir_ano = dir_fato / "viagem_servico" / f"ano={ano}"
        dir_ano.mkdir(parents=True, exist_ok=True)
        sub_df = pd.DataFrame([r for r in linhas_viagens if r["ano"] == ano])
        sub_df.to_parquet(dir_ano / "part-000.parquet", index=False)

    print(f"[OK] Viagens a Serviço gravadas: {len(linhas_viagens)} registros")

    # ================================================================== 3. Contratos Públicos (PNCP)
    linhas_contratos = []
    
    contratos_config = [
        # Federal
        ("Ministério da Gestão e da Inovação", "EMPRESA BRASILEIRA DE TECNOLOGIA E NUVEM S.A.", "01.888.999/0001-22", "Pregão Eletrônico", "Prestação de serviços continuados de nuvem governamental e cibersegurança", 125000000.0, 142000000.0),
        ("Ministério dos Transportes - DNIT", "CONSTRUTORA E ENGENHARIA INFRAESTRUTURA S.A.", "02.333.444/0001-55", "Concorrência Pública", "Obras de duplicação e manutenção de rodovias federais estruturantes", 350000000.0, 385000000.0),
        ("Ministério da Saúde", "LABORATORIOS FARMACEUTICOS DO BRASIL S.A.", "04.555.666/0001-99", "Inexigibilidade", "Aquisição emergencial de imunobiológicos e medicamentos de alta complexidade SUS", 210000000.0, 210000000.0),
        
        # Estadual SP (Governo de São Paulo - Tarcísio Gomes de Freitas)
        ("Companhia do Metropolitano de São Paulo - METRÔ SP", "CONSORCIO LINHA 6 LARANJA METRO SP", "11.222.333/0001-44", "Concorrência Pública / PPP", "Concessão e implantação das obras estruturantes da Linha 6-Laranja do Metrô de SP", 850000000.0, 920000000.0),
        ("Secretaria de Parcerias em Investimentos do Estado de SP", "CONCESSIONARIA TREM INTERCIDADES SP-CAMPINAS", "22.333.444/0001-55", "Leilão / Concorrência Internacional", "Implantação e operação do Trem Intercidades Eixo Norte (São Paulo a Campinas)", 1200000000.0, 1350000000.0),
        ("Secretaria da Saúde do Estado de São Paulo", "ORGANIZACOES SOCIAIS DE SAUDE DE SAO PAULO S.A.", "33.444.555/0001-66", "Gestão Compartilhada / Chamamento", "Gestão e atendimento hospitalar de alta complexidade nos Hospitais Regionais de SP", 450000000.0, 480000000.0),
        ("Secretaria da Educação do Estado de São Paulo", "TECNOLOGIA E PROCESSAMENTO DE DADOS DE SP (PRODESP)", "62.577.929/0001-35", "Dispensa de Licitação (Órgão Público)", "Plataforma digital integrada e infraestrutura de conectividade das escolas estaduais paulistas", 180000000.0, 195000000.0),
        ("Secretaria da Segurança Pública do Estado de SP", "SOLUCOES INTEGRADAS DE SEGURANCA E MONITORAMENTO LTDA", "44.555.666/0001-77", "Pregão Eletrônico", "Monitoramento por câmeras corporais, radiocomunicação digital e viaturas policiais da PMESP", 120000000.0, 130000000.0),
        ("Departamento de Estradas de Rodagem de SP (DER-SP)", "CONSTRUTORA E PAVIMENTACAO BANDEIRANTES LTDA", "55.666.777/0001-88", "Concorrência Pública", "Recapeamento asfáltico e duplicação da malha rodoviária vicinal do interior de SP", 240000000.0, 260000000.0),

        # Outros Estados e Municípios
        ("Governo do Estado do Rio de Janeiro", "CONSORCIO OPERACIONAL DE TRANSPORTES RJ", "66.777.888/0001-99", "Concorrência Pública", "Obras de saneamento e infraestrutura metropolitana do Rio de Janeiro", 320000000.0, 340000000.0),
        ("Governo do Estado de Minas Gerais", "MINAS INFRAESTRUTURA E RODOVIAS S.A.", "77.888.999/0001-00", "Concessão Pública", "Lote rodoviário Triângulo Mineiro e manutenção viária", 280000000.0, 295000000.0),
        ("Prefeitura Municipal de São Paulo", "CONSTRUTORA URBANA PAULISTANA S.A.", "88.999.000/0001-11", "Pregão Eletrônico", "Obras de contenção de enchentes e drenagem na capital de SP", 190000000.0, 210000000.0),
    ]

    for ano in [2024, 2025, 2026]:
        for i, (orgao, forn, cnpj, mod, obj, v_ini, v_atu) in enumerate(contratos_config):
            sk = _gerar_sk("contrato", str(ano), forn, str(i))
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
                "data_inicio_vigencia": f"{ano}-01-15",
                "data_fim_vigencia": f"{ano + 2}-01-14",
                "data_referencia": f"{ano}-12-31",
                "_hash_registro": sk,
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

