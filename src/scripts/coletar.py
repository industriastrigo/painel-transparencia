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
import os
from pathlib import Path
import sys
from datetime import date

from ..coletores import orquestrador
from ..nucleo import bruto, controle
from ..nucleo.registro import obter as obter_log

log = obter_log("scripts.coletar")

ORDEM = orquestrador.ORDEM


def montar_parser() -> argparse.ArgumentParser:
    """Separado de `principal` para poder ser testado sem executar coleta."""
    p = argparse.ArgumentParser(description="Coletores do Painel da Transparência")
    # Sem `choices=` de propósito: com nargs="*", o argparse valida também o
    # valor PADRÃO contra a lista, e a lista vazia não está nela — o que fazia
    # `--situacao` e `--tudo` sozinhos morrerem com "invalid choice: []".
    # A validação fica manual, logo abaixo.
    p.add_argument("fontes", nargs="*", default=[],
                   metavar="{" + ",".join(ORDEM) + "}",
                   help="fontes a coletar (padrão: nenhuma)")
    p.add_argument("--tudo", action="store_true", help="roda todas as fontes")
    # Sem padrão de propósito. Com `default=ano-1`, `args.ano` NUNCA era None,
    # e `anos_de()` — que existe justamente para dar a cada fonte o ano natural
    # dela — via um ano explícito em toda execução. A coleta diária da Câmara
    # voltava a buscar o ano passado, que é o defeito que `anos_de` corrigiu.
    p.add_argument("--ano", type=int,
                   help="força o ano; sem isto cada fonte usa o padrão dela "
                        "(Câmara e Senado o ano corrente, SICONFI o anterior)")
    p.add_argument("--anos", type=int, nargs="+")
    p.add_argument("--limite", type=int, help="limita nº de entes (teste rápido)")
    p.add_argument("--sem-malhas", action="store_true")
    p.add_argument("--situacao", action="store_true",
                   help="mostra a marca-d'água de cada fonte e sai")
    p.add_argument("--explicar-cinza", metavar="ANO", type=int,
                   help="para os entes sem despesa no ano, pergunta ao SICONFI "
                        "se eles entregaram — separa 'não coletamos' de 'o "
                        "ente não prestou contas'")
    p.add_argument("--diagnostico", action="store_true",
                   help="onde está o acervo, o que ele tem dentro e por que "
                        "um número pode estar sumindo da tela")
    p.add_argument("--amostra", metavar="COD_IBGE",
                   help="mostra as contas cruas de um ente já coletado — "
                        "serve para conferir a estrutura que a fonte devolve "
                        "em vez de supor")
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
    g.add_argument("--bruto", action="store_true",
                   help="guarda cada resposta INTEIRA em dados/bruto/, antes "
                        "do contrato de colunas (consulte com "
                        "`python -m src.scripts.bruto`)")

    return p


def _explicar_cinza(ano: int, limite: int = 40) -> int:
    """Por que estes entes estão cinza no mapa?

    Cinza hoje quer dizer duas coisas somadas — "não coletamos" e "o ente não
    prestou contas". A primeira é buraco nosso; a segunda é um achado sobre o
    ente. Este comando pergunta ao SICONFI, um por um, e separa as duas.

    Só consulta quem está SEM dado: são dezenas, não milhares.
    """
    from ..api import vistas  # noqa: PLC0415
    from ..coletores import siconfi  # noqa: PLC0415

    con = vistas.conexao_leitura()
    sem_dado = [linha[0] for linha in con.execute("""
        SELECT e.cod_ibge FROM dim_ente e
         WHERE e.nivel IN ('estado', 'municipio')
           AND NOT EXISTS (SELECT 1 FROM vw_despesa_total d
                            WHERE d.cod_ibge = e.cod_ibge AND d.ano = ?)
         ORDER BY e.cod_ibge""", [ano]).fetchall()]

    if not sem_dado:
        print(f"Todos os entes têm despesa em {ano}. Nada cinza a explicar.")
        return 0

    print(f"{len(sem_dado)} ente(s) sem despesa em {ano}.")
    if len(sem_dado) > limite:
        print(f"Perguntando ao SICONFI sobre os {limite} primeiros "
              f"(1 requisição por segundo).")
        sem_dado = sem_dado[:limite]
    print()

    explicacoes = siconfi.explicar_ausencia(ano, sem_dado)
    for cod, explicacao in explicacoes.items():
        print(f"  {cod:<10} {explicacao}")

    nao_entregaram = sum(1 for e in explicacoes.values() if "NÃO entregou" in e)
    nossos = sum(1 for e in explicacoes.values() if "nossa coleta" in e)
    print()
    print(f"  {nao_entregaram} não prestaram contas — é achado, não lacuna")
    print(f"  {nossos} entregaram e não coletamos — isso é nosso para consertar")
    return 0


