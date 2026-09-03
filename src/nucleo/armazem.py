"""Armazém Parquet + DuckDB.

Parquet não faz UPDATE: atualizar significa reescrever a partição inteira.
Por isso a partição é a unidade de transação deste projeto, e o `mesclar()`
abaixo é o coração do pipeline.

Estratégia de MERGE por partição:
  1. lê APENAS as partições tocadas pelo lote novo (partition pruning);
  2. mantém a linha antiga se o `_hash_registro` não mudou (preservando
     `_criado_em` e `_atualizado_em`);
  3. atualiza `_atualizado_em` só quando o conteúdo mudou de verdade;
  4. escreve num arquivo temporário e faz rename atômico por cima.

Se o processo morrer no meio, a partição continua íntegra — nada de meio
arquivo corrompido, e nada que dependa de alguém lembrar de conferir se o
job terminou.
"""

from __future__ import annotations

import os
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import duckdb
import pandas as pd

from . import config
from .chaves import hash_registro, sk
from .esquema import COLUNAS_CONTROLE, Tabela, obter
from .registro import obter as obter_log

log = obter_log("nucleo.armazem")

_ARQUIVO_PARTICAO = "part-000.parquet"

# Quantas linhas cada tabela perdeu por colisão de chave, no processo inteiro.
#
# O aviso por lote já existia e estava certo — dizia "a chave está descrevendo
# um grão mais grosso que o dado". Só que ele saiu 239 vezes no meio de 1.476
# linhas de log, e ninguém o viu. Um diagnóstico correto que só aparece onde
# ninguém olha é um diagnóstico que não existe.
#
# Este contador é lido no RESUMO da carga, que é o que alguém lê de manhã.
COLAPSOS: dict[str, int] = {}

# Quantas linhas cada tabela RECEBEU e quantas de fato GRAVOU, no processo
# inteiro. É o par que o portão de qualidade compara: a suíte de testes olha
# a forma do dado, e forma não distingue "gravou 842 mil" de "gravou zero".
#
# Fica aqui, e não no portão, porque só o merge conhece os dois números sem
# reler o disco: `recebidas` antes da deduplicação, `gravadas` depois do
# rename atômico.
MEDIDAS: dict[str, dict[str, int]] = {}


def _medir(tabela: str, chave: str, quantas: int = 1) -> None:
    linha = MEDIDAS.setdefault(tabela, {"tentativas": 0, "recebidas": 0,
                                        "gravadas": 0, "colapsadas": 0,
                                        "particao_nula": 0})
    linha[chave] = linha.get(chave, 0) + quantas


# ------------------------------------------------------------------ conexão
def conectar(somente_leitura: bool = False) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:", read_only=False)
    con.execute("SET TimeZone='UTC'")
    con.execute("SET preserve_insertion_order=false")
    try:
        con.execute("SET max_memory='4GB'")
    except Exception:
        pass
    if somente_leitura:
        con.execute("SET threads TO 4")
    return con


def agora() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ caminhos
def caminho_base(tabela: Tabela) -> Path:
    if tabela.camada == "dim":
        return config.DIM
    if tabela.camada == "_ctl":
        return config.CTL
    return config.FATO / tabela.nome


def caminho_particao(tabela: Tabela, valores: Mapping[str, Any]) -> Path:
    if tabela.camada != "fato":
        return caminho_base(tabela) / f"{tabela.nome}.parquet"
    destino = caminho_base(tabela)
    for coluna in tabela.particoes:
        destino = destino / f"{coluna}={valores[coluna]}"
    return destino / _ARQUIVO_PARTICAO


def padrao_leitura(tabela: Tabela) -> str:
    if tabela.camada != "fato":
        return str(caminho_base(tabela) / f"{tabela.nome}.parquet")
    return str(caminho_base(tabela) / "**" / "*.parquet")


# ------------------------------------------------------------------ preparo
# Do tipo declarado em esquema.py para o dtype do pandas que o pyarrow
# escreve com o tipo certo MESMO quando a coluna inteira é nula.
_DTYPES = {
    "VARCHAR": "string",
    "INTEGER": "Int64",
    "DOUBLE": "float64",
    "BOOLEAN": "boolean",
}


