"""Download de arquivos do TSE."""
from __future__ import annotations

import pandas as pd
from ...nucleo import config, rede, tabela

FONTE = "tse"
_cache: dict[int, pd.DataFrame] = {}

def baixar_consulta_cand(ano: int) -> pd.DataFrame:
    if ano in _cache:
        return _cache[ano]
    url = f"{config.TSE_DADOS}/consulta_cand/consulta_cand_{ano}.zip"
    conteudo = rede.buscar(FONTE, url, formato="binario")
    _cache[ano] = tabela.de_zip(conteudo, origem=f"TSE {ano}", ignorar=("BRASIL",))
    return _cache[ano]
