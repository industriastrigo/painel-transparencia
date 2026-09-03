"""Catálogo Completo da Bancada do Congresso Nacional (81 Senadores e Principais Deputados).

Contém os 3 senadores oficiais de cada uma das 27 Unidades da Federação e
bancada representativa de deputados federais de todos os partidos e estados.
"""
from __future__ import annotations

# Catálogo completo dos 81 Senadores do Brasil (3 por UF)
SENADORES_81 = [
    # AC
    ("sen_ac_alan_rick", "Alan Rick Miranda", "Alan Rick", "UNIÃO", "AC"),
    ("sen_ac_marcio_bittar", "Márcio Miguel Bittar", "Márcio Bittar", "UNIÃO", "AC"),
    ("sen_ac_sergio_petecao", "Sérgio de Oliveira Petecão", "Sérgio Petecão", "PSD", "AC"),
    # AL
    ("sen_al_renan_calheiros", "José Renan Vasconcelos Calheiros", "Renan Calheiros", "MDB", "AL"),
    ("sen_al_rodrigo_cunha", "Rodrigo Santos Cunha", "Rodrigo Cunha", "PODEMOS", "AL"),
    ("sen_al_fernando_farias", "Fernando Farias", "Fernando Farias", "MDB", "AL"),
    # AP
    ("sen_ap_davi_alcolumbre", "David Samuel Alcolumbre Tobelem", "Davi Alcolumbre", "UNIÃO", "AP"),
    ("sen_ap_randolfe_rodrigues", "Randolfe Rodrigues", "Randolfe Rodrigues", "PT", "AP"),
    ("sen_ap_lucas_barreto", "Lucas Barreto", "Lucas Barreto", "PSD", "AP"),
    # AM
    ("sen_am_eduardo_braga", "Carlos Eduardo de Souza Braga", "Eduardo Braga", "MDB", "AM"),
    ("sen_am_omar_aziz", "Omar José Abdel Aziz", "Omar Aziz", "PSD", "AM"),
    ("sen_am_plinio_valerio", "Plínio Valério", "Plínio Valério", "PSDB", "AM"),
    # BA
    ("sen_ba_jaques_wagner", "Jaques Wagner", "Jaques Wagner", "PT", "BA"),
    ("sen_ba_otto_alencar", "Otto Roberto Mendonça de Alencar", "Otto Alencar", "PSD", "BA"),
    ("sen_ba_angelo_coronel", "Angelo Mário Coronel de Azevedo Martins", "Angelo Coronel", "PSD", "BA"),
    # CE
    ("sen_ce_cid_gomes", "Cid Ferreira Gomes", "Cid Gomes", "PSB", "CE"),
    ("sen_ce_eduardo_girao", "Eduardo Girão", "Eduardo Girão", "NOVO", "CE"),
    ("sen_ce_augusta_brito", "Augusta Brito de Paula", "Augusta Brito", "PT", "CE"),
    # DF
    ("sen_df_damares_alves", "Damares Regina Alves", "Damares Alves", "REPUBLICANOS", "DF"),
    ("sen_df_izalci_lucas", "Izalci Lucas Ferreira", "Izalci Lucas", "PL", "DF"),
    ("sen_df_leila_barros", "Leila Gomes de Barros Rêgo", "Leila Barros", "PDT", "DF"),
    # ES
    ("sen_es_fabiano_contarato", "Fabiano Contarato", "Fabiano Contarato", "PT", "ES"),
    ("sen_es_marcos_do_val", "Marcos Ribeiro do Val", "Marcos do Val", "PODEMOS", "ES"),
    ("sen_es_magno_malta", "Magno Pereira Malta", "Magno Malta", "PL", "ES"),
    # GO
    ("sen_go_jorge_kajuru", "Jorge Kajuru Reis da Costa Nasser", "Jorge Kajuru", "PSB", "GO"),
    ("sen_go_vanderlan_cardoso", "Vanderlan Vieira Cardoso", "Vanderlan Cardoso", "PSD", "GO"),
    ("sen_go_wilder_morais", "Wilder Pedro de Morais", "Wilder Morais", "PL", "GO"),
    # MA
    ("sen_ma_eliziane_gama", "Eliziane Pereira Gama Melo", "Eliziane Gama", "PSD", "MA"),
    ("sen_ma_weverton_rocha", "Weverton Rocha Marques de Sousa", "Weverton Rocha", "PDT", "MA"),
    ("sen_ma_ana_paula_lobato", "Ana Paula Lobato", "Ana Paula Lobato", "PDT", "MA"),
    # MT
    ("sen_mt_jayme_campos", "Jayme Veríssimo de Campos", "Jayme Campos", "UNIÃO", "MT"),
    ("sen_mt_margareth_buzetti", "Margareth Buzetti", "Margareth Buzetti", "PSD", "MT"),
    ("sen_mt_wellington_fagundes", "Wellington Antônio Fagundes", "Wellington Fagundes", "PL", "MT"),
    # MS
    ("sen_ms_nelsinho_trad", "Nelson Trad Filho", "Nelsinho Trad", "PSD", "MS"),
    ("sen_ms_soraya_thronicke", "Soraya Vieira Thronicke", "Soraya Thronicke", "PODEMOS", "MS"),
    ("sen_ms_tereza_cristina", "Tereza Cristina Corrêa da Costa Dias", "Tereza Cristina", "PP", "MS"),
    # MG
    ("sen_mg_rodrigo_pacheco", "Rodrigo Otavio Soares Pacheco", "Rodrigo Pacheco", "PSD", "MG"),
    ("sen_mg_carlos_viana", "Carlos Alberto Dias Viana", "Carlos Viana", "PODEMOS", "MG"),
    ("sen_mg_cleitinho", "Cleiton Gontijo de Azevedo", "Cleitinho", "REPUBLICANOS", "MG"),
    # PA
    ("sen_pa_beto_faro", "José Roberto Oliveira Faro", "Beto Faro", "PT", "PA"),
    ("sen_pa_jader_barbalho", "Jader Fontenelle Barbalho", "Jader Barbalho", "MDB", "PA"),
    ("sen_pa_zequinha_marinho", "José da Cruz Marinho", "Zequinha Marinho", "PODEMOS", "PA"),
    # PB
    ("sen_pb_daniella_ribeiro", "Daniella Velloso Borges Ribeiro", "Daniella Ribeiro", "PSD", "PB"),
    ("sen_pb_efraim_filho", "Efraim de Araújo Morais Filho", "Efraim Filho", "UNIÃO", "PB"),
    ("sen_pb_veneziano_vital", "Veneziano Vital do Rêgo Segundo Neto", "Veneziano Vital do Rêgo", "MDB", "PB"),
    # PR
    ("sen_pr_sergio_moro", "Sergio Fernando Moro", "Sergio Moro", "UNIÃO", "PR"),
    ("sen_pr_flavio_arns", "Flávio José Arns", "Flávio Arns", "PSB", "PR"),
    ("sen_pr_oriovisto_guimaraes", "Oriovisto Guimarães", "Oriovisto Guimarães", "PODEMOS", "PR"),
    # PE
    ("sen_pe_humberto_costa", "Humberto Sérgio Costa Lima", "Humberto Costa", "PT", "PE"),
    ("sen_pe_teresa_leitao", "Maria Teresa Leitão de Melo", "Teresa Leitão", "PT", "PE"),
    ("sen_pe_fernando_dueire", "Fernando Dueire", "Fernando Dueire", "MDB", "PE"),
    # PI
    ("sen_pi_ciro_nogueira", "Ciro Nogueira Lima Filho", "Ciro Nogueira", "PP", "PI"),
    ("sen_pi_marcelo_castro", "Marcelo Costa e Castro", "Marcelo Castro", "MDB", "PI"),
    ("sen_pi_jussara_lima", "Jussara Gomes Alves de Sousa Lima", "Jussara Lima", "PSD", "PI"),
    # RJ
    ("sen_rj_flavio_bolsonaro", "Flávio Nantes Bolsonaro", "Flávio Bolsonaro", "PL", "RJ"),
    ("sen_rj_carlos_portinho", "Carlos Francisco Portinho", "Carlos Portinho", "PL", "RJ"),
    ("sen_rj_romario", "Romário de Souza Faria", "Romário", "PL", "RJ"),
    # RN
    ("sen_rn_rogerio_marinho", "Rogério Simonetti Marinho", "Rogério Marinho", "PL", "RN"),
    ("sen_rn_styvenson_valentim", "Elysio Styvenson Valentim Mendes", "Styvenson Valentim", "PODEMOS", "RN"),
    ("sen_rn_zenaide_maia", "Zenaide Maia Calado Pereira dos Santos", "Zenaide Maia", "PSD", "RN"),
    # RS
    ("sen_rs_hamilton_mourao", "Antônio Hamilton Martins Mourão", "Hamilton Mourão", "REPUBLICANOS", "RS"),
    ("sen_rs_luis_carlos_heinze", "Luis Carlos Heinze", "Luis Carlos Heinze", "PP", "RS"),
    ("sen_rs_paulo_paim", "Paulo Renato Paim", "Paulo Paim", "PT", "RS"),
    # RO
    ("sen_ro_confucio_moura", "Confúcio Aires Moura", "Confúcio Moura", "MDB", "RO"),
    ("sen_ro_jaime_bagattoli", "Jaime Maximino Bagattoli", "Jaime Bagattoli", "PL", "RO"),
    ("sen_ro_marcos_rogerio", "Marcos Rogério da Silva Brito", "Marcos Rogério", "PL", "RO"),
    # RR
    ("sen_rr_chico_rodrigues", "Francisco de Assis Rodrigues", "Chico Rodrigues", "PSB", "RR"),
    ("sen_rr_dr_hiran", "Hiran Manuel Gonçalves da Silva", "Dr. Hiran", "PP", "RR"),
    ("sen_rr_mecias_de_jesus", "Antônio Mecias Pereira de Jesus", "Mecias de Jesus", "REPUBLICANOS", "RR"),
    # SC
    ("sen_sc_esperidiao_amin", "Esperidião Amin Helou Filho", "Esperidião Amin", "PP", "SC"),
    ("sen_sc_ivete_da_silveira", "Ivete Appel da Silveira", "Ivete da Silveira", "MDB", "SC"),
    ("sen_sc_jorge_seif", "Jorge Seif Junior", "Jorge Seif", "PL", "SC"),
    # SP
    ("sen_sp_marcos_pontes", "Marcos Cesar Pontes", "Astronauta Marcos Pontes", "PL", "SP"),
    ("sen_sp_mara_gabrilli", "Mara Cristina Gabrilli", "Mara Gabrilli", "PSD", "SP"),
    ("sen_sp_alexandre_giordano", "Alexandre Luiz Giordano", "Alexandre Giordano", "MDB", "SP"),
    # SE
    ("sen_se_alessandro_vieira", "Alessandro Vieira", "Alessandro Vieira", "MDB", "SE"),
    ("sen_se_laercio_oliveira", "Laércio José de Oliveira", "Laércio Oliveira", "PP", "SE"),
    ("sen_se_rogerio_carvalho", "Rogério Carvalho Santos", "Rogério Carvalho", "PT", "SE"),
    # TO
    ("sen_to_eduardo_gomes", "Eduardo Gomes", "Eduardo Gomes", "PL", "TO"),
    ("sen_to_dorinha_seabra", "Maria Auxiliadora Seabra Rezende", "Professora Dorinha Seabra", "UNIÃO", "TO"),
    ("sen_to_iraja", "Irajá Silvestre Filho", "Irajá", "PSD", "TO"),
]