def tipar(tabela: Tabela, df: pd.DataFrame) -> pd.DataFrame:
    """Força o tipo declarado antes de gravar.

    Sem isto, uma coluna cujos valores são TODOS nulos numa partição vira
    `int32` no Parquet — o pandas não tem como adivinhar que era texto. Aí,
    quando outra partição traz a mesma coluna preenchida como VARCHAR, o
    DuckDB lê as duas juntas e estoura:

        Could not convert string 'Aguardando Providências Internas' to INT32

    Foi exatamente o que aconteceu com `situacao`: coletada nula durante
    semanas (por causa do nome de coluna errado), virou int32 na partição de
    2024 e brigou com a de 2026 assim que passou a vir preenchida.

    O tipo está declarado no esquema. Usar a declaração na ESCRITA é o que
    torna as partições compatíveis entre si por construção.
    """
    if df.empty or not tabela.colunas:
        return df

    for nome, tipo in tabela.colunas:
        dtype = _DTYPES.get(tipo)
        if not dtype or nome not in df.columns:
            continue
        try:
            df[nome] = df[nome].astype(dtype)
        except (TypeError, ValueError):
            # Valor que não cabe no tipo declarado: melhor gravar como veio
            # do que perder a linha. O contrato da view ainda o expõe.
            log.warning("%s.%s: não coube em %s; gravando como veio",
                        tabela.nome, nome, tipo)
    return df


def preparar(
    tabela: Tabela,
    registros: Iterable[Mapping[str, Any]] | pd.DataFrame,
    fonte: str,
) -> pd.DataFrame:
    """Aplica a convenção do projeto: sk na frente, controle no fim."""
    df = registros if isinstance(registros, pd.DataFrame) else pd.DataFrame(list(registros))
    _medir(tabela.nome, "recebidas", len(df))
    if df.empty:
        return df

    df = df.copy()
    for coluna in COLUNAS_CONTROLE + ["sk"]:
        if coluna in df.columns:
            df.drop(columns=[coluna], inplace=True)

    campos_negocio = list(tabela.campos_negocio) or [
        c for c in df.columns if not c.startswith("_")
    ]
    faltando = [c for c in tabela.campos_pk if c not in df.columns]
    if faltando:
        raise KeyError(f"{tabela.nome}: campos da PK ausentes {faltando}")

    linhas = df.to_dict("records")
    df.insert(0, "sk", [sk(l, tabela.campos_pk) for l in linhas])
    df["_hash_registro"] = [hash_registro(l, campos_negocio) for l in linhas]
    df["_fonte"] = fonte
    df["_criado_em"] = pd.NaT
    df["_atualizado_em"] = pd.NaT

    duplicadas = int(df["sk"].duplicated().sum())
    if duplicadas:
        COLAPSOS[tabela.nome] = COLAPSOS.get(tabela.nome, 0) + duplicadas
        _medir(tabela.nome, "colapsadas", duplicadas)
        log.warning("%s: %d linhas duplicadas no lote pela chave (%s) — "
                    "mantendo a última. Se não deveriam ser duplicatas, a "
                    "chave está descrevendo um grão mais grosso que o dado.",
                    tabela.nome, duplicadas, " + ".join(tabela.campos_pk))
        df = df.drop_duplicates(subset="sk", keep="last")

    return tipar(tabela, df)


def _sem_particao_nula(tabela: Tabela, df: pd.DataFrame) -> pd.DataFrame:
    """Separa as linhas cujo valor de partição é nulo, antes de tocar no disco.

    Sem isto, um valor nulo vira o texto `<NA>` e o caminho da partição fica
    `ano=<NA>`. No Linux isso cria uma pasta com nome ruim; no **Windows**
    `<` e `>` são caracteres proibidos e o erro que chega é:

        [WinError 123] A sintaxe do nome do arquivo ... está incorreta

    que não menciona tabela, coluna nem partição — foi o que derrubou o
    coletor do SADIPEM inteiro quando a data de protocolo deixou de ser
    reconhecida.

    A linha nula é DESCARTADA com erro registrado, não gravada num balde
    genérico: partição é o eixo de leitura do painel, e dado que cai fora de
    todo recorte de tempo é dado que ninguém vai encontrar de novo.
    """
    mascara = pd.Series(False, index=df.index)
    for coluna in tabela.particoes:
        mascara |= df[coluna].isna()

    nulas = int(mascara.sum())
    if not nulas:
        return df

    _medir(tabela.nome, "particao_nula", nulas)
    colunas_afetadas = [c for c in tabela.particoes if df[c].isna().any()]
    exemplo = df.loc[mascara].head(1).to_dict("records")
    log.error(
        "%s: %d de %d linha(s) com valor de partição nulo em %s — "
        "DESCARTADAS. Partição nula não tem onde ser gravada, e a linha "
        "sumiria de todo filtro por período. Exemplo: %s",
        tabela.nome, nulas, len(df), ", ".join(colunas_afetadas),
        {k: v for k, v in exemplo[0].items()
         if k in (*tabela.campos_pk, *tabela.particoes)} if exemplo else {})
    return df.loc[~mascara]


