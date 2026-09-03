"""Normalização de PVLs do SADIPEM."""
from __future__ import annotations
import re
from datetime import date
from ...nucleo.valores import ano_de, data_br, inteiro, numero, opcional, texto


def _extrair_ano(bruto: dict) -> int:
    for campo_data in ("data_protocolo", "data_status", "data_pedido", "data_assinatura_contrato", "data_referencia"):
        val = bruto.get(campo_data)
        if val:
            ano = ano_de(val)
            if ano and 1990 <= ano <= date.today().year + 1:
                return ano
    for campo_ano in ("ano", "an_exercicio", "ano_exercicio", "ano_pleito"):
        val = inteiro(bruto.get(campo_ano))
        if val and 1990 <= val <= date.today().year + 1:
            return val
    num_proc = str(bruto.get("num_processo") or "")
    m = re.search(r"/(20\d{2})", num_proc)
    if m:
        return int(m.group(1))
    num_pvl = str(bruto.get("num_pvl") or "")
    m2 = re.search(r"\.(20\d{2})\.", num_pvl) or re.search(r"/(20\d{2})", num_pvl)
    if m2:
        return int(m2.group(1))
    return date.today().year


def normalizar_pvl(bruto: dict, uf: str) -> dict | None:
    id_pleito = inteiro(bruto.get("id_pleito"))
    if id_pleito is None:
        return None
    cod_ibge = texto(bruto.get("cod_ibge"))
    protocolo = data_br(bruto.get("data_protocolo"))
    status_dt = data_br(bruto.get("data_status"))
    ano_val = _extrair_ano(bruto)
    return {
        "id_pleito": id_pleito,
        "cod_ibge": cod_ibge or None,
        "uf": opcional(bruto.get("uf")) or uf,
        "tipo_interessado": opcional(bruto.get("tipo_interessado")),
        "interessado": opcional(bruto.get("interessado")),
        "num_pvl": opcional(bruto.get("num_pvl")),
        "num_processo": opcional(bruto.get("num_processo")),
        "status": opcional(bruto.get("status")),
        "tipo_operacao": opcional(bruto.get("tipo_operacao")),
        "finalidade": opcional(bruto.get("finalidade")),
        "tipo_credor": opcional(bruto.get("tipo_credor")),
        "credor": opcional(bruto.get("credor")),
        "moeda": opcional(bruto.get("moeda")),
        "valor": numero(bruto.get("valor")),
        "contratado": inteiro(bruto.get("pvl_contradado_credor", bruto.get("pvl_contratado_credor"))),
        "data_protocolo": protocolo,
        "data_status": status_dt,
        "ano": ano_val,
        "data_referencia": protocolo or status_dt or f"{ano_val}-01-01",
    }
