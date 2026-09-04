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

def normalizar_viagem(v: dict, ano: int, mes: int | None = None) -> dict:
    orgao = v.get("orgao") or v.get("orgaoSuperior") or v.get("unidadeGestora") or {}
    beneficiario = v.get("beneficiario") or v.get("pessoa") or {}
    mes_calc = mes or int(str(v.get("dataInicioAfastamento") or v.get("dataInicio") or "")[3:5] or 1)
    
    return {
        "ano": int(ano),
        "mes": int(mes_calc),
        "id_viagem": texto(v.get("id") or v.get("idViagem") or v.get("processo")),
        "codigo_orgao": texto(orgao.get("codigo") or v.get("codigoOrgao")),
        "nome_orgao": opcional(orgao.get("nome") or v.get("nomeOrgao")),
        "nome_viajante": opcional(beneficiario.get("nome") or v.get("nome")),
        "cpf_viajante": opcional(beneficiario.get("cpfFormatado") or v.get("cpfFormatado") or v.get("cpf")),
        "cargo_viajante": opcional(v.get("cargo") or beneficiario.get("cargo")),
        "origem": opcional(v.get("origem") or v.get("localOrigem")),
        "destino": opcional(v.get("destino") or v.get("localDestino")),
        "motivo": opcional(v.get("motivo") or v.get("justificativa")),
        "data_inicio": opcional(v.get("dataInicioAfastamento") or v.get("dataInicio")),
        "data_fim": opcional(v.get("dataFimAfastamento") or v.get("dataFim")),
        "valor_diarias": numero(v.get("valorDiarias")),
        "valor_passagens": numero(v.get("valorPassagens")),
        "valor_outros": numero(v.get("valorOutros")),
        "valor_total": numero(v.get("valorTotalViagem") or v.get("valorTotal")),
        "data_referencia": f"{ano}-{mes_calc:02d}-01",
    }

def normalizar_contrato(c: dict, ano: int) -> dict:
    orgao = c.get("unidadeGestora") or c.get("orgao") or {}
    fornecedor = c.get("fornecedor") or {}
    modalidade = c.get("modalidadeCompra") or {}
    
    return {
        "ano": int(ano),
        "id_contrato": texto(c.get("id") or c.get("idContrato") or c.get("numero")),
        "numero_contrato": opcional(c.get("numero") or c.get("numeroContrato")),
        "codigo_orgao": texto(orgao.get("codigo") or c.get("codigoOrgao")),
        "nome_orgao": opcional(orgao.get("nome") or c.get("nomeOrgao")),
        "cnpj_fornecedor": opcional(fornecedor.get("cnpjFormatado") or fornecedor.get("cpfFormatado") or c.get("cnpjContratado")),
        "nome_fornecedor": opcional(fornecedor.get("nome") or c.get("razaoSocialContratado")),
        "modalidade_licitacao": opcional(modalidade.get("descricao") if isinstance(modalidade, dict) else modalidade or c.get("modalidade")),
        "objeto": opcional(c.get("objeto") or c.get("descricaoObjeto")),
        "valor_inicial": numero(c.get("valorInicialCompra") or c.get("valorInicial")),
        "valor_atualizado": numero(c.get("valorFinalCompra") or c.get("valorTotal") or c.get("valorAtualizado")),
        "data_inicio_vigencia": opcional(c.get("dataInicioVigencia")),
        "data_fim_vigencia": opcional(c.get("dataFimVigencia")),
        "data_referencia": f"{ano}-12-31",
    }
