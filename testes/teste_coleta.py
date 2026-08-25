"""Testes dos bugs que apareceram na primeira coleta real, e do botão Atualizar.

Cada teste desta primeira metade corresponde a uma linha de erro que o Johnny
viu no console. Nenhum deles precisa de rede.
"""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from fastapi.testclient import TestClient  # noqa: E402

from src.api import tarefas  # noqa: E402
from src.coletores import camara, orquestrador  # noqa: E402
from src.nucleo import rede  # noqa: E402
from src.nucleo.registro import ContadorDeErros, obter as obter_log  # noqa: E402


# =================================================== 1. NaN nos CSVs
# "'float' object is not subscriptable" e "'float' object has no attribute 'strip'"

def test_celula_vazia_do_pandas_e_truthy():
    """A raiz do bug: `NaN or ''` devolve NaN, não ''."""
    vazio = float("nan")
    assert bool(vazio) is True, "é isto que fazia o `or ''` não proteger nada"


def test_sem_nan_troca_vazio_por_none():
    df = pd.read_csv(io.StringIO("id;ementa\n1;\n2;texto\n"), sep=";",
                     dtype=str, keep_default_na=False, na_values=[""])
    limpo = camara._sem_nan(df)
    assert limpo.iloc[0]["ementa"] is None
    assert limpo.iloc[1]["ementa"] == "texto"


def test_ementa_vazia_nao_quebra_mais():
    """Exatamente a linha que estourou: PL sem ementa preenchida."""
    df = camara._sem_nan(pd.read_csv(
        io.StringIO("id;ementa\n1;\n"), sep=";", dtype=str,
        keep_default_na=False, na_values=[""]))
    assert (df.iloc[0].get("ementa") or "")[:2000] == ""


def test_voto_vazio_nao_quebra_mais():
    """E a outra: parlamentar sem voto registrado na linha."""
    df = camara._sem_nan(pd.read_csv(
        io.StringIO("idVotacao;voto\nV1;\n"), sep=";", dtype=str,
        keep_default_na=False, na_values=[""]))
    assert (df.iloc[0].get("voto") or "").strip() == ""


def test_sem_nan_com_quadro_vazio():
    assert camara._sem_nan(pd.DataFrame()).empty


# =================================================== 2. 404 não se repete
class RespostaFalsa:
    def __init__(self, status: int, corpo: str = "{}"):
        self.status_code = status
        self.text = corpo
        self.content = corpo.encode()

    def json(self):
        return {"ok": True}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _sessao_que_responde(status, contador):
    class Sessao:
        headers: dict = {}

        def get(self, *a, **k):
            contador.append(1)
            return RespostaFalsa(status)
    return Sessao()


def test_404_nao_e_repetido(monkeypatch):
    """Quatro tentativas com espera exponencial num 404 é meio minuto jogado fora."""
    chamadas: list[int] = []
    monkeypatch.setattr(rede, "sessao",
                        lambda fonte: _sessao_que_responde(404, chamadas))
    rede.definir_intervalo("teste404", 0)

    with pytest.raises(rede.ErroDefinitivo) as erro:
        rede.buscar("teste404", "http://exemplo/inexistente", tentativas=4)

    assert len(chamadas) == 1, f"repetiu {len(chamadas)} vezes um 404"
    assert erro.value.status == 404


def test_429_continua_sendo_repetido(monkeypatch):
    """429 é 'devagar', não 'não existe' — esperar é exatamente o certo."""
    chamadas: list[int] = []
    monkeypatch.setattr(rede, "sessao",
                        lambda fonte: _sessao_que_responde(429, chamadas))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    rede.definir_intervalo("teste429", 0)

    with pytest.raises(RuntimeError):
        rede.buscar("teste429", "http://exemplo/freado", tentativas=3)
    assert len(chamadas) == 3