def _renomear(temporario: Path, destino: Path) -> None:
    """`os.replace` com repetição — atômico, mas não imune a trava de arquivo.

    No Windows o rename falha com `[WinError 5] Acesso negado` quando alguém
    tem o arquivo de destino aberto. Três suspeitos, nesta ordem: a pasta
    `dados/` dentro do OneDrive (que sincroniza arquivo a arquivo), o
    antivírus varrendo o Parquet recém-escrito, e o próprio painel — o DuckDB
    da API mantém os Parquet abertos enquanto alguém navega.

    Quase sempre é trava passageira, então tentar de novo resolve. Se não
    resolver, a mensagem precisa dizer o que fazer.
    """
    for tentativa in range(5):
        try:
            os.replace(temporario, destino)
            return
        except PermissionError:
            if tentativa == 4:
                raise PermissionError(
                    f"não consegui substituir {destino.name}: o arquivo está "
                    f"travado por outro programa. Verifique, nesta ordem: a "
                    f"pasta dados/ está dentro do OneDrive ou Dropbox? o "
                    f"painel está aberto lendo esta tabela? o antivírus está "
                    f"varrendo a pasta? Para mover o acervo para fora da "
                    f"nuvem, defina PAINEL_DADOS no .env."
                ) from None
            time.sleep(0.3 * (tentativa + 1))


# ------------------------------------------------------------------ merge
def _mesclar_particao(
    con: duckdb.DuckDBPyConnection,
    tabela: Tabela,
    novo: pd.DataFrame,
    destino: Path,
) -> dict[str, int]:
    destino.parent.mkdir(parents=True, exist_ok=True)
    momento = agora()

    con.register("novo", novo)
    colunas = [c for c in novo.columns if c not in COLUNAS_CONTROLE]

    if destino.exists():
        con.execute(
            f"CREATE OR REPLACE TEMP VIEW atual AS "
            f"SELECT * FROM read_parquet('{destino.as_posix()}')"
        )
        lista = ", ".join(f"n.{c}" for c in colunas)
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE final AS
            SELECT * FROM atual a
             WHERE NOT EXISTS (SELECT 1 FROM novo n WHERE n.sk = a.sk)
            UNION ALL BY NAME
            SELECT {lista},
                   n._hash_registro,
                   n._fonte,
                   COALESCE(a._criado_em, TIMESTAMPTZ '{momento}')      AS _criado_em,
                   CASE WHEN a.sk IS NULL
                          OR a._hash_registro IS DISTINCT FROM n._hash_registro
                        THEN TIMESTAMPTZ '{momento}'
                        ELSE a._atualizado_em END                        AS _atualizado_em
              FROM novo n
              LEFT JOIN atual a USING (sk)
        """)
        estat = con.execute("""
            SELECT
              COUNT(*) FILTER (WHERE a.sk IS NULL)                       AS inseridos,
              COUNT(*) FILTER (WHERE a.sk IS NOT NULL
                               AND a._hash_registro IS DISTINCT FROM n._hash_registro)
                                                                          AS alterados,
              COUNT(*) FILTER (WHERE a._hash_registro = n._hash_registro) AS inalterados
            FROM novo n LEFT JOIN atual a USING (sk)
        """).fetchone()
    else:
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE final AS
            SELECT * REPLACE (
                     TIMESTAMPTZ '{momento}' AS _criado_em,
                     TIMESTAMPTZ '{momento}' AS _atualizado_em)
              FROM novo
        """)
        estat = (len(novo), 0, 0)

    temporario = destino.with_suffix(".parquet.tmp")
    con.execute(f"""
        COPY (SELECT * FROM final ORDER BY sk)
          TO '{temporario.as_posix()}'
          (FORMAT PARQUET, COMPRESSION {config.COMPRESSAO},
           COMPRESSION_LEVEL {config.NIVEL_COMPRESSAO},
           ROW_GROUP_SIZE {config.TAMANHO_ROW_GROUP})
    """)
    _renomear(temporario, destino)  # atômico no mesmo volume

    con.execute("DROP TABLE IF EXISTS final")
    con.unregister("novo")
    return {"inseridos": estat[0], "alterados": estat[1], "inalterados": estat[2]}


