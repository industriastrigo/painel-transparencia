"""Interpretação e normalização dos dados da Câmara."""
from __future__ import annotations

import pandas as pd
from ...nucleo.valores import inteiro, numero, opcional, texto

TIPOS_DELIBERATIVOS = ("sessão deliberativa", "reunião deliberativa")

def primeiro(linha, *colunas: str, limite: int | None = None) -> str | None:
    for coluna in colunas:
        valor = opcional(linha.get(coluna), limite)
        if valor is not None:
            return valor
    return None

def proposicao_ou_nada(valor) -> str | None:
    texto_id = texto(valor).strip()
    return None if texto_id in ("", "0") else texto_id

def chave_parcela(valor) -> str:
    texto_bruto = "" if valor is None else str(valor).strip()
    if texto_bruto.lower() in ("", "nan", "none", "null"):
        return "0"
    try:
        return str(int(float(texto_bruto)))
    except (TypeError, ValueError):
        return texto_bruto