def test_500_continua_sendo_repetido(monkeypatch):
    chamadas: list[int] = []
    monkeypatch.setattr(rede, "sessao",
                        lambda fonte: _sessao_que_responde(503, chamadas))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    rede.definir_intervalo("teste503", 0)

    with pytest.raises(RuntimeError):
        rede.buscar("teste503", "http://exemplo/fora", tentativas=3)
    assert len(chamadas) == 3


def test_cota_tenta_as_urls_alternativas(monkeypatch):
    """A cota mudou de endereço; fixar uma URL só é o que quebrou."""
    tentadas: list[str] = []

    def falso_csv(url, **k):
        tentadas.append(url)
        if url.endswith(".csv") and "cotas" in url:
            raise rede.ErroDefinitivo("HTTP 404", 404)
        return pd.DataFrame([{"ideDocumento": "1"}])

    def falso_binario(fonte, url, **k):
        tentadas.append(url)
        raise rede.ErroDefinitivo("HTTP 404", 404)

    monkeypatch.setattr(camara, "_csv", falso_csv)
    monkeypatch.setattr(camara.rede, "buscar", falso_binario)

    df = camara._csv_da_cota(2025)
    assert not df.empty
    assert any("cotas/Ano-2025.csv.zip" in u for u in tentadas)
    assert any("despesasParlamentares" in u for u in tentadas)


def test_cota_indisponivel_em_todas_as_urls_falha_com_mensagem_util(monkeypatch):
    monkeypatch.setattr(camara, "_csv",
                        lambda url, **k: (_ for _ in ()).throw(
                            rede.ErroDefinitivo("HTTP 404", 404)))
    monkeypatch.setattr(camara.rede, "buscar",
                        lambda *a, **k: (_ for _ in ()).throw(
                            rede.ErroDefinitivo("HTTP 404", 404)))
    with pytest.raises(RuntimeError, match="todas as URLs conhecidas"):
        camara._csv_da_cota(2025)


# =================================================== 3. erro engolido conta
def test_contador_pega_erro_registrado_no_log():
    log = obter_log("coletores.camara")
    with ContadorDeErros() as contador:
        log.info("isto não conta")
        log.error("Câmara proposições 2025 falhou: %s", "boom")
    assert contador.total == 1
    assert "boom" in contador.mensagens[0]


def test_contador_ignora_erro_de_fora_da_coleta():
    """Ver teste_relatorio.py: erro da API virava 'problema' da fonte."""
    with ContadorDeErros() as contador:
        obter_log("api.servidor").error("consulta falhou")
    assert contador.total == 0


def test_coletor_que_engole_erro_nao_e_reportado_como_ok(monkeypatch):
    """Era o pior dos quatro: três falhas viravam 'concluído com 0 falha(s)'."""
    log = obter_log("coletores.falso")

    class ColetorQueEngole:
        @staticmethod
        def executar(**kwargs):
            log.error("Câmara proposições 2025 falhou: boom")
            log.error("Câmara votos 2025 falhou: boom")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorQueEngole)
    resultado = orquestrador.executar_fonte("camara", orquestrador.Opcoes())

    assert resultado.situacao == "parcial"
    assert len(resultado.erros) == 2


def test_coletor_limpo_e_reportado_como_ok(monkeypatch):
    class ColetorLimpo:
        @staticmethod
        def executar(**kwargs):
            obter_log("coletores.falso").info("tudo certo")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorLimpo)
    assert orquestrador.executar_fonte("senado", orquestrador.Opcoes()).situacao == "ok"


def test_excecao_que_escapa_vira_erro(monkeypatch):
    class ColetorQuebrado:
        @staticmethod
        def executar(**kwargs):
            raise RuntimeError("fonte fora do ar")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorQuebrado)
    resultado = orquestrador.executar_fonte("senado", orquestrador.Opcoes())
    assert resultado.situacao == "erro"
    assert "fora do ar" in resultado.erros[0]


