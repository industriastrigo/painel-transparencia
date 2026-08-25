"""Leitura defensiva de células vindas de CSV.

Por que isto existe, em uma frase: **limpar o DataFrame não basta**.

A tentativa anterior trocava NaN por None no DataFrame inteiro, e o teste
confirmava que funcionava — porque o teste olhava `df.iloc[0]["ementa"]`. Só
que o coletor lê linha a linha com `iterrows()`, e o pandas **reconstrói cada
linha como uma Series tipada**, convertendo aquele None de volta para NaN:

    limpo.iloc[1]["ementa"]              → None      ✅
    next(limpo.iterrows())[1].get(...)   → nan       ❌  ← o coletor usa este

E como `NaN` é truthy, `(p.get("ementa") or "")` devolve o NaN e o `[:2000]`
seguinte estoura. O conserto tem que ficar no ponto de USO, não no de carga —
é o único lugar que não depende de como o pandas resolveu tipar a linha.
"""

from __future__ import annotations

import math
from typing import Any


def _vazio(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    return isinstance(valor, str) and not valor.strip()


def texto(valor: Any, limite: int | None = None, padrao: str = "") -> str:
    """Sempre devolve str. Serve para campo que o painel mostra."""
    if _vazio(valor):
        return padrao
    saida = str(valor).strip()
    return saida[:limite] if limite else saida


def opcional(valor: Any, limite: int | None = None) -> str | None:
    """Devolve None em vez de string vazia. Serve para campo que pode faltar —
    e faltar é diferente de estar em branco."""
    if _vazio(valor):
        return None
    saida = str(valor).strip()
    return saida[:limite] if limite else saida


def numero(valor: Any) -> float | None:
    """Converte para float aceitando os dois formatos que as fontes usam.

    A CGU devolve valores monetários como TEXTO no formato brasileiro
    (`"1.234.567,89"`); o IBGE e o SICONFI usam ponto decimal
    (`"1234567.89"`). A versão anterior só trocava vírgula por ponto, então
    `"1.234.567,89"` virava `"1.234.567.89"` e falhava — o valor era gravado
    como texto e qualquer soma depois quebrava.

    A regra de desempate é a posição dos separadores:
      - tem vírgula  → vírgula é o decimal, pontos são milhar
      - só pontos    → o último ponto é decimal, salvo se for grupo de 3
                       dígitos e houver mais de um ponto (`1.234.567`)
    """
    if _vazio(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto_limpo = str(valor).strip().replace(" ", "").replace("R$", "")

    if "," in texto_limpo:
        texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
    elif texto_limpo.count(".") > 1:
        # 1.234.567 — todos são milhar
        texto_limpo = texto_limpo.replace(".", "")

    try:
        return float(texto_limpo)
    except (TypeError, ValueError):
        return None


def inteiro(valor: Any, padrao: int | None = None) -> int | None:
    convertido = numero(valor)
    return padrao if convertido is None else int(convertido)
