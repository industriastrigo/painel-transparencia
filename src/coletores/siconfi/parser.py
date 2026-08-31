"""Interpretação e normalização dos dados contábeis do SICONFI."""
from __future__ import annotations

from datetime import date
from ...nucleo import nomes
from ...nucleo.valores import numero, opcional, texto
from ...nucleo.registro import obter as obter_log

log = obter_log("coletores.siconfi.parser")

COLUNA_EMPENHADA_ACUMULADA = "ATÉ O BIMESTRE (B)"

FUNCOES_DE_INTERESSE = {
    "10": "Saúde",
    "12": "Educação",
    "09": "Previdência Social",
    "06": "Segurança Pública",
    "26": "Transporte",
    "15": "Urbanismo",
    "08": "Assistência Social",
    "04": "Administração",
    "17": "Saneamento",
    "18": "Gestão Ambiental",
}

FUNCOES_OFICIAIS = {
    "01": "Legislativa",          "02": "Judiciária",
    "03": "Essencial à Justiça",  "04": "Administração",
    "05": "Defesa Nacional",      "06": "Segurança Pública",
    "07": "Relações Exteriores",  "08": "Assistência Social",
    "09": "Previdência Social",   "10": "Saúde",
    "11": "Trabalho",             "12": "Educação",
    "13": "Cultura",              "14": "Direitos da Cidadania",
    "15": "Urbanismo",            "16": "Habitação",
    "17": "Saneamento",           "18": "Gestão Ambiental",
    "19": "Ciência e Tecnologia", "20": "Agricultura",
    "21": "Organização Agrária",  "22": "Indústria",
    "23": "Comércio e Serviços",  "24": "Comunicações",
    "25": "Energia",              "26": "Transporte",
    "27": "Desporto e Lazer",     "28": "Encargos Especiais",
    "99": "Reserva de Contingência",
}

_POR_NOME = {nomes.chave_estrita(nome): cod
             for cod, nome in FUNCOES_OFICIAIS.items()}

def _funcao_oficial(conta: str) -> str | None:
    return _POR_NOME.get(nomes.chave_estrita(conta))

def _bloco_de(item: dict) -> str:
    rotulo = str(item.get("rotulo") or item.get("coluna_bloco") or "").strip()
    cod_conta = str(item.get("cod_conta") or "").strip()
    if "intra" in cod_conta.lower():
        if "exceto" in cod_conta.lower():
            return "exceto_intra"
        return "intra"
    if rotulo:
        if "exceto" in rotulo.lower():
            return "exceto_intra"
        if "intra" in rotulo.lower():
            return "intra"
    return "exceto_intra"

MEDIDA_VALOR = "valor"
MEDIDA_PERCENTUAL = "percentual"
MEDIDA_RESTOS = "restos_a_pagar"
MEDIDA_SALDO = "saldo"
MEDIDA_SALDO_ANTERIOR = "saldo_exercicio_anterior"

_ORDINAL = {1: "1º", 2: "2º", 3: "3º"}
_contas_vistas: set[str] = set()
_contas_funcao_vistas: set[str] = set()
_contas_rgf_vistas: set[str] = set()

def esfera(cod_ibge: str) -> str:
    if str(cod_ibge) in ("0", "1"):
        return "uniao"
    return "estado" if len(str(cod_ibge)) == 2 else "municipio"

def periodo_publicado(ano: int, passo: int, hoje: date | None = None) -> int:
    hoje = hoje or date.today()
    if ano < hoje.year:
        return 12 // passo
    if ano > hoje.year:
        return 0
    return max(0, (hoje.month - 2) // passo)

def interpretar_dca(itens: list, ano: int, cod_ibge: str) -> list[dict]:
    linhas = []
    for item in itens:
        conta = texto(item.get("cod_conta"))
        coluna = texto(item.get("coluna"))
        if "Empenhada" not in coluna:
            continue
        valor = item.get("valor")
        if valor in (None, ""):
            continue
        funcao = conta.split(".")[0].zfill(2)
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": "anual",
            "cod_conta": conta,
            "cod_funcao": funcao,
            "funcao": FUNCOES_DE_INTERESSE.get(funcao, opcional(item.get("conta"))),
            "rotulo_conta": opcional(item.get("conta")),
            "estagio": coluna,
            "valor": numero(valor),
            "esfera": esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-31",
        })
    if itens and not linhas:
        log.error("SICONFI DCA %s/%d: %d itens na resposta, mas nenhum passou no filtro — defeito de leitura ou mudança de layout",
                  cod_ibge, ano, len(itens))
    return linhas