# =================================================== 4. ano natural por fonte
def test_camara_usa_o_ano_corrente():
    """A coleta diária buscava o ano passado — justamente o que não muda mais."""
    from datetime import date
    assert orquestrador.anos_de("camara", orquestrador.Opcoes()) == [date.today().year]


def test_siconfi_usa_o_exercicio_fechado():
    from datetime import date
    assert orquestrador.anos_de("siconfi", orquestrador.Opcoes()) \
        == [date.today().year - 1]


def test_tse_usa_as_duas_ultimas_eleicoes():
    anos = orquestrador.anos_de("tse", orquestrador.Opcoes())
    assert len(anos) == 2 and all(a % 2 == 0 for a in anos)


def test_ano_explicito_manda_em_todas():
    assert orquestrador.anos_de("camara", orquestrador.Opcoes(ano=2019)) == [2019]
    assert orquestrador.anos_de("siconfi", orquestrador.Opcoes(anos=[2020, 2021])) \
        == [2020, 2021]


# =================================================== 5. botão Atualizar
@pytest.fixture
def cliente(monkeypatch):
    class ColetorRapido:
        @staticmethod
        def executar(**kwargs):
            obter_log("coletores.falso").info("coletando…")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorRapido)
    from src.api import servidor  # noqa: PLC0415
    return TestClient(servidor.app)


def _esperar_fim(cliente, limite=5.0):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        corpo = cliente.get("/api/coleta").json()
        if corpo.get("situacao") in ("concluida", "erro"):
            return corpo
        time.sleep(0.05)
    raise AssertionError("a tarefa não terminou a tempo")


def test_catalogo_lista_todas_as_fontes(cliente):
    catalogo = cliente.get("/api/coleta/catalogo").json()
    assert len(catalogo) == len(orquestrador.ORDEM)
    assert {c["fonte"] for c in catalogo} == set(orquestrador.ORDEM)
    assert all(c["rotulo"] and c["cadencia"] for c in catalogo)


def test_coleta_roda_em_segundo_plano_e_responde_na_hora(monkeypatch, cliente):
    """O POST volta na hora; a coleta continua atrás."""
    class ColetorLento:
        @staticmethod
        def executar(**kwargs):
            time.sleep(0.4)

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorLento)

    inicio = time.monotonic()
    resposta = cliente.post("/api/coleta", json={"fontes": ["senado"]})
    demora = time.monotonic() - inicio

    assert resposta.status_code == 202
    assert demora < 0.3, "o POST não pode esperar a coleta terminar"
    assert resposta.json()["situacao"] == "executando"

    final = _esperar_fim(cliente)
    assert final["situacao"] == "concluida"
    assert final["progresso"] == {"feitas": 1, "total": 1}


def test_log_da_coleta_chega_ao_painel(cliente):
    cliente.post("/api/coleta", json={"fontes": ["senado"]})
    final = _esperar_fim(cliente)
    textos = " ".join(l["texto"] for l in final["linhas"])
    assert "coletando" in textos


def test_ordem_das_fontes_e_respeitada(cliente):
    resposta = cliente.post("/api/coleta",
                            json={"fontes": ["camara", "ibge", "senado"]})
    assert resposta.json()["fontes"] == ["ibge", "camara", "senado"]
    _esperar_fim(cliente)


def test_segunda_coleta_simultanea_e_recusada(monkeypatch, cliente):
    class ColetorLento:
        @staticmethod
        def executar(**kwargs):
            time.sleep(0.6)

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorLento)
    assert cliente.post("/api/coleta", json={"fontes": ["senado"]}).status_code == 202

    segunda = cliente.post("/api/coleta", json={"fontes": ["ibge"]})
    assert segunda.status_code == 409, "duas varreduras disputariam a mesma partição"
    _esperar_fim(cliente)


def test_lista_de_fontes_vazia_e_recusada(cliente):
    assert cliente.post("/api/coleta", json={"fontes": []}).status_code == 422


