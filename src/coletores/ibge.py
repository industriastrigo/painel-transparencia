"""Coletor IBGE — a base geográfica de tudo.

Três recursos:
  entes      : país, 27 UFs e 5.570 municípios (dim_ente)
  malhas     : GeoJSON do Brasil por UF e de cada UF por município
  indicadores: população e PIB municipal via Agregados/SIDRA v3

O código IBGE é a chave primária de junção do projeto inteiro. TSE e SICONFI
usam identificadores próprios — o de-para para eles nasce aqui.
"""

from __future__ import annotations

import json
from datetime import date

from ..nucleo import armazem, config, controle, rede
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.ibge")

FONTE = "ibge"

# Agregados SIDRA usados. Formato: (id_agregado, id_variavel, nível, período)
AGREGADOS = {
    "populacao": {
        "agregado": "6579", "variavel": "9324",
        "rotulo": "População residente estimada", "unidade": "pessoas",
    },
    "pib": {
        "agregado": "5938", "variavel": "37",
        "rotulo": "PIB a preços correntes", "unidade": "R$ mil",
    },
}

# PIB per capita NÃO é coletado da API.
#
# A tentativa anterior pedia a variável 593 do agregado 5938 — que não existe
# ali. O SIDRA responde 500 (não 404) a combinação inválida, então o cliente
# tratava como instabilidade e repetia quatro vezes com espera exponencial,
# em três níveis territoriais: 36 requisições e ~50 segundos para descobrir
# que a variável estava errada.
#
# Como já temos PIB e população do mesmo ente e ano, o per capita sai de
# divisão — sem depender de um identificador que pode estar errado e sem
# inventar número: se faltar qualquer um dos dois, não há linha.
DERIVADAS = {
    "pib_per_capita": {
        "rotulo": "PIB per capita",
        "unidade": "R$",
        "formula": "pib × 1000 ÷ população",
    },
}


# ------------------------------------------------------------------ entes
def coletar_entes() -> int:
    estados = rede.buscar(FONTE, f"{config.IBGE_LOCALIDADES}/estados",
                          {"orderBy": "nome"})
    municipios = rede.buscar(FONTE, f"{config.IBGE_LOCALIDADES}/municipios")

    linhas = [{
        "cod_ibge": "0",
        "nivel": "pais",
        "nome": "Brasil",
        "sigla_uf": None,
        "cod_uf": None,
        "regiao": None,
        "cod_regiao": None,
    }]

    for e in estados:
        linhas.append({
            "cod_ibge": str(e["id"]),
            "nivel": "estado",
            "nome": e["nome"],
            "sigla_uf": e["sigla"],
            "cod_uf": str(e["id"]),
            "regiao": e["regiao"]["nome"],
            "cod_regiao": str(e["regiao"]["id"]),
        })

    for m in municipios:
        uf = m["microrregiao"]["mesorregiao"]["UF"] if m.get("microrregiao") else None
        if uf is None:  # municípios novos vêm com estrutura reduzida
            uf = m.get("regiao-imediata", {}).get(
                "regiao-intermediaria", {}).get("UF", {})
        linhas.append({
            "cod_ibge": str(m["id"]),
            "nivel": "municipio",
            "nome": m["nome"],
            "sigla_uf": uf.get("sigla"),
            "cod_uf": str(uf.get("id")) if uf.get("id") else None,
            "regiao": uf.get("regiao", {}).get("nome"),
            "cod_regiao": str(uf.get("regiao", {}).get("id") or "") or None,
        })

    armazem.mesclar("dim_ente", linhas, FONTE)
    controle.gravar_marca(FONTE, "entes", date.today().isoformat(), len(linhas))
    return len(linhas)