def interpretar_dca_receita(itens: list, ano: int, cod_ibge: str) -> list[dict]:
    linhas = []
    for item in itens:
        conta = texto(item.get("cod_conta"))
        coluna = texto(item.get("coluna"))
        if "Realizada" not in coluna:
            continue
        valor = item.get("valor")
        if valor in (None, ""):
            continue
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": "anual",
            "cod_conta": conta,
            "rotulo_conta": opcional(item.get("conta")),
            "estagio": coluna,
            "valor": numero(valor),
            "esfera": esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-31",
        })
    return linhas

def interpretar_funcao(itens: list, ano: int, bimestre: int, cod_ibge: str) -> list[dict]:
    linhas = []
    funcao_mae_cod = None
    funcao_mae_nome = None

    for item in itens:
        coluna = str(item.get("coluna", "")).strip()
        col_up = coluna.upper()
        if "DESPESAS EMPENHADAS ATÉ O BIMESTRE (B)" not in col_up and col_up not in ("ATÉ O BIMESTRE (B)", "ATE O BIMESTRE (B)"):
            continue
        if "(D)" in col_up or "LIQUIDADA" in col_up or "DOTAÇÃO" in col_up or "NO BIMESTRE" in col_up:
            continue

        conta = str(item.get("conta", "")).strip()
        if not conta:
            continue

        cod_funcao = _POR_NOME.get(nomes.chave_estrita(conta))
        if cod_funcao:
            funcao_mae_cod = cod_funcao
            funcao_mae_nome = FUNCOES_OFICIAIS.get(cod_funcao, conta)

        rotulo = item.get("conta")
        bloco = _bloco_de(item)
        chave_conta = f"{bloco}|{funcao_mae_cod or '00'}|{rotulo}"

        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": int(ano),
            "periodo": f"bimestre_{bimestre}",
            "cod_conta": chave_conta,
            "cod_funcao": cod_funcao,
            "cod_funcao_mae": funcao_mae_cod,
            "funcao_mae": funcao_mae_nome,
            "funcao": FUNCOES_OFICIAIS.get(cod_funcao),
            "rotulo_conta": rotulo,
            "bloco": bloco,
            "estagio": coluna,
            "valor": numero(item.get("valor")),
            "esfera": esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-01",
        })

    if itens and not linhas:
        log.error("SICONFI RREO %s/%d/b%d: %d itens na resposta, mas nenhum passou no filtro — possível defeito de leitura ou mudança de layout na fonte",
                  cod_ibge, ano, bimestre, len(itens))
    return linhas

def _medida_da_coluna(coluna: str) -> str | None:
    col = coluna.strip()
    if "%" in col:
        return MEDIDA_PERCENTUAL
    if "RESTOS" in col.upper():
        return MEDIDA_RESTOS
    if "SALDO DO EXERCÍCIO ANTERIOR" in col.upper():
        return MEDIDA_SALDO_ANTERIOR
    if "SALDO" in col.upper() or "Quadrimestre" in col:
        return MEDIDA_SALDO
    if col in (
        "Valor", "VALOR", "VALOR (a)", "VALOR (b)", "VALOR (c)", "VALOR (d)",
        "VALOR ATÉ O QUADRIMESTRE (a)", "VALOR ATÉ O QUADRIMESTRE (c)",
        "VALOR ATÉ O SEMESTRE (a)", "VALOR ATÉ O SEMESTRE (c)",
        "<VALOR>", "<VALOR DO QUADRIMESTRE>", "<VALOR DO SEMESTRE>",
    ):
        return MEDIDA_VALOR
    return None

def interpretar_rgf(itens: list, ano: int, quadrimestre: int, cod_ibge: str, poder: str, anexo: str) -> list[dict]:
    linhas = []
    ord_str = _ORDINAL.get(quadrimestre, f"{quadrimestre}º")

    for item in itens:
        coluna = str(item.get("coluna", "")).strip()
        if "Quadrimestre" in coluna and ord_str not in coluna:
            continue
        if "SALDO DO EXERCÍCIO ANTERIOR" in coluna.upper():
            continue
        if coluna.startswith("<MR"):
            continue

        medida = _medida_da_coluna(coluna)
        if not medida:
            continue
        val = item.get("valor")
        if val in (None, ""):
            continue
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": int(ano),
            "periodo": f"quadrimestre_{quadrimestre}",
            "poder": poder,
            "anexo": anexo,
            "indicador": texto(item.get("cod_conta")),
            "rotulo": opcional(item.get("conta")),
            "secao": opcional(item.get("rotulo")),
            "coluna": opcional(item.get("coluna")),
            "medida": medida,
            "valor": numero(val),
            "esfera": esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-01",
        })
    return linhas
