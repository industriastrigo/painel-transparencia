"""Arquivo bruto: a resposta inteira, antes de qualquer contrato de colunas.

O que estes testes protegem, em uma frase: **a coleta da madrugada não pode
ser perdida por causa de uma pergunta que ninguém tinha feito ainda.**

Por isso as duas propriedades centrais aqui não são sobre formato de arquivo:

1. o campo que o coletor NÃO lê continua recuperável depois;
2. arquivar nunca derruba a coleta — disco cheio, JSON estranho, o que for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.nucleo import bruto, rede  # noqa: E402


@pytest.fixture(autouse=True)
def _arquivo_limpo():
    """Cada teste começa com o arquivo vazio e o módulo em estado conhecido."""
    import shutil  # noqa: PLC0415

    shutil.rmtree(bruto.raiz(), ignore_errors=True)
    bruto._memoria.clear()
    bruto._cache_replay = None
    bruto.ligar(True)
    bruto.ligar_replay(False)
    yield
    bruto._memoria.clear()
    bruto.ligar(False)
    bruto.ligar_replay(False)
    shutil.rmtree(bruto.raiz(), ignore_errors=True)


class _Resposta:
    """Uma resposta HTTP de mentira, com o mínimo que `rede.buscar` toca."""

    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status
        self.headers = {}

    def json(self):
        return self._corpo

    @property
    def text(self):
        return json.dumps(self._corpo)

    @property
    def content(self):
        return self.text.encode("utf-8")

    def raise_for_status(self):
        pass


def _fingir(monkeypatch, corpo):
    class _Sessao:
        def get(self, url, params=None, timeout=None, headers=None, **kwargs):
            return _Resposta(corpo)

    monkeypatch.setattr(rede, "sessao", lambda fonte: _Sessao())
    monkeypatch.setattr(rede, "_frear", lambda fonte: None)


# ---------------------------------------------------------------- a promessa
RESPOSTA = {"items": [
    {"cod_ibge": "3550308", "valor": 100.0,
     # Campo que NENHUM coletor deste projeto lê hoje. É ele que o teste
     # inteiro existe para proteger.
     "modalidade_licitacao": "pregão eletrônico",
     "observacao_da_fonte": "retificado em 2026"},
]}


def test_campo_que_o_coletor_ignora_continua_recuperavel(monkeypatch):
    """A razão de ser do módulo.

    O coletor projeta a resposta num contrato de colunas e descarta o resto.
    Descobrir meses depois que o campo descartado era o interessante custaria
    uma recoleta inteira — horas, no limite de 1 requisição por segundo que as
    fontes publicam. Com o arquivo, custa uma consulta.
    """
    _fingir(monkeypatch, RESPOSTA)
    rede.buscar("siconfi", "https://exemplo/tt/rreo", {"an_exercicio": 2024})
    bruto.descarregar()

    campos = set(bruto.campos("siconfi", "rreo")["campo"])
    assert "modalidade_licitacao" in campos, (
        "o campo que ninguém lê precisa sobreviver — é para isso que o "
        "arquivo bruto existe")
    assert "observacao_da_fonte" in campos


def test_registros_expoe_o_valor_sem_contrato_nenhum():
    """Não basta saber que o campo existe: tem que dar para lê-lo."""
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"ano": 2024},
                  "json", RESPOSTA)
    bruto.descarregar()

    df = bruto.registros("siconfi", "rreo")
    valores = [json.loads(r)["modalidade_licitacao"] for r in df["registro"]]
    assert valores == ["pregão eletrônico"]


def test_a_resposta_fica_verbatim():
    """Nada de normalizar, arredondar ou renomear na entrada. O que a fonte
    mandou é o que fica — qualquer tratamento nosso é uma decisão de hoje
    imposta a uma pergunta de amanhã."""
    corpo = {"valor": 0.1 + 0.2, "texto": "acentuação, vírgula e ç",
             "nulo": None, "lista": [1, 2, {"aninhado": True}]}
    bruto.guardar("tesouro", "https://exemplo/custos", None, "json", corpo)
    bruto.descarregar()

    guardado = bruto.consultar("SELECT carga FROM bruto")["carga"][0]
    assert json.loads(guardado) == corpo


# ------------------------------------------------- nunca derrubar a coleta
def test_falha_ao_arquivar_nao_derruba_a_coleta(monkeypatch):
    """A regra que atravessa o módulo.

    Perder o arquivo bruto custa uma recoleta. Perder a coleta da madrugada
    custa a madrugada. Na dúvida, a coleta ganha.
    """
    def _explodir(*_a, **_k):
        raise OSError("[Errno 28] No space left on device")

    monkeypatch.setattr(bruto, "_guardar", _explodir)
    _fingir(monkeypatch, RESPOSTA)

    corpo = rede.buscar("siconfi", "https://exemplo/tt/rreo")
    assert corpo == RESPOSTA, "a coleta tem que seguir mesmo sem arquivar"


def test_desligado_nao_escreve_nada(monkeypatch):
    bruto.ligar(False)
    _fingir(monkeypatch, RESPOSTA)
    rede.buscar("siconfi", "https://exemplo/tt/rreo")
    bruto.descarregar()
    assert not bruto.existe()


def test_teto_de_disco_para_de_arquivar_e_deixa_coletar(monkeypatch):
    """Disco cheio às 4h da manhã derrubaria a coleta inteira. O teto existe
    para o arquivamento morrer sozinho, em silêncio, sem levar a coleta."""
    monkeypatch.setattr(bruto, "_bytes_gravados", int(50 * 1024 ** 3))
    monkeypatch.setattr(bruto, "LIMITE_GB", 40.0)
    _fingir(monkeypatch, RESPOSTA)

    assert rede.buscar("siconfi", "https://exemplo/tt/rreo") == RESPOSTA
    bruto.descarregar()
    assert not bruto.existe(), "acima do teto não deveria ter gravado"


# ---------------------------------------------------------------- replay
def test_replay_le_do_disco_em_vez_da_rede(monkeypatch):
    """O que fecha o ciclo: reprocessar sem recoletar.

    Sem isto o arquivo bruto seria só volume. Com ele, o campo que passou a
    ser lido HOJE entra no acervo típado a partir da resposta guardada ONTEM.
    """
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"an_exercicio": 2024},
                  "json", RESPOSTA)
    bruto.descarregar()

    def _proibido(*_a, **_k):
        raise AssertionError("o replay foi à rede — não deveria")

    monkeypatch.setattr(rede, "sessao", _proibido)
    bruto.ligar_replay(True)

    corpo = rede.buscar("siconfi", "https://exemplo/tt/rreo",
                        {"an_exercicio": 2024})
    assert corpo == RESPOSTA


def test_replay_nao_inventa_o_que_nao_guardou(monkeypatch):
    """Uma requisição que não está no arquivo vai para a rede, como sempre.
    Devolver vazio seria pior que ir buscar: viraria 'a fonte não tem', que é
    uma afirmação sobre o mundo."""
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"ano": 2024},
                  "json", RESPOSTA)
    bruto.descarregar()
    bruto.ligar_replay(True)

    _fingir(monkeypatch, {"items": [{"outro": 1}]})
    corpo = rede.buscar("siconfi", "https://exemplo/tt/rreo", {"ano": 2025})
    assert corpo == {"items": [{"outro": 1}]}


def test_parametros_diferentes_sao_respostas_diferentes():
    """A chave do replay inclui os parâmetros. Sem isso, o 2º bimestre
    devolveria a resposta do 6º — e ninguém veria diferença nenhuma."""
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"nr_periodo": 2},
                  "json", {"items": [{"valor": 2}]})
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"nr_periodo": 6},
                  "json", {"items": [{"valor": 6}]})
    bruto.descarregar()
    bruto.ligar_replay(True)

    assert rede.buscar("siconfi", "https://exemplo/tt/rreo",
                       {"nr_periodo": 2})["items"][0]["valor"] == 2
    assert rede.buscar("siconfi", "https://exemplo/tt/rreo",
                       {"nr_periodo": 6})["items"][0]["valor"] == 6


# ---------------------------------------------------------------- mecânica
def test_recoleta_identica_nao_vira_dado_novo():
    """O arquivo é um diário: acrescenta, nunca reescreve. Quem lê é que
    resolve — `vw_bruto` entrega a mais recente de cada `sk`."""
    for _ in range(3):
        bruto.guardar("siconfi", "https://exemplo/tt/rreo", {"ano": 2024},
                      "json", RESPOSTA)
        bruto.descarregar()

    assert len(bruto.consultar("SELECT sk FROM bruto")) == 1


def test_serie_revisada_pela_fonte_guarda_as_duas_versoes():
    """O Tesouro revisa a série de transferências. Duas capturas com corpos
    diferentes são dois fatos, não um erro — e o arquivo guarda os dois."""
    bruto.guardar("transferencias", "https://exemplo/tr", {"ano": 2024},
                  "json", {"items": [{"valor": 100}]})
    bruto.guardar("transferencias", "https://exemplo/tr", {"ano": 2024},
                  "json", {"items": [{"valor": 110}]})
    bruto.descarregar()

    todas = bruto.consultar(
        "SELECT carga FROM read_parquet('" + bruto.caminho_leitura()
        + "', hive_partitioning=1, union_by_name=1)")
    assert len(todas) == 2, "a revisão da fonte não pode apagar a versão antiga"


def test_particiona_por_fonte_e_recurso():
    bruto.guardar("siconfi", "https://exemplo/tt/rreo", None, "json", RESPOSTA)
    bruto.guardar("sadipem", "https://exemplo/tt/pvl", None, "json", RESPOSTA)
    bruto.descarregar()

    df = bruto.inventario()
    assert set(zip(df["fonte"], df["recurso"])) == {
        ("siconfi", "rreo"), ("sadipem", "pvl")}


def test_binario_nao_entra_no_parquet():
    """ZIP do TSE tem centenas de MB e a fonte o republica inteiro a cada
    coleta. Fica o registro da passagem, não o conteúdo."""
    bruto.guardar("tse", "https://exemplo/consulta.zip", None, "binario",
                  b"PK\x03\x04" + b"\x00" * 5000)
    bruto.descarregar()

    linha = bruto.consultar("SELECT formato, carga, bytes FROM bruto")
    assert linha["formato"][0] == "binario"
    assert linha["carga"][0] == ""
    assert linha["bytes"][0] == 5004, "o tamanho fica registrado"
