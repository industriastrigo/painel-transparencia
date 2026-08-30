"""Impedir que a máquina durma no meio de uma coleta longa.

Uma carga histórica leva horas e roda de madrugada, sem ninguém olhando. O
Windows, deixado por conta própria, suspende a máquina depois de alguns
minutos de ociosidade — e "ociosidade" para o sistema operacional inclui um
processo que passa a maior parte do tempo **esperando rede**, que é
exatamente o perfil de um coletor com freio de 1 requisição por segundo.

O resultado seria a pior forma de falha: a coleta não dá erro, não termina, e
de manhã está parada no meio sem explicação.

`SetThreadExecutionState` diz ao Windows "o sistema está em uso, não
suspenda" — sem exigir administrador e sem mexer no plano de energia do
usuário. O pedido vale enquanto o processo viver: fechada a janela, o
comportamento normal volta sozinho.

**A tela continua podendo apagar.** Só o sistema é mantido acordado
(`ES_SYSTEM_REQUIRED`, sem `ES_DISPLAY_REQUIRED`) — deixar o monitor ligado a
noite inteira seria desrespeitoso com quem só quer os dados de manhã.

Fora do Windows a função não faz nada e não reclama: no Linux e no macOS
quem resolve isso é o agendador do sistema, não o processo.
"""

from __future__ import annotations

import sys

from .registro import obter as obter_log

log = obter_log("nucleo.energia")

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class ManterAcordado:
    """Gerenciador de contexto. Fora do Windows, não faz nada.

        with ManterAcordado("carga histórica"):
            ...horas de coleta...
    """

    def __init__(self, motivo: str = "coleta longa"):
        self.motivo = motivo
        self.ativo = False

    def __enter__(self) -> ManterAcordado:
        if not sys.platform.startswith("win"):
            return self
        try:
            import ctypes  # noqa: PLC0415

            resposta = ctypes.windll.kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
            self.ativo = bool(resposta)
        except Exception as erro:  # noqa: BLE001
            # Falhar aqui não pode derrubar a coleta: o pior caso é a máquina
            # dormir, e isso o usuário resolve no plano de energia.
            log.warning("não consegui pedir para o Windows não suspender "
                        "(%s) — se a máquina dormir no meio, ajuste o plano "
                        "de energia", erro)
            return self

        if self.ativo:
            log.info("suspensão automática adiada durante %s "
                     "(a tela pode apagar normalmente)", self.motivo)
        return self

    def __exit__(self, *_) -> None:
        if not self.ativo:
            return
        try:
            import ctypes  # noqa: PLC0415

            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
            log.info("suspensão automática liberada")
        except Exception:  # noqa: BLE001
            pass
