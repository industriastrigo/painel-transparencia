"""Registro (log) unificado: console + arquivo diário em logs/."""

from __future__ import annotations

import logging
import sys
from datetime import date

from .config import LOGS

_FORMATO = "%(asctime)s  %(levelname)-7s  %(name)-22s  %(message)s"
_configurado = False


def configurar(nivel: str = "INFO") -> None:
    global _configurado
    if _configurado:
        return

    arquivo = LOGS / f"painel-{date.today():%Y-%m-%d}.log"
    manipuladores = [
        logging.FileHandler(arquivo, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=nivel, format=_FORMATO, handlers=manipuladores)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    _configurado = True


def obter(nome: str) -> logging.Logger:
    configurar()
    return logging.getLogger(nome)


# De quem o contador aceita erros. Fora daqui não é problema da coleta.
PREFIXOS_DA_COLETA = ("coletores.", "nucleo.")


class ContadorDeErros(logging.Handler):
    """Conta os ERROR **da coleta** registrados dentro de um bloco.

    Existe por causa de um relatório que mentia: os coletores capturam
    exceções por fonte para que uma queda não derrube as outras cinco, e
    registram o erro no log. Só que o CLI contava apenas as exceções que
    ESCAPAVAM — então três falhas viravam "concluído com 0 falha(s)".
    Capturar para continuar é certo; contar como sucesso não é.

    A restrição por prefixo veio depois, e de outro relatório mentiroso — o
    inverso: uma coleta que gravou 3.000 linhas sem um erro sequer foi
    reportada como "concluído com problema". O contador ficava pendurado no
    logger RAIZ e somava QUALQUER erro do processo durante a janela da
    coleta: uma rota da API, o uvicorn, o httpx. O painel consulta a API a
    cada dois segundos enquanto coleta, então a chance de pegar um erro
    alheio não é pequena.

    Erro de outro subsistema é problema dele. Aqui só conta o que veio de
    `coletores.*` e `nucleo.*`.

        with ContadorDeErros() as contador:
            coletor.executar()
        if contador.total:
            ...
    """

    def __init__(self, nivel: int = logging.ERROR, limite: int = 50,
                 prefixos: tuple[str, ...] = PREFIXOS_DA_COLETA):
        super().__init__(level=nivel)
        self.mensagens: list[str] = []
        self.limite = limite
        self.prefixos = prefixos
        self.total = 0

    def emit(self, record: logging.LogRecord) -> None:
        if self.prefixos and not record.name.startswith(self.prefixos):
            return
        self.total += 1
        if len(self.mensagens) < self.limite:
            try:
                self.mensagens.append(record.getMessage())
            except Exception:  # noqa: BLE001
                self.mensagens.append(str(record.msg))

    def __enter__(self) -> "ContadorDeErros":
        configurar()
        logging.getLogger().addHandler(self)
        return self

    def __exit__(self, *_) -> None:
        logging.getLogger().removeHandler(self)