def _diagnostico() -> int:
    """Responde, numa tela só, as três perguntas que se repetem quando um
    número não aparece no painel:

    1. **Onde** o projeto está lendo o acervo? (`PAINEL_DADOS` pode estar
       definido no `.env`, numa variável de ambiente do Windows, ou em lugar
       nenhum — e o painel lê um lugar enquanto você olha outro)
    2. O acervo **tem arquivo** lá dentro, ou só a estrutura de pastas?
    3. Se tem, o que as views enxergam?

    Existe porque diagnosticar isso por conversa custou várias rodadas.
    """
    from ..nucleo import config as cfg  # noqa: PLC0415

    print("== ONDE ==")
    print(f"projeto        : {cfg.RAIZ}")
    print(f"acervo (DADOS) : {cfg.DADOS}")
    origem = ("variável de ambiente / .env" if os.getenv("PAINEL_DADOS")
              else "padrão (pasta dados/ do projeto)")
    print(f"definido por   : {origem}")
    print()

    print("== O QUE TEM DENTRO ==")
    arquivos = sorted(Path(cfg.DADOS).rglob("*.parquet"))
    if not arquivos:
        print("NENHUM arquivo .parquet abaixo desse caminho.")
        print()
        print("O acervo está vazio — só a estrutura de pastas, que o próprio")
        print("projeto recria ao iniciar. Se você moveu a pasta dados/ de")
        print("lugar, aponte para o novo caminho pondo no .env:")
        print("    PAINEL_DADOS=D:\\caminho\\para\\dados")
        print("Se não moveu, os coletores precisam rodar de novo.")
        return 1

    por_tabela: dict[str, list[Path]] = {}
    for arquivo in arquivos:
        relativo = arquivo.relative_to(cfg.DADOS)
        tabela = relativo.parts[1] if len(relativo.parts) > 1 else relativo.parts[0]
        por_tabela.setdefault(tabela, []).append(arquivo)

    for tabela, lista in sorted(por_tabela.items()):
        tamanho = sum(a.stat().st_size for a in lista) / 1_048_576
        print(f"  {tabela:<24} {len(lista):>4} arquivo(s)  {tamanho:>8.1f} MB")
    print()

    print("== O QUE AS VIEWS ENXERGAM ==")
    try:
        from ..api import vistas  # noqa: PLC0415
        con = vistas.conexao_leitura()
        for view, rotulo in (("financas_ente", "linhas de finanças"),
                             ("vw_receita_total", "entes com arrecadação"),
                             ("vw_transferencia_recebida", "entes com transferência"),
                             ("vw_despesa_total", "entes com despesa"),
                             ("transferencia_uniao", "repasses da União"),
                             ("operacao_credito", "pedidos de crédito")):
            try:
                n = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            except Exception as erro:  # noqa: BLE001
                n = f"erro: {str(erro)[:60]}"
            print(f"  {rotulo:<28} {n}")

        print()
        print("== COMO A FONTE NOMEIA A CONTA ==")
        amostra = con.execute("""
            SELECT estagio, cod_conta, rotulo_conta
              FROM financas_ente LIMIT 5""").fetchall()
        for estagio, conta, rotulo in amostra:
            print(f"  [{estagio}] {conta}  ->  {str(rotulo)[:50]}")
        if not amostra:
            print("  (financas_ente está vazia)")
    except Exception as erro:  # noqa: BLE001
        print(f"  não consegui abrir as views: {erro}")
    return 0


