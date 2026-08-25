"""Coletor de custos do Governo Federal — Tesouro Transparente (SIC).

Responde "quanto cada função tira dos cofres" com dado **medido**, não com
estimativa. A alternativa era calcular ocupantes × subsídio × 13,33; o SIC
publica o custo apurado pelo próprio governo, por órgão e centro de custo.

## Por que via catálogo, e não por URL fixa

O Tesouro publica num CKAN. Cravar a URL de cada arquivo no código é como o
projeto já se queimou duas vezes (a cota parlamentar mudou de endereço; a
variável 593 do SIDRA não existia). Aqui o coletor **pergunta ao catálogo**
onde está o dado:

    {base}/api/3/action/package_show?id=<dataset>  →  resources[].url

Se o Tesouro trocar o arquivo de lugar, o catálogo aponta para o novo e o
coletor segue funcionando.

## Sobre as colunas

O esquema exato dos CSVs não está documentado publicamente de forma estável.
Em vez de adivinhar nomes de coluna — o erro que deixou a Situação das
proposições inteira em branco — o coletor **detecta** as colunas por padrão
de nome e, na primeira execução, registra no log exatamente o que encontrou.
Se algo não casar, aparece no log em vez de virar coluna vazia.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from ..nucleo import armazem, config, controle, rede
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import inteiro, numero, opcional, texto

log = obter_log("coletores.tesouro")

FONTE = "tesouro"

# Os seis recortes de custo, com o id do dataset no CKAN.
CONJUNTOS = {
    "pessoal_ativo": "custos-por-itens-de-custos-pessoal-ativo",
    "pessoal_inativo": "dados-de-custos-com-pessoal-inativo-do-governo-federal",
    "pensionista": "dados-de-custos-pensionistas-do-governo-federal",
    "depreciacao": "custos-por-itens-de-custos-depreciacao",
    "transferencia": "custos-por-itens-de-custos-transferencia",
    "demais_custos": "gestao-por-centros-de-custos-demais-custos",
}

# Como reconhecer cada coluna. Primeiro pedaço que casar, vence.
PADROES = {
    "orgao_nome": ("orgao", "órgão", "unidade", "ug_nome", "nome_ug"),
    "orgao_codigo": ("cod_orgao", "codigo_orgao", "ug", "cod_ug", "codigo_ug"),
    "ano": ("ano", "exercicio", "exercício"),
    "mes": ("mes", "mês", "periodo", "período"),
    "item_custo": ("item", "elemento", "natureza", "conta", "descricao",
                   "descrição", "centro"),
    "valor": ("valor", "custo", "montante", "vl_"),
}


def _base_ckan() -> str:
    return f"{config.TESOURO_CKAN}/api/3/action"


def catalogar(conjunto: str) -> list[dict]:
    """Pergunta ao catálogo quais arquivos existem para um conjunto."""
    dataset = CONJUNTOS[conjunto]
    corpo = rede.buscar(FONTE, f"{_base_ckan()}/package_show", {"id": dataset})

    if not corpo.get("success"):
        raise RuntimeError(f"catálogo recusou o conjunto {dataset}")

    recursos = [{
        "nome": texto(r.get("name")),
        "formato": texto(r.get("format")).upper(),
        "url": texto(r.get("url")),
        "tamanho": r.get("size"),
    } for r in corpo["result"].get("resources", [])]

    log.info("%s: %d arquivo(s) no catálogo (%s)", conjunto, len(recursos),
             ", ".join(sorted({r["formato"] for r in recursos if r["formato"]})))
    return recursos


def _escolher_recurso(recursos: list[dict], ano: int) -> dict | None:
    """Prefere o arquivo do ano pedido; cai para o mais recente tabular."""
    tabulares = [r for r in recursos
                 if r["formato"] in ("CSV", "XLSX", "JSON")]
    if not tabulares:
        return None

    do_ano = [r for r in tabulares
              if str(ano) in r["nome"] or str(ano) in r["url"]]
    return (do_ano or tabulares)[0]


def _mapear_colunas(colunas: list[str]) -> dict[str, str]:
    """Casa as colunas do arquivo com os campos do nosso esquema."""
    mapa: dict[str, str] = {}
    disponiveis = {c.lower().strip(): c for c in colunas}

    for destino, pistas in PADROES.items():
        for pista in pistas:
            achou = next((original for baixa, original in disponiveis.items()
                          if pista in baixa and original not in mapa.values()),
                         None)
            if achou:
                mapa[destino] = achou
                break
    return mapa


def _ler_tabela(recurso: dict) -> pd.DataFrame:
    conteudo = rede.buscar(FONTE, recurso["url"], formato="binario")

    if recurso["formato"] == "XLSX":
        return pd.read_excel(io.BytesIO(conteudo), dtype=str)

    if recurso["formato"] == "JSON":
        return pd.read_json(io.BytesIO(conteudo), dtype=str)

    # CSV: o Tesouro usa ponto e vírgula e latin-1 na maioria dos arquivos,
    # mas nem sempre. Tenta as combinações prováveis antes de desistir.
    for sep, enc in ((";", "latin-1"), (";", "utf-8"),
                     (",", "utf-8"), (",", "latin-1")):
        try:
            df = pd.read_csv(io.BytesIO(conteudo), sep=sep, encoding=enc,
                             dtype=str, low_memory=False)
            if len(df.columns) > 1:
                return df
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError(f"não consegui ler {recurso['url']} como tabela")


def coletar_custos(conjunto: str, ano: int) -> int:
    recursos = catalogar(conjunto)
    recurso = _escolher_recurso(recursos, ano)
    if not recurso:
        log.warning("%s: nenhum arquivo tabular no catálogo", conjunto)
        controle.gravar_marca(FONTE, f"{conjunto}_{ano}", None, 0,
                              situacao="sem_arquivo")
        return 0

    log.info("%s: lendo %s (%s)", conjunto, recurso["nome"], recurso["formato"])
    df = _ler_tabela(recurso)
    if df.empty:
        return 0

    mapa = _mapear_colunas(list(df.columns))
    faltando = [c for c in ("orgao_nome", "valor") if c not in mapa]
    if faltando:
        # Registra o que veio, para o ajuste ser sobre fato e não sobre
        # suposição — foi assim que a Situação ficou vazia por uma semana.
        log.error("%s: não reconheci as colunas %s. O arquivo tem: %s",
                  conjunto, faltando, ", ".join(list(df.columns)[:25]))
        return 0

    log.info("%s: colunas reconhecidas → %s", conjunto,
             ", ".join(f"{k}={v}" for k, v in mapa.items()))

    linhas = []
    for _, l in df.iterrows():
        valor = numero(l.get(mapa["valor"]))
        if valor is None:
            continue
        linhas.append({
            "conjunto": conjunto,
            "orgao_nome": texto(l.get(mapa["orgao_nome"]), 200),
            "orgao_codigo": opcional(l.get(mapa.get("orgao_codigo", ""))),
            "item_custo": opcional(l.get(mapa.get("item_custo", ""))) or conjunto,
            "ano": inteiro(l.get(mapa.get("ano", "")), ano),
            "mes": inteiro(l.get(mapa.get("mes", "")), 0),
            "valor": valor,
            "data_referencia": f"{ano}-12-31",
        })

    if linhas:
        armazem.mesclar("custo_orgao", linhas, f"{FONTE}_{conjunto}")

    controle.gravar_marca(FONTE, f"{conjunto}_{ano}", ano, len(linhas),
                          detalhe=recurso["nome"])
    return len(linhas)


def descobrir() -> dict[str, list[dict]]:
    """Lista o que o catálogo oferece, sem gravar nada.

    Serve para saber o que existe antes de coletar — e para diagnosticar
    quando um conjunto muda de formato.
    """
    achados = {}
    for conjunto in CONJUNTOS:
        try:
            achados[conjunto] = catalogar(conjunto)
        except Exception as erro:  # noqa: BLE001
            log.error("catálogo de %s falhou: %s", conjunto, erro)
            achados[conjunto] = []
    return achados


def executar(anos: list[int] | None = None,
             conjuntos: list[str] | None = None) -> None:
    anos = anos or [date.today().year - 1]
    conjuntos = conjuntos or list(CONJUNTOS)

    for ano in anos:
        for conjunto in conjuntos:
            if conjunto not in CONJUNTOS:
                log.error("conjunto desconhecido: %s", conjunto)
                continue
            try:
                coletar_custos(conjunto, ano)
            except Exception as erro:  # noqa: BLE001
                log.error("Tesouro %s/%d falhou: %s", conjunto, ano, erro)


if __name__ == "__main__":
    executar()
