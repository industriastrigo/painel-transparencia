"""Normalização de PVLs do SADIPEM."""
from __future__ import annotations
from ...nucleo.valores import ano_de, data_br, inteiro, numero, opcional, texto

def normalizar_pvl(bruto: dict, uf: str) -> dict | None:
    id_pleito = inteiro(bruto.get("id_pleito"))
    if id_pleito is None:
        return None
    cod_ibge = texto(bruto.get("cod_ibge"))
    protocolo = data_br(bruto.get("data_protocolo"))
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
        "data_status": data_br(bruto.get("data_status")),
        "ano": ano_de(bruto.get("data_protocolo")),
        "data_referencia": protocolo,
    }