def _amostrar(cod_ibge: str, ano: int | None) -> int:
    """Imprime as contas de um ente como elas estão no armazém.

    Existe porque duas perguntas do painel não se respondem por raciocínio:
    quais colunas (estágios) a fonte devolve, e se o `cod_conta` é hierárquico
    com pontos ou um identificador textual. As views derivam o NÍVEL da conta
    do código; se o código não for o que se supõe, a agregação erra em
    silêncio — foi assim que a despesa dos estados apareceu inflada em 5×.

        python -m src.scripts.coletar --amostra 29 --ano 2025
    """
    from ..nucleo import armazem  # noqa: PLC0415

    filtro = f"cod_ibge = '{cod_ibge}'"
    if ano:
        filtro += f" AND ano = {ano}"
    df = armazem.ler("financas_ente", filtro=filtro)
    if df.empty:
        print(f"nada coletado para o ente {cod_ibge}"
              f"{f' em {ano}' if ano else ''}")
        return 1

    print(f"{len(df)} linha(s) para o ente {cod_ibge}\n")

    print("== colunas (estágios) devolvidas pela fonte ==")
    print(df["estagio"].value_counts().to_string())

    for estagio, grupo in df.groupby("estagio"):
        print(f"\n== {estagio} — {len(grupo)} linha(s) ==")
        colunas = [c for c in ("cod_conta", "cod_funcao", "funcao",
                               "rotulo_conta", "valor") if c in grupo.columns]
        print(grupo[colunas].head(40).to_string(index=False))

        com_ponto = grupo["cod_conta"].astype(str).str.contains(r"\.").sum()
        print(f"\ncod_conta com ponto: {com_ponto} de {len(grupo)}")
        if com_ponto == 0:
            print("  ATENÇÃO: nenhum código tem ponto. As views derivam o "
                  "nível da conta contando pontos — se o código for textual, "
                  "toda linha vira nível 1 e a soma conta pai e filho juntos.")
        if grupo["cod_conta"].duplicated().any():
            repetidos = grupo["cod_conta"].duplicated().sum()
            print(f"  ATENÇÃO: {repetidos} cod_conta repetido(s) no mesmo "
                  f"ente/ano. A chave primária inclui cod_conta — linhas "
                  f"repetidas foram DESCARTADAS no merge (armadilha 2c).")
    return 0


def principal(argv: list[str] | None = None) -> int:
    p = montar_parser()
    args = p.parse_args(argv)

    desconhecidas = [f for f in args.fontes if f not in ORDEM]
    if desconhecidas:
        p.error(f"fonte desconhecida: {', '.join(desconhecidas)}. "
                f"Disponíveis: {', '.join(ORDEM)}")

    if args.explicar_cinza:
        return _explicar_cinza(args.explicar_cinza)

    if args.diagnostico:
        return _diagnostico()

    if args.amostra:
        return _amostrar(args.amostra, args.ano)

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
        for ano in {args.ano or date.today().year - 1, *(args.anos or [])}:
            resumo = controle.resumo_entes("siconfi", "dca", ano)
            if resumo:
                print(f"\nSICONFI dca {ano} — entes por situação: {resumo}")
        return 0

    fontes = ORDEM if args.tudo else args.fontes
    if not fontes:
        p.print_help()
        return 1

    if args.bruto:
        bruto.ligar(True)

    opcoes = orquestrador.Opcoes(
        ano=args.ano, anos=args.anos, nivel=args.nivel, uf=args.uf,
        trabalhadores=args.trabalhadores, intervalo=args.intervalo,
        limite=args.limite, sem_malhas=args.sem_malhas,
        refazer_vazios=args.refazer_vazios, refazer_tudo=args.refazer_tudo,
    )
    resultados = orquestrador.executar(fontes, opcoes)
    if bruto.ativo():
        bruto.descarregar()

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
