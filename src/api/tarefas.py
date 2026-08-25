"""Coleta disparada pelo painel, em segundo plano.

Uma tarefa por vez, de propósito: duas varreduras simultâneas competiriam
pelo mesmo freio de rede e reescreveriam as mesmas partições. Pedir uma
segunda enquanto a primeira roda devolve 409, não uma fila silenciosa.

O log da execução é espelhado num buffer circular para o painel poder mostrar
o que está acontecendo — a mesma informação que apareceria no console, sem
precisar de console.
"""

from __future__ import annotations

import itertools
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..coletores import orquestrador
from ..nucleo.registro import configurar
from ..nucleo.registro import obter as obter_log

log = obter_log("api.tarefas")

LIMITE_LINHAS = 400
_contador = itertools.count(1)
_trava = threading.Lock()
_atual: "Tarefa | None" = None
_historico: deque["Tarefa"] = deque(maxlen=10)


class EspelhoDeLog(logging.Handler):
    """Copia o log da coleta para dentro da tarefa."""

    def __init__(self, tarefa: "Tarefa"):
        super().__init__(level=logging.INFO)
        self.tarefa = tarefa

    # Ruído de rotina destes módulos não interessa a quem olha a coleta.
    RUIDO = ("api.", "uvicorn", "httpx", "watchfiles")

    def emit(self, record: logging.LogRecord) -> None:
        # Só o ruído de ROTINA é filtrado. Aviso e erro passam venham de onde
        # vierem: esconder um erro que ainda assim conta é a pior combinação
        # possível — foi o que produziu um "concluído com problema" sem uma
        # única linha de erro visível no painel.
        if (record.levelno < logging.WARNING
                and record.name.startswith(self.RUIDO)):
            return
        try:
            mensagem = record.getMessage()
        except Exception:  # noqa: BLE001
            mensagem = str(record.msg)
        self.tarefa.registrar(record.levelname, mensagem)


@dataclass
class Tarefa:
    id: int
    fontes: list[str]
    opcoes: dict[str, Any]
    situacao: str = "executando"          # executando | concluida | erro
    fonte_atual: str | None = None
    inicio: str = ""
    fim: str | None = None
    etapas: dict[str, dict] = field(default_factory=dict)
    linhas: deque = field(default_factory=lambda: deque(maxlen=LIMITE_LINHAS))
    _trava_linhas: threading.Lock = field(default_factory=threading.Lock)

    def registrar(self, nivel: str, mensagem: str) -> None:
        with self._trava_linhas:
            self.linhas.append({
                "hora": datetime.now().strftime("%H:%M:%S"),
                "nivel": nivel,
                "texto": mensagem,
            })

    def como_dicionario(self) -> dict:
        with self._trava_linhas:
            linhas = list(self.linhas)
        concluidas = sum(1 for e in self.etapas.values()
                         if e["situacao"] != "executando")
        return {
            "id": self.id,
            "situacao": self.situacao,
            "fontes": self.fontes,
            "fonte_atual": self.fonte_atual,
            "opcoes": self.opcoes,
            "inicio": self.inicio,
            "fim": self.fim,
            "progresso": {"feitas": concluidas, "total": len(self.fontes)},
            "etapas": [{"fonte": f, **self.etapas[f]} for f in self.fontes
                       if f in self.etapas],
            "linhas": linhas,
        }


class TarefaEmAndamento(RuntimeError):
    pass


def atual() -> Tarefa | None:
    return _atual


def ultima() -> Tarefa | None:
    return _atual or (_historico[-1] if _historico else None)


def por_id(id_tarefa: int) -> Tarefa | None:
    if _atual and _atual.id == id_tarefa:
        return _atual
    return next((t for t in _historico if t.id == id_tarefa), None)


