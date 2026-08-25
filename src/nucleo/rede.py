"""Cliente HTTP com repetição, espera exponencial e freio por fonte.

O TSE e o SICONFI bloqueiam IP em rajada de requisições, então cada fonte tem
seu próprio espaçamento mínimo, declarado em config.INTERVALO_REQUISICOES.

O freio é **global por fonte e seguro para threads**: mesmo com oito
trabalhadores em paralelo, as requisições ao SICONFI saem espaçadas pelo
intervalo configurado. Paralelismo aqui serve para esconder a latência da
resposta (~1s por ente), não para multiplicar a taxa de requisições — que é
exatamente o que faria a fonte bloquear o IP.

Cada thread tem sua própria `requests.Session`: uma Session compartilhada
funciona na prática, mas não é garantida como thread-safe.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Iterator

import requests

from . import config
from .registro import obter as obter_log

log = obter_log("nucleo.rede")

_local = threading.local()
_trava = threading.Lock()
_geracao = 0
_proxima_chamada: dict[str, float] = {}
_intervalos: dict[str, float] = dict(config.INTERVALO_REQUISICOES)

CABECALHO = {
    "User-Agent": "PainelTransparencia/1.0 (+projeto de dados abertos)",
    "Accept": "application/json",
}


def sessao(fonte: str) -> requests.Session:
    sessoes = getattr(_local, "sessoes", None)
    if sessoes is None:
        sessoes = _local.sessoes = {}

    # Geração diferente da global: alguma credencial mudou desde que estas
    # sessões nasceram. Fecha e refaz — o cabeçalho é lido de novo abaixo.
    if getattr(_local, "geracao", None) != _geracao:
        for aberta in sessoes.values():
            try:
                aberta.close()
            except Exception:  # noqa: BLE001
                pass
        sessoes.clear()
        _local.geracao = _geracao

    if fonte not in sessoes:
        s = requests.Session()
        s.headers.update(CABECALHO)
        if fonte == "portal_transparencia" and config.CHAVE_PORTAL_TRANSPARENCIA:
            s.headers["chave-api-dados"] = config.CHAVE_PORTAL_TRANSPARENCIA
        adaptador = requests.adapters.HTTPAdapter(
            pool_connections=16, pool_maxsize=16)
        s.mount("https://", adaptador)
        s.mount("http://", adaptador)
        sessoes[fonte] = s
    return sessoes[fonte]


def esquecer_sessoes() -> None:
    """Invalida as Sessions de TODAS as threads.

    O cabeçalho `chave-api-dados` é fixado quando a Session nasce. Sem isto,
    salvar a chave pelo painel não teria efeito até reiniciar — o usuário
    veria "salvo" na tela e "falta configurar" na coleta seguinte.

    Não dá para limpar o `threading.local` das outras threads a partir daqui,
    e a coleta roda justamente noutra thread. Por isso a invalidação é por
    contador de geração: quem tem sessão de geração antiga descarta e refaz.
    """
    global _geracao
    with _trava:
        _geracao += 1


def definir_intervalo(fonte: str, segundos: float) -> None:
    """Ajusta o espaçamento de uma fonte em tempo de execução.

    Usado pelos coletores em massa, que trocam latência por vazão sem passar
    do que a fonte tolera.
    """
    with _trava:
        _intervalos[fonte] = max(0.0, float(segundos))


def intervalo_de(fonte: str) -> float:
    return _intervalos.get(fonte, 0.3)


def _frear(fonte: str) -> None:
    """Reserva o próximo horário de saída para esta fonte e dorme até ele.

    A reserva acontece dentro da trava, o sono fora dela: assim N threads
    pegam horários distintos e espaçados sem ficarem presas umas nas outras.
    """
    intervalo = intervalo_de(fonte)
    if intervalo <= 0:
        return
    with _trava:
        agora = time.monotonic()
        saida = max(agora, _proxima_chamada.get(fonte, 0.0))
        _proxima_chamada[fonte] = saida + intervalo
    espera = saida - time.monotonic()
    if espera > 0:
        time.sleep(espera)


_ja_avisado: set[str] = set()


def _avisar_se_depreciado(fonte: str, url: str, resposta) -> None:
    """A fonte diz quando o endpoint vai morrer. Vale escutar.

    O Senado marca serviços em descontinuação com os cabeçalhos padrão
    `Deprecation`, `Sunset` e `Link: rel="successor"`. Sem isto, o coletor
    seguiria chamando um endereço até o dia em que ele simplesmente para —
    e aí seria mais um "não veio dado" sem causa aparente.

    Avisa uma vez por URL, para não poluir uma varredura de milhares.
    """
    sunset = resposta.headers.get("Sunset")
    deprecation = resposta.headers.get("Deprecation")
    if not (sunset or deprecation):
        return

    chave = f"{fonte}|{url}"
    if chave in _ja_avisado:
        return
    _ja_avisado.add(chave)

    sucessor = ""
    link = resposta.headers.get("Link", "")
    if 'rel="successor"' in link:
        sucessor = link.split(">")[0].lstrip("<")

    log.warning("%s: %s está DEPRECIADO (desativação: %s).%s",
                fonte, url, sunset or "sem data",
                f" Substituto: {sucessor}" if sucessor else
                " Procure o serviço substituto na documentação da fonte.")


class ErroDefinitivo(RuntimeError):
    """A fonte respondeu que não vai dar certo. Repetir é perda de tempo."""

    def __init__(self, mensagem: str, status: int | None = None):
        super().__init__(mensagem)
        self.status = status


# 4xx é "sua requisição está errada" — repetir devolve o mesmo 404.
# 429 é a exceção: significa "devagar", e aí esperar é exatamente o certo.
_REPETIVEIS = {408, 425, 429, 500, 502, 503, 504}


def buscar(
    fonte: str,
    url: str,
    parametros: dict[str, Any] | None = None,
    formato: str = "json",
    tentativas: int | None = None,
    silencioso: bool = False,
) -> Any:
    tentativas = tentativas or config.TENTATIVAS
    ultimo_erro: Exception | None = None

    for tentativa in range(1, tentativas + 1):
        _frear(fonte)
        try:
            resp = sessao(fonte).get(
                url, params=parametros, timeout=config.TEMPO_LIMITE
            )
            if 400 <= resp.status_code < 500 and resp.status_code not in _REPETIVEIS:
                raise ErroDefinitivo(
                    f"{fonte}: HTTP {resp.status_code} em {url}", resp.status_code)
            if resp.status_code in _REPETIVEIS:
                raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
            resp.raise_for_status()
            _avisar_se_depreciado(fonte, url, resp)
            if formato == "json":
                return resp.json()
            if formato == "texto":
                return resp.text
            return resp.content
        except ErroDefinitivo as erro:
            # Nada de quatro tentativas com espera exponencial num 404.
            if not silencioso:
                log.warning("%s", erro)
            raise
        except Exception as erro:  # noqa: BLE001
            ultimo_erro = erro
            espera = min(2 ** tentativa, 30)
            if not silencioso:
                log.warning("%s %s — tentativa %d/%d falhou (%s), aguardando %ds",
                            fonte, url, tentativa, tentativas, erro, espera)
            if tentativa < tentativas:
                time.sleep(espera)

    raise RuntimeError(f"{fonte}: falha definitiva em {url}") from ultimo_erro


def paginar_camara(url: str, parametros: dict[str, Any] | None = None,
                   limite_paginas: int | None = None) -> Iterator[dict]:
    """Percorre a paginação por links `next` da API da Câmara."""
    parametros = dict(parametros or {})
    parametros.setdefault("itens", 100)
    pagina = 0
    while url:
        pagina += 1
        corpo = buscar("camara", url, parametros)
        yield from corpo.get("dados", [])
        proximo = next(
            (l["href"] for l in corpo.get("links", []) if l.get("rel") == "next"),
            None,
        )
        url, parametros = proximo, None
        if limite_paginas and pagina >= limite_paginas:
            break
