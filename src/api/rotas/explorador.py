"""Rotas do Explorador de Dados (Data Lakehouse / Estilo GCP BigQuery Studio)."""
from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from ..db import con, _consultar
from ...nucleo import config
from ...nucleo.esquema import TABELAS
from ...nucleo.registro import obter as obter_log
from ..vistas import DERIVADAS

log = obter_log("api.rotas.explorador")
router = APIRouter(tags=["explorador"])


class ConsultaRequisicao(BaseModel):
    sql: str
    limite: int = 500


class ExportarRequisicao(BaseModel):
    sql: str
    formato: str = "csv"  # csv ou json


def _obter_alvo_sql(dataset: str, tabela: str) -> str:
    if dataset == "_ctl":
        caminho = (Path(config.DADOS) / "_ctl" / f"{tabela}.parquet").as_posix()
        return f"read_parquet('{caminho}')"
    return tabela


@router.get("/api/explorador/arvore")
def obter_arvore_de_dados():
    """Retorna a hierarquia Projeto -> Datasets -> Tabelas/Views com métricas."""
    dados_path = Path(config.DADOS)
    
    datasets_dict: dict[str, dict[str, Any]] = {
        "dim": {"id": "dim", "nome": "Dimensões Cadastrais e Mestres", "icone": "folder", "tabelas": []},
        "fato": {"id": "fato", "nome": "Fatos Transacionais e Orçamentários", "icone": "folder", "tabelas": []},
        "vistas": {"id": "vistas", "nome": "Vistas Analíticas (Views DuckDB)", "icone": "auto_graph", "tabelas": []},
        "_ctl": {"id": "_ctl", "nome": "Controle, Ingestão e Qualidade", "icone": "settings", "tabelas": []},
    }

    for sub in ["dim", "fato", "_ctl"]:
        dir_p = dados_path / sub
        tabelas_do_dataset = [t for t in TABELAS.values() if t.camada == sub]
        nomes_conhecidos = {t.nome for t in tabelas_do_dataset}
        
        if dir_p.exists():
            for item in dir_p.iterdir():
                nome_tab = item.stem if item.is_file() else item.name
                if nome_tab not in nomes_conhecidos and not nome_tab.startswith("."):
                    nomes_conhecidos.add(nome_tab)

        for nome_tab in sorted(nomes_conhecidos):
            info_esquema = TABELAS.get(nome_tab)
            caminho_item = dir_p / f"{nome_tab}.parquet"
            caminho_dir = dir_p / nome_tab
            
            tamanho_bytes = 0
            modificado_em = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            if caminho_item.is_file():
                tamanho_bytes = caminho_item.stat().st_size
                modificado_em = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(caminho_item.stat().st_mtime))
            elif caminho_dir.is_dir():
                arquivos = list(caminho_dir.rglob("*.parquet"))
                tamanho_bytes = sum(f.stat().st_size for f in arquivos)
                if arquivos:
                    modificado_em = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(f.stat().st_mtime for f in arquivos)))

            # Contagem de linhas
            linhas = 0
            try:
                alvo = _obter_alvo_sql(sub, nome_tab)
                res = _consultar(f"SELECT COUNT(*) AS total FROM {alvo}")
                linhas = int(res[0]["total"]) if res else 0
            except Exception:
                linhas = 0
                
            descricao = info_esquema.descricao if info_esquema else ""

            datasets_dict[sub]["tabelas"].append({
                "id": nome_tab,
                "nome": nome_tab,
                "dataset": sub,
                "tipo": "tabela",
                "linhas": linhas,
                "tamanho_bytes": tamanho_bytes,
                "tamanho_formatado": _formatar_tamanho(tamanho_bytes),
                "modificado_em": modificado_em,
                "descricao": descricao,
            })

    for v_nome in sorted(DERIVADAS.keys()):
        linhas = 0
        try:
            res = _consultar(f"SELECT COUNT(*) AS total FROM {v_nome}")
            linhas = int(res[0]["total"]) if res else 0
        except Exception:
            linhas = 0

        datasets_dict["vistas"]["tabelas"].append({
            "id": v_nome,
            "nome": v_nome,
            "dataset": "vistas",
            "tipo": "view",
            "linhas": linhas,
            "tamanho_bytes": 0,
            "tamanho_formatado": "Virtual",
            "modificado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "descricao": "Vista relacional compilada em memória sobre dados DuckDB.",
        })

    return {
        "projeto": "painel-transparencia",
        "sgbd": "DuckDB Data Lakehouse (Parquet)",
        "datasets": list(datasets_dict.values()),
        "total_tabelas": sum(len(d["tabelas"]) for d in datasets_dict.values()),
    }


