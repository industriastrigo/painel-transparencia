"""Módulo IBGE."""
from __future__ import annotations

import json
from datetime import date
from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log

from .cliente import buscar_estados, buscar_municipios, buscar_malha_brasil, buscar_malha_uf, buscar_agregado
from .parser import AGREGADOS, DERIVADAS
from .erros import ErroIBGE, diagnosticar_erro

log = obter_log("coletores.ibge")
FONTE = "ibge"

def coletar_entes() -> int:
    estados = buscar_estados()
    municipios = buscar_municipios()

    linhas = [{
        "cod_ibge": "0", "nivel": "pais", "nome": "Brasil",
        "sigla_uf": None, "cod_uf": None, "regiao": None, "cod_regiao": None,
    }]

    for e in estados:
        linhas.append({
            "cod_ibge": str(e["id"]), "nivel": "estado", "nome": e["nome"],
            "sigla_uf": e["sigla"], "cod_uf": str(e["id"]),
            "regiao": e["regiao"]["nome"], "cod_regiao": str(e["regiao"]["id"]),
        })

    for m in municipios:
        uf = m["microrregiao"]["mesorregiao"]["UF"] if m.get("microrregiao") else None
        if uf is None:
            uf = m.get("regiao-imediata", {}).get("regiao-intermediaria", {}).get("UF", {})
        linhas.append({
            "cod_ibge": str(m["id"]), "nivel": "municipio", "nome": m["nome"],
            "sigla_uf": uf.get("sigla"), "cod_uf": str(uf.get("id")) if uf.get("id") else None,
            "regiao": uf.get("regiao", {}).get("nome"),
            "cod_regiao": str(uf.get("regiao", {}).get("id") or "") or None,
        })

    armazem.mesclar("dim_ente", linhas, FONTE)
    controle.gravar_marca(FONTE, "entes", date.today().isoformat(), len(linhas))
    return len(linhas)

def coletar_malha_brasil() -> str:
    destino = config.MALHAS / "brasil-uf.json"
    dados = buscar_malha_brasil()
    destino.write_text(json.dumps(dados), encoding="utf-8")
    log.info("malha do Brasil gravada (%d KB)", destino.stat().st_size // 1024)
    return str(destino)

def coletar_malha_uf(sigla_uf: str) -> str:
    destino = config.MALHAS / f"uf-{sigla_uf.upper()}.json"
    dados = buscar_malha_uf(sigla_uf)
    destino.write_text(json.dumps(dados), encoding="utf-8")
    return str(destino)

def variaveis_do_agregado(agregado: str) -> dict[str, str]:
    try:
        corpo = rede.buscar(FONTE, f"{config.IBGE_AGREGADOS}/{agregado}/metadados")
    except Exception as erro:  # noqa: BLE001
        log.warning("metadados do agregado %s indisponíveis (%s) — seguindo sem validar", agregado, erro)
        return {}
    return {str(v["id"]): v.get("nome", "") for v in (corpo.get("variaveis", []) if isinstance(corpo, dict) else [])}

def coletar_indicador(chave: str, periodo: str, nivel: str = "N6") -> int:
    spec = AGREGADOS.get(chave, {"agregado": "0", "variavel": "0"})
    agregado = spec["agregado"]
    variavel = spec["variavel"]

    variaveis = variaveis_do_agregado(agregado)
    if variaveis and str(variavel) not in variaveis:
        raise ValueError(f"a variável {variavel} não existe no agregado {agregado}. Variáveis disponíveis: {list(variaveis.keys())}")

    corpo = buscar_agregado(agregado, variavel, periodo, nivel)
    if not corpo or not isinstance(corpo, list):
        return 0

    linhas = []
    for serie in corpo[0].get("resultados", []):
        for item in serie.get("series", []):
            cod_ibge = str(item.get("localidade", {}).get("id", ""))
            valores = item.get("serie", {})
            for ano_str, val in valores.items():
                if val in (None, "", "...", "-"):
                    continue
                try:
                    v_float = float(val)
                except ValueError:
                    continue
                linhas.append({
                    "cod_ibge": cod_ibge,
                    "ano": int(ano_str),
                    "cod_metrica": chave,
                    "valor": v_float,
                    "data_referencia": f"{ano_str}-12-31",
                })

    if linhas:
        armazem.mesclar("indicador_ente", linhas, f"{FONTE}_sidra")
    return len(linhas)

def derivar_pib_per_capita() -> int:
    df_pib = armazem.ler("indicador_ente", filtro="cod_metrica = 'pib'")
    df_pop = armazem.ler("indicador_ente", filtro="cod_metrica = 'populacao'")
    if df_pib.empty or df_pop.empty:
        return 0

    m = df_pib.merge(df_pop, on=["cod_ibge", "ano"], suffixes=("_pib", "_pop"))
    if m.empty:
        return 0

    m = m[m["valor_pop"] > 0]
    linhas = [{
        "cod_ibge": str(r["cod_ibge"]),
        "ano": int(r["ano"]),
        "cod_metrica": "pib_per_capita",
        "valor": round((float(r["valor_pib"]) * 1000.0) / float(r["valor_pop"]), 2),
        "data_referencia": f"{int(r['ano'])}-12-31",
    } for _, r in m.iterrows()]

    if linhas:
        armazem.mesclar("indicador_ente", linhas, "derivado")
    return len(linhas)

def executar(anos: list[int] | None = None) -> None:
    coletar_entes()
    coletar_malha_brasil()
    anos = anos or [date.today().year - 2, date.today().year - 1]
    for ano in anos:
        for chave in AGREGADOS:
            try:
                coletar_indicador(chave, str(ano), "N6")
            except Exception as erro:  # noqa: BLE001
                log.warning("IBGE %s/%d falhou: %s", chave, ano, erro)
    derivar_pib_per_capita()
