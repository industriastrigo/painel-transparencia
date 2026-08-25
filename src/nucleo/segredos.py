"""Guarda credenciais no `.env`, sem que elas passem por mais lugar nenhum.

Duas regras que valem para tudo aqui:

1. **A chave nunca sai daqui inteira.** Nem no log, nem na resposta da API,
   nem numa mensagem de erro. O painel só recebe uma máscara
   (`a1b2…f9e8`) suficiente para você conferir que é a certa.
2. **O `.env` é reescrito preservando o resto.** Comentários, ordem das linhas
   e as outras variáveis continuam onde estavam — o arquivo é seu, não do
   programa.

O `.env` está no `.gitignore` desde o primeiro dia, e a API só escuta em
127.0.0.1, então a chave não sai da sua máquina.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import config
from .registro import obter as obter_log

log = obter_log("nucleo.segredos")

# Chave da CGU: 32 caracteres hexadecimais. A validação existe para pegar
# colagem errada (o texto todo do exemplo, aspas, o rótulo junto), não para
# ser rigorosa com a fonte.
_FORMATO_CHAVE = re.compile(r"^[0-9a-fA-F]{16,64}$")

# O que a CGU mostra na página de exemplo. Se vier isto, foi copiado o
# modelo em vez da chave.
_PLACEHOLDERS = {"chave_api", "chave-api-dados", "sua_chave", "your_key",
                 "chave", "token"}


def mascarar(valor: str | None) -> str | None:
    """Só o sufixo — `…f9e8`.

    A versão anterior mostrava início E fim (`a1b2…f9e8`). Oito dos 32
    caracteres reduzem bastante o espaço de busca de quem vir a tela, e o
    sufixo sozinho já basta para o usuário reconhecer qual chave está ativa.
    """
    if not valor:
        return None
    if len(valor) <= 8:
        return "…" * 3
    return f"…{valor[-4:]}"


def limpar_chave(bruto: str) -> str:
    """Aceita o que dá para aceitar de uma colagem apressada.

    A página da CGU mostra a chave dentro de um JSON de exemplo; colar o
    bloco inteiro é o caminho natural, e recusar isso seria implicância.
    """
    texto = (bruto or "").strip().strip('"\'')

    # Formato do exemplo: [{"key":"chave-api-dados","value":"<chave>"}]
    achado = re.search(r'"value"\s*:\s*"([^"]+)"', texto)
    if achado:
        texto = achado.group(1)

    return texto.strip().strip('"\'')


def validar_chave(bruto: str) -> str:
    """Devolve a chave limpa ou explica por que não serve."""
    chave = limpar_chave(bruto)

    if not chave:
        raise ValueError("nenhuma chave informada.")
    if chave.lower() in _PLACEHOLDERS:
        raise ValueError(
            "isso é o texto de exemplo da página da CGU, não a sua chave. "
            "A chave real tem 32 caracteres, só números e letras de A a F.")
    if not _FORMATO_CHAVE.match(chave):
        raise ValueError(
            f"formato inesperado ({len(chave)} caracteres). A chave da CGU "
            "tem 32 caracteres hexadecimais — confira se não veio texto junto.")
    return chave


def gravar_no_env(nome: str, valor: str, caminho: Path | None = None) -> Path:
    """Grava (ou substitui) uma variável no `.env`, preservando o resto."""
    destino = caminho or (config.RAIZ / ".env")

    linhas: list[str] = []
    if destino.exists():
        linhas = destino.read_text(encoding="utf-8").splitlines()

    prefixo = f"{nome}="
    substituida = False
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(prefixo):
            linhas[i] = f"{prefixo}{valor}"
            substituida = True
            break
    if not substituida:
        linhas.append(f"{prefixo}{valor}")

    temporario = destino.with_suffix(".env.tmp")
    temporario.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.replace(temporario, destino)  # atômico: nunca deixa .env pela metade

    log.info("%s gravada no .env (%s)", nome, mascarar(valor))
    return destino


def aplicar_chave_portal(bruto: str) -> str:
    """Valida, grava e passa a valer AGORA — sem reiniciar o painel.

    Três lugares guardam a chave: o ambiente, o módulo de configuração e as
    sessões HTTP já abertas (que fixam o cabeçalho na criação). Esquecer
    qualquer um deles faria o usuário salvar a chave, ver "salvo" na tela e a
    coleta continuar dizendo que falta configurar.
    """
    from . import rede  # noqa: PLC0415  (evita ciclo de import)

    chave = validar_chave(bruto)

    gravar_no_env("CHAVE_PORTAL_TRANSPARENCIA", chave)
    os.environ["CHAVE_PORTAL_TRANSPARENCIA"] = chave
    config.CHAVE_PORTAL_TRANSPARENCIA = chave
    rede.esquecer_sessoes()

    return chave


def testar_chave_portal(chave: str) -> tuple[bool, str]:
    """Faz uma chamada barata para saber se a CGU aceita a chave.

    Vale o segundo que custa: sem isto, um erro de digitação só apareceria na
    próxima coleta, como "falta configurar" — a mesma mensagem de quem nunca
    configurou nada.
    """
    from . import rede  # noqa: PLC0415

    try:
        rede.buscar("portal_transparencia",
                    f"{config.PORTAL_TRANSPARENCIA}/emendas",
                    {"ano": 2024, "pagina": 1}, tentativas=1, silencioso=True)
        return True, "chave aceita pelo Portal da Transparência."
    except rede.ErroDefinitivo as erro:
        if erro.status in (401, 403):
            return False, ("o Portal recusou a chave (não autorizado). "
                           "Confira se copiou a chave inteira.")
        return False, f"o Portal respondeu HTTP {erro.status}."
    except Exception as erro:  # noqa: BLE001
        # Sem internet, por exemplo. A chave foi salva; não dá para afirmar
        # que está errada.
        return False, f"não deu para testar agora ({erro})."
