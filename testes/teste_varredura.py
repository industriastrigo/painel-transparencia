"""Testes da varredura em massa: retomada, lotes, erros e freio de rede.

O que estes testes protegem é a promessa de poder desligar o computador no
meio de 5.570 municípios e retomar depois sem perder nem duplicar nada.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from src.coletores import siconfi  # noqa: E402
from src.nucleo import armazem, controle, rede  # noqa: E402


@pytest.fixture(autouse=True)
def limpar():
    armazem.remover("financas_ente")
    armazem.remover("coleta_ente")
    yield


def _linhas_falsas(ano, cod, quantas=3):
    return [{
        "cod_ibge": str(cod), "ano": int(ano), "periodo": "anual",
        "cod_conta": f"1{i}", "cod_funcao": f"1{i}", "funcao": "Saúde",
        "rotulo_conta": "Saúde", "estagio": "Despesas Empenhadas",
        "valor": 1000.0 * (i + 1), "esfera": "municipio", "uf": "SP",
        "data_referencia": f"{ano}-12-31",
    } for i in range(quantas)]


# ------------------------------------------------------------------ freio
def test_freio_limita_a_taxa_mesmo_com_varias_threads():
    """O que a fonte enxerga é a TAXA, não o intervalo entre chegadas.

    A primeira versão deste teste media a distância entre dois carimbos de
    tempo consecutivos e ficava intermitente: as saídas são reservadas
    espaçadas, mas uma thread pode dormir além da conta e registrar logo
    depois de outra. A invariante honesta é o tempo total: 30 requisições a
    0,05 s não podem sair em menos de 29 × 0,05 s.
    """
    intervalo, threads_n, por_thread = 0.05, 6, 5
    esperado = (threads_n * por_thread - 1) * intervalo

    rede.definir_intervalo("fonte_teste", intervalo)
    saidas: list[float] = []
    trava = threading.Lock()

    def bater():
        for _ in range(por_thread):
            rede._frear("fonte_teste")
            with trava:
                saidas.append(time.monotonic())

    inicio = time.monotonic()
    threads = [threading.Thread(target=bater) for _ in range(threads_n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    decorrido = time.monotonic() - inicio

    assert len(saidas) == threads_n * por_thread
    assert decorrido >= esperado * 0.95, (
        f"rajada: {len(saidas)} requisições em {decorrido:.2f}s, "
        f"esperado ao menos {esperado:.2f}s")


def test_freio_nao_serializa_o_trabalho_das_threads():
    """Reservar o horário acontece sob trava; dormir até ele, não.

    Se o sono ficasse dentro da trava, seis threads virariam uma fila e o
    paralelismo não teria serventia nenhuma.
    """
    rede.definir_intervalo("fonte_paralela", 0.01)
    trabalho = 0.05
    inicio = time.monotonic()

    def bater():
        rede._frear("fonte_paralela")
        time.sleep(trabalho)  # simula a latência da resposta HTTP

    threads = [threading.Thread(target=bater) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    decorrido = time.monotonic() - inicio

    assert decorrido < trabalho * 6 * 0.6, (
        f"as threads ficaram em fila: {decorrido:.3f}s para 6 × {trabalho}s")


def test_intervalo_zero_nao_freia():
    rede.definir_intervalo("sem_freio", 0)
    inicio = time.monotonic()
    for _ in range(50):
        rede._frear("sem_freio")
    assert time.monotonic() - inicio < 0.2


def test_cada_thread_tem_sua_sessao():
    """Guardamos os OBJETOS, não os `id()`.

    Com `id()` o teste ficava intermitente: thread que termina libera sua
    Session, e o CPython reaproveita o endereço na próxima — duas sessões
    distintas apareciam com o mesmo id. A barreira mantém as quatro vivas ao
    mesmo tempo, que é a situação real durante uma varredura.
    """
    sessoes = []
    trava = threading.Lock()
    barreira = threading.Barrier(4)

    def pegar():
        s = rede.sessao("camara")
        with trava:
            sessoes.append(s)
        barreira.wait(timeout=5)  # nenhuma sai antes de todas terem a sua

    threads = [threading.Thread(target=pegar) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(sessoes) == 4
    assert len({id(s) for s in sessoes}) == 4


def test_a_mesma_thread_reaproveita_a_sessao():
    assert rede.sessao("camara") is rede.sessao("camara")


# ------------------------------------------------------------- pendentes
def test_sem_historico_tudo_e_pendente():
    assert controle.entes_pendentes("siconfi", "dca", 2024, ["1", "2", "3"]) \
        == ["1", "2", "3"]


def test_pula_resolvidos_e_repete_erros():
    controle.registrar_entes("siconfi", "dca", 2024, [
        {"cod_ibge": "1", "situacao": "ok", "linhas": 10},
        {"cod_ibge": "2", "situacao": "vazio", "linhas": 0},
        {"cod_ibge": "3", "situacao": "erro", "linhas": 0, "detalhe": "timeout"},
    ])
    assert controle.entes_pendentes("siconfi", "dca", 2024,
                                    ["1", "2", "3", "4"]) == ["3", "4"]


def test_refazer_vazios_traz_os_sem_dado_de_volta():
    controle.registrar_entes("siconfi", "dca", 2024, [
        {"cod_ibge": "1", "situacao": "ok", "linhas": 10},
        {"cod_ibge": "2", "situacao": "vazio", "linhas": 0},
    ])
    assert controle.entes_pendentes("siconfi", "dca", 2024, ["1", "2"],
                                    refazer_vazios=True) == ["2"]


def test_refazer_tudo_ignora_o_historico():
    controle.registrar_entes("siconfi", "dca", 2024, [
        {"cod_ibge": "1", "situacao": "ok", "linhas": 10}])
    assert controle.entes_pendentes("siconfi", "dca", 2024, ["1"],
                                    refazer_tudo=True) == ["1"]


def test_historico_de_outro_ano_nao_contamina():
    controle.registrar_entes("siconfi", "dca", 2023, [
        {"cod_ibge": "1", "situacao": "ok", "linhas": 10}])
    assert controle.entes_pendentes("siconfi", "dca", 2024, ["1"]) == ["1"]


# ------------------------------------------------------------- varredura
def test_varredura_coleta_todos_e_grava(monkeypatch):
    monkeypatch.setattr(siconfi, "coletar_dca",
                        lambda ano, cod: _linhas_falsas(ano, cod))
    entes = [str(1000 + i) for i in range(50)]

    total = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0,
                           lote=10)

    assert total["entes"] == 50
    assert total["linhas"] == 150
    assert total["erros"] == 0
    assert len(armazem.ler("financas_ente")) == 150


def test_segunda_execucao_nao_refaz_nada(monkeypatch):
    chamadas: list[str] = []

    def falso(ano, cod):
        chamadas.append(cod)
        return _linhas_falsas(ano, cod)

    monkeypatch.setattr(siconfi, "coletar_dca", falso)
    entes = [str(2000 + i) for i in range(20)]

    siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0, lote=5)
    assert len(chamadas) == 20

    chamadas.clear()
    total = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0, lote=5)
    assert chamadas == [], "não devia ter buscado nada de novo"
    assert total["entes"] == 0
    assert len(armazem.ler("financas_ente")) == 60, "nem duplicou"


def test_retomada_apos_queda_no_meio(monkeypatch):
    """Simula a máquina hibernando: metade coletada, metade com erro."""
    entes = [str(3000 + i) for i in range(20)]
    caidos = set(entes[10:])

    def instavel(ano, cod):
        if cod in caidos:
            raise RuntimeError("conexão perdida")
        return _linhas_falsas(ano, cod)

    monkeypatch.setattr(siconfi, "coletar_dca", instavel)
    primeira = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0, lote=5)
    assert primeira["erros"] == 10
    assert len(armazem.ler("financas_ente")) == 30

    # rede voltou
    caidos.clear()
    tentados: list[str] = []

    def estavel(ano, cod):
        tentados.append(cod)
        return _linhas_falsas(ano, cod)

    monkeypatch.setattr(siconfi, "coletar_dca", estavel)
    segunda = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0, lote=5)

    assert sorted(tentados) == sorted(entes[10:]), "só os que falharam"
    assert segunda["erros"] == 0
    assert len(armazem.ler("financas_ente")) == 60


def test_ente_sem_dado_publicado_e_marcado_como_vazio(monkeypatch):
    monkeypatch.setattr(siconfi, "coletar_dca",
                        lambda ano, cod: [] if cod == "9001"
                        else _linhas_falsas(ano, cod))
    total = siconfi.varrer(2024, ["9001", "9002"], trabalhadores=2,
                           intervalo=0, lote=10)
    assert total["vazios"] == 1
    assert controle.resumo_entes("siconfi", "dca", 2024).get("vazio") == 1


def test_erro_em_um_ente_nao_derruba_a_varredura(monkeypatch):
    def as_vezes(ano, cod):
        if cod.endswith("7"):
            raise RuntimeError("HTTP 500")
        return _linhas_falsas(ano, cod)

    monkeypatch.setattr(siconfi, "coletar_dca", as_vezes)
    entes = [str(4000 + i) for i in range(30)]
    total = siconfi.varrer(2024, entes, trabalhadores=5, intervalo=0, lote=7)

    assert total["erros"] == 3
    assert total["entes"] == 30, "as outras 27 continuaram"
    assert len(armazem.ler("financas_ente")) == 81


def test_gravacao_em_lotes_nao_perde_o_resto(monkeypatch):
    """Lote de 7 sobre 20 entes: sobram 6 no buffer no fim."""
    monkeypatch.setattr(siconfi, "coletar_dca",
                        lambda ano, cod: _linhas_falsas(ano, cod, 1))
    entes = [str(5000 + i) for i in range(20)]
    siconfi.varrer(2024, entes, trabalhadores=3, intervalo=0, lote=7)
    assert len(armazem.ler("financas_ente")) == 20


def test_concorrencia_nao_duplica_nem_perde(monkeypatch):
    """Oito threads gravando na MESMA partição — o merge tem que fechar a conta."""
    monkeypatch.setattr(siconfi, "coletar_dca",
                        lambda ano, cod: _linhas_falsas(ano, cod, 2))
    entes = [str(6000 + i) for i in range(120)]
    total = siconfi.varrer(2024, entes, trabalhadores=8, intervalo=0, lote=13)

    df = armazem.ler("financas_ente")
    assert total["linhas"] == 240
    assert len(df) == 240
    assert df["sk"].is_unique
    assert df["cod_ibge"].nunique() == 120
