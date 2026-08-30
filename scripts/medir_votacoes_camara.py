"""Mede os arquivos em lote de votação da Câmara. NÃO grava nada.

Existe por um defeito medido no acervo: das 21.128 votações coletadas,
**nenhuma** tem `id_proposicao` preenchido. O coletor procura os campos
`ultimaAberturaVotacao_idProposicao` e `idProposicaoObjeto` dentro de
`votacoes-ANO.csv`, e nenhum dos dois aparece — a coluna `url` também sai
vazia, o que sugere que os nomes supostos não existem nesse arquivo.

Sem essa ligação, a promessa central do painel não se cumpre: a ficha de uma
proposição nunca mostra quem votou a favor e contra, mesmo quando o voto
nominal está no acervo.

O que este script responde, sem baixar o conteúdo inteiro:
  1. quais colunas cada arquivo REALMENTE tem;
  2. se existe um arquivo separado que faz a ligação votação → proposição;
  3. uma linha de exemplo de cada, para os nomes aparecerem com valor ao lado.

    python scripts/medir_votacoes_camara.py

Cole a saída inteira na conversa.
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

ANO = 2026
BASE = "https://dadosabertos.camara.leg.br/arquivos"

# Os quatro que a Câmara publica sobre votação. `votacoesProposicoes` e
# `votacoesObjetos` são os candidatos a carregar a ligação que falta.
ARQUIVOS = [
    f"{BASE}/votacoes/csv/votacoes-{ANO}.csv",
    f"{BASE}/votacoesProposicoes/csv/votacoesProposicoes-{ANO}.csv",
    f"{BASE}/votacoesObjetos/csv/votacoesObjetos-{ANO}.csv",
    f"{BASE}/votacoesOrientacoes/csv/votacoesOrientacoes-{ANO}.csv",
]


def cabecalho(url: str, bytes_max: int = 400_000) -> None:
    print(f"\n[{url.rsplit('/', 1)[-1]}]")
    try:
        requisicao = urllib.request.Request(url, headers={"Accept": "text/csv"})
        with urllib.request.urlopen(requisicao, timeout=120) as resposta:
            bruto = resposta.read(bytes_max)
    except Exception as erro:  # noqa: BLE001
        print(f"  ERRO: {str(erro)[:140]}")
        return

    texto = bruto.decode("utf-8", errors="replace")
    # O arquivo é grande: corto no último fim de linha completo.
    corte = texto.rfind("\n")
    leitor = csv.DictReader(io.StringIO(texto[:corte]), delimiter=";")
    colunas = leitor.fieldnames or []
    if len(colunas) == 1 and "," in colunas[0]:      # separador é vírgula
        leitor = csv.DictReader(io.StringIO(texto[:corte]))
        colunas = leitor.fieldnames or []

    print(f"  {len(colunas)} coluna(s): {', '.join(colunas)}")
    for i, linha in enumerate(leitor):
        if i >= 2:
            break
        curto = {k: (str(v)[:40] if v not in (None, "") else "")
                 for k, v in linha.items()}
        print(f"  exemplo {i + 1}: {curto}")


def main() -> int:
    print(f"Arquivos em lote da Câmara, ano {ANO}")
    for url in ARQUIVOS:
        cabecalho(url)
    print("\nCole a saída inteira na conversa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