def test_fonte_desconhecida_e_recusada(cliente):
    assert cliente.post("/api/coleta", json={"fontes": ["nasa"]}).status_code == 400


def test_falha_de_fonte_aparece_na_etapa(monkeypatch, cliente):
    class ColetorQuebrado:
        @staticmethod
        def executar(**kwargs):
            raise RuntimeError("deu ruim")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: ColetorQuebrado)
    cliente.post("/api/coleta", json={"fontes": ["senado"]})
    final = _esperar_fim(cliente)

    etapa = final["etapas"][0]
    assert etapa["situacao"] == "erro"
    assert "deu ruim" in etapa["erros"][0]
    assert final["situacao"] == "concluida", \
        "a tarefa termina; quem falhou foi a fonte"


def test_tarefa_pode_ser_consultada_por_id(cliente):
    id_tarefa = cliente.post("/api/coleta", json={"fontes": ["senado"]}).json()["id"]
    _esperar_fim(cliente)
    corpo = cliente.get(f"/api/coleta/{id_tarefa}").json()
    assert corpo["id"] == id_tarefa


def test_tarefa_inexistente_devolve_404(cliente):
    assert cliente.get("/api/coleta/999999").status_code == 404


# =================================================== 6. falta configurar ≠ ok
def test_fonte_sem_chave_nao_e_sucesso(monkeypatch, cliente):
    """O Portal terminava como 'ok' sem ter coletado uma linha sequer."""
    from src.nucleo.erros import ConfiguracaoAusente

    class SemChave:
        @staticmethod
        def executar(**kwargs):
            raise ConfiguracaoAusente("falta a chave da CGU.",
                                      "Cadastre em portaldatransparencia.gov.br")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: SemChave)
    resultado = orquestrador.executar_fonte("portal_transparencia",
                                            orquestrador.Opcoes())

    assert resultado.situacao == "configuracao"
    assert resultado.situacao != "erro", "não houve falha, falta configuração"
    assert "Cadastre" in resultado.erros[0], "a tela precisa dizer o que fazer"


def test_configuracao_pendente_aparece_na_etapa(monkeypatch, cliente):
    from src.nucleo.erros import ConfiguracaoAusente

    class SemChave:
        @staticmethod
        def executar(**kwargs):
            raise ConfiguracaoAusente("falta a chave.", "Cadastre o e-mail.")

    monkeypatch.setattr(orquestrador, "_modulo", lambda nome: SemChave)
    cliente.post("/api/coleta", json={"fontes": ["portal_transparencia"]})
    final = _esperar_fim(cliente)

    assert final["etapas"][0]["situacao"] == "configuracao"
    assert "Cadastre" in final["etapas"][0]["erros"][0]


def test_portal_sem_chave_levanta_configuracao_ausente(monkeypatch):
    from src.coletores import portal_transparencia
    from src.nucleo.erros import ConfiguracaoAusente

    monkeypatch.setattr(portal_transparencia.config,
                        "CHAVE_PORTAL_TRANSPARENCIA", "")
    monkeypatch.setattr(portal_transparencia.controle, "gravar_marca",
                        lambda *a, **k: None)

    with pytest.raises(ConfiguracaoAusente) as erro:
        portal_transparencia.coletar_emendas(2026)
    assert "cadastrar-email" in erro.value.como_resolver


def test_portal_com_chave_nao_reclama(monkeypatch):
    from src.coletores import portal_transparencia

    monkeypatch.setattr(portal_transparencia.config,
                        "CHAVE_PORTAL_TRANSPARENCIA", "abc123")
    monkeypatch.setattr(portal_transparencia.rede, "buscar",
                        lambda *a, **k: [])
    monkeypatch.setattr(portal_transparencia.controle, "gravar_marca",
                        lambda *a, **k: None)
    assert portal_transparencia.coletar_emendas(2026) == 0