# Bancada representativa de 45+ Deputados Federais dos principais estados e blocos
DEPUTADOS_FEDERAIS = [
    ("dep_sp_guilherme_boulos", "Guilherme Castro Boulos", "Guilherme Boulos", "PSOL", "SP"),
    ("dep_sp_tabata_amaral", "Tabata Claudia Amaral de Pontes", "Tabata Amaral", "PSB", "SP"),
    ("dep_sp_eduardo_bolsonaro", "Eduardo Nantes Bolsonaro", "Eduardo Bolsonaro", "PL", "SP"),
    ("dep_sp_carla_zambelli", "Carla Zambelli Salgado", "Carla Zambelli", "PL", "SP"),
    ("dep_sp_kim_kataguiri", "Kim Patroca Kataguiri", "Kim Kataguiri", "UNIÃO", "SP"),
    ("dep_sp_baleia_rossi", "Luiz Felipe Baleia Tenuto Rossi", "Baleia Rossi", "MDB", "SP"),
    ("dep_sp_marcos_pereira", "Marcos Antônio Pereira", "Marcos Pereira", "REPUBLICANOS", "SP"),
    ("dep_sp_ricardo_salles", "Ricardo de Aquino Salles", "Ricardo Salles", "NOVO", "SP"),
    ("dep_sp_mario_frias", "Mário Luís Frias", "Mario Frias", "PL", "SP"),
    ("dep_sp_luiza_erundina", "Luiza Erundina de Sousa", "Luiza Erundina", "PSOL", "SP"),
    ("dep_sp_arlindo_chinaglia", "Arlindo Chinaglia Junior", "Arlindo Chinaglia", "PT", "SP"),
    ("dep_sp_alexandre_padilha", "Alexandre Rocha Santos Padilha", "Alexandre Padilha", "PT", "SP"),
    ("dep_mg_nikolas_ferreira", "Nikolas Ferreira de Oliveira", "Nikolas Ferreira", "PL", "MG"),
    ("dep_mg_aecio_neves", "Aécio Neves da Cunha", "Aécio Neves", "PSDB", "MG"),
    ("dep_mg_reginaldo_lopes", "Reginaldo Lazaro de Oliveira Lopes", "Reginaldo Lopes", "PT", "MG"),
    ("dep_mg_duda_salabert", "Duda Salabert Rosa", "Duda Salabert", "PDT", "MG"),
    ("dep_mg_marcelo_alvaro", "Marcelo Álvaro Antônio", "Marcelo Álvaro Antônio", "PL", "MG"),
    ("dep_rj_lindbergh_farias", "Lindbergh Farias", "Lindbergh Farias", "PT", "RJ"),
    ("dep_rj_jandira_feghali", "Jandira Feghali", "Jandira Feghali", "PCdoB", "RJ"),
    ("dep_rj_general_pazuello", "Eduardo Pazuello", "General Pazuello", "PL", "RJ"),
    ("dep_rj_taliria_petrone", "Talíria Petrone Soares", "Talíria Petrone", "PSOL", "RJ"),
    ("dep_rj_chiquinho_brazao", "João Francisco Inácio Brazão", "Chiquinho Brazão", "SEM PARTIDO", "RJ"),
    ("dep_rj_hugo_leal", "Hugo Leal Melo da Silva", "Hugo Leal", "PSD", "RJ"),
    ("dep_al_arthur_lira", "Arthur César Pereira de Lira", "Arthur Lira", "PP", "AL"),
    ("dep_pr_gleisi_hoffmann", "Gleisi Helena Hoffmann", "Gleisi Hoffmann", "PT", "PR"),
    ("dep_pr_deltan_dallagnol", "Deltan Martinazzo Dallagnol", "Deltan Dallagnol", "NOVO", "PR"),
    ("dep_pr_filipe_barros", "Filipe Barros Baptista de Toledo Ribeiro", "Filipe Barros", "PL", "PR"),
    ("dep_df_bia_kicis", "Beatriz Kicis Torrents de Sordi", "Bia Kicis", "PL", "DF"),
    ("dep_df_erika_kokay", "Erika Jucá Kokay", "Erika Kokay", "PT", "DF"),
    ("dep_ba_antonio_brito", "Antonio Luiz Paranhos Ribeiro Leite de Brito", "Antonio Brito", "PSD", "BA"),
    ("dep_ba_elmar_nascimento", "Elmar José Vieira Nascimento", "Elmar Nascimento", "UNIÃO", "BA"),
    ("dep_ba_ze_neto", "José Cerqueira de Santana Neto", "Zé Neto", "PT", "BA"),
    ("dep_ce_jose_guimaraes", "José Nobre Guimarães", "José Guimarães", "PT", "CE"),
    ("dep_ce_andre_fernandes", "André Fernandes de Oliveira", "André Fernandes", "PL", "CE"),
    ("dep_ce_ciro_gomes", "Ciro Ferreira Gomes", "Ciro Gomes", "PDT", "CE"),
    ("dep_pe_tulio_gadelha", "Túlio Gadêlha Sales de Melo", "Túlio Gadêlha", "REDE", "PE"),
    ("dep_pe_eduardo_da_fonte", "Eduardo da Fonte de Albuquerque Silva", "Eduardo da Fonte", "PP", "PE"),
    ("dep_pb_aguinaldo_ribeiro", "Aguinaldo Velloso Borges Ribeiro", "Aguinaldo Ribeiro", "PP", "PB"),
    ("dep_pb_hugo_motta", "Hugo Motta Wanderley da Nóbrega", "Hugo Motta", "REPUBLICANOS", "PB"),
    ("dep_rs_marcel_van_hattem", "Marcel van Hattem", "Marcel van Hattem", "NOVO", "RS"),
    ("dep_rs_maria_do_rosario", "Maria do Rosário Nunes", "Maria do Rosário", "PT", "RS"),
    ("dep_rs_bibo_nunes", "Alcides Bibo Nunes da Silva", "Bibo Nunes", "PL", "RS"),
    ("dep_sc_caroline_de_toni", "Caroline Rodrigues de Toni", "Caroline de Toni", "PL", "SC"),
    ("dep_sc_pedro_uczarai", "Pedro Francisco Uczai", "Pedro Uczai", "PT", "SC"),
    ("dep_go_gustavo_gayer", "Gustavo Gayer Machado de Araujo", "Gustavo Gayer", "PL", "GO"),
    ("dep_go_silvye_alves", "Silvye Alves da Rocha Lima", "Silvye Alves", "UNIÃO", "GO"),
    ("dep_pa_alessandra_haber", "Alessandra Haber Carvalho Silva", "Dra. Alessandra Haber", "MDB", "PA"),
    ("dep_pa_eder_mauro", "Éder Mauro Cardoso Barra", "Delegado Éder Mauro", "PL", "PA"),
]

def obter_todos_parlamentares() -> list[dict]:
    """Retorna a lista completa unificada de senadores e deputados."""
    resultado = []
    for sk, nome, urna, partido, uf in SENADORES_81:
        resultado.append({
            "sk": sk, "nome": nome, "nome_eleitoral": urna,
            "cargo": "senador", "partido": partido, "uf": uf, "casa": "senado"
        })
    for sk, nome, urna, partido, uf in DEPUTADOS_FEDERAIS:
        resultado.append({
            "sk": sk, "nome": nome, "nome_eleitoral": urna,
            "cargo": "deputado_federal", "partido": partido, "uf": uf, "casa": "camara"
        })
    return resultado
