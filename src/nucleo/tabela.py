"""Ler tabela de qualquer coisa que a fonte devolva — e explicar quando falha.

Três coletores liam CSV e cada um do seu jeito: o TSE com `;` e latin-1, a
Câmara com `;` e UTF-8, o Tesouro com quatro combinações e uma mensagem que
não dizia nada. Quando o arquivo do Tesouro mudou de forma, tudo que apareceu
no log foi:

    não consegui ler ... como tabela

Isso mandou a investigação para o lado errado por duas rodadas. **A mensagem
de falha é parte da função**: um leitor que não sabe dizer por que não leu
transfere para uma pessoa o trabalho que o código já tinha condição de fazer.

O que este módulo faz de diferente:

- reconhece **ZIP** e lê os CSVs de dentro, inclusive vários de uma vez —
  é o formato do TSE e o plano B da cota parlamentar;
- reconhece **HTML** (página de erro servida com status 200, o disfarce mais
  comum de indisponibilidade) e diz isso em vez de tentar parsear;
- reconhece **XLSX** e **JSON**;
- tenta as combinações de separador e codificação em ordem de probabilidade
  para fonte brasileira, e **para na primeira que produz mais de uma coluna**
  — uma coluna só quase sempre significa separador errado, não tabela de uma
  coluna;
- quando nada funciona, levanta erro com o **tamanho**, os **primeiros bytes**
  e o que foi tentado.

Nunca devolve DataFrame vazio disfarçando erro: ou leu, ou explica.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from .registro import obter as obter_log

log = obter_log("nucleo.tabela")

# Ordem de tentativa. Duas regras a sustentam:
#
# 1. **Ponto e vírgula antes de vírgula.** É o separador de quem usa vírgula
#    decimal, que é o caso de quase todo CSV de órgão público brasileiro.
#
# 2. **UTF-8 antes de latin-1, sempre.** `latin-1` mapeia qualquer byte e por
#    isso NUNCA levanta erro: posto primeiro, ele "consegue ler" um arquivo
#    UTF-8 e devolve `SÃ£o Paulo` no lugar de `São Paulo` — sem falha, sem
#    aviso, com a tabela inteira parecendo correta. Já o UTF-8 recusa byte
#    inválido, então ele se valida sozinho e latin-1 fica como último recurso,
#    que é o papel certo para uma codificação que aceita tudo.
TENTATIVAS = (
    (";", "utf-8-sig"), (";", "utf-8"),
    (",", "utf-8-sig"), (",", "utf-8"),
    (";", "latin-1"), (",", "latin-1"),
    ("\t", "utf-8"), ("|", "latin-1"),
)

_LEITURA = dict(dtype=str, keep_default_na=False, na_values=[""],
                low_memory=False)


def sem_nan(df: pd.DataFrame) -> pd.DataFrame:
    """Troca NaN por None no DataFrame inteiro.

    Não substitui a proteção no ponto de uso (`nucleo.valores`): `iterrows()`
    reconstrói cada linha como Series tipada e o pandas devolve o NaN. Isto
    aqui é conveniência para quem lê por `.iloc`; a garantia está lá.
    Ver armadilha 2b.
    """
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)


def _descrever(conteudo: bytes) -> str:
    """O que o começo do arquivo revela. É isto que faltava no log."""
    inicio = conteudo[:200]
    if inicio[:2] == b"PK":
        return "parece um ZIP (ou XLSX), não um CSV"
    if inicio.lstrip()[:1] == b"<":
        return f"parece HTML — página de erro servida como sucesso? {inicio[:120]!r}"
    if inicio.lstrip()[:1] in (b"{", b"["):
        return "parece JSON, não CSV"
    return repr(inicio)


def _de_csv(dados: bytes | io.IOBase, origem: str) -> pd.DataFrame:
    conteudo = dados if isinstance(dados, bytes) else dados.read()
    motivos = []

    for sep, enc in TENTATIVAS:
        try:
            df = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=enc,
                             on_bad_lines="skip", **_LEITURA)
        except Exception as erro:  # noqa: BLE001
            # A mensagem, não só o tipo: `ParserError` sozinho não diz se o
            # separador está errado ou se o arquivo veio cortado.
            motivos.append(f"{sep!r}/{enc}: {type(erro).__name__} "
                           f"({str(erro).splitlines()[0][:120]})")
            continue

        if len(df.columns) > 1:
            if (sep, enc) != TENTATIVAS[0]:
                log.info("%s: lido com separador %r e codificação %s",
                         origem, sep, enc)
            return sem_nan(df)
        motivos.append(f"{sep!r}/{enc}: {len(df.columns)} coluna")

    # "EOF inside string" é assinatura de ARQUIVO CORTADO, não de CSV
    # malformado: o leitor abriu aspas e o arquivo acabou antes de fechar. Foi
    # o que aconteceu com `eventosPresencaDeputados-2026.csv`, e a mensagem
    # antiga mandava investigar o separador — o problema estava no download.
    truncado = any("EOF inside string" in m for m in motivos)
    pista = (" O arquivo parece CORTADO no meio: o leitor chegou ao fim dentro "
             "de um campo entre aspas. Quase sempre é download incompleto, "
             "não CSV malformado — vale recoletar." if truncado else "")

    raise RuntimeError(
        f"não consegui ler {origem} como tabela. {len(conteudo)} bytes; "
        f"começo: {_descrever(conteudo)}.{pista} "
        f"Tentativas: {'; '.join(motivos[:4])}")


def ler(dados: bytes, origem: str = "conteúdo",
        formato: str | None = None) -> pd.DataFrame:
    """Devolve um DataFrame de texto a partir dos bytes que a fonte mandou.

    `formato` força o tipo quando se conhece de antemão ("CSV", "XLSX",
    "JSON"); sem ele, o tipo sai dos primeiros bytes. Um ZIP com vários CSVs
    vira um DataFrame só, concatenado — é assim que o TSE publica, um arquivo
    por UF.
    """
    if not dados:
        raise RuntimeError(f"{origem}: resposta vazia, 0 byte")

    tipo = (formato or "").upper()

    if tipo == "JSON" or (not tipo and dados.lstrip()[:1] in (b"{", b"[")):
        return sem_nan(pd.read_json(io.BytesIO(dados), dtype=str))

    if dados[:2] == b"PK":
        if tipo == "XLSX":
            return sem_nan(pd.read_excel(io.BytesIO(dados), dtype=str))
        return _de_zip(dados, origem)

    if tipo == "XLSX":
        return sem_nan(pd.read_excel(io.BytesIO(dados), dtype=str))

    return _de_csv(dados, origem)


def _de_zip(dados: bytes, origem: str, ignorar: tuple[str, ...] = ()) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv")]
        for palavra in ignorar:
            nomes = [n for n in nomes if palavra.upper() not in n.upper()]

        if not nomes:
            # Um ZIP de XLSX cai aqui: é ZIP por dentro, planilha por fora.
            try:
                return sem_nan(pd.read_excel(io.BytesIO(dados), dtype=str))
            except Exception:  # noqa: BLE001
                dentro = z.namelist()[:8]
                raise RuntimeError(
                    f"{origem}: ZIP sem CSV dentro. Contém: {dentro}") from None

        quadros = [_de_csv(z.read(nome), f"{origem}::{nome}") for nome in nomes]

    return pd.concat(quadros, ignore_index=True) if quadros else pd.DataFrame()


def de_zip(dados: bytes, origem: str = "zip",
           ignorar: tuple[str, ...] = ()) -> pd.DataFrame:
    """Todos os CSVs de dentro de um ZIP, num DataFrame só.

    `ignorar` descarta arquivos cujo nome contenha a palavra — o TSE publica
    um `BRASIL.csv` que repete o conteúdo das 27 UFs, e somá-lo dobraria tudo.
    """
    return _de_zip(dados, origem, ignorar)


def colunas_faltando(df: pd.DataFrame, obrigatorias: tuple[str, ...],
                     origem: str) -> list[str]:
    """Quais colunas esperadas não vieram — para o coletor avisar em vez de
    gravar campo vazio. É a armadilha 2d posta em função."""
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        log.error("%s: faltam as colunas %s. O arquivo tem: %s",
                  origem, faltando, list(df.columns)[:20])
    return faltando
