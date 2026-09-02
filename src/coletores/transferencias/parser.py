"""Normalização de repasses constitucionais."""
from __future__ import annotations
from ...nucleo.valores import inteiro, numero, opcional, texto

CAMPOS = {
    "cod_ibge": ("co_ibge", "cod_ibge", "codigo_ibge", "co_municipio_ibge"),
    "cod_transferencia": ("codigo", "co_transferencia", "cod_transferencia"),
    "transferencia": ("transferencia", "no_transferencia", "nome"),
    "uf": ("uf", "sg_uf", "sigla_uf"),
    "municipio": ("municipio", "no_municipio", "nome"),
    "ano": ("ano", "an_referencia", "exercicio"),
    "mes": ("mes", "me_referencia", "mes_referencia"),
    "valor": ("valor", "vl_transferencia", "vl_valor", "montante"),
    "cod_siafi": ("cod_siafi", "co_siafi", "codigo_siafi"),
    "regiao": ("regiao", "no_regiao"),
}

def primeiro(linha: dict, *nomes: str):
    if not isinstance(linha, dict):
        return None
    por_minuscula = {str(k).lower(): v for k, v in linha.items()}
    for nome in nomes:
        valor = por_minuscula.get(nome.lower())
        if valor not in (None, ""):
            return valor
    return None

def campo(linha: dict, chave: str):
    return primeiro(linha, *CAMPOS[chave])
