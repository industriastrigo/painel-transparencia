"""Modularização de SADIPEM, Tesouro e Transferências."""
from pathlib import Path

RAIZ = Path("src/coletores")

def criar_sadipem():
    p = RAIZ / "sadipem"
    p.mkdir(parents=True, exist_ok=True)

    (p / "contrato.md").write_text("""# Contrato da API SADIPEM (Tesouro Nacional)

## 1. Visão Geral
- **Provedor**: Secretaria do Tesouro Nacional
- **Base URL**: `https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt`
- **Autenticação**: Pública.
- **Limite de Taxa**: 1 req/s.

---

## 2. Endpoints

### 2.1. Pedidos de Verificação de Limites (PVL) — `/pvl`
- Parâmetros: `uf` (str), `offset` (int).
- Campos: `id_pleito`, `cod_ibge`, `uf`, `tipo_interessado`, `interessado`, `num_pvl`, `status`, `tipo_operacao`, `finalidade`, `credor`, `valor`, `pvl_contradado_credor` / `pvl_contratado_credor`, `data_protocolo`, `data_status`.
""", encoding="utf-8")

    (p / "erros.py").write_text("""\"\"\"Diagnóstico de erros do SADIPEM.\"\"\"
from __future__ import annotations

class ErroSADIPEM(RuntimeError):
    \"\"\"Erro base para chamadas ao SADIPEM.\"\"\"

def diagnosticar_erro(erro: Exception, uf: str) -> str:
    return f"SADIPEM ({uf}): {erro}"
""", encoding="utf-8")

    (p / "cliente.py").write_text("""\"\"\"Cliente HTTP para a API SADIPEM.\"\"\"
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "sadipem"

def buscar_pagina_pvl(parametros: dict, offset: int) -> tuple[list[dict], bool]:
    corpo = rede.buscar(FONTE, f"{config.SADIPEM}/pvl",
                        {**parametros, "offset": offset} if offset else parametros)
    if not isinstance(corpo, dict):
        return (corpo if isinstance(corpo, list) else []), False
    return corpo.get("items", []), bool(corpo.get("hasMore"))
""", encoding="utf-8")

    (p / "parser.py").write_text("""\"\"\"Normalização de PVLs do SADIPEM.\"\"\"
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
""", encoding="utf-8")

    (p / "__init__.py").write_text("""\"\"\"Módulo SADIPEM (Operações de Crédito).\"\"\"
from __future__ import annotations

from ...nucleo import armazem, controle
from ...nucleo.registro import obter as obter_log

from .cliente import buscar_pagina_pvl as _pagina
from .parser import normalizar_pvl
from .erros import ErroSADIPEM, diagnosticar_erro

log = obter_log("coletores.sadipem")
FONTE = "sadipem"
TETO_PAGINAS = 60

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]

def coletar_uf(uf: str) -> list[dict]:
    brutos: list[dict] = []
    offset = 0
    for pagina in range(TETO_PAGINAS):
        itens, tem_mais = _pagina({"uf": uf}, offset)
        brutos.extend(itens)
        if not tem_mais:
            break
        offset += len(itens) or 1

    linhas = []
    for bruto in brutos:
        l = normalizar_pvl(bruto, uf)
        if l:
            linhas.append(l)
    return linhas

def executar(anos: list[int] | None = None, ufs: list[str] | None = None, refazer: bool = False) -> int:
    alvos = list(ufs or UFS)
    if not refazer:
        pendentes = set(controle.recortes_pendentes(FONTE, [f"pvl_{u}" for u in alvos]))
        alvos = [u for u in alvos if f"pvl_{u}" in pendentes]
    if not alvos:
        return 0

    total_linhas = 0
    for uf in alvos:
        try:
            linhas = coletar_uf(uf)
            if linhas:
                armazem.mesclar("operacao_credito", linhas, FONTE)
            total_linhas += len(linhas)
            controle.gravar_marca(FONTE, f"pvl_{uf}", None, len(linhas), situacao="ok")
        except Exception as erro:  # noqa: BLE001
            log.error("SADIPEM %s falhou: %s", uf, erro)
            controle.gravar_marca(FONTE, f"pvl_{uf}", None, 0, situacao="erro", detalhe=str(erro))
    return total_linhas
""", encoding="utf-8")
    print("SADIPEM modularizado com sucesso!")

