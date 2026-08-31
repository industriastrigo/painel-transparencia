"""Testes da chave da CGU: colagem, mascaramento e gravação no .env.

Regra que os testes protegem: a chave é gravada no `.env` e em mais lugar
nenhum. Nunca no log, nunca numa resposta de leitura, nunca por inteiro.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from fastapi.testclient import TestClient  # noqa: E402

from src.nucleo import config, rede, segredos  # noqa: E402

CHAVE = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


# ------------------------------------------------------------------ colagem
def test_aceita_a_chave_pura():
    assert segredos.validar_chave(CHAVE) == CHAVE


def test_aceita_o_bloco_de_exemplo_da_cgu():
    """Colar o JSON inteiro da página é o caminho natural."""
    colado = f'[{{"key":"chave-api-dados","value":"{CHAVE}"}}]'
    assert segredos.validar_chave(colado) == CHAVE


def test_aceita_com_espacos_e_aspas():
    assert segredos.validar_chave(f'  "{CHAVE}"  ') == CHAVE


def test_recusa_o_placeholder_da_pagina():
    """`chave_api` é o texto de exemplo, não uma chave."""
    colado = '[{"key":"chave-api-dados","value":"chave_api"}]'
    with pytest.raises(ValueError, match="texto de exemplo"):
        segredos.validar_chave(colado)


def test_recusa_texto_que_nao_e_chave():
    with pytest.raises(ValueError, match="formato inesperado"):
        segredos.validar_chave("minha chave é essa aqui ó")


def test_recusa_vazio():
    with pytest.raises(ValueError, match="nenhuma chave"):
        segredos.validar_chave("   ")


def test_recusa_chave_curta_demais():
    with pytest.raises(ValueError):
        segredos.validar_chave("abc123")


# --------------------------------------------------------------- mascarar
def test_mascara_mostra_so_o_sufixo():
    """Início + fim expunha 8 dos 32 caracteres. Só o final basta para o
    usuário reconhecer a chave."""
    mascara = segredos.mascarar(CHAVE)
    assert mascara == "…8f90"
    assert CHAVE[:4] not in mascara, "o início não pode aparecer"
    assert CHAVE not in mascara


def test_mascara_de_vazio_e_nula():
    assert segredos.mascarar("") is None
    assert segredos.mascarar(None) is None


def test_mascara_de_valor_curto_nao_vaza_nada():
    assert segredos.mascarar("abc") == "………"


# ------------------------------------------------------------------- .env
def test_grava_criando_o_arquivo(tmp_path):
    destino = tmp_path / ".env"
    segredos.gravar_no_env("CHAVE_PORTAL_TRANSPARENCIA", CHAVE, destino)
    assert destino.read_text() == f"CHAVE_PORTAL_TRANSPARENCIA={CHAVE}\n"


def test_grava_preservando_o_resto_do_arquivo(tmp_path):
    destino = tmp_path / ".env"
    destino.write_text(
        "# comentário meu\n"
        "PAINEL_API_PORTA=8123\n"
        "CHAVE_PORTAL_TRANSPARENCIA=antiga\n"
        "PAINEL_COMPRESSAO=zstd\n", encoding="utf-8")

    segredos.gravar_no_env("CHAVE_PORTAL_TRANSPARENCIA", CHAVE, destino)
    linhas = destino.read_text(encoding="utf-8").splitlines()

    assert linhas[0] == "# comentário meu", "comentário do usuário sobrevive"
    assert linhas[1] == "PAINEL_API_PORTA=8123"
    assert linhas[2] == f"CHAVE_PORTAL_TRANSPARENCIA={CHAVE}"
    assert linhas[3] == "PAINEL_COMPRESSAO=zstd", "ordem preservada"


def test_acrescenta_quando_a_variavel_nao_existia(tmp_path):
    destino = tmp_path / ".env"
    destino.write_text("PAINEL_API_PORTA=8123\n", encoding="utf-8")
    segredos.gravar_no_env("CHAVE_PORTAL_TRANSPARENCIA", CHAVE, destino)
    assert "PAINEL_API_PORTA=8123" in destino.read_text(encoding="utf-8")
    assert f"CHAVE_PORTAL_TRANSPARENCIA={CHAVE}" in destino.read_text(encoding="utf-8")


def test_gravacao_nao_deixa_arquivo_temporario(tmp_path):
    destino = tmp_path / ".env"
    segredos.gravar_no_env("X", "1", destino)
    assert list(tmp_path.iterdir()) == [destino]


def test_a_chave_nao_aparece_no_log(tmp_path, caplog):
    with caplog.at_level("INFO"):
        segredos.gravar_no_env("CHAVE_PORTAL_TRANSPARENCIA", CHAVE,
                               tmp_path / ".env")
    assert CHAVE not in caplog.text, "a chave inteira vazou para o log"
    assert "…8f90" in caplog.text


# ------------------------------------------------------------- aplicação
@pytest.fixture
def sem_chave(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    monkeypatch.setattr(config, "CHAVE_PORTAL_TRANSPARENCIA", "")
    yield tmp_path


def test_aplicar_passa_a_valer_na_hora(sem_chave, monkeypatch):
    monkeypatch.setattr(segredos, "testar_chave_portal",
                        lambda c: (True, "ok"))
    segredos.aplicar_chave_portal(CHAVE)

    assert config.CHAVE_PORTAL_TRANSPARENCIA == CHAVE
    sessao = rede.sessao("portal_transparencia")
    assert sessao.headers.get("chave-api-dados") == CHAVE, \
        "a Session guarda o cabeçalho da criação — precisa ser refeita"


def test_trocar_a_chave_refaz_a_sessao(sem_chave, monkeypatch):
    monkeypatch.setattr(segredos, "testar_chave_portal", lambda c: (True, "ok"))
    segredos.aplicar_chave_portal(CHAVE)
    primeira = rede.sessao("portal_transparencia")

    outra = "f" * 32
    segredos.aplicar_chave_portal(outra)
    segunda = rede.sessao("portal_transparencia")

    assert segunda is not primeira
    assert segunda.headers.get("chave-api-dados") == outra


def test_chave_invalida_nao_toca_no_env(sem_chave):
    with pytest.raises(ValueError):
        segredos.aplicar_chave_portal("chave_api")
    assert not (sem_chave / ".env").exists()


# ------------------------------------------------------------------- API
@pytest.fixture
def cliente(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    monkeypatch.setattr(config, "CHAVE_PORTAL_TRANSPARENCIA", "")
    monkeypatch.setattr(segredos, "testar_chave_portal",
                        lambda c: (True, "chave aceita pelo Portal."))
    from src.api import servidor  # noqa: PLC0415
    return TestClient(servidor.app)


def test_config_diz_que_falta_chave(cliente):
    corpo = cliente.get("/api/config").json()["portal_transparencia"]
    assert corpo["configurada"] is False
    assert corpo["mascara"] is None


def test_salvar_pela_api(cliente):
    resposta = cliente.post("/api/config/chave-portal", json={"chave": CHAVE})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["salva"] is True and corpo["validada"] is True
    assert corpo["mascara"] == "…8f90"

    depois = cliente.get("/api/config").json()["portal_transparencia"]
    assert depois["configurada"] is True


def test_a_api_nunca_devolve_a_chave_inteira(cliente):
    cliente.post("/api/config/chave-portal", json={"chave": CHAVE})
    for rota in ("/api/config", "/api/saude"):
        assert CHAVE not in cliente.get(rota).text, f"vazou em {rota}"


def test_placeholder_e_recusado_com_explicacao(cliente):
    resposta = cliente.post("/api/config/chave-portal",
                            json={"chave": "chave_api"})
    assert resposta.status_code == 400
    assert "texto de exemplo" in resposta.json()["detail"]


def test_chave_vazia_e_recusada(cliente):
    assert cliente.post("/api/config/chave-portal",
                        json={"chave": ""}).status_code == 422


def test_chave_salva_mesmo_quando_o_teste_nao_responde(cliente, monkeypatch):
    """Sem internet, a chave é salva — só não dá para afirmar que serve."""
    monkeypatch.setattr(segredos, "testar_chave_portal",
                        lambda c: (False, "não deu para testar agora."))
    corpo = cliente.post("/api/config/chave-portal",
                         json={"chave": CHAVE}).json()
    assert corpo["salva"] is True
    assert corpo["validada"] is False
