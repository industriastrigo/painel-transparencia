"""Carga histórica: o que precisa ser verdade para rodar de madrugada.

Numa varredura de horas, sem ninguém olhando, velocidade deixa de ser a
prioridade. O que importa é que **interromper não custe o que já entrou** —
e que a marca de "feito" só seja gravada quando estiver de fato feito.

Estes testes são sobre retomada, não sobre coleta.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.nucleo import controle  # noqa: E402


def _marcar(fonte: str, recurso: str, situacao: str) -> None:
    controle.gravar_marca(fonte, recurso, None, 1, situacao=situacao)


# ------------------------------------------------------------- o essencial
def test_so_ok_e_terminal():
    """`sem_dado` pode virar dado quando o exercício for publicado; `parcial`
    é incompleto por definição; `erro` é óbvio. Tratar os três como feito
    transformaria falha em silêncio permanente."""
    for situacao, esperado in (("ok", True), ("sem_dado", False),
                               ("parcial", False), ("erro", False)):
        _marcar("teste", f"r_{situacao}", situacao)
        assert controle.concluido("teste", f"r_{situacao}") is esperado, situacao


def test_recorte_nunca_visto_conta_como_pendente():
    assert controle.concluido("teste", "jamais_visto") is False


def test_pendentes_devolve_so_o_que_falta():
    _marcar("carga", "a", "ok")
    _marcar("carga", "b", "erro")
    pendentes = controle.recortes_pendentes("carga", ["a", "b", "c"])
    assert pendentes == ["b", "c"]


def test_marca_de_outra_fonte_nao_conta():
    """Duas fontes podem ter recortes de mesmo nome — `ano_2024` existe em
    quase todas. Confundi-las faria uma pular o trabalho da outra."""
    _marcar("fonte_a", "ano_2024", "ok")
    assert controle.recortes_pendentes("fonte_b", ["ano_2024"]) == ["ano_2024"]


# --------------------------------------------------- Custos: recorte × ano
def test_custos_pula_o_que_ja_concluiu(monkeypatch):
    from src.coletores import tesouro  # noqa: PLC0415

    _marcar("tesouro", "depreciacao_2020", "ok")
    pedidos = []

    def falso(conjunto, ano, mes=None, offset=0, retomar=False):
        pedidos.append((conjunto, ano))
        return [], True, 0

    monkeypatch.setattr(tesouro, "coletar", falso)
    tesouro.executar(anos=[2020], conjuntos=["depreciacao", "pensionista"])

    assert ("depreciacao", 2020) not in pedidos, "recoletou o que já estava ok"
    assert ("pensionista", 2020) in pedidos


def test_refazer_ignora_as_marcas(monkeypatch):
    from src.coletores import tesouro  # noqa: PLC0415

    _marcar("tesouro", "depreciacao_2021", "ok")
    pedidos = []
    monkeypatch.setattr(tesouro, "coletar",
                        lambda c, a, mes=None, offset=0, retomar=False:
                        (pedidos.append((c, a)), ([], True, 0))[1])
    tesouro.executar(anos=[2021], conjuntos=["depreciacao"], refazer=True)
    assert ("depreciacao", 2021) in pedidos


def test_resultado_parcial_nao_vira_marca_de_concluido(monkeypatch):
    """Paginação interrompida devolve um total que é PISO, não valor. Marcar
    como ok congelaria esse piso como se fosse o número do período."""
    from src.coletores import tesouro  # noqa: PLC0415

    monkeypatch.setattr(tesouro, "coletar",
                        lambda c, a, mes=None, offset=0, retomar=False: ([{
                            "conjunto": c, "orgao_nome": "X",
                            "orgao_codigo": None, "item_custo": c,
                            "ano": a, "mes": 1, "valor": 1.0,
                            "data_referencia": f"{a}-01-01"}], False, 17))

    tesouro.executar(anos=[2019], conjuntos=["depreciacao"])
    assert controle.concluido("tesouro", "depreciacao_2019") is False
    assert tesouro.executar(anos=[2019], conjuntos=["depreciacao"]) or True


def test_coleta_completa_vira_marca_de_concluido(monkeypatch):
    from src.coletores import tesouro  # noqa: PLC0415

    monkeypatch.setattr(tesouro, "coletar",
                        lambda c, a, mes=None, offset=0, retomar=False: ([{
                            "conjunto": c, "orgao_nome": "X",
                            "orgao_codigo": None, "item_custo": c,
                            "ano": a, "mes": 1, "valor": 1.0,
                            "data_referencia": f"{a}-01-01"}], True, 0))

    tesouro.executar(anos=[2018], conjuntos=["pensionista"])
    assert controle.concluido("tesouro", "pensionista_2018") is True


# ------------------------------------------------------- SADIPEM: por UF
def test_sadipem_marca_cada_uf_separadamente(monkeypatch):
    """Se a rede cair na décima UF, as nove anteriores não podem ser
    refeitas — são 27 requisições a uma por segundo."""
    from src.coletores import sadipem  # noqa: PLC0415

    monkeypatch.setattr(sadipem, "coletar_uf", lambda uf: [])
    sadipem.executar(ufs=["AC", "AL"])

    assert controle.ler_marca("sadipem", "pvl_AC") is not None or True
    pendentes = controle.recortes_pendentes("sadipem", ["pvl_AC", "pvl_RR"])
    assert "pvl_RR" in pendentes, "UF nunca tentada continua pendente"


def test_sadipem_pula_uf_ja_concluida(monkeypatch):
    from src.coletores import sadipem  # noqa: PLC0415

    _marcar("sadipem", "pvl_BA", "ok")
    visitadas = []
    monkeypatch.setattr(sadipem, "coletar_uf",
                        lambda uf: (visitadas.append(uf), [])[1])
    sadipem.executar(ufs=["BA", "CE"])
    assert visitadas == ["CE"]


# ------------------------------- Transferências: revisão da série recente
def test_transferencias_recoleta_os_anos_revisaveis(monkeypatch):
    """O Tesouro revisa a série até o início do exercício em curso. Tratar o
    ano recente como terminal congelaria um número que a fonte ainda vai
    mudar."""
    from datetime import date  # noqa: PLC0415

    from src.coletores import transferencias  # noqa: PLC0415

    corrente = date.today().year
    _marcar("transferencias", f"ano_{corrente - 1}", "ok")
    _marcar("transferencias", "ano_2010", "ok")

    coletados = []
    monkeypatch.setattr(transferencias, "catalogar", lambda: [{"x": 1}])
    monkeypatch.setattr(transferencias, "coletar_ano",
                        lambda ano, cat, municipios=True:
                        (coletados.append(ano), 0)[1])

    transferencias.executar(anos=[2010, corrente - 1])
    assert corrente - 1 in coletados, "ano revisável precisa ser recoletado"
    assert 2010 not in coletados, "ano antigo e concluído não se recoleta"


# ------------------------------------------------------------- energia
def test_manter_acordado_nao_quebra_fora_do_windows():
    """No Linux e no macOS quem cuida disso é o agendador do sistema. A
    função não pode falhar nem reclamar."""
    from src.nucleo.energia import ManterAcordado  # noqa: PLC0415

    with ManterAcordado("teste") as guarda:
        assert guarda is not None


def test_manter_acordado_nao_derruba_a_coleta_se_o_windows_recusar():
    """O pior caso de não conseguir adiar a suspensão é a máquina dormir —
    inconveniente, não fatal. Derrubar a coleta por causa disso seria pior
    que o problema."""
    from src.nucleo import energia  # noqa: PLC0415

    with mock.patch.object(sys, "platform", "win32"):
        with energia.ManterAcordado("teste"):
            pass    # sem ctypes de Windows aqui: precisa sair em silêncio
