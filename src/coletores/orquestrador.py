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

ORDEM = ["referencias", "ibge", "siconfi", "camara", "senado", "tse",
         "portal_transparencia", "tesouro"]

ROTULOS = {
    "ibge": "IBGE — municípios, população, PIB e malhas",
    "siconfi": "SICONFI — finanças de estados e municípios",
    "camara": "Câmara — deputados, projetos, votos e cota",
    "senado": "Senado — senadores e votações",
    "tse": "TSE — eleitos, do presidente ao vereador",
    "portal_transparencia": "Portal da Transparência — emendas",
    "tesouro": "Tesouro/SIC — custo apurado por órgão federal",
    "referencias": "Referências — subsídios por cargo (arquivo local)",
}

CADENCIAS = {
    "ibge": "anual",
    "siconfi": "mensal",
    "camara": "diária",
    "senado": "diária",
    "tse": "a cada eleição",
    "portal_transparencia": "mensal",
    "tesouro": "mensal",
    "referencias": "a cada reajuste",
}


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
    if fonte == "tse":
        # geral (par, não múltiplo de 4 no calendário brasileiro) e municipal
        ultimo_par = hoje.year - (hoje.year % 2)
        return sorted({ultimo_par - 2, ultimo_par})
    return [hoje.year - 1]


def _modulo(nome: str):
    from . import (  # noqa: PLC0415
        camara, ibge, portal_transparencia, referencias, senado, siconfi,
        tesouro, tse,
    )
    return {
        "ibge": ibge, "siconfi": siconfi, "camara": camara,
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
            elif fonte == "siconfi":
                for ano in anos:
                    modulo.executar(
                        ano=ano, limite=opcoes.limite, nivel=opcoes.nivel,
                        uf=opcoes.uf, trabalhadores=opcoes.trabalhadores,
                        intervalo=opcoes.intervalo,
                        refazer_vazios=opcoes.refazer_vazios,
                        refazer_tudo=opcoes.refazer_tudo)
            elif fonte in ("camara", "portal_transparencia", "tse",
                           "tesouro"):
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
