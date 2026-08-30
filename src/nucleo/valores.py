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


def data_br(valor: Any) -> str | None:
    """`dd/mm/aaaa` ou `dd/mm/aa` → `aaaa-mm-dd`.

    O SADIPEM mistura os dois formatos no MESMO registro: `data_protocolo`
    vem como "14/08/02" e `data_status` como "14/03/2019". Ano de dois
    dígitos é ambíguo por construção, e a escolha aqui é explícita:

        00–69 → 2000–2069        70–99 → 1970–1999

    O corte em 70 não é arbitrário: o SADIPEM cobre pedidos de verificação de
    limites, que existem desde a Lei de Responsabilidade Fiscal (2000). Um
    "98" no acervo é muito mais provavelmente lixo de digitação do que um
    pleito de 1998 — mas transformá-lo em 2098 seria pior, porque um ano no
    futuro passa despercebido em qualquer filtro.

    Devolve None em vez de chutar quando não reconhece o formato: data errada
    é pior que data ausente, porque entra nos filtros como se fosse verdade.
    """
    if _vazio(valor):
        return None
    bruto = str(valor).strip()

    # ISO 8601, com ou sem hora: "2017-08-14", "2014-05-31T23:00:03Z".
    # O SADIPEM devolve NESTE formato, não no dd/mm/aa que a documentação
    # mostra — e a versão anterior desta função lia "2017-08-14" como
    # dia 2017, o que reprovava na validação e devolvia None. Resultado: 84 de
    # 84 pleitos sem data, partição `ano=<NA>` e um WinError 123 no Windows.
    if len(bruto) >= 10 and bruto[4] == "-" and bruto[7] == "-":
        cabeca = bruto[:10]
        try:
            ano, mes, dia = (int(p) for p in cabeca.split("-"))
        except ValueError:
            return None
        if 1 <= mes <= 12 and 1 <= dia <= 31 and 1900 <= ano <= 2100:
            return f"{ano:04d}-{mes:02d}-{dia:02d}"
        return None

    partes = bruto.replace("-", "/").split("/")
    if len(partes) != 3:
        return None
    try:
        dia, mes, ano = (int(p) for p in partes)
    except ValueError:
        return None

    if ano < 100:
        ano = 2000 + ano if ano < 70 else 1900 + ano
    if not (1 <= mes <= 12 and 1 <= dia <= 31 and 1900 <= ano <= 2100):
        return None
    return f"{ano:04d}-{mes:02d}-{dia:02d}"


def ano_de(valor: Any) -> int | None:
    """O ano de uma data brasileira, para particionar."""
    data = data_br(valor)
    return int(data[:4]) if data else None
