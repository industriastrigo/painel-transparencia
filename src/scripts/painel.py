"""Sobe a API + painel web e abre o navegador.

  python -m src.scripts.painel
  python -m src.scripts.painel --porta 8123

No Windows, a porta preferida pode estar dentro de uma faixa reservada pelo
Hyper-V / WinNAT (Docker, WSL, Área de Trabalho Remota). O sintoma é um
`[Errno 13]` na hora do bind, mesmo sem nenhum programa usando a porta — não é
"porta ocupada", é "porta proibida". Ver com:

    netsh int ipv4 show excludedportrange protocol=tcp

Em vez de fazer você caçar uma porta livre na mão, o script testa e escolhe.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser

import uvicorn

from ..nucleo import config
from ..nucleo.registro import obter as obter_log

log = obter_log("scripts.painel")

# Se a preferida não der, tenta estas. 8000 é a faixa mais disputada no
# Windows justamente por ser a mais usada por todo mundo.
ALTERNATIVAS = [8000, 8080, 8123, 8765, 9000, 5500, 3333, 4321]


def porta_disponivel(host: str, porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, porta))
            return True
        except OSError:
            return False


def escolher_porta(host: str, preferida: int) -> int:
    candidatas = [preferida] + [p for p in ALTERNATIVAS if p != preferida]

    for porta in candidatas:
        if porta_disponivel(host, porta):
            if porta != preferida:
                log.warning("porta %d indisponível neste Windows — usando %d",
                            preferida, porta)
            return porta

    # Último recurso: deixa o sistema operacional escolher qualquer porta livre.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        porta = s.getsockname()[1]
    log.warning("nenhuma porta da lista disponível — usando a porta %d, "
                "sorteada pelo sistema", porta)
    return porta


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Sobe o Painel da Transparência")
    p.add_argument("--porta", type=int, default=config.API_PORTA)
    p.add_argument("--host", default=config.API_HOST)
    p.add_argument("--sem-navegador", action="store_true")
    args = p.parse_args(argv)

    porta = escolher_porta(args.host, args.porta)
    endereco = f"http://{args.host}:{porta}"

    print()
    print("=" * 52)
    print(f"  PAINEL DA TRANSPARENCIA  →  {endereco}")
    print("=" * 52)
    print("  Feche esta janela (ou Ctrl+C) para encerrar.")
    print()

    if not args.sem_navegador:
        threading.Timer(1.5, lambda: webbrowser.open(endereco)).start()

    try:
        uvicorn.run("src.api.servidor:app", host=args.host, port=porta,
                    log_level="info")
    except OSError as erro:
        log.error("não foi possível subir em %s: %s", endereco, erro)
        print("\nO Windows recusou essa porta. Tente com uma porta explícita:")
        print("    python -m src.scripts.painel --porta 8123")
        print("\nPara ver quais faixas o Windows reservou:")
        print("    netsh int ipv4 show excludedportrange protocol=tcp")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
