"""Testes do segundo log de coleta real.

O tema desta rodada é: **o conserto anterior não pegou o caso real**. O
`_sem_nan` limpava o DataFrame e o teste confirmava — olhando `df.iloc[...]`.
Só que o coletor lê com `iterrows()`, e aí o pandas devolve o NaN de volta.
Os testes abaixo passam pelo mesmo caminho que o coletor usa.
"""

from __future__ import annotations

import io
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O armazém temporário deste arquivo é criado pela fixture em conftest.py.

from src.coletores import camara, ibge, siconfi, tse  # noqa: E402
from src.nucleo import armazem, controle  # noqa: E402
from src.nucleo.valores import inteiro, numero, opcional, texto  # noqa: E402


def _quadro(csv: str) -> pd.DataFrame:
    return camara._sem_nan(pd.read_csv(
        io.StringIO(csv), sep=";", dtype=str,
        keep_default_na=False, na_values=[""]))


# ============================== 1. o NaN que voltou pelo iterrows
def test_iterrows_ressuscita_o_nan():
    """A prova de que limpar o DataFrame não basta.

    Este teste documenta o comportamento do pandas que derrubou o conserto
    anterior. Se um dia ele falhar, é porque o pandas mudou — e aí a proteção
    em `valores.texto()` continua correta de qualquer jeito.
    """
    limpo = _quadro("id;ementa\n1;\n")
    assert limpo.iloc[0]["ementa"] is None, "no quadro, é None"

    _, linha = next(limpo.iterrows())
    assert linha.get("ementa") != linha.get("ementa"), \
        "pela linha, voltou a ser NaN (NaN != NaN)"


def test_texto_protege_no_ponto_de_uso():
    _, linha = next(_quadro("id;ementa\n1;\n").iterrows())
    assert texto(linha.get("ementa"), 2000) == ""
    assert opcional(linha.get("ementa")) is None


def test_valores_lidam_com_os_tipos_que_aparecem():
    assert texto(None) == "" and texto(float("nan")) == ""
    assert texto("  Lei  ") == "Lei"
    assert texto("abcdef", 3) == "abc"
    assert opcional("   ") is None
    assert numero("1.234,5") is None or isinstance(numero("1234.5"), float)
    assert numero(float("nan")) is None
    assert numero("não é número") is None
    assert inteiro(None, 7) == 7
    assert inteiro("12") == 12


def test_proposicao_sem_ementa_e_sem_autor_nao_quebra(monkeypatch):
    """Exatamente a linha do log: 'Câmara proposições 2026 falhou'."""
    proposicoes = ("id;siglaTipo;numero;ano;ementa;keywords;dataApresentacao;"
                   "descricaoSituacao;despacho;urlInteiroTeor\n"
                   "2400001;PL;1;2026;Uma ementa;;2026-02-01;Em tramitação;;http://x\n"
                   "2400002;PL;2;2026;;;2026-02-02;;;\n")
    autores = ("idProposicao;idDeputadoAutor;nomeAutor;siglaPartidoAutor;"
               "siglaUFAutor;ordemAssinatura\n"
               "2400001;123;Fulano;XYZ;SP;1\n")

    monkeypatch.setattr(camara, "_csv", lambda url, **k: _quadro(
        autores if "Autores" in url else proposicoes))
    gravadas: list[dict] = []
    monkeypatch.setattr(camara.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.extend(linhas))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    assert camara.coletar_proposicoes(2026) == 2

    sem_ementa = next(l for l in gravadas if l["id_proposicao"] == "2400002")
    assert sem_ementa["ementa"] == ""
    assert sem_ementa["nome_autor"] is None, "proposição sem autor no arquivo"
    com_ementa = next(l for l in gravadas if l["id_proposicao"] == "2400001")
    assert com_ementa["nome_autor"] == "Fulano"


