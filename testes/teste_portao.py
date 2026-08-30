"""O portão de qualidade — asserções sobre o RESULTADO da carga.

Estes testes existem por causa da noite de 26/08: a suíte inteira passou
enquanto a carga gravava zero linha. Todo teste aqui monta um acervo com um
defeito PLAUSÍVEL de produção e verifica se o portão barra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.nucleo import armazem, portao  # noqa: E402


@pytest.fixture(autouse=True)
def contadores_limpos():
    armazem.MEDIDAS.clear()
    armazem.COLAPSOS.clear()
    yield
    armazem.MEDIDAS.clear()
    armazem.COLAPSOS.clear()


def _entes(quantos: int, inicio: int = 0, **extra):
    return [{"cod_ibge": str(3500000 + i), "nome": f"Cidade {i}",
             "nivel": "municipio", "sigla_uf": "SP", **extra}
            for i in range(inicio, inicio + quantos)]


# ------------------------------------------------------------------ volume
def test_carga_limpa_nao_gera_achado_de_volume():
    armazem.mesclar("dim_ente", _entes(10), fonte="teste")
    assert portao.conferir_volume() == []


def test_colisao_de_chave_acima_do_limiar_bloqueia():
    """O defeito mais silencioso: a linha chegou, o merge descartou."""
    lote = _entes(2) + [{"cod_ibge": "3500000", "nome": "Cidade repetida",
                         "nivel": "municipio", "sigla_uf": "SP"}]
    armazem.mesclar("dim_ente", lote, fonte="teste")

    achados = portao.conferir_volume()
    assert len(achados) == 1
    assert achados[0].bloqueia
    assert "colisão de chave" in achados[0].mensagem
    assert achados[0].alvo == "dim_ente"


def test_perda_dentro_do_limiar_vira_aviso_e_nao_bloqueio():
    lote = _entes(1000) + [{"cod_ibge": "3500000", "nome": "repetida",
                            "nivel": "municipio", "sigla_uf": "SP"}]
    armazem.mesclar("dim_ente", lote, fonte="teste")

    achados = portao.conferir_volume()
    assert len(achados) == 1
    assert not achados[0].bloqueia


def test_merge_chamado_e_nada_chegou_bloqueia():
    """A noite de 26/08 em uma linha: a carga rodou, a fonte respondeu vazio."""
    armazem.mesclar("dim_ente", [], fonte="teste")
    achados = portao.conferir_volume()
    assert [a.bloqueia for a in achados] == [True]
    assert "nenhuma linha chegou" in achados[0].mensagem


# ----------------------------------------------------------- preenchimento
def test_coluna_que_despenca_de_cheia_para_vazia_bloqueia():
    """`situacao` esteve 98% preenchida e virou 3% por nome de campo trocado.
    O formato continua válido — é por isso que nenhum teste de forma pega."""
    armazem.remover("dim_ente")
    armazem.mesclar("dim_ente", _entes(300, situacao="Em tramitação"),
                    fonte="teste")
    assert portao.conferir_preenchimento(["dim_ente"]) == []

    armazem.mesclar("dim_ente", _entes(300, situacao=None), fonte="teste")
    achados = portao.conferir_preenchimento(["dim_ente"])

    assert [a.alvo for a in achados] == ["dim_ente.situacao"]
    assert achados[0].bloqueia
    assert "100%" in achados[0].mensagem and "0%" in achados[0].mensagem


def test_referencia_nao_afunda_com_a_carga_ruim():
    """Comparar com a carga ANTERIOR tem buraco: a primeira carga ruim vira a
    nova referência e a segunda passa. A referência é a melhor taxa já vista."""
    armazem.remover("dim_ente")
    armazem.mesclar("dim_ente", _entes(300, situacao="cheia"), fonte="teste")
    portao.conferir_preenchimento(["dim_ente"])

    armazem.mesclar("dim_ente", _entes(300, situacao=None), fonte="teste")
    assert portao.conferir_preenchimento(["dim_ente"])          # acusa
    assert portao.conferir_preenchimento(["dim_ente"])          # continua acusando


def test_tabela_pequena_demais_nao_e_perfilada():
    """Com 12 linhas, uma linha a mais move a taxa 8 pontos. Ruído."""
    armazem.remover("dim_ente")
    armazem.mesclar("dim_ente", _entes(12, situacao="cheia"), fonte="teste")
    portao.conferir_preenchimento(["dim_ente"])
    armazem.mesclar("dim_ente", _entes(12, situacao=None), fonte="teste")
    assert portao.conferir_preenchimento(["dim_ente"]) == []


# ------------------------------------------------------------------- ouro
def test_sem_registro_ouro_o_portao_avisa_mas_nao_barra(tmp_path):
    achados = portao.conferir_ouro(tmp_path / "nao-existe.csv")
    assert len(achados) == 1
    assert not achados[0].bloqueia
    assert "nada aqui prova" in achados[0].mensagem


def test_valor_divergente_do_documento_oficial_bloqueia(tmp_path):
    armazem.remover("dim_ente")
    armazem.mesclar("dim_ente", _entes(10), fonte="teste")

    csv = tmp_path / "ouro.csv"
    csv.write_text(
        "tabela,filtro,expressao,valor_esperado,tolerancia_pct,documento\n"
        "dim_ente,sigla_uf = 'SP',COUNT(*),10,0,doc oficial\n"
        "dim_ente,sigla_uf = 'SP',COUNT(*),42,0,doc oficial\n",
        encoding="utf-8")

    achados = portao.conferir_ouro(csv)
    assert len(achados) == 1          # a primeira confere, a segunda não
    assert achados[0].bloqueia
    assert "42" in achados[0].mensagem


def test_recorte_que_sumiu_do_acervo_bloqueia(tmp_path):
    armazem.remover("dim_ente")
    armazem.mesclar("dim_ente", _entes(10), fonte="teste")
    csv = tmp_path / "ouro.csv"
    csv.write_text(
        "tabela,filtro,expressao,valor_esperado,tolerancia_pct,documento\n"
        "dim_ente,sigla_uf = 'BA',SUM(1),100,1,doc oficial\n",
        encoding="utf-8")

    achados = portao.conferir_ouro(csv)
    assert achados[0].bloqueia
    assert "não existe mais no acervo" in achados[0].mensagem


# --------------------------------------------------------------- veredito
def test_veredito_separa_bloqueio_de_aviso():
    v = portao.Veredito([
        portao.Achado("volume", "t", True, "barra"),
        portao.Achado("ouro", "t", False, "avisa"),
    ])
    assert v.bloqueia
    assert len(v.bloqueios) == 1 and len(v.avisos) == 1
    v.relatar()


# ------------------------------------------------------------ marca vazia
def test_marca_ok_com_zero_linha_bloqueia():
    """`dca_2026` ficou `ok` com 0 linhas. Como só `ok` é terminal, aquele ano
    saiu da fila de coleta para sempre — sem ninguém decidir isso."""
    from src.nucleo import controle  # noqa: PLC0415

    controle.gravar_marca("siconfi", "dca_2026", 2026, 0, situacao="ok")
    controle.gravar_marca("siconfi", "dca_2025", 2025, 5000, situacao="ok")

    achados = portao.conferir_marcas_vazias()
    assert [a.alvo for a in achados] == ["siconfi/dca_2026"]
    assert achados[0].bloqueia
    assert "nunca mais será coletado" in achados[0].mensagem