@router.get("/api/explorador/tabela/{dataset}/{tabela}/esquema")
def obter_esquema_tabela(dataset: str, tabela: str):
    """Retorna a estrutura de colunas e tipos de dados da tabela/view."""
    alvo = _obter_alvo_sql(dataset, tabela)
    try:
        linhas_desc = _consultar(f"DESCRIBE SELECT * FROM {alvo}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Tabela {tabela} não encontrada ou inacessível: {e}")

    colunas = []
    info_esquema = TABELAS.get(tabela)
    pks = set(info_esquema.campos_pk if info_esquema else ())

    for row in linhas_desc:
        nome_col = row.get("column_name") or row.get("Field") or list(row.values())[0]
        tipo_col = row.get("column_type") or row.get("Type") or list(row.values())[1]
        nulo = row.get("null") == "YES" if "null" in row else True
        is_pk = nome_col in pks or nome_col == "sk"
        colunas.append({
            "nome": nome_col,
            "tipo": str(tipo_col).upper(),
            "modo": "REQUIRED" if not nulo or is_pk else "NULLABLE",
            "is_pk": is_pk,
            "tipo_gcp": _mapear_tipo_gcp(str(tipo_col)),
        })

    return {
        "dataset": dataset,
        "tabela": tabela,
        "colunas": colunas,
        "total_colunas": len(colunas),
    }


@router.get("/api/explorador/tabela/{dataset}/{tabela}/detalhes")
def obter_detalhes_tabela(dataset: str, tabela: str):
    """Retorna metadados detalhados de armazenamento e partição."""
    alvo = _obter_alvo_sql(dataset, tabela)
    try:
        res_cnt = _consultar(f"SELECT COUNT(*) AS total FROM {alvo}")
        total_linhas = int(res_cnt[0]["total"]) if res_cnt else 0
    except Exception:
        total_linhas = 0

    if dataset in ("dim", "fato", "_ctl"):
        dados_path = Path(config.DADOS) / dataset
        caminho_arq = dados_path / f"{tabela}.parquet"
        caminho_dir = dados_path / tabela
        
        tam_bytes = 0
        mod_em = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        localizacao = f"dados/{dataset}/{tabela}"
        
        if caminho_arq.is_file():
            tam_bytes = caminho_arq.stat().st_size
            mod_em = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(caminho_arq.stat().st_mtime))
            localizacao = f"dados/{dataset}/{tabela}.parquet"
        elif caminho_dir.is_dir():
            arqs = list(caminho_dir.rglob("*.parquet"))
            tam_bytes = sum(f.stat().st_size for f in arqs)
            if arqs:
                mod_em = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(max(f.stat().st_mtime for f in arqs)))
            localizacao = f"dados/{dataset}/{tabela}/*.parquet ({len(arqs)} arquivos)"
            
        info_t = TABELAS.get(tabela)
        return {
            "dataset": dataset,
            "tabela": tabela,
            "tipo": "Tabela Física Parquet (Lakehouse)",
            "formato": "Apache Parquet (Compressão Snappy / ZSTD)",
            "localizacao": localizacao,
            "tamanho_bytes": tam_bytes,
            "tamanho_formatado": _formatar_tamanho(tam_bytes),
            "total_linhas": total_linhas,
            "modificado_em": mod_em,
            "particionamento": list(info_t.particoes) if info_t else [],
            "chaves_primarias": list(info_t.campos_pk) if info_t else ["sk"],
            "cadencia": info_t.cadencia if info_t else "Sob demanda",
            "descricao": info_t.descricao if info_t else "Sem descrição cadastrada.",
        }
    else:
        return {
            "dataset": "vistas",
            "tabela": tabela,
            "tipo": "Vista Analítica Virtual (SQL View)",
            "formato": "DuckDB Query Optimizer",
            "localizacao": f"vistas.{tabela}",
            "tamanho_bytes": 0,
            "tamanho_formatado": "Virtual / Em Memória",
            "total_linhas": total_linhas,
            "modificado_em": "Tempo Real",
            "particionamento": [],
            "chaves_primarias": [],
            "cadencia": "Tempo Real",
            "descricao": "Vista relacional derivada sobre dados de fato e dimensão.",
        }


