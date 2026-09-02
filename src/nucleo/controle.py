"""Marca-d'água de ingestão: até onde cada coletor já leu.

Fica em dados/_ctl/ingestao.parquet e responde duas perguntas:
  - de onde retomar a carga incremental (`marca`);
  - quando a fonte foi lida pela última vez (`lido_em`), que é o que o
    rodapé do painel mostra ao usuário.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from . import armazem
from .esquema import ingestao
from .registro import obter as obter_log

log = obter_log("nucleo.controle")


def _arquivo():
    return armazem.caminho_particao(ingestao, {})


def ler_marca(fonte: str, recurso: str) -> str | None:
    df = armazem.ler("ingestao")
    if df.empty:
        return None
    linha = df[(df["fonte"] == fonte) & (df["recurso"] == recurso)]
    if linha.empty:
        return None
    valor = linha.iloc[0]["marca"]
    return None if pd.isna(valor) else str(valor)


def gravar_marca(
    fonte: str,
    recurso: str,
    marca: Any,
    linhas: int = 0,
    situacao: str = "ok",
    detalhe: str = "",
) -> None:
    armazem.mesclar(
        "ingestao",
        [{
            "fonte": fonte,
            "recurso": recurso,
            "marca": None if marca is None else str(marca),
            "linhas": int(linhas),
            "situacao": situacao,
            "detalhe": detalhe[:500],
            "lido_em": datetime.now(timezone.utc),
        }],
        fonte="controle",
    )


# ------------------------------------------------------ coleta ente a ente

def registrar_entes(fonte: str, recurso: str, ano: int,
                    resultados: list[dict]) -> None:
    """Grava o desfecho de um lote de entes.

    `resultados` = [{"cod_ibge": ..., "situacao": "ok|vazio|erro",
                     "linhas": n, "detalhe": ""}, ...]
    """
    if not resultados:
        return
    momento = datetime.now(timezone.utc)
    armazem.mesclar(
        "coleta_ente",
        [{
            "fonte": fonte,
            "recurso": recurso,
            "ano": int(ano),
            "cod_ibge": str(r["cod_ibge"]),
            "situacao": r.get("situacao", "ok"),
            "linhas": int(r.get("linhas", 0)),
            "detalhe": str(r.get("detalhe", ""))[:300],
            "lido_em": momento,
        } for r in resultados],
        fonte="controle",
    )


def entes_pendentes(fonte: str, recurso: str, ano: int,
                    candidatos: list[str],
                    refazer_vazios: bool = False,
                    refazer_tudo: bool = False) -> list[str]:
    """Filtra os entes que ainda precisam ser buscados.

    Por padrão pula os já resolvidos (`ok`) e os que a fonte respondeu sem
    dado (`vazio`), e **repete os que deram erro** — que é justamente o caso
    de queda de rede no meio da varredura.
    """
    if refazer_tudo:
        return list(candidatos)

    df = armazem.ler("coleta_ente")
    if df.empty:
        return list(candidatos)

    feitos = df[(df["fonte"] == fonte) & (df["recurso"] == recurso)
                & (df["ano"].astype(int) == int(ano))]
    if feitos.empty:
        return list(candidatos)

    resolvidos = {"ok"} if refazer_vazios else {"ok", "vazio"}
    pular = set(feitos[feitos["situacao"].isin(resolvidos)]["cod_ibge"].astype(str))
    return [c for c in candidatos if str(c) not in pular]


def esquecer_entes(fonte: str, recurso: str, ano: int) -> int:
    """Apaga as marcas de um ano inteiro.

    Só faz sentido num caso: a varredura descobriu que o exercício não foi
    publicado. Manter as 5.571 marcas de "vazio" faria a próxima execução
    pular tudo silenciosamente quando o dado finalmente saísse.
    """
    df = armazem.ler("coleta_ente")
    if df.empty:
        return 0
    alvo = ((df["fonte"] == fonte) & (df["recurso"] == recurso)
            & (df["ano"].astype(int) == int(ano)))
    apagadas = int(alvo.sum())
    if apagadas:
        armazem.reescrever("coleta_ente", df[~alvo])
        log.info("controle: %d marcas de %s/%s/%d esquecidas",
                 apagadas, fonte, recurso, ano)
    return apagadas


def resumo_entes(fonte: str, recurso: str, ano: int) -> dict[str, int]:
    df = armazem.ler("coleta_ente")
    if df.empty:
        return {}
    feitos = df[(df["fonte"] == fonte) & (df["recurso"] == recurso)
                & (df["ano"].astype(int) == int(ano))]
    if feitos.empty:
        return {}
    return feitos["situacao"].value_counts().to_dict()


def situacao() -> pd.DataFrame:
    df = armazem.ler("ingestao")
    if df.empty:
        return df
    return df.sort_values("lido_em", ascending=False)[
        ["fonte", "recurso", "marca", "linhas", "situacao", "lido_em"]
    ]


def concluido(fonte: str, recurso: str) -> bool:
    """Este recorte já foi coletado com sucesso?

    Serve para carga histórica retomável: numa varredura de horas, o que
    importa não é velocidade — é que interromper (ou a rede cair, ou a
    máquina reiniciar) não custe o que já entrou.

    Só `ok` é terminal. `sem_dado`, `parcial` e `erro` são retentados de
    propósito:

    - `sem_dado` pode virar dado quando o exercício for publicado;
    - `parcial` é, por definição, incompleto;
    - `erro` é o caso óbvio.
    """
    df = armazem.ler("ingestao")
    if df.empty:
        return False
    linha = df[(df["fonte"] == fonte) & (df["recurso"] == recurso)]
    if linha.empty:
        return False
    return str(linha.iloc[0].get("situacao", "")) == "ok"


def recortes_pendentes(fonte: str, recursos: list[str]) -> list[str]:
    """Dos recortes pedidos, os que ainda não foram concluídos.

    Uma leitura só do controle para a lista inteira — perguntar um por um
    numa carga de dez anos abriria o Parquet centenas de vezes.
    """
    df = armazem.ler("ingestao")
    if df.empty:
        return list(recursos)

    feitos = set(
        df[(df["fonte"] == fonte) & (df["situacao"] == "ok")]["recurso"]
        .astype(str).tolist()
    )
    return [r for r in recursos if r not in feitos]
