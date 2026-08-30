"""O leitor de tabela — e, principalmente, o que ele diz quando falha.

Três coletores liam CSV cada um do seu jeito. Quando o arquivo do Tesouro
mudou de forma, a única pista no log foi "não consegui ler como tabela", e a
investigação foi para o lado errado por duas rodadas.

A mensagem de falha é parte da função. Metade destes testes verifica o
conteúdo do erro, não o caminho feliz.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src.nucleo import tabela  # noqa: E402


# ------------------------------------------------------------ caminho feliz
def test_le_csv_brasileiro_com_ponto_e_virgula_e_latin1():
    """O padrão de órgão público brasileiro: `;` porque a vírgula é decimal."""
    dados = "nome;valor\nSão Paulo;1.234,56\n".encode("latin-1")
    df = tabela.ler(dados, "teste")
    assert list(df.columns) == ["nome", "valor"]
    assert df.iloc[0]["nome"] == "São Paulo"


def test_le_csv_com_virgula_e_utf8():
    dados = "nome,valor\nBahia,10\n".encode()
    df = tabela.ler(dados, "teste")
    assert list(df.columns) == ["nome", "valor"]
    assert len(df) == 1


def test_le_csv_com_bom_do_excel():
    """UTF-8 com BOM é o que o Excel grava, e sem `utf-8-sig` a primeira
    coluna vem com lixo grudado no nome."""
    dados = "﻿nome;valor\nA;1\n".encode("utf-8-sig")
    df = tabela.ler(dados, "teste")
    assert list(df.columns) == ["nome", "valor"], df.columns


def test_uma_coluna_so_e_tratada_como_separador_errado():
    """Um `;` lido com separador `,` produz UMA coluna com tudo dentro. Isso
    quase nunca é uma tabela de uma coluna — é o separador errado."""
    dados = "a;b;c\n1;2;3\n".encode()
    df = tabela.ler(dados, "teste")
    assert len(df.columns) == 3


# ------------------------------------------------------------------- zip
def _zip(arquivos: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo.encode("latin-1"))
    return buffer.getvalue()


def test_zip_com_varios_csvs_vira_um_dataframe_so():
    """O TSE publica um CSV por UF dentro do mesmo ZIP."""
    dados = _zip({"SP.csv": "uf;n\nSP;1\n", "BA.csv": "uf;n\nBA;2\n"})
    df = tabela.de_zip(dados, "tse")
    assert sorted(df["uf"]) == ["BA", "SP"]


def test_zip_pode_ignorar_arquivo_que_repete_o_conteudo():
    """O TSE inclui um BRASIL.csv que repete as 27 UFs. Somá-lo dobraria cada
    candidatura — e o número continuaria plausível."""
    dados = _zip({"SP.csv": "uf;n\nSP;1\n",
                  "BRASIL.csv": "uf;n\nSP;1\n"})
    df = tabela.de_zip(dados, "tse", ignorar=("BRASIL",))
    assert len(df) == 1


def test_zip_e_reconhecido_sem_precisar_avisar():
    dados = _zip({"a.csv": "x;y\n1;2\n"})
    df = tabela.ler(dados, "teste")
    assert list(df.columns) == ["x", "y"]


def test_zip_sem_csv_dentro_diz_o_que_tem():
    dados = _zip({"leiame.txt": "nada aqui"})
    with pytest.raises(RuntimeError) as erro:
        tabela.de_zip(dados, "pacote")
    assert "leiame.txt" in str(erro.value)


# --------------------------------------------------- mensagens de falha
def test_html_disfarcado_de_csv_e_reconhecido():
    """Página de erro servida com status 200 é o disfarce mais comum de
    indisponibilidade. Sem reconhecer, o log diz "não consegui ler" e a
    investigação vai procurar defeito no parser."""
    dados = b"<!doctype html><html><body>Servico indisponivel</body></html>"
    with pytest.raises(RuntimeError) as erro:
        tabela.ler(dados, "https://exemplo/arquivo.csv")
    assert "HTML" in str(erro.value)
    assert "exemplo" in str(erro.value)


def test_erro_diz_o_tamanho_e_o_comeco_do_arquivo():
    dados = b"\x00\x01\x02 lixo binario que nao e tabela nenhuma"
    with pytest.raises(RuntimeError) as erro:
        tabela.ler(dados, "arquivo")
    mensagem = str(erro.value)
    assert str(len(dados)) in mensagem, "o tamanho ajuda a ver se veio truncado"
    assert "lixo" in mensagem, "os primeiros bytes precisam aparecer"


def test_resposta_vazia_nao_vira_tabela_vazia():
    """Zero byte é falha da fonte, não tabela sem linhas. Devolver um
    DataFrame vazio faria a coleta reportar sucesso com nada dentro."""
    with pytest.raises(RuntimeError) as erro:
        tabela.ler(b"", "arquivo")
    assert "vazia" in str(erro.value)


def test_json_e_lido_como_json():
    dados = b'[{"a": "1", "b": "2"}]'
    df = tabela.ler(dados, "teste")
    assert list(df.columns) == ["a", "b"]


# ------------------------------------------------------- colunas ausentes
def test_coluna_faltando_e_registrada_com_a_lista_real(caplog):
    """Gravar campo vazio em silêncio é a armadilha 2d — a Situação das
    proposições ficou uma semana em branco assim."""
    df = pd.DataFrame([{"foo": "1", "bar": "2"}])
    with caplog.at_level("ERROR"):
        faltando = tabela.colunas_faltando(df, ("valor", "orgao"), "arquivo")
    assert faltando == ["valor", "orgao"]
    assert "foo" in caplog.text and "bar" in caplog.text


def test_nada_falta_quando_todas_estao_la():
    df = pd.DataFrame([{"valor": "1", "orgao": "x"}])
    assert tabela.colunas_faltando(df, ("valor",), "arquivo") == []


# --------------------------------------------------------------- NaN
def test_celula_vazia_vira_none_e_nao_nan():
    """NaN é truthy: `(linha.get("x") or "")` devolve o NaN e o `[:10]`
    seguinte estoura. Ver armadilha 2b."""
    dados = "a;b\n1;\n".encode()
    df = tabela.ler(dados, "teste")
    assert df.iloc[0]["b"] is None


def test_utf8_nao_e_lido_como_latin1():
    """`latin-1` mapeia qualquer byte e nunca levanta erro. Posto antes do
    UTF-8, ele "consegue ler" um arquivo UTF-8 e devolve `SÃ£o Paulo` — sem
    falha, sem aviso, com a tabela parecendo correta.

    O acento quebrado atravessaria tudo: viraria nome de município no mapa,
    nome de deputado na votação, e ninguém saberia de onde veio.
    """
    dados = "municipio;uf\nSão Paulo;SP\nBrasília;DF\n".encode("utf-8")
    df = tabela.ler(dados, "teste")
    assert df.iloc[0]["municipio"] == "São Paulo"
    assert df.iloc[1]["municipio"] == "Brasília"


def test_latin1_continua_funcionando_quando_e_mesmo_latin1():
    """O TSE publica em latin-1. UTF-8 recusa esses bytes, e aí latin-1 entra
    — como último recurso, que é o papel certo dele."""
    dados = "municipio;uf\nSão Paulo;SP\n".encode("latin-1")
    df = tabela.ler(dados, "teste")
    assert df.iloc[0]["municipio"] == "São Paulo"