@router.get("/api/explorador/tabela/{dataset}/{tabela}/dados")
def obter_dados_tabela(
    dataset: str,
    tabela: str,
    pagina: int = Query(1, ge=1),
    limite: int = Query(100, ge=1, le=500),
    busca: str | None = None,
):
    """Retorna linhas da tabela paginadas (100 por página) com contagem total."""
    alvo = _obter_alvo_sql(dataset, tabela)
    offset = (pagina - 1) * limite

    filtro_where = ""
    params: list[Any] = []
    if busca and busca.strip():
        try:
            linhas_desc = _consultar(f"DESCRIBE SELECT * FROM {alvo}")
            cols = [r.get("column_name") or r.get("Field") or list(r.values())[0] for r in linhas_desc]
            conds = [f"CAST({col} AS VARCHAR) ILIKE ?" for col in cols]
            filtro_where = f"WHERE {' OR '.join(conds)}"
            params = [f"%{busca.strip()}%"] * len(cols)
        except Exception:
            filtro_where = ""

    try:
        sql_total = f"SELECT COUNT(*) AS total FROM {alvo} {filtro_where}"
        total_res = _consultar(sql_total, params)
        total_linhas = int(total_res[0]["total"]) if total_res else 0
        
        sql_dados = f"SELECT * FROM {alvo} {filtro_where} LIMIT {limite} OFFSET {offset}"
        linhas = _consultar(sql_dados, params)
        col_names = list(linhas[0].keys()) if linhas else [r.get("column_name") or r.get("Field") or list(r.values())[0] for r in _consultar(f"DESCRIBE SELECT * FROM {alvo}")]

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao consultar dados da tabela {tabela}: {e}")

    total_paginas = max(1, (total_linhas + limite - 1) // limite)

    return {
        "dataset": dataset,
        "tabela": tabela,
        "pagina": pagina,
        "limite": limite,
        "total_linhas": total_linhas,
        "total_paginas": total_paginas,
        "colunas": col_names,
        "linhas": linhas,
    }


@router.post("/api/explorador/consulta")
def executar_consulta_sql(req: ConsultaRequisicao):
    """Executa consulta SQL (DuckDB) com proteção de somente leitura."""
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="A consulta SQL não pode estar vazia.")

    sql_upper = sql.upper()
    palavras_proibidas = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for palavra in palavras_proibidas:
        if f" {palavra} " in f" {sql_upper} " or sql_upper.startswith(f"{palavra} "):
            raise HTTPException(status_code=403, detail=f"Comando proibido: '{palavra}'. Apenas consultas SELECT são permitidas.")

    if "LIMIT" not in sql_upper:
        sql = f"{sql} LIMIT {min(req.limite, 2000)}"

    inicio = time.perf_counter()
    try:
        linhas = _consultar(sql)
        tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
        colunas = list(linhas[0].keys()) if linhas else []
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de sintaxe/execução SQL: {e}")

    return {
        "colunas": colunas,
        "linhas": linhas,
        "total_linhas": len(linhas),
        "tempo_ms": tempo_ms,
    }


@router.post("/api/explorador/exportar")
def exportar_dados_sql(req: ExportarRequisicao):
    """Exporta os resultados de uma consulta SQL para download em CSV ou JSON."""
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="A consulta SQL não pode estar vazia.")

    sql_upper = sql.upper()
    for palavra in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"]:
        if f" {palavra} " in f" {sql_upper} " or sql_upper.startswith(f"{palavra} "):
            raise HTTPException(status_code=403, detail=f"Comando proibido: '{palavra}'.")

    if "LIMIT" not in sql_upper:
        sql = f"{sql} LIMIT 100000"

    try:
        linhas = _consultar(sql)
        colunas = list(linhas[0].keys()) if linhas else []
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao executar exportação SQL: {e}")

    if req.formato.lower() == "json":
        conteudo = json.dumps(linhas, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=conteudo,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="extracao_dados.json"'},
        )
    else:
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(colunas)
        for r in linhas:
            writer.writerow([str(r.get(c, "")) if r.get(c) is not None else "" for c in colunas])
        conteudo_csv = stream.getvalue()
        return Response(
            content=conteudo_csv.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="extracao_dados.csv"'},
        )


def _formatar_tamanho(bytes_len: int) -> str:
    if bytes_len < 1024:
        return f"{bytes_len} B"
    elif bytes_len < 1024 * 1024:
        return f"{bytes_len / 1024:.1f} KB"
    elif bytes_len < 1024 * 1024 * 1024:
        return f"{bytes_len / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_len / (1024 * 1024 * 1024):.2f} GB"


def _mapear_tipo_gcp(tipo_duckdb: str) -> str:
    t = tipo_duckdb.upper()
    if "VARCHAR" in t or "TEXT" in t or "CHAR" in t:
        return "STRING"
    elif "INT" in t or "BIGINT" in t or "SMALLINT" in t:
        return "INT64"
    elif "DOUBLE" in t or "FLOAT" in t or "DECIMAL" in t or "NUMERIC" in t:
        return "FLOAT64"
    elif "BOOL" in t:
        return "BOOLEAN"
    elif "DATE" in t:
        return "DATE"
    elif "TIME" in t:
        return "TIMESTAMP"
    return "STRING"
