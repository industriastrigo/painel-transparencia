"""Isolamento dos testes: um armazém temporário por ARQUIVO de teste.

Antes, cada arquivo apontava `PAINEL_DADOS` para uma pasta própria — mas
`src.nucleo.config` lia a variável **uma vez, no import**. Como o pytest
importa tudo no mesmo processo, o primeiro arquivo a importar definia o
armazém de todos, e os testes passavam ou falhavam conforme a ORDEM de
coleta, que é alfabética e ninguém garante.

O sintoma foi um teste de CLI afirmando "nenhuma pendência" e falhando porque
o teste do de-para, coletado antes, tinha gravado uma. Inverter a ordem dos
arquivos quebrava outros dois.

A correção tem duas partes:
  - `config.recarregar()` relê os caminhos do ambiente em vez de fixá-los
    no import;
  - a fixture abaixo dá a cada arquivo de teste seu próprio diretório, antes
    de qualquer fixture do próprio arquivo rodar.

Para conferir que continua isolado, rode a suíte com os arquivos fora de
ordem:

    python -m pytest testes/teste_cli.py testes/teste_de_para.py testes/teste_api.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("PAINEL_DADOS", tempfile.mkdtemp(prefix="painel-testes-"))
os.environ.setdefault("PAINEL_LOGS", os.environ["PAINEL_DADOS"])


@pytest.fixture(scope="module", autouse=True)
def armazem_isolado(request):
    """Um diretório por arquivo de teste. Autouse e de escopo de módulo, então
    roda antes das fixtures do próprio arquivo."""
    from src.nucleo import config  # noqa: PLC0415

    nome = Path(request.module.__file__).stem
    destino = tempfile.mkdtemp(prefix=f"painel-{nome}-")

    anterior = os.environ.get("PAINEL_DADOS")
    os.environ["PAINEL_DADOS"] = destino
    os.environ["PAINEL_LOGS"] = destino
    config.recarregar()
    _esquecer_conexao_da_api()

    yield destino

    if anterior:
        os.environ["PAINEL_DADOS"] = anterior
        os.environ["PAINEL_LOGS"] = anterior
    config.recarregar()
    _esquecer_conexao_da_api()


def _esquecer_conexao_da_api() -> None:
    """A API guarda uma conexão DuckDB em cache, e as views dela apontam para
    os caminhos do armazém anterior. Sem descartar, um arquivo de teste lê o
    armazém do arquivo que rodou antes — de novo um resultado que depende da
    ordem de coleta."""
    servidor = sys.modules.get("src.api.servidor")
    if servidor is not None:
        servidor.reiniciar_conexao()