def test_voto_em_branco_nao_quebra(monkeypatch):
    csv = ("idVotacao;deputado_id;deputado_nome;deputado_siglaPartido;"
           "deputado_siglaUf;voto;dataHoraVoto\n"
           "V1;1;Fulano;XYZ;SP;Sim;2026-05-02T15:00\n"
           "V1;2;Beltrano;ABC;BA;;2026-05-02T15:00\n")
    monkeypatch.setattr(camara, "_csv", lambda url, **k: _quadro(csv))
    gravadas: list[dict] = []
    monkeypatch.setattr(camara.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.extend(linhas))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    assert camara.coletar_votos(2026) == 2
    assert [l["voto"] for l in gravadas] == ["Sim", ""]


# ============================== 2. cota parlamentar: 1.307 notas descartadas
def test_documento_parcelado_nao_e_duplicata(monkeypatch):
    """Mesmo `ideDocumento`, parcelas diferentes: são notas distintas."""
    csv = ("ideDocumento;numParcela;numRessarcimento;numDeputadoId;"
           "txNomeParlamentar;vlrLiquido;datEmissao;numAno;numMes\n"
           "555;1;10;7;Fulano;100,0;2026-01-05;2026;1\n"
           "555;2;10;7;Fulano;200,0;2026-02-05;2026;2\n")
    monkeypatch.setattr(camara, "_csv_da_cota", lambda ano: _quadro(csv))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    armazem.remover("despesa_parlamentar")
    assert camara.coletar_despesas(2026) == 2

    gravado = armazem.ler("despesa_parlamentar")
    assert len(gravado) == 2, "as duas parcelas têm que sobreviver"
    assert gravado["sk"].is_unique


def test_mesma_nota_recoletada_continua_sendo_uma(monkeypatch):
    csv = ("ideDocumento;numParcela;numRessarcimento;numDeputadoId;"
           "txNomeParlamentar;vlrLiquido;datEmissao;numAno;numMes\n"
           "777;0;0;7;Fulano;50,0;2026-03-05;2026;3\n")
    monkeypatch.setattr(camara, "_csv_da_cota", lambda ano: _quadro(csv))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    armazem.remover("despesa_parlamentar")
    camara.coletar_despesas(2026)
    camara.coletar_despesas(2026)
    assert len(armazem.ler("despesa_parlamentar")) == 1


# ============================== 3. SIDRA: variável inexistente
def test_variavel_invalida_falha_antes_de_pedir_dado(monkeypatch):
    """O SIDRA responde 500 a variável inexistente, e o cliente repetia 4x
    em 3 níveis — 36 requisições para descobrir um erro de configuração."""
    pedidos: list[str] = []

    def falso(fonte, url, parametros=None, **k):
        pedidos.append(url)
        if url.endswith("/metadados"):
            return {"variaveis": [{"id": 37, "nome": "PIB a preços correntes"}]}
        raise AssertionError("não devia ter chegado a pedir a série")

    monkeypatch.setattr(ibge.rede, "buscar", falso)
    monkeypatch.setitem(ibge.AGREGADOS, "inventada",
                        {"agregado": "5938", "variavel": "593",
                         "rotulo": "x", "unidade": "y"})

    with pytest.raises(ValueError, match="não existe no agregado"):
        ibge.coletar_indicador("inventada", "last 6", "N1")

    assert sum(1 for u in pedidos if u.endswith("/metadados")) == 1


def test_metadados_indisponiveis_nao_impedem_a_coleta(monkeypatch):
    """Validação é uma ajuda, não um novo ponto de falha."""
    def falso(fonte, url, parametros=None, **k):
        if url.endswith("/metadados"):
            raise RuntimeError("fora do ar")
        return []

    monkeypatch.setattr(ibge.rede, "buscar", falso)
    monkeypatch.setattr(ibge.armazem, "mesclar", lambda *a, **k: None)
    monkeypatch.setattr(ibge.controle, "gravar_marca", lambda *a, **k: None)
    assert ibge.coletar_indicador("populacao", "last 6", "N1") == 0


