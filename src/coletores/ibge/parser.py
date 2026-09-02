"""Normalização de localidades e indicadores do IBGE."""
from __future__ import annotations

AGREGADOS = {
    "populacao": {
        "agregado": "6579", "variavel": "9324",
        "rotulo": "População residente estimada", "unidade": "pessoas",
    },
    "pib": {
        "agregado": "5938", "variavel": "37",
        "rotulo": "PIB a preços correntes", "unidade": "R$ mil",
    },
}

DERIVADAS = {
    "pib_per_capita": {
        "rotulo": "PIB per capita",
        "unidade": "R$",
        "formula": "pib × 1000 ÷ população",
    },
}
