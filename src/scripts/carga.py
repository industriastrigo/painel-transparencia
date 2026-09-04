"""Carga histórica — a série inteira de cada fonte, retomável.

Feita para rodar de madrugada, sem ninguém olhando. Isso muda o que importa:
velocidade deixa de ser a prioridade e **sobreviver à interrupção** passa a
ser. Três coisas garantem isso:

**Retomada por recorte.** Cada par (fonte, recorte) vira uma marca em
`_ctl/ingestao` assim que conclui. Se a rede cair na terceira hora, a próxima
execução começa da quarta — não do zero. Rodar duas noites seguidas compõe.

**Só `ok` é terminal.** Um recorte que voltou vazio, parcial ou com erro é
retentado na execução seguinte. Marcar tudo como feito seria transformar uma
falha em silêncio permanente.

**A máquina não dorme no meio.** Um coletor com freio de 1 req/s passa a maior
parte do tempo esperando rede, e para o Windows isso é ociosidade. Ver
`nucleo.energia`.

## Quanto tempo leva

O freio de 1 requisição por segundo é o que manda, e ele é publicado pelas
fontes — não é escolha nossa. A conta honesta:

| Fonte | Volume | Tempo |
|---|---|---|
| SADIPEM | 27 UFs | ~2 min |
| Transferências | 18 modalidades × 2 níveis × N anos | ~40 min por década |
| Custos, cinco recortes | 5 × N anos | ~1 min por ano |
| Custos, `pessoal_ativo` | +100 mil linhas/mês | **~80 min por ano** |
| SICONFI municipal | 5.570 entes × 2 anexos | **~3 h por ano** |

`pessoal_ativo` e o SICONFI municipal são os caros, e por isso são opcionais.
A série completa de Custos desde 2015 com `pessoal_ativo` passa de quinze
horas: **não cabe numa noite**, e é justamente para isso que a retomada
existe — rode quantas noites forem necessárias.

## Guardar o bruto

`--bruto` grava **cada resposta inteira**, antes de qualquer contrato de
colunas, em `dados/bruto/`. Custa disco e não custa tempo — e é o que evita
repetir esta madrugada quando a pergunta de amanhã precisar de um campo que o
coletor de hoje não lia. Ver `nucleo.bruto`.

    python -m src.scripts.carga --tudo
    python -m src.scripts.carga --tudo --bruto
    python -m src.scripts.carga --tudo --bruto --com-pessoal-ativo
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

from ..nucleo import armazem, bruto, controle, portao
from ..nucleo.energia import ManterAcordado
from ..nucleo.registro import obter as obter_log

log = obter_log("scripts.carga")


def _duracao(segundos: float) -> str:
    return str(timedelta(seconds=int(segundos)))


def _etapa(nome: str, funcao) -> tuple[str, int, str]:
    """Roda uma etapa e devolve (nome, linhas, desfecho), sem deixar escapar.

    Uma fonte fora do ar às 3h da manhã não pode derrubar as outras — de
    manhã o que importa é o resumo do que entrou e do que faltou.
    """
    inicio = time.monotonic()
    log.info("=" * 60)
    log.info("INÍCIO %s", nome)
    try:
        linhas = funcao() or 0
        desfecho = "ok"
    except KeyboardInterrupt:
        raise
    except Exception as erro:  # noqa: BLE001
        log.exception("%s falhou: %s", nome, erro)
        return nome, 0, f"erro: {str(erro)[:120]}"

    log.info("FIM %s — %d linhas em %s",
             nome, linhas, _duracao(time.monotonic() - inicio))
    return nome, linhas, desfecho


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Carga histórica retomável e validação inteligente do Painel da Transparência")
    p.add_argument("--tudo", action="store_true",
                   help="todas as fontes com série histórica")
    p.add_argument("--validar", action="store_true",
                   help="executa validação acervo x origem: apaga e refaz se houver divergência, pula se íntegro")
    p.add_argument("--tabela", type=str,
                   help="executa apenas para a tabela especificada")
    p.add_argument("--desde", type=int,
                   help="primeiro ano (padrão: o início da série de cada fonte)")
    p.add_argument("--ate", type=int, default=date.today().year - 1)
    p.add_argument("--com-pessoal-ativo", action="store_true",
                   help="inclui o recorte de custo mais caro (~80 min por ano)")
    p.add_argument("--com-municipios", action="store_true",
                   help="inclui a varredura municipal do SICONFI (~3 h por ano)")
    p.add_argument("--refazer", action="store_true",
                   help="ignora as marcas e recoleta tudo")
    p.add_argument("--bruto", action="store_true",
                   help="guarda cada resposta INTEIRA em dados/bruto/, "
                        "antes do contrato de colunas — permite responder "
                        "amanhã uma pergunta nova sem recoletar")
    p.add_argument("--sem-bruto", action="store_true",
                   help="desliga o arquivo bruto mesmo se o .env o ligar")
    args = p.parse_args(argv)

    if not args.tudo and not args.validar and not args.tabela:
        p.print_help()
        return 1

    if args.validar or args.tabela:
        from ..nucleo.auditoria_carga import validar_e_sincronizar_tabela, executar_auditoria_completa
        anos_lista = list(range(args.desde or 2015, (args.ate or date.today().year) + 1))
        
        if args.tabela:
            log.info("Iniciando validação inteligente para tabela: %s", args.tabela)
            if args.tabela.startswith("dim_"):
                res = validar_e_sincronizar_tabela(args.tabela, None, forcar=args.refazer)
                log.info("Resultado %s: %s (status=%s)", args.tabela, res.get("detalhe_mudanca"), res.get("status_validacao"))
            else:
                for a in anos_lista:
                    res = validar_e_sincronizar_tabela(args.tabela, a, forcar=args.refazer)
                    log.info("Resultado %s/%d: %s (status=%s)", args.tabela, a, res.get("detalhe_mudanca"), res.get("status_validacao"))
            return 0
        else:
            log.info("Iniciando auditoria e validação inteligente de todas as tabelas...")
            res_lista = executar_auditoria_completa(anos=anos_lista, forcar=args.refazer)
            log.info("Auditoria concluída: %d partições validadas.", len(res_lista))
            return 0


    if args.bruto and not args.sem_bruto:
        bruto.ligar(True)
        # Descobrir às 3h da manhã que o Parquet não grava seria descobrir
        # tarde demais. O ensaio custa menos de um segundo e responde agora.
        # E se falhar, quem sai é o ARQUIVO, não a coleta: o arquivo bruto é
        # bônus, a coleta é a missão.
        deu_certo, motivo = bruto.autoteste()
        if not deu_certo:
            log.error("o arquivo bruto NÃO está gravando nesta máquina (%s). "
                      "Seguindo SEM ele — a coleta é mais importante. "
                      "Causas comuns: pasta dados/ dentro do OneDrive, disco "
                      "cheio, ou permissão de escrita.", motivo)
            bruto.ligar(False)
    elif args.sem_bruto:
        bruto.ligar(False)

    from ..coletores import sadipem, tesouro, transferencias  # noqa: PLC0415

    def anos(padrao: list[int]) -> list[int]:
        primeiro = args.desde or padrao[0]
        return [a for a in padrao if primeiro <= a <= args.ate]

    conjuntos = list(tesouro.CONJUNTOS)
    if not args.com_pessoal_ativo:
        conjuntos = [c for c in conjuntos if c != "pessoal_ativo"]
        log.info("pessoal_ativo fora desta carga (use --com-pessoal-ativo). "
                 "É o recorte mais caro: ~80 min por ano.")

    etapas = [
        ("SADIPEM — operações de crédito",
         lambda: sadipem.executar(refazer=args.refazer)),
        ("Transferências da União",
         lambda: transferencias.executar(
             anos=anos(transferencias.anos_disponiveis()),
             refazer=args.refazer)),
        ("Custos do Governo Federal",
         lambda: tesouro.executar(anos=anos(tesouro.anos_disponiveis()),
                                  conjuntos=conjuntos, refazer=args.refazer)),
    ]

    # RREO e RGF nas 27 UFs: barato (~1 min por ano em cada relatório) e é o
    # que dá série histórica a saúde, educação e ao limite da LRF. Ano a ano
    # de propósito — o período publicado muda com o ano, e pedir o 6º
    # bimestre de um ano em curso devolveria vazio (armadilha 2ad).
    #
    # `--ate` para no ano anterior porque quase toda fonte só fecha o
    # exercício passado. Estas duas são a exceção: elas saem DURANTE o ano,
    # então o ano corrente entra mesmo assim.
    from ..coletores import siconfi  # noqa: PLC0415
    primeiro = args.desde or 2015
    for ano in range(primeiro, date.today().year + 1):
        etapas.append((
            f"SICONFI RREO função {ano}",
            lambda a=ano: siconfi.executar(ano=a, recursos=("funcao",),
                                           refazer_tudo=args.refazer)))
        etapas.append((
            f"SICONFI RGF {ano}",
            lambda a=ano: siconfi.executar(ano=a, recursos=("rgf",),
                                           refazer_tudo=args.refazer)))

    if args.com_municipios:
        for ano in anos(list(range(2015, date.today().year))):
            etapas.append((
                f"SICONFI municipal {ano}",
                lambda a=ano: siconfi.executar(ano=a, nivel="municipio")))
            etapas.append((
                f"SICONFI municipal função {ano}",
                lambda a=ano: siconfi.executar(ano=a, nivel="municipio",
                                               recursos=("funcao",))))

    inicio = time.monotonic()
    log.info("CARGA HISTÓRICA — %d etapa(s). Retomável: interromper não perde "
             "o que já entrou.", len(etapas))

    if bruto.ativo():
        log.info("arquivo bruto LIGADO — cada resposta será guardada inteira. "
                 "Teto de %.0f GB; ao bater, o arquivamento para e a coleta "
                 "segue.", bruto.LIMITE_GB)

    resultados = []
    with ManterAcordado("carga histórica"):
        try:
            for nome, funcao in etapas:
                resultados.append(_etapa(nome, funcao))
        except KeyboardInterrupt:
            log.warning("interrompido — o que já entrou está gravado; "
                        "rode de novo para continuar de onde parou")

    # O resumo é o que alguém vai ler de manhã. Ele precisa distinguir o que
    # entrou do que faltou, sem obrigar a reler horas de log.
    log.info("=" * 60)
    log.info("RESUMO — %s no total", _duracao(time.monotonic() - inicio))
    for nome, linhas, desfecho in resultados:
        marca = "[ok] " if desfecho == "ok" else "[x]  "
        log.info("%s%-42s %8d linha(s)  %s",
                 marca, nome, linhas,
                 "" if desfecho == "ok" else desfecho)

    if bruto.ativo():
        bruto.descarregar()
        log.info("arquivo bruto: %.2f GB em %s. Consulte com "
                 "`python -m src.scripts.bruto`.",
                 bruto.tamanho_gb(), bruto.raiz().as_posix())

    # Colisão de chave é a falha mais silenciosa do pipeline: a linha CHEGOU,
    # o merge a descartou, e o total no painel fica menor sem nada parecer
    # errado. O aviso por lote sempre existiu — e saiu 239 vezes no meio de
    # 1.476 linhas de log, invisível. Aqui ele aparece onde alguém lê.
    if armazem.COLAPSOS:
        log.error("LINHAS PERDIDAS POR COLISÃO DE CHAVE — a fonte mandou, o "
                  "merge descartou. A chave da tabela está descrevendo um "
                  "grão mais grosso que o dado:")
        for tabela, quantas in sorted(armazem.COLAPSOS.items(),
                                      key=lambda x: -x[1]):
            log.error("   %-24s %d linha(s) descartadas", tabela, quantas)

    # PORTÃO. Até aqui o resumo INFORMA; daqui em diante ele DECIDE. A carga
    # de 26/08 passou nos 375 testes e gravou zero linha: teste de formato não
    # distingue acervo cheio de acervo vazio. Estas regras comparam recebido
    # com gravado, preenchimento de hoje com o melhor já visto, e o acervo com
    # os valores conferidos à mão. Código de saída 2 quando barra.
    veredito = portao.avaliar()
    veredito.relatar()

    pendentes = controle.situacao()
    if not pendentes.empty and "situacao" in pendentes:
        nao_ok = pendentes[pendentes["situacao"] != "ok"]
        if not nao_ok.empty:
            ano_atual_str = str(date.today().year)
            falhas = []
            informativos = []
            for _, linha in nao_ok.iterrows():
                rec = str(linha.get("recurso", ""))
                sit = str(linha.get("situacao", ""))
                if sit == "sem_dado" and ano_atual_str in rec:
                    informativos.append(linha)
                else:
                    falhas.append(linha)

            if falhas:
                log.warning("%d recorte(s) NÃO concluídos — rode de novo para "
                            "tentar só eles:", len(falhas))
                for linha in falhas[:20]:
                    log.warning("   %s / %s — %s",
                                linha.get("fonte"), linha.get("recurso"),
                                linha.get("situacao"))
            if informativos:
                log.info("%d recorte(s) do exercício corrente (%s) ainda sem publicação oficial:",
                         len(informativos), ano_atual_str)
                for linha in informativos[:20]:
                    log.info("   %s / %s — exercício em andamento",
                             linha.get("fonte"), linha.get("recurso"))
    return 2 if veredito.bloqueia else 0


if __name__ == "__main__":
    sys.exit(principal())
