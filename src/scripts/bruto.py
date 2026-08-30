"""Consulta o arquivo bruto — a resposta da fonte, inteira, como ela veio.

É a ferramenta do dia seguinte. A carga histórica passou a madrugada guardando
cada resposta verbatim; aqui se pergunta a ela o que quiser, sem tocar na rede
e sem depender do que o coletor daquela noite sabia ler.

    # o que existe no arquivo
    python -m src.scripts.bruto

    # TODOS os campos que a fonte mandou — inclusive os que ninguém leu
    python -m src.scripts.bruto --campos siconfi rreo

    # espiar uma resposta inteira
    python -m src.scripts.bruto --ver siconfi rreo

    # qualquer pergunta, em SQL, com `bruto` já montado
    python -m src.scripts.bruto --sql "SELECT fonte, COUNT(*) FROM bruto GROUP BY 1"

    # reprocessar sem recoletar: roda o coletor lendo do arquivo
    python -m src.scripts.bruto --reprocessar siconfi
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from ..nucleo import bruto
from ..nucleo.registro import configurar, obter as obter_log

log = obter_log("scripts.bruto")


def _mostrar(df: pd.DataFrame, vazio: str) -> None:
    if df.empty:
        print(vazio)
        return
    with pd.option_context("display.max_columns", None,
                           "display.width", 160,
                           "display.max_colwidth", 60):
        print(df.to_string(index=False))


def _inventario() -> int:
    if not bruto.existe():
        print("Nenhum arquivo bruto ainda.\n")
        print("Ele é gravado durante a coleta, quando ligado:")
        print("  CARGA HISTORICA.bat  (pergunta se você quer)")
        print("  python -m src.scripts.carga --tudo --bruto")
        print("  python -m src.scripts.coletar siconfi --bruto")
        return 1

    df = bruto.inventario()
    _mostrar(df, "arquivo vazio")
    print(f"\nTotal: {int(df['respostas'].sum())} resposta(s), "
          f"{bruto.tamanho_gb():.2f} GB em {bruto.raiz().as_posix()}")
    return 0


def _campos(fonte: str, recurso: str) -> int:
    """A pergunta que justifica o arquivo inteiro: o que veio junto?

    Campo que aparece aqui e não está no acervo típado é dado que a fonte
    entregou e o coletor descartou — e agora dá para aproveitar sem gastar
    outra madrugada de coleta.
    """
    df = bruto.campos(fonte, recurso)
    if df.empty:
        print(f"nada guardado para {fonte}/{recurso} — confira o inventário "
              f"com `python -m src.scripts.bruto`")
        return 1
    _mostrar(df, "")
    print(f"\n{len(df)} campo(s) distinto(s) na amostra.")
    return 0


def _ver(fonte: str, recurso: str, quantas: int) -> int:
    df = bruto.consultar(f"""
        SELECT url, parametros, bytes, coletado_em, carga
          FROM bruto
         WHERE fonte = '{fonte}' AND recurso = '{recurso}'
         ORDER BY coletado_em DESC
         LIMIT {quantas}
    """)
    if df.empty:
        print(f"nada guardado para {fonte}/{recurso}")
        return 1
    for linha in df.itertuples(index=False):
        print("=" * 70)
        print(f"{linha.url}\n  parâmetros: {linha.parametros}"
              f"\n  {linha.bytes} bytes, capturado em {linha.coletado_em}")
        try:
            print(json.dumps(json.loads(linha.carga), ensure_ascii=False,
                             indent=2)[:4000])
        except (json.JSONDecodeError, TypeError):
            print(str(linha.carga)[:4000])
    return 0


def _reprocessar(fontes: list[str], ano: int | None) -> int:
    """Roda os coletores lendo do arquivo em vez da rede.

    É o que fecha o ciclo. O arquivo bruto sozinho seria só volume; com o
    replay, o campo que passou a ser lido HOJE entra no acervo típado a partir
    da resposta guardada ONTEM — sem uma requisição sequer, e portanto sem as
    horas que o limite de 1 req/s impõe.

    Coisa que precisa ficar clara: se a resposta não estiver no arquivo, o
    coletor **vai para a rede**, como sempre. O replay não inventa dado.
    """
    from ..coletores import orquestrador  # noqa: PLC0415

    if not bruto.existe():
        log.error("não há arquivo bruto para reprocessar")
        return 1

    bruto.ligar_replay(True)
    log.info("REPLAY ligado: a fonte agora é o disco. O que não estiver "
             "guardado ainda será buscado na rede.")

    opcoes = orquestrador.Opcoes(ano=ano)
    resultados = orquestrador.executar(fontes, opcoes)
    ruins = [r for r in resultados if r.situacao != "ok"]
    for r in resultados:
        log.info("%-24s %s %s", r.fonte, r.situacao, r.detalhe)
    return 1 if ruins else 0


def principal(argv: list[str] | None = None) -> int:
    configurar()
    p = argparse.ArgumentParser(
        description="Consulta o arquivo bruto do Painel da Transparência")
    p.add_argument("--campos", nargs=2, metavar=("FONTE", "RECURSO"),
                   help="todos os nomes de campo que a fonte mandou")
    p.add_argument("--ver", nargs=2, metavar=("FONTE", "RECURSO"),
                   help="mostra respostas inteiras, como vieram")
    p.add_argument("--quantas", type=int, default=1,
                   help="quantas respostas mostrar com --ver (padrão: 1)")
    p.add_argument("--sql", help="SQL livre; a view `bruto` já está montada")
    p.add_argument("--reprocessar", nargs="+", metavar="FONTE",
                   help="roda o coletor lendo do arquivo, sem rede")
    p.add_argument("--ano", type=int, help="ano, para --reprocessar")
    args = p.parse_args(argv)

    if args.campos:
        return _campos(*args.campos)
    if args.ver:
        return _ver(*args.ver, args.quantas)
    if args.sql:
        _mostrar(bruto.consultar(args.sql), "sem resultado")
        return 0
    if args.reprocessar:
        return _reprocessar(args.reprocessar, args.ano)
    return _inventario()


if __name__ == "__main__":
    sys.exit(principal())