def test_pib_per_capita_e_derivado_de_pib_e_populacao():
    armazem.remover("indicador_ente")
    armazem.mesclar("indicador_ente", [
        {"cod_ibge": "35", "cod_metrica": "pib", "ano": 2023,
         "valor": 2_000_000.0, "unidade": "R$ mil", "nivel_territorial": "N3",
         "data_referencia": "2023-12-31"},
        {"cod_ibge": "35", "cod_metrica": "populacao", "ano": 2023,
         "valor": 40_000.0, "unidade": "pessoas", "nivel_territorial": "N3",
         "data_referencia": "2023-12-31"},
    ], "teste")

    assert ibge.derivar_pib_per_capita() == 1
    derivado = armazem.ler("indicador_ente",
                           filtro="cod_metrica = 'pib_per_capita'")
    assert float(derivado.iloc[0]["valor"]) == 2_000_000.0 * 1000 / 40_000
    assert derivado.iloc[0]["_fonte"] == "derivado"


def test_ente_sem_populacao_nao_vira_divisao_por_zero():
    armazem.remover("indicador_ente")
    armazem.mesclar("indicador_ente", [
        {"cod_ibge": "99", "cod_metrica": "pib", "ano": 2023, "valor": 100.0,
         "unidade": "R$ mil", "nivel_territorial": "N3",
         "data_referencia": "2023-12-31"},
        {"cod_ibge": "99", "cod_metrica": "populacao", "ano": 2023,
         "valor": 0.0, "unidade": "pessoas", "nivel_territorial": "N3",
         "data_referencia": "2023-12-31"},
    ], "teste")
    assert ibge.derivar_pib_per_capita() == 0


# ============================== 4. exercício não publicado
def test_varredura_desiste_quando_o_ano_nao_foi_publicado(monkeypatch):
    """14 minutos e 5.571 requisições para descobrir que 2026 não existe."""
    consultados: list[str] = []

    def vazio(ano, cod):
        consultados.append(cod)
        return []

    monkeypatch.setattr(siconfi, "coletar_dca", vazio)
    entes = [str(1000 + i) for i in range(600)]

    total = siconfi.varrer(2026, entes, trabalhadores=4, intervalo=0,
                           lote=50, amostra_inicial=100)

    assert total.get("abandonado") == 1
    assert len(consultados) < 300, \
        f"consultou {len(consultados)} de 600 — devia ter desistido cedo"


def test_desistencia_nao_bloqueia_a_proxima_tentativa(monkeypatch):
    """As marcas de 'vazio' de um ano não publicado precisam sumir."""
    monkeypatch.setattr(siconfi, "coletar_dca", lambda ano, cod: [])
    entes = [str(2000 + i) for i in range(400)]
    siconfi.varrer(2026, entes, trabalhadores=4, intervalo=0, lote=50,
                   amostra_inicial=100)

    pendentes = controle.entes_pendentes("siconfi", "dca", 2026, entes)
    assert len(pendentes) == len(entes), \
        "todos devem voltar a ser pendentes quando o dado sair"


def test_varredura_com_dado_nao_desiste(monkeypatch):
    def com_dado(ano, cod):
        return [{
            "cod_ibge": cod, "ano": ano, "periodo": "anual", "cod_conta": "10",
            "cod_funcao": "10", "funcao": "Saúde", "rotulo_conta": "Saúde",
            "estagio": "Despesas Empenhadas", "valor": 1.0,
            "esfera": "municipio", "uf": "SP",
            "data_referencia": f"{ano}-12-31"}]

    monkeypatch.setattr(siconfi, "coletar_dca", com_dado)
    entes = [str(3000 + i) for i in range(300)]
    total = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0,
                           lote=50, amostra_inicial=100)
    assert "abandonado" not in total
    assert total["entes"] == 300


