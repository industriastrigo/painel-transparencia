"""Mapeamento e extração de campos da API Custos do Governo Federal."""
from __future__ import annotations

CONJUNTOS = {
    "pessoal_ativo": "pessoal_ativo",
    "pessoal_inativo": "pessoal_inativo",
    "pensionista": "pensionistas",
    "demais_custos": "demais_custos",
    "depreciacao": "depreciacao",
    "transferencias": "transferencias",
}

CAMPOS = {
    "ano": ("an_lanc", "an_referencia", "ano"),
    "mes": ("me_lanc", "me_referencia", "mes"),
    "orgao_nome": ("ds_organizacao_n1", "ds_siorg_n05", "ds_organizacao_n0", "ds_siorg_n04", "orgao_nome"),
    "orgao_codigo": ("co_organizacao_n1", "co_siorg_n05", "co_organizacao_n0", "co_siorg_n04", "orgao_codigo"),
    "orgao_n2": ("ds_organizacao_n2", "ds_siorg_n06", "orgao_n2"),
    "orgao_n3": ("ds_organizacao_n3", "ds_siorg_n07", "orgao_n3"),
    "item_custo": ("no_natureza_despesa_deta", "ds_natureza_juridica", "item_custo"),
    "natureza_juridica": ("ds_natureza_juridica", "natureza_juridica"),
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
    return primeiro(linha, *CAMPOS.get(chave, (chave,)))

def valor_custo(linha: dict) -> float | None:
    for k, v in linha.items():
        if k.startswith("va_custo") and v not in (None, ""):
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
    return None
