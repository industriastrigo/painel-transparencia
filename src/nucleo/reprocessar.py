"""Reconstrói tabelas a partir do arquivo bruto, sem tocar na rede.

Existe por um caso concreto. Quando a chave de `despesa_funcao` e
`indicador_fiscal` mudou, os parquets antigos foram movidos para `_to_delete/`
— porque `sk` derivado de chave nova não bate com o antigo — e a recoleta que
deveria repor nunca rodou. As duas tabelas ficaram VAZIAS, e as abas do
painel que dependem delas passaram a mostrar nada. Ninguém percebeu, porque
ausência de dado não gera erro em lugar nenhum.

Recoletar seria oito horas de rede. Mas o arquivo bruto guardou as 324
respostas do RREO e as 648 do RGF exatamente como vieram, e o coletor já sabe
lê-las: `interpretar_funcao` e `interpretar_rgf` são funções puras, separadas
de quem foi buscar. Então dá para refazer tudo em minutos, offline, com a
regra de leitura ATUAL aplicada a payloads antigos.

É esta a promessa que justificou guardar 95 MB de JSON cru: mudar a regra de
leitura sem precisar pedir o dado de novo.

Uso:
    python -m src.nucleo.reprocessar --listar
    python -m src.nucleo.reprocessar despesa_funcao --ensaio
    python -m src.nucleo.reprocessar despesa_funcao indicador_fiscal
"""
from __future__ import annotations

import argparse
import json

from . import armazem, bruto
from .registro import obter as obter_log

log = obter_log("nucleo.reprocessar")


def _param(linha, nome, padrao=None):
    """Os parâmetros da chamada, que o arquivo guarda como JSON de texto."""
    brutos = linha.get("parametros")
    if isinstance(brutos, str):
        try:
            brutos = json.loads(brutos)
        except (TypeError, ValueError):
            return padrao
    if not isinstance(brutos, dict):
        return padrao
    return brutos.get(nome, padrao)


def _corpo(linha) -> list:
    """Os `items` da resposta guardada."""
    carga = linha.get("carga")
    if isinstance(carga, (bytes, bytearray)):
        carga = carga.decode("utf-8", errors="replace")
    if isinstance(carga, str):
        try:
            carga = json.loads(carga)
        except (TypeError, ValueError):
            return []
    if isinstance(carga, dict):
        return carga.get("items", []) or []
    return carga if isinstance(carga, list) else []


def _refazer_despesa_funcao(linhas_brutas) -> list[dict]:
    from ..coletores.siconfi import interpretar_funcao  # noqa: PLC0415

    saida, ignoradas = [], 0
    for linha in linhas_brutas:
        # O arquivo guarda RREO de vários anexos; só o Anexo 02 tem função.
        if "Anexo 02" not in str(_param(linha, "no_anexo", "")):
            ignoradas += 1
            continue
        ano = _param(linha, "an_exercicio")
        bimestre = _param(linha, "nr_periodo")
        ente = _param(linha, "id_ente")
        if not (ano and bimestre and ente):
            ignoradas += 1
            continue
        saida.extend(interpretar_funcao(_corpo(linha), int(ano),
                                        int(bimestre), str(ente)))
    if ignoradas:
        log.info("despesa_funcao: %d chamada(s) do arquivo não eram do "
                 "Anexo 02 e ficaram de fora", ignoradas)
    return saida


def _refazer_indicador_fiscal(linhas_brutas) -> list[dict]:
    from ..coletores.siconfi import interpretar_rgf  # noqa: PLC0415

    saida = []
    for linha in linhas_brutas:
        ano = _param(linha, "an_exercicio")
        quadri = _param(linha, "nr_periodo")
        ente = _param(linha, "id_ente")
        anexo = _param(linha, "no_anexo")
        poder = _param(linha, "co_poder", "E")
        if not (ano and quadri and ente and anexo):
            continue
        saida.extend(interpretar_rgf(_corpo(linha), int(ano), int(quadri),
                                     str(ente), str(poder), str(anexo)))
    return saida