def iniciar(fontes: list[str], opcoes: orquestrador.Opcoes) -> Tarefa:
    global _atual

    validas = [f for f in fontes if f in orquestrador.ORDEM]
    if not validas:
        raise ValueError("nenhuma fonte válida selecionada")

    with _trava:
        if _atual is not None and _atual.situacao == "executando":
            raise TarefaEmAndamento(
                f"a atualização #{_atual.id} ainda está rodando")

        tarefa = Tarefa(
            id=next(_contador),
            fontes=[f for f in orquestrador.ORDEM if f in validas],
            opcoes={k: v for k, v in vars(opcoes).items() if v not in (None, False)},
            inicio=datetime.now(timezone.utc).isoformat(),
        )
        for fonte in tarefa.fontes:
            tarefa.etapas[fonte] = {"situacao": "aguardando", "detalhe": "",
                                    "erros": []}
        _atual = tarefa

    threading.Thread(target=_rodar, args=(tarefa, opcoes),
                     name=f"coleta-{tarefa.id}", daemon=True).start()
    return tarefa


def _rodar(tarefa: Tarefa, opcoes: orquestrador.Opcoes) -> None:
    global _atual

    configurar()
    espelho = EspelhoDeLog(tarefa)
    raiz = logging.getLogger()
    raiz.addHandler(espelho)

    # O logger raiz descarta o registro ANTES de qualquer handler se o nível
    # dele for mais alto. Se algo tiver subido esse nível (o pytest sobe para
    # WARNING; um `.env` também poderia), o painel mostraria um log vazio sem
    # nenhum aviso. Baixamos enquanto a tarefa roda e devolvemos ao terminar.
    nivel_anterior = raiz.level
    if nivel_anterior > logging.INFO:
        raiz.setLevel(logging.INFO)

    def ao_comecar(fonte: str) -> None:
        tarefa.fonte_atual = fonte
        tarefa.etapas[fonte] = {"situacao": "executando", "detalhe": "",
                                "erros": []}

    def ao_terminar(resultado: orquestrador.Resultado) -> None:
        tarefa.etapas[resultado.fonte] = {
            "situacao": resultado.situacao,
            "detalhe": resultado.detalhe,
            "erros": resultado.erros[:10],
        }

    try:
        tarefa.registrar("INFO", f"atualizando: {', '.join(tarefa.fontes)}")
        resultados = orquestrador.executar(
            tarefa.fontes, opcoes, ao_comecar=ao_comecar, ao_terminar=ao_terminar)
        houve_problema = any(r.situacao != "ok" for r in resultados)
        tarefa.situacao = "concluida"
        tarefa.registrar(
            "WARNING" if houve_problema else "INFO",
            "terminou com problemas em alguma fonte — veja o detalhe acima"
            if houve_problema else "terminou sem erros")
    except Exception as erro:  # noqa: BLE001
        log.exception("tarefa %d falhou: %s", tarefa.id, erro)
        tarefa.situacao = "erro"
        tarefa.registrar("ERROR", str(erro))
    finally:
        # A coleta mudou o armazém, então as views ficaram velhas — inclusive
        # as vazias, criadas para tabelas que ainda não existiam. Invalidar
        # aqui, do lado do servidor, é o que faz a aba Custo do Estado parar
        # de dizer "nada carregado" para dado que a aba Fontes registra como
        # carregado. Antes isso dependia do navegador chamar /api/recarregar.
        try:
            from .servidor import marcar_dados_alterados  # noqa: PLC0415
            marcar_dados_alterados()
            tarefa.registrar("INFO", "views serão refeitas na próxima consulta")
        except Exception as erro:  # noqa: BLE001
            log.warning("não consegui marcar as views como obsoletas: %s", erro)

        tarefa.fonte_atual = None
        tarefa.fim = datetime.now(timezone.utc).isoformat()
        raiz.removeHandler(espelho)
        raiz.setLevel(nivel_anterior)
        with _trava:
            _historico.append(tarefa)
            _atual = None


def catalogo() -> list[dict]:
    """O que o painel oferece para marcar."""
    return [{
        "fonte": f,
        "rotulo": orquestrador.ROTULOS[f],
        "cadencia": orquestrador.CADENCIAS[f],
    } for f in orquestrador.ORDEM]
