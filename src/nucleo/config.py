"""Configuração central do Painel da Transparência.

Todos os caminhos do projeto derivam de RAIZ, para que o projeto possa ser
movido de pasta sem quebrar nada.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # opcional: só serve para ler o .env
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

RAIZ = Path(__file__).resolve().parents[2]

if load_dotenv is not None:
    load_dotenv(RAIZ / ".env")

# ---------------------------------------------------------------- caminhos
def recarregar() -> None:
    """Relê os caminhos a partir do ambiente.

    Existe porque os caminhos eram constantes fixadas no import: o primeiro
    módulo a importar `config` definia o armazém do processo inteiro, e os
    testes acabavam todos no mesmo diretório — passando ou falhando conforme
    a ordem alfabética de coleta do pytest. Em produção é chamada uma vez; nos
    testes, uma vez por arquivo.
    """
    global DADOS, DIM, FATO, CTL, MALHAS, LOGS

    DADOS = Path(os.getenv("PAINEL_DADOS", RAIZ / "dados"))
    DIM = DADOS / "dim"
    FATO = DADOS / "fato"
    CTL = DADOS / "_ctl"
    MALHAS = DADOS / "malhas"
    LOGS = Path(os.getenv("PAINEL_LOGS", RAIZ / "logs"))

    for caminho in (DIM, FATO, CTL, MALHAS, LOGS):
        caminho.mkdir(parents=True, exist_ok=True)


DADOS = DIM = FATO = CTL = MALHAS = LOGS = None  # preenchidos abaixo
recarregar()

# ---------------------------------------------------------------- fontes
IBGE_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"
IBGE_MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas"
IBGE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
# O Swagger atual documenta o caminho com `cdwhprd`; o endereço sem ele
# continua respondendo e é o que o acervo deste projeto usou até aqui. Trocar
# sem poder testar seria arriscar uma coleta que funciona — defina
# PAINEL_SICONFI para experimentar o novo:
#   https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt
SICONFI = os.getenv("PAINEL_SICONFI",
                    "https://apidatalake.tesouro.gov.br/ords/siconfi/tt")
CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_ARQUIVOS = "https://dadosabertos.camara.leg.br/arquivos"
SENADO = "https://legis.senado.leg.br/dadosabertos"
TSE_DADOS = "https://cdn.tse.jus.br/estatistica/sead/odsele"
PORTAL_TRANSPARENCIA = "https://api.portaldatransparencia.gov.br/api-de-dados"
TESOURO_CKAN = "https://www.tesourotransparente.gov.br/ckan"
# Portal de Custos do Governo Federal. Substituiu a raspagem de CSV do CKAN:
# mesmos seis recortes, em REST, com filtro por ano e mês.
TESOURO_CUSTOS = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/custos/tt"
TESOURO_ARIA = "https://apiapex.tesouro.gov.br/aria"
SADIPEM = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt"

# Chave gratuita obtida em portaldatransparencia.gov.br/api-de-dados/cadastrar-email
CHAVE_PORTAL_TRANSPARENCIA = os.getenv("CHAVE_PORTAL_TRANSPARENCIA", "")

# A API Aria (Transferências Constitucionais) pode exigir liberação:
# "Para solicitar acesso, entrar em contato com desenvolvimento@tesouro.gov.br".
# Se a liberação vier com chave, ela entra aqui; se for por IP, fica vazia.
CHAVE_TESOURO_ARIA = os.getenv("CHAVE_TESOURO_ARIA", "")

# ---------------------------------------------------------------- pipeline
COMPRESSAO = os.getenv("PAINEL_COMPRESSAO", "zstd")
NIVEL_COMPRESSAO = int(os.getenv("PAINEL_NIVEL_COMPRESSAO", "3"))
TAMANHO_ROW_GROUP = int(os.getenv("PAINEL_ROW_GROUP", "122880"))

# Intervalo MÍNIMO entre requisições à mesma fonte, em segundos.
# É piso, não padrão: `rede.definir_intervalo` não deixa ninguém pedir menos.
#
# Onde a fonte publica o limite, o número aqui é o dela — não uma estimativa
# nossa. O SICONFI e o SADIPEM dizem "uma requisição por segundo" na primeira
# tela da documentação.
INTERVALO_REQUISICOES = {
    "ibge": 0.2,
    "siconfi": 1.0,   # documentado: 1 req/s
    "camara": 0.1,
    "senado": 0.3,
    "tse": 1.0,
    "portal_transparencia": 0.5,
    "tesouro": 1.0,   # documentado: 1 req/s
    "transferencias": 0.4,
    # A documentação do SADIPEM é explícita: uma requisição por segundo.
    "sadipem": 1.0,   # documentado: 1 req/s
}

TENTATIVAS = int(os.getenv("PAINEL_TENTATIVAS", "4"))
TEMPO_LIMITE = int(os.getenv("PAINEL_TEMPO_LIMITE", "60"))

# ---------------------------------------------------------------- api
API_HOST = os.getenv("PAINEL_API_HOST", "127.0.0.1")
API_PORTA = int(os.getenv("PAINEL_API_PORTA", "8000"))
