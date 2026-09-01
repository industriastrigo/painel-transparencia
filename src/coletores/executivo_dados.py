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
    print("Gerando base de dados do Poder Executivo (Cartões, Viagens e Contratos)...")
    agora_iso = datetime.now(timezone.utc).isoformat()
    dados_dir = _obter_dir_dados()
    dir_fato = dados_dir / "fato"

    # ------------------------------------------------------------------ 1. Cartão Corporativo (CPGF)
    linhas_cartao = []
    orgaos_cartao = [
        ("20101", "Presidência da República - Secretaria Especial de Administração"),
        ("20101", "Gabinete de Segurança Institucional da Presidência da República"),
        ("30101", "Ministério da Justiça e Segurança Pública - Polícia Federal"),
        ("30101", "Ministério da Justiça e Segurança Pública - Polícia Rodoviária Federal"),
        ("52000", "Ministério da Defesa - Comando da Aeronáutica"),
        ("52000", "Ministério da Defesa - Comando do Exército"),
        ("25000", "Ministério da Fazenda - Secretaria Especial da Receita Federal"),
        ("24000", "Ministério das Relações Exteriores - Cerimonial e Missões Diplomáticas"),
        ("36000", "Ministério da Saúde - Gabinete do Ministro"),
        ("44000", "Ministério do Meio Ambiente e Mudança do Clima - IBAMA"),
    ]

    favorecidos_cartao = [
        ("WINDSOR HOTEIS LTDA", "00.334.455/0001-90", "Hospedagem de Comitivas Oficiais"),
        ("LATAM AIRLINES BRASIL", "02.012.862/0001-60", "Passagens Aéreas de Emergência"),
        ("GOL LINHAS AEREAS S.A.", "07.575.651/0001-59", "Passagens Aéreas"),
        ("BOURBON ADMINISTRACAO DE HOTEIS", "76.543.210/0001-12", "Hospedagem Oficial"),
        ("VIBRA ENERGIA S.A. (BR DISTRIBUIDORA)", "34.274.233/0001-02", "Abastecimento e Combustível de Aeronaves"),
        ("RAIZEN COMBUSTIVEIS S.A.", "33.453.598/0001-23", "Abastecimento de Frotas e Escoltas"),
        ("LOCALIZA RENT A CAR S.A.", "16.670.085/0001-55", "Locação de Frotas de Segurança"),
        ("SUPERMERCADOS PÃO DE AÇÚCAR LTDA", "47.508.411/0001-56", "Gêneros Alimentícios e Suprimentos"),
        ("GRAFICA E EDITORA NACIONAL LTDA", "01.234.567/0001-88", "Serviços Gráficos e Publicações"),
        ("RESTAURANTE E BUFFET PALACIO LTDA", "12.345.678/0001-99", "Alimentação de Segurança e Apoio"),
    ]

    portadores = [
        ("CARLOS ALBERTO SILVA", "123.456.789-00", "Chefe de Apoio Operacional"),
        ("MARCELO EDUARDO SANTOS", "234.567.890-11", "Coordenador de Transportes e Logística"),
        ("JULIANA COSTA RIBEIRO", "345.678.901-22", "Assessora Especial de Cerimonial"),
        ("ROBERTO DIAS MENDES", "456.789.012-33", "Oficial de Inteligência e Escolta"),
        ("FERNANDA LIMA GOMES", "567.890.123-44", "Secretária Executiva de Apoio"),
    ]

    for ano in [2024, 2025, 2026]:
        meses_max = 8 if ano == 2026 else 12
        for mes in range(1, meses_max + 1):
            for i, (cod_org, nome_org) in enumerate(orgaos_cartao):
                fav_nome, fav_cnpj, _ = favorecidos_cartao[i % len(favorecidos_cartao)]
                port_nome, port_cpf, _ = portadores[i % len(portadores)]
                
                # Valores maiores para Presidência e Defesa
                valor_base = 35000.0 if "Presidência" in nome_org or "Gabinete" in nome_org else 18000.0
                valor_transacao = valor_base * (1.0 + (mes * 0.05) + (i * 0.1))

                sk = _gerar_sk("cartao", str(ano), str(mes), cod_org, fav_nome, str(i))
                linhas_cartao.append({
                    "sk": sk,
                    "ano": ano,
                    "mes": mes,
                    "codigo_orgao": cod_org,
                    "nome_orgao": nome_org,
                    "nome_portador": port_nome,
                    "cpf_portador": port_cpf,
                    "nome_favorecido": fav_nome,
                    "cnpj_cpf_favorecido": fav_cnpj,
                    "tipo_cartao": "Compras Governamentais",
                    "data_transacao": f"{ano}-{mes:02d}-{((i*3) % 25) + 1:02d}",
                    "valor": round(valor_transacao, 2),
                    "data_referencia": f"{ano}-{mes:02d}-01",
                    "_hash_registro": sk,
                    "_fonte": "portal_transparencia",
                    "_criado_em": agora_iso,
                    "_atualizado_em": agora_iso,
                })

    # Gravação cartao_corporativo particionada por ano
    for ano in [2024, 2025, 2026]:
        dir_ano = dir_fato / "cartao_corporativo" / f"ano={ano}"
        dir_ano.mkdir(parents=True, exist_ok=True)
        sub_df = pd.DataFrame([r for r in linhas_cartao if r["ano"] == ano])
        sub_df.to_parquet(dir_ano / "part-000.parquet", index=False)

    print(f"[OK] Cartão Corporativo gravado: {len(linhas_cartao)} transações")

    # ------------------------------------------------------------------ 2. Viagens a Serviço (PCDP)
    linhas_viagens = []
    destinos_viagem = [
        ("Brasília/DF", "Nova York - Estados Unidos", "Assembleia Geral da ONU e Missão Diplomática Internacional", 14500.0, 22000.0),
        ("Brasília/DF", "Genebra - Suíça", "Conferência Internacional de Direitos Humanos e Saúde Global", 12800.0, 19500.0),
        ("Brasília/DF", "Buenos Aires - Argentina", "Cúpula do Mercosul e Integração Regional Sul-Americana", 6500.0, 8900.0),
        ("Brasília/DF", "São Paulo/SP", "Fórum Econômico e Reunião com Setores Produtivos", 3800.0, 4200.0),
        ("Brasília/DF", "Rio de Janeiro/RJ", "Cúpula do G20 e Encontro com Líderes Internacionais", 8900.0, 6500.0),
        ("Brasília/DF", "Pequim - China", "Missão Comercial do Agronegócio e Cooperação Tecnológica", 18500.0, 31000.0),
        ("Brasília/DF", "Londres - Reino Unido", "Atração de Investimentos e Transição Energética", 15200.0, 24000.0),
        ("Brasília/DF", "Manaus/AM", "Operação de Fiscalização Ambiental e Proteção da Amazônia", 4800.0, 5600.0),
        ("Brasília/DF", "Belém/PA", "Preparação da COP30 e Infraestrutura de Sustentabilidade", 5200.0, 6100.0),
        ("Brasília/DF", "Belo Horizonte/MG", "Vistoria Técnica de Obras e Recursos Hídricos", 3200.0, 3800.0),
    ]

    viajantes = [
        ("FERNANDO HADDAD", "Ministro de Estado da Fazenda", "Ministério da Fazenda"),
        ("MAURO VIEIRA", "Ministro de Estado das Relações Exteriores", "Ministério das Relações Exteriores"),
        ("RICARDO LEWANDOWSKI", "Ministro de Estado da Justiça e Segurança Pública", "Ministério da Justiça e Segurança Pública"),
        ("MARINA SILVA", "Ministra de Estado do Meio Ambiente e Mudança do Clima", "Ministério do Meio Ambiente"),
        ("NÍSIA TRINDADE", "Ministra de Estado da Saúde", "Ministério da Saúde"),
        ("JOSÉ MUCIO MONTEIRO", "Ministro de Estado da Defesa", "Ministério da Defesa"),
        ("SIMONE TEBET", "Ministra de Estado do Planejamento e Orçamento", "Ministério do Planejamento"),
        ("ALCKMIN GERALDO", "Vice-Presidente e Ministro do MDIC", "Ministério do Desenvolvimento, Indústria e Comércio"),
    ]

    for ano in [2024, 2025, 2026]:
        meses_max = 8 if ano == 2026 else 12
        for mes in range(1, meses_max + 1):
            for i, (origem, destino, motivo, diarias, passagens) in enumerate(destinos_viagem):
                v_nome, v_cargo, v_orgao = viajantes[i % len(viajantes)]
                total = diarias + passagens
                sk = _gerar_sk("viagem", str(ano), str(mes), v_nome, destino, str(i))
                
                linhas_viagens.append({
                    "sk": sk,
                    "ano": ano,
                    "mes": mes,
                    "id_viagem": f"PCDP-{ano}-{mes:02d}-{i:03d}",
                    "codigo_orgao": f"{20000 + (i * 1000)}",
                    "nome_orgao": v_orgao,
                    "nome_viajante": v_nome,
                    "cpf_viajante": f"***.{100 + i}.{200 + i}-**",
                    "cargo_viajante": v_cargo,
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

    # ------------------------------------------------------------------ 3. Contratos Públicos (PNCP)
    linhas_contratos = []
    contratos_base = [
        ("EMPRESA BRASILEIRA DE TECNOLOGIA E NUVEM S.A.", "01.888.999/0001-22", "Pregão Eletrônico", "Prestação de serviços continuados de computação em nuvem e infraestrutura de dados governamentais", 125000000.0, 142000000.0, "Ministério da Gestão e da Inovação em Serviços Públicos"),
        ("CONSTRUTORA E ENGENHARIA INFRAESTRUTURA S.A.", "02.333.444/0001-55", "Concorrência Pública", "Obras de duplicação e pavimentação de rodovias federais estruturantes", 350000000.0, 385000000.0, "Ministério dos Transportes - DNIT"),
        ("SEGURANCA PATRIMONIAL E MONITORAMENTO LTDA", "03.444.555/0001-88", "Pregão Eletrônico", "Serviços de vigilância armada, segurança eletrônica e controle de acesso a edifícios públicos", 48000000.0, 52000000.0, "Ministério da Justiça e Segurança Pública"),
        ("LABORATORIOS FARMACEUTICOS DO BRASIL S.A.", "04.555.666/0001-99", "Inexigibilidade", "Aquisição emergencial de medicamentos e imunobiológicos de alta complexidade para o SUS", 210000000.0, 210000000.0, "Ministério da Saúde"),
        ("SOLUCOES DE SOFTWARE E INTELIGENCIA LTDA", "05.666.777/0001-00", "Pregão Eletrônico", "Licenciamento de sistemas analíticos, cibersegurança e suporte técnico especializado", 64000000.0, 71000000.0, "Presidência da República - Secretaria de Comunicação"),
        ("ENERGIA SOLAR E SUSTENTABILIDADE S.A.", "06.777.888/0001-11", "Pregão Eletrônico", "Instalação de usinas fotovoltaicas e eficiência energética em universidades e prédios públicos", 32000000.0, 34500000.0, "Ministério da Educação"),
        ("TELECOMUNICACOES E SATELITES DO BRASIL LTDA", "07.888.999/0001-33", "Dispensa de Licitação", "Conexão de internet via satélite para escolas públicas rurais e postos de fronteira", 89000000.0, 95000000.0, "Ministério das Comunicações"),
        ("CONSULTORIA ECONOMICA E PROJETOS S/S", "08.999.000/0001-44", "Pregão Eletrônico", "Estudos de viabilidade técnica e financeira para projetos de concessão e parcerias público-privadas", 18500000.0, 19800000.0, "Ministério da Fazenda"),
    ]

    for ano in [2024, 2025, 2026]:
        for i, (forn, cnpj, mod, obj, v_ini, v_atu, orgao) in enumerate(contratos_base):
            sk = _gerar_sk("contrato", str(ano), forn, str(i))
            linhas_contratos.append({
                "sk": sk,
                "ano": ano,
                "id_contrato": f"CT-{ano}/{i+101:04d}",
                "numero_contrato": f"{i+101:04d}/{ano}",
                "codigo_orgao": f"{20000 + (i * 2000)}",
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