# tabela → (fonte no arquivo, recurso, função que refaz)
RECEITAS = {
    "despesa_funcao": ("siconfi", "rreo", _refazer_despesa_funcao),
    "indicador_fiscal": ("siconfi", "rgf", _refazer_indicador_fiscal),
}


def reprocessar(tabela: str, ensaio: bool = False,
                do_zero: bool = False) -> int:
    if tabela not in RECEITAS:
        raise SystemExit(f"não sei refazer '{tabela}'. "
                         f"Conheço: {', '.join(sorted(RECEITAS))}")
    fonte, recurso, refazer = RECEITAS[tabela]

    log.info("lendo o arquivo bruto: fonte=%s recurso=%s", fonte, recurso)
    brutas = bruto.consultar(
        "SELECT parametros, carga FROM bruto",
        fonte=fonte, recurso=recurso, unico=False)
    if not len(brutas):
        log.error("o arquivo bruto não tem nada de %s/%s. Sem isso não há o "
                  "que reprocessar — só a recoleta resolve.", fonte, recurso)
        return 0
    log.info("%d resposta(s) guardada(s)", len(brutas))

    linhas = refazer(brutas.to_dict("records"))
    if not linhas:
        # O modo de falha que este projeto mais teme: rodou, não deu erro,
        # não gravou nada. Sai como ERROR para não passar por sucesso.
        log.error("%s: as respostas existem mas NENHUMA linha saiu delas. "
                  "A regra de leitura provavelmente não casa mais com o "
                  "formato guardado — não é 'sem dado', é defeito.", tabela)
        return 0

    anos = sorted({linha.get("ano") for linha in linhas if linha.get("ano")})
    log.info("%s: %d linha(s) reconstruída(s), anos %s–%s",
             tabela, len(linhas), anos[0] if anos else "?",
             anos[-1] if anos else "?")

    if ensaio:
        log.info("ENSAIO: nada foi gravado. Rode sem --ensaio para valer.")
        exemplo = linhas[0]
        for campo in sorted(exemplo):
            if not campo.startswith("_"):
                log.info("    %s = %r", campo, exemplo[campo])
        return len(linhas)

    if do_zero:
        # Quando a REGRA DE LEITURA muda, o `sk` de cada linha muda com ela,
        # e o merge não tem como reconhecer que a linha nova substitui a
        # velha: ele vê duas identidades diferentes e guarda as duas. O
        # acervo fica com a versão certa E a errada convivendo, e qualquer
        # soma passa a contar parte do dinheiro duas vezes.
        #
        # Mesclar por cima só é seguro quando a regra é a mesma e o que muda
        # é o dado. Se a regra mudou, apaga-se antes.
        log.warning("%s: apagando a tabela antes de refazer — a regra de "
                    "leitura mudou, então os `sk` antigos não casam com os "
                    "novos e as duas versões conviveriam.", tabela)
        armazem.remover(tabela)

    armazem.mesclar(tabela, linhas, f"{fonte}_reprocessado")
    return len(linhas)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tabelas", nargs="*", help="o que refazer")
    ap.add_argument("--ensaio", action="store_true",
                    help="mostra o que sairia sem gravar")
    ap.add_argument("--do-zero", action="store_true",
                    help="apaga a tabela antes; use quando a REGRA de "
                         "leitura mudou, não quando só o dado mudou")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()

    if args.listar or not args.tabelas:
        print("Tabelas que sei refazer a partir do arquivo bruto:\n")
        for nome, (fonte, recurso, _) in sorted(RECEITAS.items()):
            print(f"  {nome:<20} ← bruto fonte={fonte} recurso={recurso}")
        print("\nExemplo:")
        print("  python -m src.nucleo.reprocessar despesa_funcao --ensaio")
        return 0

    total = 0
    for tabela in args.tabelas:
        total += reprocessar(tabela, ensaio=args.ensaio, do_zero=args.do_zero)
    print(f"\ntotal: {total:,} linha(s)"
          f"{' (ensaio, nada gravado)' if args.ensaio else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
