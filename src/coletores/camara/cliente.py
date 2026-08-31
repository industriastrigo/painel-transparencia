"""Cliente HTTP e download de arquivos da Câmara."""
from __future__ import annotations

import pandas as pd
from typing import Any
from ...nucleo import config, rede, tabela

FONTE = "camara"

def buscar_api(endpoint: str, parametros: dict[str, Any] | None = None) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.CAMARA}/{endpoint.lstrip('/')}", parametros)

def baixar_csv(url: str) -> pd.DataFrame:
    conteudo = rede.buscar(FONTE, url, formato="binario")
    return tabela.ler(conteudo, origem=url)

def baixar_cota_zip_ou_csv(ano: int) -> pd.DataFrame:
    candidatas = [
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", "zip"),
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv", "csv"),
        (f"{config.CAMARA_ARQUIVOS}/despesasParlamentares/csv/despesasParlamentares-{ano}.csv", "csv"),
    ]
    erros = []
    for url, tipo in candidatas:
        try:
            if tipo == "csv":
                return baixar_csv(url)
            conteudo = rede.buscar(FONTE, url, formato="binario")
            return tabela.de_zip(conteudo, origem=url)
        except Exception as erro:  # noqa: BLE001
            erros.append(f"{url}: {erro}")
            continue
    raise RuntimeError(f"cota parlamentar de {ano} indisponível em todas as URLs conhecidas. " + " | ".join(erros))
