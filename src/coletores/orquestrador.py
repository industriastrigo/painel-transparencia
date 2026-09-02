"""Executa coletores e diz a verdade sobre o que aconteceu.

Um só lugar decide o que rodar e como reportar, usado tanto pela linha de
comando quanto pelo botão Atualizar do painel — para os dois não divergirem.

Os coletores capturam exceções por fonte de propósito: uma fonte fora do ar
não pode derrubar as outras cinco. O problema é que quem chama contava apenas
as exceções que **escapavam**, então três falhas registradas no log viravam
"concluído com 0 falha(s)". Aqui, erro registrado conta como erro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from ..nucleo.erros import ConfiguracaoAusente
from ..nucleo.registro import ContadorDeErros
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.orquestrador")

@dataclass(frozen=True)
class Fonte:
    """O que uma fonte é, e como ela atualiza.

    Isto existe porque "atualizar" não quer dizer a mesma coisa em duas
    fontes. A Câmara publica o ano corrente todo dia; o SICONFI só fecha o
    exercício anterior; o TSE só muda a cada eleição. Marcar as duas na mesma
    tela e clicar num botão só esconde essa diferença — e quem clica acaba
    esperando dado que não existe ainda, ou recoletando o que não mudou.

    A tela mostra estes campos ao lado de cada fonte, para a diferença ficar
    visível na hora de decidir.
    """
    rotulo: str
    cadencia: str          # de quanto em quanto tempo vale rodar
    periodo: str           # o que o ano significa PARA ESTA FONTE
    granularidade: str     # o grão de cada linha coletada
    duracao: str           # quanto costuma demorar
    usa_ano: bool          # o campo Ano tem efeito aqui?
    observacao: str = ""
    requer: str = ""       # o que precisa estar configurado antes
    modulo: str = ""       # coletor por trás (vazio = o próprio nome)
    recursos: tuple[str, ...] = ()   # quais relatórios daquele coletor


FONTES: dict[str, Fonte] = {
    "referencias": Fonte(
        rotulo="Referências — subsídios por cargo (arquivo local)",
        cadencia="a cada reajuste",
        periodo="não usa ano — vale a vigência escrita no arquivo",
        granularidade="uma linha por cargo",
        duracao="instantâneo",
        usa_ano=False,
        observacao="Lê referencias/subsidios.csv do disco. Nenhuma rede "
                   "envolvida. Valor com 'conferido=nao' aparece marcado no "
                   "painel até você conferir a norma.",
    ),
    "ibge": Fonte(
        rotulo="IBGE — municípios, população, PIB e malhas",
        cadencia="anual",
        periodo="não usa ano — traz a série que o SIDRA publicar",
        granularidade="um valor por ente × métrica × ano",
        duracao="2 a 5 minutos (malhas incluídas)",
        usa_ano=False,
        observacao="Base de tudo: sem o cadastro do IBGE, nenhuma outra fonte "
                   "tem onde se pendurar. As malhas mudam raramente; a "
                   "população é reestimada todo ano.",
    ),
    "siconfi": Fonte(
        rotulo="SICONFI — despesa e arrecadação de estados e municípios",
        cadencia="mensal",
        periodo="exercício FECHADO — o ano corrente só aparece depois do "
                "encerramento e da entrega de cada ente",
        granularidade="uma linha por conta contábil, por ente e exercício",
        duracao="~2 min nas 27 UFs · ~3 h nos 5.570 municípios",
        usa_ano=True,
        observacao="Dois anexos do DCA por ente: despesa por NATUREZA "
                   "(pessoal, custeio, investimento) e receita. Despesa por "
                   "FUNÇÃO — saúde, educação — é outro relatório, listado "
                   "abaixo. A fonte limita a 1 requisição por segundo, e o "
                   "projeto respeita — daí as 3 horas. A varredura é "
                   "retomável: fechar no meio não perde o que já entrou.",
        modulo="siconfi",
        recursos=("dca", "receita"),
    ),
    "siconfi_funcao": Fonte(
        rotulo="SICONFI · RREO Anexo 02 — despesa por função (saúde, educação)",
        cadencia="bimestral",
        periodo="ano corrente, no bimestre já publicado — o RREO sai durante "
                "o exercício, não depois dele",
        granularidade="uma linha por função e subfunção, por ente e bimestre",
        duracao="~2 min nas 27 UFs · ~3 h nos 5.570 municípios",
        usa_ano=True,
        observacao="Responde 'quanto meu município gasta em saúde'. O "
                   "relatório é ACUMULADO no exercício: o 6º bimestre já "
                   "contém o 1º, então o painel mostra o bimestre mais "
                   "recente e nunca soma os seis. Fica em tabela separada da "
                   "despesa por natureza porque são dois recortes do MESMO "
                   "dinheiro — somar os dois daria o dobro do real.",
        modulo="siconfi",
        recursos=("funcao",),
    ),
    "siconfi_rgf": Fonte(
        rotulo="SICONFI · RGF — pessoal, dívida e limites da LRF",
        cadencia="quadrimestral",
        periodo="ano corrente, no quadrimestre já publicado",
        granularidade="um indicador por ente × quadrimestre × poder",
        duracao="~2 min nas 27 UFs · ~3 h nos 5.570 municípios",
        usa_ano=True,
        observacao="Duas perguntas de uma vez: quanto o ente deve, e se a "
                   "folha cabe no limite da LRF. O percentual E o limite vêm "
                   "do próprio demonstrativo — o projeto não crava 60% no "
                   "código, porque o limite muda por esfera e por poder. Sem "
                   "limite publicado, o painel não afirma nada.",
        modulo="siconfi",
        recursos=("rgf",),
    ),
    "transferencias": Fonte(
        rotulo="Transferências da União — FPM, FPE, FUNDEB, royalties",
        cadencia="mensal",
        periodo="ano de competência do repasse",
        granularidade="uma linha por ente × modalidade × mês",
        duracao="alguns minutos por ano",
        usa_ano=True,
        observacao="A série é REVISADA pelo Tesouro e pode mudar até o "
                   "início do exercício em curso — recoletar um ano recente é "
                   "rotina, não desperdício.",
        requer="pode exigir liberação em desenvolvimento@tesouro.gov.br",
    ),
    "sadipem": Fonte(
        rotulo="SADIPEM — operações de crédito de estados e municípios",
        cadencia="mensal",
        periodo="não usa ano — a base vem inteira, desde o início da série",
        granularidade="uma linha por pedido (PVL)",
        duracao="~1 min por UF (limite de 1 requisição por segundo)",
        usa_ano=False,
        observacao="O valor é o do PEDIDO, não o saldo devedor. Um pedido que "
                   "muda de status é reescrito, não duplicado.",
    ),
    "camara": Fonte(
        rotulo="Câmara — deputados, projetos, votos e cota",
        cadencia="diária",
        periodo="ano CORRENTE — a Câmara republica os arquivos todo dia",
        granularidade="proposição, votação, voto nominal e nota fiscal",
        duracao="3 a 10 minutos",
        usa_ano=True,
        observacao="Votos vêm dos arquivos em lote, não da API: a API "
                   "devolve lista vazia para votações posteriores a "
                   "maio/2024. A cota parlamentar é o volume maior do acervo.",
    ),
    "senado": Fonte(
        rotulo="Senado — senadores e votações",
        cadencia="diária",
        periodo="ano CORRENTE",
        granularidade="senador, votação e voto nominal",
        duracao="1 a 3 minutos",
        usa_ano=True,
    ),
    "tse": Fonte(
        rotulo="TSE — eleitos, do presidente ao vereador",
        cadencia="a cada eleição",
        periodo="ano ELEITORAL — 2022 e 2024 têm dado; ano ímpar não tem",
        granularidade="um registro por candidatura",
        duracao="5 a 15 minutos por eleição",
        usa_ano=True,
        observacao="Pedir um ano sem eleição apurada devolve vazio, e isso "
                   "não é erro. Depois de coletar, confira as cidades que não "
                   "casaram com o cadastro do IBGE (de-para).",
    ),
    "portal_transparencia": Fonte(
        rotulo="Portal da Transparência — emendas",
        cadencia="mensal",
        periodo="ano de execução da emenda",
        granularidade="uma linha por documento de emenda",
        duracao="2 a 8 minutos",
        usa_ano=True,
        requer="chave gratuita da CGU (o campo abaixo grava no .env)",
    ),
    "tesouro": Fonte(
        rotulo="Tesouro — custo apurado por órgão federal",
        cadencia="mensal",
        periodo="ano de competência do custo — a série começa em 2015",
        granularidade="uma linha por órgão × item de custo × mês",
        duracao="1 a 4 minutos por ano (seis consultas, 1 req/s)",
        usa_ano=True,
        observacao="Custo MEDIDO pelo próprio governo, por competência — "
                   "diferente da despesa empenhada do SICONFI e diferente da "
                   "conta ocupantes × subsídio que a aba Custo do Estado "
                   "estima. É por ÓRGÃO, nunca por cargo.",
    ),
}

ORDEM = list(FONTES)
ROTULOS = {nome: f.rotulo for nome, f in FONTES.items()}
CADENCIAS = {nome: f.cadencia for nome, f in FONTES.items()}


@dataclass
class Opcoes:
    ano: int | None = None
    anos: list[int] | None = None
    nivel: str = "estado"
    uf: str | None = None
    trabalhadores: int = 6
    intervalo: float = 0.15
    limite: int | None = None
    sem_malhas: bool = False
    refazer_vazios: bool = False
    refazer_tudo: bool = False


@dataclass
class Resultado:
    fonte: str
    situacao: str = "pendente"      # ok | parcial | erro | pendente
    erros: list[str] = field(default_factory=list)
    detalhe: str = ""


def anos_de(fonte: str, opcoes: Opcoes) -> list[int]:
    """Cada fonte tem seu ano natural.

    A Câmara publica o ano corrente todo dia; o SICONFI só fecha o exercício
    anterior. Usar um único padrão para as duas fazia a coleta "diária" da
    Câmara buscar o ano passado — que é justamente o que não muda mais.
    """
    if opcoes.anos:
        return opcoes.anos
    if opcoes.ano:
        return [opcoes.ano]

    hoje = date.today()
    if fonte in ("camara", "senado"):
        return [hoje.year]
    if fonte in ("siconfi_funcao", "siconfi_rgf"):
        # O RREO e o RGF saem DURANTE o exercício — é o único dado fiscal do
        # ente que não fica um ano atrasado. Em janeiro e fevereiro, porém,
        # nada do ano corrente venceu ainda; aí vale o anterior.
        passo = 2 if fonte == "siconfi_funcao" else 4
        return [hoje.year if (hoje.month - 2) // passo >= 1 else hoje.year - 1]
    if fonte == "tse":
        # geral (par, não múltiplo de 4 no calendário brasileiro) e municipal
        ultimo_par = hoje.year - (hoje.year % 2)
        return sorted({ultimo_par - 2, ultimo_par})
    return [hoje.year - 1]


def _modulo(nome: str):
    from . import (  # noqa: PLC0415
        camara, ibge, portal_transparencia, referencias, sadipem, senado,
        siconfi, transferencias,
        tesouro, tse,
    )
    nome = FONTES[nome].modulo or nome if nome in FONTES else nome
    return {
        "ibge": ibge, "siconfi": siconfi, "camara": camara,
        "transferencias": transferencias, "sadipem": sadipem,
        "senado": senado, "tse": tse, "tesouro": tesouro,
        "portal_transparencia": portal_transparencia,
        "referencias": referencias,
    }[nome]


def executar_fonte(fonte: str, opcoes: Opcoes) -> Resultado:
    """Roda uma fonte e devolve o que realmente aconteceu."""
    resultado = Resultado(fonte=fonte)
    modulo = _modulo(fonte)
    anos = anos_de(fonte, opcoes)

    with ContadorDeErros() as contador:
        try:
            if fonte == "ibge":
                modulo.executar(com_malhas=not opcoes.sem_malhas)
            elif fonte.startswith("siconfi"):
                # Três entradas na tela, um coletor só: o que muda é qual
                # relatório se pede. Cada uma tem a própria retomada, então
                # marcar as três não refaz o trabalho das outras.
                recursos = FONTES[fonte].recursos or ("dca", "receita")
                for ano in anos:
                    modulo.executar(
                        ano=ano, limite=opcoes.limite, nivel=opcoes.nivel,
                        uf=opcoes.uf, trabalhadores=opcoes.trabalhadores,
                        intervalo=opcoes.intervalo,
                        refazer_vazios=opcoes.refazer_vazios,
                        refazer_tudo=opcoes.refazer_tudo,
                        recursos=recursos)
            elif fonte in ("camara", "portal_transparencia", "tse",
                           "tesouro", "transferencias", "sadipem"):
                modulo.executar(anos=anos)
            else:
                modulo.executar()
        except ConfiguracaoAusente as pendencia:
            # Nem "ok" nem "erro": falta uma ação do usuário. Antes isto
            # aparecia como fonte concluída com sucesso, sem coletar nada.
            log.warning("%s precisa de configuração: %s", fonte, pendencia)
            resultado.situacao = "configuracao"
            resultado.detalhe = str(pendencia)
            resultado.erros.append(pendencia.como_resolver or str(pendencia))
            return resultado
        except Exception as erro:  # noqa: BLE001
            log.exception("%s falhou: %s", fonte, erro)
            resultado.situacao = "erro"
            resultado.erros.append(str(erro))
            return resultado

    # Nenhuma exceção escapou — mas o coletor pode ter registrado erros
    # internos que ele mesmo capturou. Isso não é sucesso.
    resultado.erros = contador.mensagens
    if contador.total == 0:
        resultado.situacao = "ok"
    else:
        resultado.situacao = "parcial"
        resultado.detalhe = (f"{contador.total} erro(s) durante a coleta — "
                             f"parte dos dados pode não ter entrado")
    return resultado


def executar(
    fontes: list[str],
    opcoes: Opcoes | None = None,
    ao_comecar: Callable[[str], None] | None = None,
    ao_terminar: Callable[[Resultado], None] | None = None,
) -> list[Resultado]:
    opcoes = opcoes or Opcoes()
    ordenadas = [f for f in ORDEM if f in fontes]
    resultados = []

    for fonte in ordenadas:
        log.info("=== %s ===", fonte)
        if ao_comecar:
            ao_comecar(fonte)
        resultado = executar_fonte(fonte, opcoes)
        resultados.append(resultado)
        if ao_terminar:
            ao_terminar(resultado)

    com_problema = [r for r in resultados if r.situacao != "ok"]
    if com_problema:
        log.warning("concluído com problema em %d de %d fonte(s): %s",
                    len(com_problema), len(resultados),
                    ", ".join(r.fonte for r in com_problema))
    else:
        log.info("concluído sem erros em %d fonte(s)", len(resultados))
    return resultados
