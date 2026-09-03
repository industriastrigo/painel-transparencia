"""Dados de referência curados — o que não vem de API.

Subsídio de cargo público é fixado em **norma**, não publicado em endpoint.
Alguém precisa transcrever. Este módulo carrega essa transcrição de
`referencias/subsidios.csv` para dentro do armazém, com duas garantias:

1. **Toda linha carrega a norma e a vigência.** Valor de salário sem a norma
   ao lado é número indefensável — e num painel de transparência ser
   contestado é o cenário esperado, não o excepcional.
2. **Toda linha diz se foi conferida.** As que vieram do meu rascunho entram
   com `conferido=nao`, e o painel as mostra marcadas. Quem confere é você,
   trocando para `sim` no CSV.

O arquivo é um CSV comum, editável no Excel. Não é código, é dado — e dado
que você precisa poder corrigir sem me pedir nada.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..nucleo import armazem, config, controle
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import numero, opcional, texto

log = obter_log("coletores.referencias")

FONTE = "referencia"


def caminho_subsidios() -> Path:
    return config.RAIZ / "referencias" / "subsidios.csv"


def carregar_subsidios(arquivo: Path | None = None) -> int:
    destino = arquivo or caminho_subsidios()
    if not destino.exists():
        log.error("arquivo de referência não encontrado: %s", destino)
        return 0

    with destino.open(encoding="utf-8") as f:
        linhas_csv = list(csv.DictReader(f))

    cargos, subsidios = [], []
    for l in linhas_csv:
        cod = texto(l.get("cod_cargo"))
        if not cod:
            continue

        cargos.append({
            "cod_cargo": cod,
            "cargo": texto(l.get("cargo")),
            "poder": opcional(l.get("poder")),
            "esfera": opcional(l.get("esfera")),
            "ramo": opcional(l.get("ramo")),
            "ocupantes": numero(l.get("ocupantes")),
        })

        subsidios.append({
            "cod_cargo": cod,
            "vigencia_inicio": texto(l.get("vigencia_inicio"), padrao="sem_data"),
            "valor_mensal": numero(l.get("valor_mensal")),
            "norma": opcional(l.get("norma")),
            "url_norma": opcional(l.get("url_norma")),
            "conferido": texto(l.get("conferido"), padrao="nao").lower() == "sim",
            "observacao": opcional(l.get("observacao")),
            "data_referencia": texto(l.get("vigencia_inicio"), padrao=""),
        })

    armazem.mesclar("dim_cargo_publico", cargos, FONTE)
    armazem.mesclar("dim_subsidio", subsidios, FONTE)

    com_valor = sum(1 for s in subsidios if s["valor_mensal"] is not None)
    conferidos = sum(1 for s in subsidios if s["conferido"])

    log.info("referências: %d cargos, %d com valor, %d conferidos",
             len(cargos), com_valor, conferidos)
    if conferidos < com_valor:
        log.warning("%d valor(es) de subsídio ainda NÃO CONFERIDOS — o painel "
                    "os exibe marcados. Confira contra a norma e troque "
                    "`conferido` para `sim` em %s",
                    com_valor - conferidos, destino.name)

    controle.gravar_marca(FONTE, "subsidios", destino.stat().st_mtime,
                          len(subsidios),
                          situacao="ok" if conferidos == com_valor else "a_conferir",
                          detalhe=f"{conferidos}/{com_valor} conferidos")
    return len(subsidios)


def executar(anos: list[int] | None = None) -> None:  # noqa: ARG001
    carregar_subsidios()


if __name__ == "__main__":
    executar()
