"""Mede como o endpoint de Custos do Tesouro pagina. NÃO grava nada.

Existe porque o conserto da paginação depende de três fatos que só a API
responde, e supor qualquer um deles seria repetir o erro que este projeto
existe para não cometer:

  1. o servidor honra um `limit` maior que o padrão de 250?
  2. ele sabe dizer o total de linhas do recorte (`totalResults`)?
  3. quanto custa cada página, em segundos?

Roda em menos de um minuto, faz cerca de dez requisições e imprime um bloco
pronto para colar na conversa.

    python scripts/medir_paginacao_custos.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

BASE = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/custos/tt"
ANO = 2023


def pedir(recurso: str, **parametros) -> tuple[dict | None, float, str]:
    url = f"{BASE}/{recurso}?" + urllib.parse.urlencode(parametros)
    inicio = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=120) as resposta:
            corpo = json.load(resposta)
        return corpo, time.monotonic() - inicio, ""
    except Exception as erro:  # noqa: BLE001
        return None, time.monotonic() - inicio, str(erro)[:120]


def linha(rotulo: str, corpo: dict | None, seg: float, erro: str) -> None:
    if corpo is None:
        print(f"  {rotulo:<26} ERRO: {erro}")
        return
    itens = corpo.get("items", [])
    print(f"  {rotulo:<26} itens={len(itens):<6} limit={corpo.get('limit')} "
          f"hasMore={corpo.get('hasMore')} count={corpo.get('count')} "
          f"totalResults={corpo.get('totalResults')} ({seg:.1f}s)")


def main() -> int:
    print(f"Endpoint: {BASE}")
    print(f"Recorte de teste: ano={ANO}\n")

    for recurso in ("pessoal_ativo", "demais"):
        print(f"[{recurso}]")
        # 1. página padrão, para confirmar o tamanho que o servidor usa sozinho
        corpo, seg, erro = pedir(recurso, ano=ANO)
        linha("padrão (sem limit)", corpo, seg, erro)

        # 2. o servidor honra limites maiores? A resposta traz o `limit` que
        #    ele DE FATO aplicou — é isso que vale, não o que pedimos.
        for limite in (500, 1000, 5000, 10000):
            time.sleep(1.1)  # o freio de 1 req/s é publicado pela fonte
            corpo, seg, erro = pedir(recurso, ano=ANO, limit=limite)
            linha(f"limit={limite}", corpo, seg, erro)

        # 3. dá para saber o tamanho do recorte antes de baixar tudo?
        time.sleep(1.1)
        corpo, seg, erro = pedir(recurso, ano=ANO, limit=1, totalResults="true")
        linha("totalResults=true", corpo, seg, erro)

        # 4. o filtro por mês reduz o recorte na medida esperada?
        time.sleep(1.1)
        corpo, seg, erro = pedir(recurso, ano=ANO, mes=1, limit=1,
                                 totalResults="true")
        linha("mes=1 + totalResults", corpo, seg, erro)
        print()

    print("Cole a saída inteira na conversa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
