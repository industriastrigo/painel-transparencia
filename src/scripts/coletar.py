"""Linha de comando dos coletores.

  python -m src.scripts.coletar --tudo
  python -m src.scripts.coletar ibge siconfi --ano 2024
  python -m src.scripts.coletar camara --anos 2023 2024 2026
  python -m src.scripts.coletar --situacao

Cadências diferentes, jobs diferentes: Câmara é diária, SICONFI mensal/anual,
IBGE anual, TSE a cada eleição. Não rode tudo no mesmo agendamento.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from ..coletores import orquestrador
from ..nucleo import controle
from ..nucleo.registro import obter as obter_log

log = obter_log("scripts.coletar")

ORDEM = orquestrador.ORDEM


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Coletores do Painel da Transparência")
    # Sem `choices=` de propósito: com nargs="*", o argparse valida também o
    # valor PADRÃO contra a lista, e a lista vazia não está nela — o que fazia
    # `--situacao` e `--tudo` sozinhos morrerem com "invalid choice: []".
    # A validação fica manual, logo abaixo.
    p.add_argument("fontes", nargs="*", default=[],
                   metavar="{" + ",".join(ORDEM) + "}",
                   help="fontes a coletar (padrão: nenhuma)")
    p.add_argument("--tudo", action="store_true", help="roda todas as fontes")
    p.add_argument("--ano", type=int, default=date.today().year - 1)
    p.add_argument("--anos", type=int, nargs="+")
    p.add_argument("--limite", type=int, help="limita nº de entes (teste rápido)")
    p.add_argument("--sem-malhas", action="store_true")
    p.add_argument("--situacao", action="store_true",
                   help="mostra a marca-d'água de cada fonte e sai")
    p.add_argument("--pendencias", action="store_true",
                   help="lista unidades eleitorais que não casaram com "
                        "nenhum município do IBGE, e sai")

    g = p.add_argument_group("varredura em massa (SICONFI)")
    g.add_argument("--nivel", choices=["estado", "municipio", "todos"],
                   default="estado",
                   help="estado = 27 entes (~1 min); municipio = 5.570 "
                        "(~15-25 min na primeira vez)")
    g.add_argument("--uf", help="restringe a varredura a uma UF")
    g.add_argument("--trabalhadores", type=int, default=6,
                   help="threads simultâneas (padrão 6)")
    g.add_argument("--intervalo", type=float, default=0.15,
                   help="segundos entre requisições à fonte (padrão 0.15)")
    g.add_argument("--refazer-vazios", action="store_true",
                   help="tenta de novo os entes que não tinham dado publicado")
    g.add_argument("--refazer-tudo", action="store_true",
                   help="ignora o que já foi coletado e varre do zero")

    args = p.parse_args(argv)

    desconhecidas = [f for f in args.fontes if f not in ORDEM]
    if desconhecidas:
        p.error(f"fonte desconhecida: {', '.join(desconhecidas)}. "
                f"Disponíveis: {', '.join(ORDEM)}")

    if args.pendencias:
        from ..coletores import de_para  # noqa: PLC0415
        df = de_para.pendencias()
        if df.empty:
            print("nenhuma pendência: todas as unidades eleitorais casaram")
        else:
            print(df.to_string(index=False))
            print(f"\n{len(df)} pendência(s). Para resolver, acrescente a "
                  f"grafia em EXCECOES de src/coletores/de_para.py e rode\n"
                  f"    python -m src.scripts.coletar tse --anos <ano>")
        return 0

    if args.situacao:
        df = controle.situacao()
        print("nenhuma coleta registrada" if df.empty else df.to_string(index=False))
        for ano in {args.ano, *(args.anos or [])}:
            resumo = controle.resumo_entes("siconfi", "dca", ano)
            if resumo:
                print(f"\nSICONFI dca {ano} — entes por situação: {resumo}")
        return 0

    fontes = ORDEM if args.tudo else args.fontes
    if not fontes:
        p.print_help()
        return 1

    opcoes = orquestrador.Opcoes(
        ano=args.ano, anos=args.anos, nivel=args.nivel, uf=args.uf,
        trabalhadores=args.trabalhadores, intervalo=args.intervalo,
        limite=args.limite, sem_malhas=args.sem_malhas,
        refazer_vazios=args.refazer_vazios, refazer_tudo=args.refazer_tudo,
    )
    resultados = orquestrador.executar(fontes, opcoes)

    print()
    for r in resultados:
        marca = {"ok": "[ok]", "parcial": "[!]", "erro": "[x]",
                 "configuracao": "[config]"}.get(r.situacao, "[?]")
        print(f"  {marca} {r.fonte}"
              + (f" — {r.detalhe}" if r.detalhe else ""))
        for mensagem in r.erros[:5]:
            print(f"        {mensagem}")

    com_problema = [r for r in resultados if r.situacao != "ok"]
    return 0 if not com_problema else 2


if __name__ == "__main__":
    sys.exit(principal())