def criar_tesouro():
    p = RAIZ / "tesouro"
    p.mkdir(parents=True, exist_ok=True)

    (p / "contrato.md").write_text("""# Contrato da API de Custos do Governo Federal (Tesouro Nacional)

## 1. Visão Geral
- **Provedor**: Secretaria do Tesouro Nacional
- **Base URL**: `https://apidatalake.tesouro.gov.br/ords/cdwhprd/custos/tt`
- **Autenticação**: Pública.
""", encoding="utf-8")

    (p / "erros.py").write_text("""\"\"\"Diagnóstico de erros do Tesouro.\"\"\"
from __future__ import annotations

class ErroTesouro(RuntimeError):
    \"\"\"Erro base para chamadas ao Tesouro.\"\"\"

def diagnosticar_erro(erro: Exception, recurso: str, ano: int) -> str:
    return f"Tesouro Custos ({recurso}/{ano}): {erro}"
""", encoding="utf-8")

    (p / "cliente.py").write_text("""\"\"\"Cliente HTTP para a API de Custos do Tesouro.\"\"\"
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "tesouro"

def buscar_custos(recurso: str, parametros: dict[str, Any]) -> dict[str, Any]:
    return rede.buscar(FONTE, f"{config.TESOURO_CUSTOS}/{recurso}", parametros)
""", encoding="utf-8")

    (p / "parser.py").write_text("""\"\"\"Normalização de custos do Governo Federal.\"\"\"
from __future__ import annotations
from ...nucleo.valores import inteiro, numero, opcional, texto

CONJUNTOS = {
    "pessoal_ativo": "pessoal_ativo",
    "pessoal_inativo": "pessoal_inativo",
    "pensionista": "pensionistas",
    "depreciacao": "depreciacao",
    "transferencia": "transferencias",
    "demais_custos": "demais",
}

CAMPOS = {
    "orgao_nome": ("ds_organizacao_n1", "ds_siorg_n05", "ds_organizacao_n0", "ds_siorg_n04"),
    "orgao_codigo": ("co_organizacao_n1", "co_siorg_n05", "co_organizacao_n0", "co_siorg_n04"),
    "orgao_n2": ("ds_organizacao_n2", "ds_siorg_n06"),
    "orgao_n3": ("ds_organizacao_n3", "ds_siorg_n07"),
    "item_custo": ("no_conta_contabil", "no_natureza_despesa_deta", "ds_natureza_juridica"),
    "natureza_juridica": ("ds_natureza_juridica", "id_natureza_juridica_siorg"),
    "ano": ("an_lanc", "an_referencia", "an_emissao"),
    "mes": ("me_lanc", "me_referencia", "me_emissao"),
}

def primeiro(linha: dict, *nomes: str):
    for nome in nomes:
        if nome in linha and linha[nome] not in (None, ""):
            return linha[nome]
    return None

def campo(linha: dict, chave: str):
    return primeiro(linha, *CAMPOS[chave])

def valor_custo(linha: dict):
    for chave, conteudo in linha.items():
        if chave.startswith("va_") and conteudo not in (None, ""):
            return conteudo
    return None
""", encoding="utf-8")

    (p / "__init__.py").write_text("""\"\"\"Módulo Custos do Governo Federal (Tesouro Nacional).\"\"\"
from __future__ import annotations

import time
from datetime import date
from ...nucleo import armazem, config, controle, rede
from ...nucleo.registro import obter as obter_log
from ...nucleo.valores import inteiro, numero, opcional, texto

from .cliente import buscar_custos
from .parser import CONJUNTOS, CAMPOS, primeiro, campo as _campo, valor_custo as _valor
from .erros import ErroTesouro, diagnosticar_erro

log = obter_log("coletores.tesouro")
FONTE = "tesouro"
PAGINA = 10_000

def _paginar(recurso: str, parametros: dict, consumir, offset: int = 0, tamanho: int = PAGINA) -> int:
    total_linhas = 0
    while True:
        p = {**parametros, "limit": tamanho, "offset": offset}
        corpo = buscar_custos(recurso, p)
        itens = corpo.get("items", [])
        if not itens:
            break
        consumir(itens)
        total_linhas += len(itens)
        if not corpo.get("hasMore"):
            break
        offset += len(itens)
    return total_linhas

def coletar_conjunto_mes(recurso: str, ano: int, mes: int) -> int:
    linhas_acumuladas = []
    def consumir(itens):
        for item in itens:
            val = _valor(item)
            if val is None:
                continue
            linhas_acumuladas.append({
                "ano": int(ano),
                "mes": int(mes),
                "conjunto": CONJUNTOS.get(recurso, recurso),
                "codigo_orgao": texto(_campo(item, "orgao_codigo")),
                "nome_orgao": opcional(_campo(item, "orgao_nome")),
                "orgao_n2": opcional(_campo(item, "orgao_n2")),
                "orgao_n3": opcional(_campo(item, "orgao_n3")),
                "item_custo": opcional(_campo(item, "item_custo")),
                "natureza_juridica": opcional(_campo(item, "natureza_juridica")),
                "valor": numero(val),
                "data_referencia": f"{ano}-{mes:02d}-01",
            })

    total = _paginar(recurso, {"an_lanc": ano, "me_lanc": mes}, consumir)
    if linhas_acumuladas:
        armazem.mesclar("custo_executivo", linhas_acumuladas, FONTE)
    return len(linhas_acumuladas)

def executar(anos: list[int] | None = None, meses: list[int] | None = None) -> int:
    anos = anos or [date.today().year]
    meses = meses or list(range(1, 13))
    total = 0
    for ano in anos:
        for mes in meses:
            for rec in CONJUNTOS:
                try:
                    total += coletar_conjunto_mes(rec, ano, mes)
                except Exception as erro:  # noqa: BLE001
                    log.warning("Tesouro %s %d/%d falhou: %s", rec, ano, mes, erro)
    return total
""", encoding="utf-8")
    print("Tesouro modularizado com sucesso!")