def test_lista_pequena_nao_desiste(monkeypatch):
    """27 UFs sem dado não são amostra suficiente para concluir nada."""
    monkeypatch.setattr(siconfi, "coletar_dca", lambda ano, cod: [])
    entes = [str(4000 + i) for i in range(27)]
    total = siconfi.varrer(2024, entes, trabalhadores=4, intervalo=0,
                           lote=50, amostra_inicial=200)
    assert "abandonado" not in total
    assert total["entes"] == 27


# ============================== 5. eleição não apurada
def test_eleicao_sem_apuracao_avisa_em_vez_de_ficar_muda(monkeypatch, caplog):
    candidaturas = pd.DataFrame([{
        "DS_SIT_TOT_TURNO": "NÃO ELEITO", "CD_CARGO": "11",
        "SQ_CANDIDATO": "1", "NM_CANDIDATO": "Fulano", "SG_UE": "71072",
        "NM_UE": "SAO PAULO", "SG_UF": "SP",
    }])
    monkeypatch.setattr(tse, "_baixar_consulta_cand", lambda ano: candidaturas)
    monkeypatch.setattr(tse.controle, "gravar_marca", lambda *a, **k: None)

    with caplog.at_level("WARNING"):
        assert tse.coletar_eleitos(2026) == 0
    assert "ainda não saiu" in caplog.text


# ============================== 6. situação da proposição vinha vazia
def test_situacao_vem_do_nome_de_coluna_do_lote(monkeypatch):
    """A coluna Situação do painel ficou inteira em '—' sem erro nenhum.

    A API v2 chama o campo de `descricaoSituacao`; o arquivo em lote chama de
    `ultimoStatus_descricaoSituacao`. Ler só o nome da API devolvia None em
    100% das linhas — falha silenciosa, a pior espécie.
    """
    csv = ("id;siglaTipo;numero;ano;ementa;dataApresentacao;"
           "ultimoStatus_descricaoSituacao;ultimoStatus_siglaOrgao;"
           "ultimoStatus_descricaoTramitacao;ultimoStatus_despacho\n"
           "1;PL;10;2026;Uma ementa;2026-02-01;Aguardando Parecer;CCJC;"
           "Recebimento;Despacho X\n")

    monkeypatch.setattr(camara, "_csv", lambda url, **k:
                        pd.DataFrame() if "Autores" in url else _quadro(csv))
    gravadas: list[dict] = []
    monkeypatch.setattr(camara.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.extend(linhas))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    camara.coletar_proposicoes(2026)
    assert gravadas[0]["situacao"] == "Aguardando Parecer"
    assert gravadas[0]["orgao_atual"] == "CCJC"
    assert gravadas[0]["tramitacao_atual"] == "Recebimento"
    assert gravadas[0]["ultimo_status"] == "Despacho X"


def test_nome_antigo_da_api_continua_funcionando(monkeypatch):
    """`primeiro()` aceita os dois nomes — a API v2 não deixou de existir."""
    csv = ("id;siglaTipo;numero;ano;ementa;dataApresentacao;descricaoSituacao\n"
           "1;PL;10;2026;Uma ementa;2026-02-01;Pronta para Pauta\n")
    monkeypatch.setattr(camara, "_csv", lambda url, **k:
                        pd.DataFrame() if "Autores" in url else _quadro(csv))
    gravadas: list[dict] = []
    monkeypatch.setattr(camara.armazem, "mesclar",
                        lambda t, linhas, f: gravadas.extend(linhas))
    monkeypatch.setattr(camara.controle, "gravar_marca", lambda *a, **k: None)

    camara.coletar_proposicoes(2026)
    assert gravadas[0]["situacao"] == "Pronta para Pauta"


def test_primeiro_devolve_none_quando_nenhuma_coluna_existe():
    _, linha = next(_quadro("id\n1\n").iterrows())
    assert camara.primeiro(linha, "nao_existe", "tambem_nao") is None


def test_primeiro_pula_coluna_vazia():
    _, linha = next(_quadro("a;b\n;valor\n").iterrows())
    assert camara.primeiro(linha, "a", "b") == "valor"
