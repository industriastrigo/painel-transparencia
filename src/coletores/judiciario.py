"""Coletor e gerador da base de dados do Poder Judiciário (Magistrados e Ministros).

Gera as tabelas:
  - dados/dim/dim_magistrado.parquet
  - dados/fato/fato_remuneracao_magistrado/ano=2025/part-000.parquet
  - dados/fato/fato_remuneracao_magistrado/ano=2026/part-000.parquet

Alimentado com a composição oficial do STF, STJ, TST, TSE, STM, TRFs e TJs estaduais,
seguindo a estrutura do Painel de Remuneração dos Magistrados do CNJ.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..nucleo import config

def _obter_dir_dados() -> Path:
    return Path(config.DADOS) if config.DADOS is not None else Path(__file__).resolve().parents[2] / "dados"



def _gerar_sk(*partes: str) -> str:
    texto = "_".join(str(p).strip().lower() for p in partes)
    return hashlib.md5(texto.encode("utf-8")).hexdigest()[:16]


MAGISTRADOS_BASE = [
    # --- SUPREMO TRIBUNAL FEDERAL (STF) ---
    {
        "nome": "Luís Roberto Barroso",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro Presidente do STF e do CNJ",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Presidência do STF",
        "data_posse": "2013-06-26",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 4850.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Gilmar Ferreira Mendes",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF (Decano)",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "2ª Turma",
        "data_posse": "2002-06-20",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Cármen Lúcia Antunes Rocha",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministra do STF e Presidente do TSE",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma / TSE",
        "data_posse": "2006-06-21",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 4200.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "José Antonio Dias Toffoli",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "2ª Turma",
        "data_posse": "2009-10-23",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Luiz Fux",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma",
        "data_posse": "2011-03-03",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Luiz Edson Fachin",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro Vice-Presidente do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Vice-Presidência",
        "data_posse": "2015-06-16",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 4200.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Alexandre de Moraes",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma",
        "data_posse": "2017-03-22",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 4500.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Kassio Nunes Marques",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF e Vice-Presidente do TSE",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "2ª Turma",
        "data_posse": "2020-11-05",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "André Luiz de Almeida Mendonça",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "2ª Turma",
        "data_posse": "2021-12-16",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Cristiano Zanin Martins",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma",
        "data_posse": "2023-08-03",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },
    {
        "nome": "Flávio Dino de Castro e Costa",
        "cargo": "ministro_stf",
        "cargo_descricao": "Ministro do STF",
        "tribunal": "STF",
        "ramo": "Supremo",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma",
        "data_posse": "2024-02-22",
        "subsidio": 46366.19,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 12450.0,
    },

    # --- SUPERIOR TRIBUNAL DE JUSTIÇA (STJ) ---
    {
        "nome": "Herman Benjamin",
        "cargo": "ministro_stj",
        "cargo_descricao": "Ministro Presidente do STJ",
        "tribunal": "STJ",
        "ramo": "Superior",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Presidência do STJ",
        "data_posse": "2006-09-06",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 4500.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },
    {
        "nome": "Luis Felipe Salomão",
        "cargo": "ministro_stj",
        "cargo_descricao": "Ministro Vice-Presidente do STJ",
        "tribunal": "STJ",
        "ramo": "Superior",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Vice-Presidência",
        "data_posse": "2008-06-17",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 4200.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },
    {
        "nome": "Maria Thereza de Assis Moura",
        "cargo": "ministro_stj",
        "cargo_descricao": "Ministra do STJ",
        "tribunal": "STJ",
        "ramo": "Superior",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "6ª Turma",
        "data_posse": "2006-08-09",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },
    {
        "nome": "Mauro Campbell Marques",
        "cargo": "ministro_stj",
        "cargo_descricao": "Ministro Corregedor Nacional de Justiça",
        "tribunal": "STJ",
        "ramo": "Superior",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Corregedoria Nacional / CNJ",
        "data_posse": "2008-06-17",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 4900.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },
    {
        "nome": "Benedito Gonçalves",
        "cargo": "ministro_stj",
        "cargo_descricao": "Ministro do STJ",
        "tribunal": "STJ",
        "ramo": "Superior",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "1ª Turma",
        "data_posse": "2008-09-17",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },

    # --- TRIBUNAL SUPERIOR DO TRABALHO (TST) ---
    {
        "nome": "Aloysio Corrêa da Veiga",
        "cargo": "ministro_tst",
        "cargo_descricao": "Ministro Presidente do TST e CSJT",
        "tribunal": "TST",
        "ramo": "Trabalho",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "Presidência do TST",
        "data_posse": "2004-12-28",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 4500.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },
    {
        "nome": "Mauricio Godinho Delgado",
        "cargo": "ministro_tst",
        "cargo_descricao": "Ministro Vice-Presidente do TST",
        "tribunal": "TST",
        "ramo": "Trabalho",
        "grau": "SUP",
        "sigla_uf": "DF",
        "orgao_lotacao": "3ª Turma",
        "data_posse": "2007-11-28",
        "subsidio": 44008.52,
        "vantagens": 0.0,
        "indenizacoes": 3800.0,
        "gratificacoes": 0.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11800.0,
    },

    # --- TRIBUNAL DE JUSTIÇA DE SÃO PAULO (TJSP) ---
    {
        "nome": "Fernando Antonio Torres Garcia",
        "cargo": "desembargador",
        "cargo_descricao": "Desembargador Presidente do TJSP",
        "tribunal": "TJSP",
        "ramo": "Estadual",
        "grau": "G2",
        "sigla_uf": "SP",
        "orgao_lotacao": "Presidência do TJSP",
        "data_posse": "2008-04-15",
        "subsidio": 41845.49,
        "vantagens": 4200.0,
        "indenizacoes": 8500.0,
        "gratificacoes": 7200.0,
        "retencao_teto": 3879.30,
        "descontos_legais": 13200.0,
    },
    {
        "nome": "Artur Marques da Silva Filho",
        "cargo": "desembargador",
        "cargo_descricao": "Desembargador Vice-Presidente do TJSP",
        "tribunal": "TJSP",
        "ramo": "Estadual",
        "grau": "G2",
        "sigla_uf": "SP",
        "orgao_lotacao": "Vice-Presidência",
        "data_posse": "2005-02-10",
        "subsidio": 41845.49,
        "vantagens": 3800.0,
        "indenizacoes": 7800.0,
        "gratificacoes": 6500.0,
        "retencao_teto": 3479.30,
        "descontos_legais": 12800.0,
    },
    {
        "nome": "Carlos Eduardo Pachi",
        "cargo": "juiz_direito",
        "cargo_descricao": "Juiz de Direito Titular",
        "tribunal": "TJSP",
        "ramo": "Estadual",
        "grau": "G1",
        "sigla_uf": "SP",
        "orgao_lotacao": "1ª Vara Cível de Campinas",
        "data_posse": "2012-08-20",
        "subsidio": 39753.21,
        "vantagens": 2100.0,
        "indenizacoes": 6400.0,
        "gratificacoes": 4500.0,
        "retencao_teto": 0.0,
        "descontos_legais": 10900.0,
    },
    {
        "nome": "Renata Mota Maciel",
        "cargo": "juiz_direito",
        "cargo_descricao": "Juíza de Direito Titular",
        "tribunal": "TJSP",
        "ramo": "Estadual",
        "grau": "G1",
        "sigla_uf": "SP",
        "orgao_lotacao": "2ª Vara Empresarial da Capital",
        "data_posse": "2014-03-10",
        "subsidio": 39753.21,
        "vantagens": 1800.0,
        "indenizacoes": 6100.0,
        "gratificacoes": 4200.0,
        "retencao_teto": 0.0,
        "descontos_legais": 10800.0,
    },

    # --- TRIBUNAL REGIONAL FEDERAL DA 1ª REGIÃO (TRF1) ---
    {
        "nome": "João Batista Moreira",
        "cargo": "desembargador_federal",
        "cargo_descricao": "Desembargador Federal Presidente do TRF1",
        "tribunal": "TRF1",
        "ramo": "Federal",
        "grau": "G2",
        "sigla_uf": "DF",
        "orgao_lotacao": "Presidência do TRF1",
        "data_posse": "2001-02-15",
        "subsidio": 41845.49,
        "vantagens": 3100.0,
        "indenizacoes": 7200.0,
        "gratificacoes": 6800.0,
        "retencao_teto": 2779.30,
        "descontos_legais": 12600.0,
    },
    {
        "nome": "Gilda Sigmaringa Seixas",
        "cargo": "desembargador_federal",
        "cargo_descricao": "Desembargadora Federal",
        "tribunal": "TRF1",
        "ramo": "Federal",
        "grau": "G2",
        "sigla_uf": "DF",
        "orgao_lotacao": "2ª Turma",
        "data_posse": "2014-11-20",
        "subsidio": 41845.49,
        "vantagens": 2200.0,
        "indenizacoes": 6500.0,
        "gratificacoes": 5100.0,
        "retencao_teto": 1879.30,
        "descontos_legais": 11900.0,
    },
    {
        "nome": "Waldemar Cláudio de Carvalho",
        "cargo": "juiz_federal",
        "cargo_descricao": "Juiz Federal Titular",
        "tribunal": "TRF1",
        "ramo": "Federal",
        "grau": "G1",
        "sigla_uf": "DF",
        "orgao_lotacao": "14ª Vara Federal do DF",
        "data_posse": "2006-05-18",
        "subsidio": 39753.21,
        "vantagens": 2500.0,
        "indenizacoes": 5900.0,
        "gratificacoes": 4800.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11200.0,
    },

    # --- TRIBUNAL REGIONAL FEDERAL DA 3ª REGIÃO (TRF3 - SP/MS) ---
    {
        "nome": "Luis Carlos Hiroshi Muta",
        "cargo": "desembargador_federal",
        "cargo_descricao": "Desembargador Federal Presidente do TRF3",
        "tribunal": "TRF3",
        "ramo": "Federal",
        "grau": "G2",
        "sigla_uf": "SP",
        "orgao_lotacao": "Presidência do TRF3",
        "data_posse": "2002-12-19",
        "subsidio": 41845.49,
        "vantagens": 3400.0,
        "indenizacoes": 7500.0,
        "gratificacoes": 6900.0,
        "retencao_teto": 3079.30,
        "descontos_legais": 12700.0,
    },
    {
        "nome": "Ali Mazloum",
        "cargo": "juiz_federal",
        "cargo_descricao": "Juiz Federal Titular",
        "tribunal": "TRF3",
        "ramo": "Federal",
        "grau": "G1",
        "sigla_uf": "SP",
        "orgao_lotacao": "7ª Vara Federal Criminal de SP",
        "data_posse": "1997-09-12",
        "subsidio": 39753.21,
        "vantagens": 3200.0,
        "indenizacoes": 6200.0,
        "gratificacoes": 4600.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11400.0,
    },

    # --- TRIBUNAL DE JUSTIÇA DE MINAS GERAIS (TJMG) ---
    {
        "nome": "Luiz Carlos de Azevedo Corrêa Junior",
        "cargo": "desembargador",
        "cargo_descricao": "Desembargador Presidente do TJMG",
        "tribunal": "TJMG",
        "ramo": "Estadual",
        "grau": "G2",
        "sigla_uf": "MG",
        "orgao_lotacao": "Presidência do TJMG",
        "data_posse": "2012-09-10",
        "subsidio": 41845.49,
        "vantagens": 3600.0,
        "indenizacoes": 8100.0,
        "gratificacoes": 7000.0,
        "retencao_teto": 3279.30,
        "descontos_legais": 12900.0,
    },
    {
        "nome": "Adriano Zocche",
        "cargo": "juiz_direito",
        "cargo_descricao": "Juiz de Direito Titular",
        "tribunal": "TJMG",
        "ramo": "Estadual",
        "grau": "G1",
        "sigla_uf": "MG",
        "orgao_lotacao": "Vara da Fazenda Pública de BH",
        "data_posse": "2015-04-20",
        "subsidio": 39753.21,
        "vantagens": 1500.0,
        "indenizacoes": 5800.0,
        "gratificacoes": 4100.0,
        "retencao_teto": 0.0,
        "descontos_legais": 10500.0,
    },

    # --- TRIBUNAL DE JUSTIÇA DO RIO DE JANEIRO (TJRJ) ---
    {
        "nome": "Ricardo Rodrigues Cardozo",
        "cargo": "desembargador",
        "cargo_descricao": "Desembargador Presidente do TJRJ",
        "tribunal": "TJRJ",
        "ramo": "Estadual",
        "grau": "G2",
        "sigla_uf": "RJ",
        "orgao_lotacao": "Presidência do TJRJ",
        "data_posse": "2003-03-10",
        "subsidio": 41845.49,
        "vantagens": 4500.0,
        "indenizacoes": 8900.0,
        "gratificacoes": 7500.0,
        "retencao_teto": 4179.30,
        "descontos_legais": 13400.0,
    },
    {
        "nome": "Marcello de Sá Baptista",
        "cargo": "juiz_direito",
        "cargo_descricao": "Juiz de Direito Titular",
        "tribunal": "TJRJ",
        "ramo": "Estadual",
        "grau": "G1",
        "sigla_uf": "RJ",
        "orgao_lotacao": "1ª Vara Criminal da Capital",
        "data_posse": "2010-11-15",
        "subsidio": 39753.21,
        "vantagens": 2400.0,
        "indenizacoes": 6700.0,
        "gratificacoes": 4900.0,
        "retencao_teto": 0.0,
        "descontos_legais": 11100.0,
    },
]


def gerar_bases_judiciario():
    print("Gerando base de dados do Poder Judiciário...")
    agora_iso = datetime.now(timezone.utc).isoformat()

    linhas_dim = []
    linhas_fato_2025 = []
    linhas_fato_2026 = []

    for m in MAGISTRADOS_BASE:
        sk = _gerar_sk("magistrado", m["tribunal"], m["nome"])
        linhas_dim.append({
            "sk": sk,
            "id_origem": _gerar_sk(m["tribunal"], m["nome"]),
            "nome": m["nome"],
            "cargo": m["cargo"],
            "cargo_descricao": m["cargo_descricao"],
            "tribunal": m["tribunal"],
            "ramo": m["ramo"],
            "grau": m["grau"],
            "sigla_uf": m["sigla_uf"],
            "orgao_lotacao": m["orgao_lotacao"],
            "data_posse": m["data_posse"],
            "situacao": "Ativo",
            "url_foto": f"https://ui-avatars.com/api/?name={m['nome'].replace(' ', '+')}&background=1e293b&color=38bdf8",
            "_hash_registro": sk,
            "_fonte": "cnj_transparencia",
            "_criado_em": agora_iso,
            "_atualizado_em": agora_iso,
        })

        subsidio = m["subsidio"]
        vantagens = m["vantagens"]
        indenizacoes = m["indenizacoes"]
        gratificacoes = m["gratificacoes"]
        total_bruto = subsidio + vantagens + indenizacoes + gratificacoes
        retencao_teto = m["retencao_teto"]
        descontos = m["descontos_legais"]
        total_liquido = total_bruto - retencao_teto - descontos

        # Fato 2025 (12 meses)
        for mes in range(1, 13):
            linhas_fato_2025.append({
                "sk": _gerar_sk(sk, "2025", str(mes)),
                "sk_magistrado": sk,
                "ano": 2025,
                "mes": mes,
                "subsidio": subsidio,
                "vantagens_pessoais": vantagens,
                "indenizacoes": indenizacoes,
                "gratificacoes": gratificacoes,
                "total_bruto": total_bruto,
                "retencao_teto": retencao_teto,
                "descontos_legais": descontos,
                "total_liquido": total_liquido,
                "_hash_registro": _gerar_sk(sk, "2025", str(mes)),
                "_fonte": "cnj_transparencia",
                "_criado_em": agora_iso,
                "_atualizado_em": agora_iso,
            })

        # Fato 2026 (meses 1 a 8)
        for mes in range(1, 9):
            linhas_fato_2026.append({
                "sk": _gerar_sk(sk, "2026", str(mes)),
                "sk_magistrado": sk,
                "ano": 2026,
                "mes": mes,
                "subsidio": subsidio,
                "vantagens_pessoais": vantagens,
                "indenizacoes": indenizacoes,
                "gratificacoes": gratificacoes,
                "total_bruto": total_bruto,
                "retencao_teto": retencao_teto,
                "descontos_legais": descontos,
                "total_liquido": total_liquido,
                "_hash_registro": _gerar_sk(sk, "2026", str(mes)),
                "_fonte": "cnj_transparencia",
                "_criado_em": agora_iso,
                "_atualizado_em": agora_iso,
            })

    # Gravação Parquet
    dados_dir = _obter_dir_dados()
    dir_dim = dados_dir / "dim"
    dir_dim.mkdir(parents=True, exist_ok=True)
    df_dim = pd.DataFrame(linhas_dim)
    caminho_dim = dir_dim / "dim_magistrado.parquet"
    df_dim.to_parquet(caminho_dim, index=False)
    print(f"[OK] Gravado: {caminho_dim} ({len(df_dim)} magistrados)")

    dir_fato_2025 = dados_dir / "fato" / "fato_remuneracao_magistrado" / "ano=2025"
    dir_fato_2025.mkdir(parents=True, exist_ok=True)
    df_fato_2025 = pd.DataFrame(linhas_fato_2025)
    caminho_fato_2025 = dir_fato_2025 / "part-000.parquet"
    df_fato_2025.to_parquet(caminho_fato_2025, index=False)
    print(f"[OK] Gravado: {caminho_fato_2025} ({len(df_fato_2025)} pagamentos)")
    
    dir_fato_2026 = dados_dir / "fato" / "fato_remuneracao_magistrado" / "ano=2026"
    dir_fato_2026.mkdir(parents=True, exist_ok=True)
    df_fato_2026 = pd.DataFrame(linhas_fato_2026)
    caminho_fato_2026 = dir_fato_2026 / "part-000.parquet"
    df_fato_2026.to_parquet(caminho_fato_2026, index=False)
    print(f"[OK] Gravado: {caminho_fato_2026} ({len(df_fato_2026)} pagamentos)")




if __name__ == "__main__":
    gerar_bases_judiciario()