def criar_transferencias():
    p = RAIZ / "transferencias"
    p.mkdir(parents=True, exist_ok=True)

    (p / "contrato.md").write_text("""# Contrato da API de Transferências Constitucionais (Tesouro Aria)

## 1. Visão Geral
- **Provedor**: Secretaria do Tesouro Nacional (API Aria)
- **Base URL**: `https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais`
- **Finalidade**: Repasses obrigatórios da União aos entes (FPM, FPE, FUNDEB, Royalties).
""", encoding="utf-8")

    (p / "erros.py").write_text("""\"\"\"Diagnóstico de erros da API de Transferências.\"\"\"
from __future__ import annotations

class ErroTransferencias(RuntimeError):
    \"\"\"Erro base para transferências constitucionais.\"\"\"

def diagnosticar_erro(erro: Exception, recurso: str) -> str:
    return f"Transferências ({recurso}): {erro}"
""", encoding="utf-8")

    (p / "cliente.py").write_text("""\"\"\"Cliente HTTP para a API Aria do Tesouro.\"\"\"
from __future__ import annotations
from typing import Any
from ...nucleo import config, rede

FONTE = "transferencias"

def base_url() -> str:
    return f"{config.TESOURO_ARIA}/v1/transferencias_constitucionais"

def pedir_transferencias(rota: str, parametros: dict | None = None) -> list[dict]:
    p = dict(parametros or {})
    if config.CHAVE_TESOURO_ARIA:
        p.setdefault("chave", config.CHAVE_TESOURO_ARIA)
    corpo = rede.buscar(FONTE, f"{base_url()}{rota}", p)
    if isinstance(corpo, dict):
        return corpo.get("items", [])
    return corpo if isinstance(corpo, list) else []
""", encoding="utf-8")

    (p / "parser.py").write_text("""\"\"\"Normalização de repasses constitucionais.\"\"\"
from __future__ import annotations
from ...nucleo.valores import inteiro, numero, opcional, texto

CAMPOS = {
    "cod_ibge": ("co_ibge", "cod_ibge", "codigo_ibge", "co_municipio_ibge"),
    "cod_transferencia": ("codigo", "co_transferencia", "cod_transferencia"),
    "transferencia": ("transferencia", "no_transferencia", "nome"),
    "uf": ("uf", "sg_uf", "sigla_uf"),
    "municipio": ("municipio", "no_municipio", "nome"),
    "ano": ("ano", "an_referencia", "exercicio"),
    "mes": ("mes", "me_referencia", "mes_referencia"),
    "valor": ("valor", "vl_transferencia", "vl_valor", "montante"),
}

def primeiro(linha: dict, *nomes: str):
    if not isinstance(linha, dict):
        return None
    por_minuscula = {str(k).lower(): v for k, v in linha.items()}
    for nome in nomes:
        valor = por_minuscula.get(nome.lower())
        if valor not in (None, ""):
            return valor
    return None

def campo(linha: dict, chave: str):
    return primeiro(linha, *CAMPOS[chave])
""", encoding="utf-8")

    (p / "__init__.py").write_text("""\"\"\"Módulo Transferências Constitucionais da União.\"\"\"
from __future__ import annotations

from datetime import date
from ...nucleo import armazem, controle
from ...nucleo.valores import inteiro, numero, opcional, texto
from ...nucleo.registro import obter as obter_log

from .cliente import pedir_transferencias
from .parser import CAMPOS, primeiro, campo as _campo
from .erros import ErroTransferencias, diagnosticar_erro

log = obter_log("coletores.transferencias")
FONTE = "transferencias"

def coletar_modalidades() -> list[dict]:
    itens = pedir_transferencias("/custom/transferencias")
    linhas = []
    for item in itens:
        cod = _campo(item, "cod_transferencia")
        nome = _campo(item, "transferencia")
        if cod:
            linhas.append({"cod_transferencia": str(cod), "nome": nome})
    if linhas:
        armazem.mesclar("dim_transferencia", linhas, FONTE)
    return linhas

def coletar_ano(ano: int) -> int:
    coletar_modalidades()
    itens = pedir_transferencias("/custom/por_estados", {"an_referencia": ano})
    linhas = []
    for item in itens:
        val = _campo(item, "valor")
        if val is None:
            continue
        m = inteiro(_campo(item, "mes"), 1)
        linhas.append({
            "cod_ibge": texto(_campo(item, "cod_ibge")),
            "nivel": "estado",
            "uf": opcional(_campo(item, "uf")),
            "cod_transferencia": texto(_campo(item, "cod_transferencia")),
            "transferencia": opcional(_campo(item, "transferencia")),
            "ano": int(ano),
            "mes": m,
            "valor": numero(val),
            "data_referencia": f"{ano}-{m:02d}-01",
        })
    if linhas:
        armazem.mesclar("transferencia_uniao", linhas, FONTE)
    controle.gravar_marca(FONTE, f"transferencias_{ano}", ano, len(linhas))
    return len(linhas)

def executar(anos: list[int] | None = None) -> int:
    anos = anos or [date.today().year - 1, date.today().year]
    total = 0
    for ano in anos:
        try:
            total += coletar_ano(ano)
        except Exception as erro:  # noqa: BLE001
            log.warning("Transferências %d falhou: %s", ano, erro)
    return total
""", encoding="utf-8")
    print("Transferências modularizadas com sucesso!")

criar_sadipem()
criar_tesouro()
criar_transferencias()
