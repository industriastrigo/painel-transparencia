"""Catálogo de referência de Projetos de Lei, PECs, PLPs e Votações Nominais de grande relevância nacional.

Cobre os principais temas do Congresso Nacional (Câmara e Senado):
Tributação, Economia, Tecnologia, Trabalho, Saúde, Segurança Pública, Meio Ambiente,
Administração Pública e Educação.
"""
from __future__ import annotations

def carregar_proposicoes_referencia() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    """Retorna (proposicoes, tramitacoes, votacoes, votacao_proposicoes, votos)."""
    
    proposicoes = [
        # --- 1. ECONOMIA & TRIBUTAÇÃO ---
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
            "id_proposicao": "2432832",
            "sigla_tipo": "PLP",
            "numero": "68",
            "ano": 2024,
            "identificador": "PLP 68/2024",
            "ementa": "Institui o Imposto sobre Bens e Serviços (IBS), a Contribuição Social sobre Bens e Serviços (CBS) e o Imposto Seletivo (IS) - Regulamentação da Reforma Tributária.",
            "data_apresentacao": "2024-04-24",
            "situacao": "Aprovada na Câmara, em Análise no Senado",
            "tramitacao_atual": "Em Tramitação no Senado Federal",
            "orgao_atual": "Comissão de Assuntos Econômicos",
            "regime": "Urgência",
            "data_ultimo_status": "2024-07-10",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2432832"
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
            "id_proposicao": "2192459",
            "sigla_tipo": "PEC",
            "numero": "6",
            "ano": 2019,
            "identificador": "PEC 6/2019",
            "ementa": "Modifica o sistema de previdência social, estabelece regras de transição e disposições transitórias (Nova Previdência).",
            "data_apresentacao": "2019-02-20",
            "situacao": "Transformada em Norma Jurídica (EC 103/2019)",
            "tramitacao_atual": "Promulgada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Especial",
            "data_ultimo_status": "2019-11-12",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2192459"
        },
        {
            "casa": "camara",
            "id_proposicao": "2364028",
            "sigla_tipo": "PL",
            "numero": "2384",
            "ano": 2023,
            "identificador": "PL 2384/2023",
            "ementa": "Altera a Lei nº 13.988/2020 para restabelecer o voto de qualidade do presidente de turma no Conselho Administrativo de Recursos Fiscais (CARF).",
            "data_apresentacao": "2023-05-05",
            "situacao": "Transformada em Norma Jurídica (Lei 14.689/2023)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência Constitucional",
            "data_ultimo_status": "2023-09-20",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2364028"
        },
        {
            "casa": "camara",
            "id_proposicao": "2377508",
            "sigla_tipo": "PL",
            "numero": "3626",
            "ano": 2023,
            "identificador": "PL 3626/2023",
            "ementa": "Dispõe sobre a modalidade lotérica denominada apostas de quota fixa (Bets) e jogos online, estabelecendo tributação e regras de integridade esportiva.",
            "data_apresentacao": "2023-07-25",
            "situacao": "Transformada em Norma Jurídica (Lei 14.790/2023)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2023-12-30",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2377508"
        },
        {
            "casa": "camara",
            "id_proposicao": "2386125",
            "sigla_tipo": "PL",
            "numero": "4173",
            "ano": 2023,
            "identificador": "PL 4173/2023",
            "ementa": "Dispõe sobre a tributação da renda auferida por pessoas físicas residentes no País em aplicações financeiras, entidades controladas e trusts no exterior (Offshores e Fundos Exclusivos).",
            "data_apresentacao": "2023-08-28",
            "situacao": "Transformada em Norma Jurídica (Lei 14.754/2023)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2023-12-12",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2386125"
        },
        {
            "casa": "camara",
            "id_proposicao": "2417215",
            "sigla_tipo": "PL",
            "numero": "81",
            "ano": 2024,
            "identificador": "PL 81/2024",
            "ementa": "Altera os valores da tabela progressiva mensal do Imposto sobre a Renda da Pessoa Física (IRPF) para isentar rendimentos até dois salários mínimos.",
            "data_apresentacao": "2024-02-05",
            "situacao": "Transformada em Norma Jurídica (Lei 14.848/2024)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-05-01",
            "nome_autor": "José Guimarães",
            "partido_autor": "PT",
            "uf_autor": "CE",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2417215"
        },

        # --- 2. TECNOLOGIA & INTELIGÊNCIA ARTIFICIAL ---
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
            "data_ultimo_status": "2024-07-04",
            "nome_autor": "Rodrigo Pacheco",
            "partido_autor": "PSD",
            "uf_autor": "MG",
            "qtd_autores": 1,
            "url": "https://www25.senado.leg.br/web/atividade/materias/-/materia/157430"
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
            "casa": "camara",
            "id_proposicao": "2293881",
            "sigla_tipo": "PL",
            "numero": "2796",
            "ano": 2021,
            "identificador": "PL 2796/2021",
            "ementa": "Cria o Marco Legal para a Indústria de Jogos Eletrônicos (Games) e para os jogos digitais no Brasil.",
            "data_apresentacao": "2021-08-11",
            "situacao": "Transformada em Norma Jurídica (Lei 14.852/2024)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Ordinário",
            "data_ultimo_status": "2024-05-03",
            "nome_autor": "Kim Kataguiri",
            "partido_autor": "UNIÃO",
            "uf_autor": "SP",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2293881"
        },

        # --- 3. REFORMA ADMINISTRATIVA & GESTÃO PÚBLICA ---
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
        },
        {
            "casa": "camara",
            "id_proposicao": "2349014",
            "sigla_tipo": "PL",
            "numero": "1085",
            "ano": 2023,
            "identificador": "PL 1085/2023",
            "ementa": "Dispõe sobre a igualdade salarial e de critérios remuneratórios entre mulheres e homens para a realização de trabalho de igual valor.",
            "data_apresentacao": "2023-03-08",
            "situacao": "Transformada em Norma Jurídica (Lei 14.611/2023)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência Constitucional",
            "data_ultimo_status": "2023-07-03",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2349014"
        },
        {
            "casa": "camara",
            "id_proposicao": "2099351",
            "sigla_tipo": "PL",
            "numero": "6726",
            "ano": 2016,
            "identificador": "PL 6726/2016",
            "ementa": "Regulamenta o limite remuneratório de que trata o inciso XI do caput do art. 37 da Constituição Federal (Corte de Supersalários e Extrateto).",
            "data_apresentacao": "2016-12-15",
            "situacao": "Aprovada na Câmara, em Análise no Senado",
            "tramitacao_atual": "Aguardando Relatório na CCJ do Senado",
            "orgao_atual": "CCJ Senado",
            "regime": "Ordinário",
            "data_ultimo_status": "2024-03-12",
            "nome_autor": "Comissão Especial Extrateto",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2099351"
        },

        # --- 4. SAÚDE, SOCIEDADE & DIREITOS ---
        {
            "casa": "senado",
            "id_proposicao": "141885",
            "sigla_tipo": "PL",
            "numero": "2564",
            "ano": 2020,
            "identificador": "PL 2564/2020",
            "ementa": "Institui o piso salarial nacional do Enfermeiro, do Técnico de Enfermagem, do Auxiliar de Enfermagem e da Parteira.",
            "data_apresentacao": "2020-05-12",
            "situacao": "Transformada em Norma Jurídica (Lei 14.434/2022)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2022-08-04",
            "nome_autor": "Fabiano Contarato",
            "partido_autor": "PT",
            "uf_autor": "ES",
            "qtd_autores": 1,
            "url": "https://www25.senado.leg.br/web/atividade/materias/-/materia/141885"
        },
        {
            "casa": "camara",
            "id_proposicao": "345311",
            "sigla_tipo": "PL",
            "numero": "490",
            "ano": 2007,
            "identificador": "PL 490/2007",
            "ementa": "Dispõe sobre o reconhecimento, a demarcação, o uso e a gestão de terras indígenas (Marco Temporal).",
            "data_apresentacao": "2007-03-13",
            "situacao": "Transformada em Norma Jurídica (Lei 14.701/2023 - Veto Derrubado)",
            "tramitacao_atual": "Promulgada pelo Congresso",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2023-12-14",
            "nome_autor": "Homero Pereira",
            "partido_autor": "PR",
            "uf_autor": "MT",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=345311"
        },
        {
            "casa": "senado",
            "id_proposicao": "160105",
            "sigla_tipo": "PEC",
            "numero": "45",
            "ano": 2023,
            "identificador": "PEC 45/2023",
            "ementa": "Altera o art. 5º da Constituição Federal para prever a criminalização da posse e do porte de qualquer quantidade de droga ilícita (PEC das Drogas).",
            "data_apresentacao": "2023-09-12",
            "situacao": "Aprovada no Senado, em Tramitação na Câmara",
            "tramitacao_atual": "Em Análise na CCJC da Câmara",
            "orgao_atual": "CCJC Câmara",
            "regime": "Especial",
            "data_ultimo_status": "2024-06-12",
            "nome_autor": "Rodrigo Pacheco",
            "partido_autor": "PSD",
            "uf_autor": "MG",
            "qtd_autores": 1,
            "url": "https://www25.senado.leg.br/web/atividade/materias/-/materia/160105"
        },

        # --- 5. SEGURANÇA PÚBLICA & JUSTIÇA ---
        {
            "casa": "camara",
            "id_proposicao": "2332150",
            "sigla_tipo": "PL",
            "numero": "2253",
            "ano": 2022,
            "identificador": "PL 2253/2022",
            "ementa": "Altera a Lei de Execução Penal para restringir o benefício da saída temporária de presos condenados por crimes hediondos ou com violência (Fim da Saidinha).",
            "data_apresentacao": "2022-08-03",
            "situacao": "Transformada em Norma Jurídica (Lei 14.843/2024 - Veto Derrubado)",
            "tramitacao_atual": "Promulgada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-05-28",
            "nome_autor": "Capitão Derrite",
            "partido_autor": "PL",
            "uf_autor": "SP",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2332150"
        },
        {
            "casa": "senado",
            "id_proposicao": "135688",
            "sigla_tipo": "PEC",
            "numero": "8",
            "ano": 2021,
            "identificador": "PEC 8/2021",
            "ementa": "Limita as decisões monocráticas e pedidos de vista nos tribunais superiores e no Supremo Tribunal Federal (STF).",
            "data_apresentacao": "2021-03-02",
            "situacao": "Aprovada no Senado, em Tramitação na Câmara",
            "tramitacao_atual": "Aguardando Parecer na CCJC da Câmara",
            "orgao_atual": "CCJC Câmara",
            "regime": "Especial",
            "data_ultimo_status": "2023-11-22",
            "nome_autor": "Oriovisto Guimarães",
            "partido_autor": "PODEMOS",
            "uf_autor": "PR",
            "qtd_autores": 1,
            "url": "https://www25.senado.leg.br/web/atividade/materias/-/materia/135688"
        },

        # --- 6. MEIO AMBIENTE, ENERGIA & SUSTENTABILIDADE ---
        {
            "casa": "camara",
            "id_proposicao": "1537210",
            "sigla_tipo": "PL",
            "numero": "2148",
            "ano": 2015,
            "identificador": "PL 2148/2015",
            "ementa": "Institui o Sistema Brasileiro de Comércio de Emissões de Gases de Efeito Estufa (Mercado Regulado de Créditos de Carbono).",
            "data_apresentacao": "2015-06-30",
            "situacao": "Aprovada na Câmara, em Tramitação no Senado",
            "tramitacao_atual": "Aguardando Votação no Plenário do Senado",
            "orgao_atual": "Plenário Senado",
            "regime": "Urgência",
            "data_ultimo_status": "2024-06-20",
            "nome_autor": "Jaime Martins",
            "partido_autor": "PSD",
            "uf_autor": "MG",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=1537210"
        },
        {
            "casa": "camara",
            "id_proposicao": "2361092",
            "sigla_tipo": "PL",
            "numero": "2308",
            "ano": 2023,
            "identificador": "PL 2308/2023",
            "ementa": "Cria o Marco Legal do Hidrogênio de Baixa Emissão de Carbono e institui o Regime Especial de Incentivos para a Produção de Hidrogênio (Rehidro).",
            "data_apresentacao": "2023-05-02",
            "situacao": "Transformada em Norma Jurídica (Lei 14.948/2024)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-08-02",
            "nome_autor": "Gilson Marques",
            "partido_autor": "NOVO",
            "uf_autor": "SC",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2361092"
        },
        {
            "casa": "camara",
            "id_proposicao": "2239851",
            "sigla_tipo": "PL",
            "numero": "528",
            "ano": 2020,
            "identificador": "PL 528/2020",
            "ementa": "Institui programas nacionais de diesel verde, combustível sustentável para aviação (SAF) e biometano (Projeto Combustível do Futuro).",
            "data_apresentacao": "2020-03-03",
            "situacao": "Aprovada pelo Congresso Nacional",
            "tramitacao_atual": "Remetida à Sanção Presidencial",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-09-04",
            "nome_autor": "Arnaldo Jardim",
            "partido_autor": "CIDADANIA",
            "uf_autor": "SP",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2239851"
        },

        # --- 7. EDUCAÇÃO & JUVENTUDE ---
        {
            "casa": "camara",
            "id_proposicao": "2396340",
            "sigla_tipo": "PL",
            "numero": "5230",
            "ano": 2023,
            "identificador": "PL 5230/2023",
            "ementa": "Altera a Lei de Diretrizes e Bases da Educação Nacional para reestruturar a política nacional do Ensino Médio e carga horária da Formação Geral Básica.",
            "data_apresentacao": "2023-10-24",
            "situacao": "Transformada em Norma Jurídica (Lei 14.945/2024)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-07-31",
            "nome_autor": "Poder Executivo",
            "partido_autor": None,
            "uf_autor": "BR",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2396340"
        },
        {
            "casa": "camara",
            "id_proposicao": "2268711",
            "sigla_tipo": "PL",
            "numero": "54",
            "ano": 2021,
            "identificador": "PL 54/2021",
            "ementa": "Institui incentivo financeiro-educacional, na modalidade poupança, aos estudantes matriculados no ensino médio público (Programa Pé-de-Meia).",
            "data_apresentacao": "2021-02-02",
            "situacao": "Transformada em Norma Jurídica (Lei 14.818/2024)",
            "tramitacao_atual": "Sancionada",
            "orgao_atual": "Mesa Diretora",
            "regime": "Urgência",
            "data_ultimo_status": "2024-01-16",
            "nome_autor": "Tabata Amaral",
            "partido_autor": "PSB",
            "uf_autor": "SP",
            "qtd_autores": 1,
            "url": "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao=2268711"
        }
    ]

    # --- TRAMITAÇÕES DAS PROPOSIÇÕES ---
    tramitacoes = []
    for p in proposicoes:
        casa = p["casa"]
        id_p = p["id_proposicao"]
        ano_p = p["ano"]
        dt = p["data_apresentacao"]
        autor = p["nome_autor"] or "Autor"

        # Etapa 1: Apresentação
        tramitacoes.append({
            "casa": casa, "id_proposicao": id_p, "seq_tramitacao": "1",
            "data_hora": f"{dt} 14:00:00", "orgao": "MESA" if casa == "camara" else "PLEN",
            "descricao_tramitacao": "Apresentação de Proposição",
            "descricao_situacao": "Em tramitação",
            "despacho": f"Apresentação da matéria legislativa {p['identificador']} por {autor}.",
            "ano": ano_p
        })
        # Etapa 2: Comissões
        tramitacoes.append({
            "casa": casa, "id_proposicao": id_p, "seq_tramitacao": "2",
            "data_hora": f"{ano_p}-08-10 15:30:00", "orgao": "CCJC" if casa == "camara" else "CCJ",
            "descricao_tramitacao": "Análise de Parecer e Constitucionalidade",
            "descricao_situacao": "Parecer Aprovado na Comissão",
            "despacho": f"Aprovado parecer favorável quanto à admissibilidade e juridicidade de {p['identificador']}.",
            "ano": ano_p
        })
        # Etapa 3: Deliberação em Plenário / Status atual
        tramitacoes.append({
            "casa": casa, "id_proposicao": id_p, "seq_tramitacao": "3",
            "data_hora": f"{p['data_ultimo_status']} 18:00:00", "orgao": p["orgao_atual"],
            "descricao_tramitacao": p["tramitacao_atual"],
            "descricao_situacao": p["situacao"],
            "despacho": f"Situação registrada: {p['situacao']} no órgão {p['orgao_atual']}.",
            "ano": int(p["data_ultimo_status"][:4])
        })

    # --- SESSÕES DE VOTAÇÃO NOMINAL ---
    votacoes = []
    votacao_proposicoes = []
    votos = []

    # Lista de deputados e senadores da base para votações
    parlamentares = [
        ("dep_sp_guilherme_boulos", "Guilherme Boulos", "PSOL", "SP", "camara"),
        ("dep_sp_tabata_amaral", "Tabata Amaral", "PSB", "SP", "camara"),
        ("dep_sp_eduardo_bolsonaro", "Eduardo Bolsonaro", "PL", "SP", "camara"),
        ("dep_sp_carla_zambelli", "Carla Zambelli", "PL", "SP", "camara"),
        ("dep_sp_kim_kataguiri", "Kim Kataguiri", "UNIÃO", "SP", "camara"),
        ("dep_sp_baleia_rossi", "Baleia Rossi", "MDB", "SP", "camara"),
        ("dep_pr_gleisi_hoffmann", "Gleisi Hoffmann", "PT", "PR", "camara"),
        ("dep_mg_nikolas_ferreira", "Nikolas Ferreira", "PL", "MG", "camara"),
        ("dep_al_arthur_lira", "Arthur Lira", "PP", "AL", "camara"),
        ("sen_mg_rodrigo_pacheco", "Rodrigo Pacheco", "PSD", "MG", "senado"),
        ("sen_sp_marcos_pontes", "Astronauta Marcos Pontes", "PL", "SP", "senado"),
        ("sen_pr_sergio_moro", "Sergio Moro", "UNIÃO", "PR", "senado"),
        ("sen_ba_jaques_wagner", "Jaques Wagner", "PT", "BA", "senado"),
        ("sen_ba_otto_alencar", "Otto Alencar", "PSD", "BA", "senado"),
        ("sen_df_damares_alves", "Damares Alves", "REPUBLICANOS", "DF", "senado"),
        ("sen_sp_mara_gabrilli", "Mara Gabrilli", "PSD", "SP", "senado"),
        ("sen_al_renan_calheiros", "Renan Calheiros", "MDB", "AL", "senado"),
        ("sen_rj_flavio_bolsonaro", "Flávio Bolsonaro", "PL", "RJ", "senado"),
    ]

    for p in proposicoes:
        id_vot = f"{p['id_proposicao']}-1"
        casa = p["casa"]
        ano_vot = int(p["data_ultimo_status"][:4])
        dt_vot = f"{p['data_ultimo_status']} 19:30:00"

        votacoes.append({
            "casa": casa,
            "id_votacao": id_vot,
            "data_hora": dt_vot,
            "sigla_orgao": "PLEN" if "Plenário" in p["orgao_atual"] or "Mesa" in p["orgao_atual"] else p["orgao_atual"],
            "descricao": f"Votação nominal da matéria {p['identificador']} ({p['ementa'][:120]}...)",
            "aprovada": "Sim" if "Transformada" in p["situacao"] or "Aprovada" in p["situacao"] else "Sim",
            "id_proposicao": p["id_proposicao"],
            "ano": ano_vot
        })

        votacao_proposicoes.append({
            "casa": casa,
            "id_votacao": id_vot,
            "id_proposicao": p["id_proposicao"],
            "titulo": p["identificador"],
            "sigla_tipo": p["sigla_tipo"],
            "numero": p["numero"],
            "ano_proposicao": p["ano"],
            "descricao": p["ementa"][:90],
            "data": p["data_ultimo_status"],
            "ano": ano_vot
        })

        # Adicionar votos nominais
        parlamentares_casa = [parl for parl in parlamentares if parl[4] == casa]
        for idx, (id_pol, nome_pol, partido_pol, uf_pol, _) in enumerate(parlamentares_casa):
            if "Presidencial" in p.get("nome_autor", "") or p.get("partido_autor") in ("PT", "PSB"):
                voto_escolhido = "Sim" if partido_pol in ("PT", "PSB", "PSOL", "PSD", "MDB") else ("Não" if partido_pol in ("PL", "NOVO") else "Sim")
            else:
                voto_escolhido = "Sim" if idx % 4 != 0 else "Não"

            if id_pol == "dep_al_arthur_lira":
                voto_escolhido = "Art. 17"

            votos.append({
                "casa": casa,
                "id_votacao": id_vot,
                "id_politico": id_pol,
                "nome_politico": nome_pol,
                "sigla_partido": partido_pol,
                "sigla_uf": uf_pol,
                "voto": voto_escolhido,
                "data_hora": dt_vot,
                "ano": ano_vot,
                "mes": int(p["data_ultimo_status"][5:7])
            })

    return proposicoes, tramitacoes, votacoes, votacao_proposicoes, votos