# ------------------------------------------------------------------ malhas
def coletar_malha_brasil() -> str:
    """Malha do Brasil dividida por UF — carregada no boot do painel."""
    destino = config.MALHAS / "brasil-uf.json"
    dados = rede.buscar(
        FONTE, f"{config.IBGE_MALHAS}/paises/BR",
        {"formato": "application/vnd.geo+json", "intrarregiao": "UF",
         "qualidade": "minima"},
    )
    destino.write_text(json.dumps(dados), encoding="utf-8")
    log.info("malha do Brasil gravada (%d KB)", destino.stat().st_size // 1024)
    return str(destino)


def coletar_malha_uf(sigla_uf: str) -> str:
    """Malha de uma UF dividida por município — carregada sob demanda.

    Nunca baixe as malhas dos 5.570 municípios de uma vez: são centenas de MB.
    """
    destino = config.MALHAS / f"uf-{sigla_uf.upper()}.json"
    dados = rede.buscar(
        FONTE, f"{config.IBGE_MALHAS}/estados/{sigla_uf.upper()}",
        {"formato": "application/vnd.geo+json", "intrarregiao": "municipio",
         "qualidade": "minima"},
    )
    destino.write_text(json.dumps(dados), encoding="utf-8")
    return str(destino)


# ------------------------------------------------------------------ SIDRA
def variaveis_do_agregado(agregado: str) -> dict[str, str]:
    """Lê os metadados e devolve {id da variável: rótulo}.

    Serve para falhar cedo e com mensagem útil quando a variável configurada
    não existe — em vez de tomar 500 da API e interpretar como instabilidade.
    """
    try:
        corpo = rede.buscar(FONTE, f"{config.IBGE_AGREGADOS}/{agregado}/metadados")
    except Exception as erro:  # noqa: BLE001
        log.warning("metadados do agregado %s indisponíveis (%s) — seguindo "
                    "sem validar", agregado, erro)
        return {}
    return {str(v["id"]): v.get("nome", "") for v in corpo.get("variaveis", [])}


def coletar_indicador(chave: str, periodo: str, nivel: str = "N6") -> int:
    """N6 = municípios, N3 = UFs, N1 = Brasil."""
    spec = AGREGADOS[chave]

    disponiveis = variaveis_do_agregado(spec["agregado"])
    if disponiveis and spec["variavel"] not in disponiveis:
        raise ValueError(
            f"variável {spec['variavel']} não existe no agregado "
            f"{spec['agregado']}. Disponíveis: "
            + ", ".join(f"{i} ({n})" for i, n in list(disponiveis.items())[:8]))

    url = (f"{config.IBGE_AGREGADOS}/{spec['agregado']}/periodos/{periodo}"
           f"/variaveis/{spec['variavel']}")
    corpo = rede.buscar(FONTE, url, {"localidades": f"{nivel}[all]"})

    linhas = []
    for variavel in corpo:
        for serie in variavel.get("resultados", [])[0].get("series", []):
            cod = str(serie["localidade"]["id"])
            for ano, valor in serie["serie"].items():
                if valor in ("...", "-", "..", "X", None, ""):
                    continue
                linhas.append({
                    "cod_ibge": cod,
                    "cod_metrica": chave,
                    "ano": int(ano),
                    "valor": float(valor),
                    "unidade": spec["unidade"],
                    "nivel_territorial": nivel,
                    "data_referencia": f"{ano}-12-31",
                })

    armazem.mesclar("indicador_ente", linhas, f"{FONTE}_sidra")
    controle.gravar_marca(FONTE, f"sidra_{chave}_{nivel}", periodo, len(linhas))
    return len(linhas)


def derivar_pib_per_capita() -> int:
    """PIB per capita = PIB (R$ mil) × 1000 ÷ população, por ente e ano.

    Só gera linha onde os DOIS insumos existem para o mesmo ente e ano —
    ente sem população não vira divisão por zero nem número inventado.
    """
    df = armazem.ler(
        "indicador_ente",
        filtro="cod_metrica IN ('pib', 'populacao')",
        colunas=["cod_ibge", "cod_metrica", "ano", "valor", "nivel_territorial"])
    if df.empty:
        log.info("sem PIB e população coletados — nada a derivar")
        return 0

    largo = df.pivot_table(index=["cod_ibge", "ano", "nivel_territorial"],
                           columns="cod_metrica", values="valor",
                           aggfunc="first").reset_index()
    if "pib" not in largo.columns or "populacao" not in largo.columns:
        log.warning("falta PIB ou população — pib_per_capita não foi derivado")
        return 0

    validos = largo[(largo["pib"].notna()) & (largo["populacao"] > 0)]
    linhas = [{
        "cod_ibge": str(l["cod_ibge"]),
        "cod_metrica": "pib_per_capita",
        "ano": int(l["ano"]),
        "valor": float(l["pib"]) * 1000 / float(l["populacao"]),
        "unidade": "R$",
        "nivel_territorial": l["nivel_territorial"],
        "data_referencia": f"{int(l['ano'])}-12-31",
    } for _, l in validos.iterrows()]

    armazem.mesclar("indicador_ente", linhas, "derivado")
    descartados = len(largo) - len(validos)
    log.info("pib_per_capita derivado para %d ente-ano%s", len(linhas),
             f" ({descartados} sem PIB ou sem população)" if descartados else "")
    controle.gravar_marca(FONTE, "derivado_pib_per_capita",
                          date.today().isoformat(), len(linhas))
    return len(linhas)


def catalogo_metricas() -> int:
    linhas = [{
        "cod_metrica": chave,
        "rotulo": spec["rotulo"],
        "unidade": spec["unidade"],
        "fonte_origem": "IBGE/SIDRA",
        "agregado": spec["agregado"],
        "variavel": spec["variavel"],
    } for chave, spec in AGREGADOS.items()]

    linhas += [{
        "cod_metrica": chave,
        "rotulo": spec["rotulo"],
        "unidade": spec["unidade"],
        "fonte_origem": f"derivado: {spec['formula']}",
        "agregado": None, "variavel": None,
    } for chave, spec in DERIVADAS.items()]

    linhas.append({
        "cod_metrica": "despesa_total_per_capita",
        "rotulo": "Despesa total per capita",
        "unidade": "R$/hab",
        "fonte_origem": "derivado: SICONFI ÷ IBGE",
        "agregado": None, "variavel": None,
    })
    armazem.mesclar("dim_metrica", linhas, FONTE)
    return len(linhas)


# ------------------------------------------------------------------ execução
def executar(periodo: str = "last 6", com_malhas: bool = True) -> None:
    catalogo_metricas()
    coletar_entes()
    for chave in AGREGADOS:
        for nivel in ("N1", "N3", "N6"):
            try:
                coletar_indicador(chave, periodo, nivel)
            except Exception as erro:  # noqa: BLE001
                log.error("SIDRA %s %s falhou: %s", chave, nivel, erro)
                controle.gravar_marca(FONTE, f"sidra_{chave}_{nivel}", None,
                                      situacao="erro", detalhe=str(erro))

    derivar_pib_per_capita()

    if com_malhas:
        coletar_malha_brasil()


if __name__ == "__main__":
    executar()