def mesclar(
    nome_tabela: str,
    registros: Iterable[Mapping[str, Any]] | pd.DataFrame,
    fonte: str,
    con: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, int]:
    """Grava um lote na tabela, sem duplicar e sem perder histórico."""
    tabela = obter(nome_tabela)
    _medir(nome_tabela, "tentativas")
    df = preparar(tabela, registros, fonte)
    if df.empty:
        log.info("%s: lote vazio, nada a fazer", nome_tabela)
        return {"inseridos": 0, "alterados": 0, "inalterados": 0}

    proprio = con is None
    con = con or conectar()
    total = {"inseridos": 0, "alterados": 0, "inalterados": 0}
    try:
        if not tabela.particoes:
            destino = caminho_particao(tabela, {})
            total = _mesclar_particao(con, tabela, df, destino)
        else:
            faltando = [c for c in tabela.particoes if c not in df.columns]
            if faltando:
                raise KeyError(f"{nome_tabela}: colunas de partição ausentes {faltando}")
            df = _sem_particao_nula(tabela, df)
            if df.empty:
                return total
            for chave, grupo in df.groupby(list(tabela.particoes), dropna=False):
                chave = chave if isinstance(chave, tuple) else (chave,)
                valores = dict(zip(tabela.particoes, chave))
                destino = caminho_particao(tabela, valores)
                parcial = _mesclar_particao(con, tabela, grupo, destino)
                for k in total:
                    total[k] += parcial[k]
    finally:
        if proprio:
            con.close()

    _medir(nome_tabela, "gravadas", sum(total.values()))
    log.info("%s <- %s: %d novos, %d alterados, %d inalterados",
             nome_tabela, fonte, total["inseridos"], total["alterados"],
             total["inalterados"])
    return total


# ------------------------------------------------------------------ leitura
def ler(
    nome_tabela: str,
    filtro: str | None = None,
    colunas: Sequence[str] | str = "*",
    con: duckdb.DuckDBPyConnection | None = None,
) -> pd.DataFrame:
    tabela = obter(nome_tabela)
    padrao = padrao_leitura(tabela)
    if tabela.camada == "fato" and not any(caminho_base(tabela).rglob("*.parquet")):
        return pd.DataFrame()
    if tabela.camada != "fato" and not Path(padrao).exists():
        return pd.DataFrame()

    proprio = con is None
    con = con or conectar()
    try:
        campos = colunas if isinstance(colunas, str) else ", ".join(colunas)
        hive = (", hive_partitioning=1, union_by_name=1"
                if tabela.camada == "fato" else "")
        sql = f"SELECT {campos} FROM read_parquet('{padrao}'{hive})"
        if filtro:
            sql += f" WHERE {filtro}"
        return con.execute(sql).df()
    finally:
        if proprio:
            con.close()


def reescrever(nome_tabela: str, df: pd.DataFrame) -> int:
    """Substitui o conteúdo de uma tabela sem partição pelo DataFrame dado.

    Usada para APAGAR linhas de controle — o merge só insere e atualiza, e há
    um caso em que remover é o certo: quando a varredura descobre que o ano
    inteiro não foi publicado, as 5.571 marcas de "vazio" que ela gravou
    impediriam uma nova tentativa quando o dado saísse.
    """
    tabela = obter(nome_tabela)
    if tabela.particoes:
        raise ValueError(f"{nome_tabela} é particionada — apague a partição")

    destino = caminho_particao(tabela, {})
    if df.empty:
        destino.unlink(missing_ok=True)
        return 0

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".parquet.tmp")
    con = conectar()
    try:
        con.register("conteudo", df)
        con.execute(f"""
            COPY (SELECT * FROM conteudo)
              TO '{temporario.as_posix()}'
              (FORMAT PARQUET, COMPRESSION {config.COMPRESSAO},
               COMPRESSION_LEVEL {config.NIVEL_COMPRESSAO})
        """)
        _renomear(temporario, destino)
    finally:
        con.close()
    return len(df)


def remover(nome_tabela: str) -> None:
    """Apaga fisicamente uma tabela. Usado só por testes e reprocessamento."""
    tabela = obter(nome_tabela)
    if tabela.camada == "fato":
        shutil.rmtree(caminho_base(tabela), ignore_errors=True)
    else:
        caminho_particao(tabela, {}).unlink(missing_ok=True)


def remover_particao(nome_tabela: str, valores_particao: Mapping[str, Any]) -> bool:
    """Apaga uma partição específica de uma tabela fato (ex: ano=2025)."""
    tabela = obter(nome_tabela)
    if tabela.camada != "fato":
        caminho_particao(tabela, {}).unlink(missing_ok=True)
        return True
    
    destino = caminho_base(tabela)
    for coluna in tabela.particoes:
        if coluna in valores_particao:
            destino = destino / f"{coluna}={valores_particao[coluna]}"
    
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
        return True
    return False

