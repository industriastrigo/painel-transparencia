"""Normalização dos dados do Portal da Transparência."""
from __future__ import annotations
from ...nucleo.valores import numero, opcional, texto

TIPOS_EMENDA = {
    "1": "Emenda individual",
    "2": "Emenda de bancada",
    "3": "Emenda de comissão",
    "4": "Emenda de relator (RP-9)",
    "5": "Transferência especial (Pix)",
}

def normalizar_emenda(e: dict, ano: int) -> dict:
    return {
        "ano": int(ano),
        "codigo_emenda": texto(e.get("codigoEmenda")),
        "tipo_emenda": opcional(e.get("tipoEmenda")),
        "autor": opcional(e.get("nomeAutor")),
        "numero_emenda": opcional(e.get("numeroEmenda")),
        "funcao": opcional(e.get("funcao")),
        "subfuncao": opcional(e.get("subfuncao")),
        "valor_empenhado": numero(e.get("valorEmpenhado")),
        "valor_liquidado": numero(e.get("valorLiquidado")),
        "valor_pago": numero(e.get("valorPago")),
        "valor_resto_pago": numero(e.get("valorRestoInscrito")),
        "localidade": opcional(e.get("localidadeDoGasto")),
        "data_referencia": f"{ano}-12-31",
    }

def normalizar_cartao(c: dict, ano: int, mes: int) -> dict:
    orgao = c.get("unidadeGestora") or c.get("orgao") or {}
    portador = c.get("portador") or {}
    favorecido = c.get("favorecido") or {}
    return {
        "ano": int(ano),
        "mes": int(mes),
        "codigo_orgao": texto(orgao.get("codigo") or c.get("codigoOrgao")),
        "nome_orgao": opcional(orgao.get("nome") or c.get("nomeOrgao")),
        "nome_portador": opcional(portador.get("nome") or c.get("nomePortador")),
        "cpf_portador": opcional(portador.get("codigoFormatado") or c.get("cpfPortador")),
        "nome_favorecido": opcional(favorecido.get("nome") or c.get("nomeFavorecido")),
        "cnpj_cpf_favorecido": opcional(favorecido.get("codigoFormatado") or c.get("cnpjFavorecido")),
        "tipo_cartao": opcional(c.get("tipoCartao", {}).get("descricao") or c.get("tipoCartao")),
        "data_transacao": opcional(c.get("dataTransacao")),
        "valor": numero(c.get("valorTransacao") or c.get("valor")),
        "data_referencia": f"{ano}-{mes:02d}-01",
    }
