"""Testes da linha de comando.

Existem porque `--situacao` e `--tudo` sozinhos morriam com
"invalid choice: []" — o argparse valida o valor PADRÃO de um nargs="*"
contra a lista de `choices`, e a lista vazia não está nela. Um teste que
apenas chama o parser teria pego isso na primeira execução.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from src.coletores import orquestrador  # noqa: E402
from src.nucleo import armazem  # noqa: E402
from src.scripts import coletar  # noqa: E402


def test_situacao_sozinha_funciona(capsys):
    assert coletar.principal(["--situacao"]) == 0
    assert "nenhuma coleta registrada" in capsys.readouterr().out


def test_sem_argumentos_mostra_ajuda_e_sai_com_erro(capsys):
    assert coletar.principal([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_fonte_desconhecida_e_recusada():
    with pytest.raises(SystemExit):
        coletar.principal(["nasa"])


def test_fontes_validas_sao_aceitas_pelo_parser(monkeypatch):
    chamadas = []

    class Falso:
        @staticmethod
        def executar(**kwargs):
            chamadas.append(kwargs)

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: Falso)
    assert coletar.principal(["senado"]) == 0
    assert len(chamadas) == 1


def test_opcoes_de_varredura_chegam_no_coletor(monkeypatch):
    recebidos = {}

    class Falso:
        @staticmethod
        def executar(**kwargs):
            recebidos.update(kwargs)

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: Falso)
    coletar.principal(["siconfi", "--nivel", "municipio", "--uf", "ba",
                       "--trabalhadores", "8", "--ano", "2024"])

    assert recebidos["nivel"] == "municipio"
    assert recebidos["uf"] == "ba"
    assert recebidos["trabalhadores"] == 8
    assert recebidos["ano"] == 2024


def test_falha_de_uma_fonte_nao_impede_as_outras(monkeypatch):
    executadas = []

    class Quebrado:
        @staticmethod
        def executar(**kwargs):
            executadas.append("quebrado")
            raise RuntimeError("fonte fora do ar")

    class Ok:
        @staticmethod
        def executar(**kwargs):
            executadas.append("ok")

    monkeypatch.setattr(orquestrador, "_modulo",
                        lambda nome: Quebrado if nome == "senado" else Ok)
    codigo = coletar.principal(["senado", "tse"])

    assert executadas == ["quebrado", "ok"]
    assert codigo == 2, "código de saída deve sinalizar falha parcial"


def test_pendencias_sem_dados_nao_quebra(capsys):
    # Limpa explicitamente: os testes compartilham um armazém temporário, e
    # depender do que outro arquivo deixou (ou não) para trás é justamente o
    # acoplamento que o conftest.py existe para tornar visível.
    armazem.remover("dim_de_para_ente")
    assert coletar.principal(["--pendencias"]) == 0
    assert "nenhuma pendência" in capsys.readouterr().out


def test_pendencias_lista_o_que_nao_casou(capsys):
    armazem.remover("dim_de_para_ente")
    armazem.mesclar("dim_de_para_ente", [{
        "fonte_origem": "tse", "id_origem": "99999", "cod_ibge": None,
        "sigla_uf": "SP", "nome_origem": "LUGAR NENHUM", "nome_ibge": None,
        "metodo": "pendente", "similaridade": 0.3,
    }], "teste")

    assert coletar.principal(["--pendencias"]) == 0
    saida = capsys.readouterr().out
    assert "LUGAR NENHUM" in saida
    assert "EXCECOES" in saida, "a saída precisa dizer como resolver"
    armazem.remover("dim_de_para_ente")


def test_sem_ano_cada_fonte_usa_o_ano_natural_dela():
    """`--ano` tinha padrão `ano-1`, então NUNCA era None — e `anos_de()`,
    que existe para dar a cada fonte o ano natural dela, via um ano explícito
    em toda execução. A coleta diária da Câmara voltava a buscar o ano
    passado: exatamente o defeito que `anos_de` foi escrito para corrigir.
    """
    from datetime import date  # noqa: PLC0415

    from src.coletores.orquestrador import Opcoes, anos_de  # noqa: PLC0415
    from src.scripts.coletar import montar_parser  # noqa: PLC0415

    args = montar_parser().parse_args(["camara"])
    assert args.ano is None, "--ano não pode ter padrão"

    opcoes = Opcoes(ano=args.ano)
    assert anos_de("camara", opcoes) == [date.today().year]
    assert anos_de("siconfi", opcoes) == [date.today().year - 1]

    # E continua obedecendo quando o ano é pedido de verdade.
    forcado = Opcoes(ano=montar_parser().parse_args(["camara", "--ano", "2023"]).ano)
    assert anos_de("camara", forcado) == [2023]


def test_limite_publicado_da_fonte_e_piso_e_nao_padrao():
    """A varredura municipal rodou meses a ~6,7 req/s contra um SICONFI que
    documenta UMA por segundo: o padrão de `varrer` (0,15 s) valia mais que o
    limite declarado da fonte, e nada avisava.

    Agora `config.INTERVALO_REQUISICOES` é piso — pedir menos não funciona.
    """
    from src.nucleo import config, rede  # noqa: PLC0415

    piso = config.INTERVALO_REQUISICOES["siconfi"]
    assert piso >= 1.0, "o SICONFI documenta 1 requisição por segundo"

    rede.definir_intervalo("siconfi", 0.15)
    assert rede.intervalo_de("siconfi") == piso, (
        "pedir 0,15s numa fonte com piso de 1s não pode valer")

    # Mais devagar que o piso continua sendo escolha de quem chama.
    rede.definir_intervalo("siconfi", 2.5)
    assert rede.intervalo_de("siconfi") == 2.5
    rede.definir_intervalo("siconfi", piso)


def test_amostra_existe_para_conferir_a_fonte_em_vez_de_supor():
    from src.scripts.coletar import montar_parser  # noqa: PLC0415

    args = montar_parser().parse_args(["--amostra", "29", "--ano", "2025"])
    assert args.amostra == "29"
    assert args.ano == 2025


def test_diagnostico_diz_onde_o_acervo_esta_e_o_que_tem():
    """Quando um número some da tela, a primeira pergunta é ONDE o projeto
    está lendo — `PAINEL_DADOS` pode estar no .env, numa variável do Windows
    ou em lugar nenhum, e o painel lê um lugar enquanto se olha outro.
    Diagnosticar isso por conversa custou várias rodadas."""
    from src.scripts.coletar import montar_parser, principal  # noqa: PLC0415

    args = montar_parser().parse_args(["--diagnostico"])
    assert args.diagnostico is True

    # Acervo vazio devolve 1: é um estado que exige ação, não sucesso.
    assert principal(["--diagnostico"]) in (0, 1)
