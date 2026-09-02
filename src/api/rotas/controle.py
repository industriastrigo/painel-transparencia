"""Rotas de Controle, Configuração, Tarefas e Recarga."""
from __future__ import annotations

import json
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import _consultar, recarregar_views
from .. import tarefas
from ...coletores import orquestrador
from ...nucleo import config, controle, segredos

router = APIRouter(tags=["controle"])

@router.get("/api/saude")
def saude():
    df = controle.situacao()
    return {
        "situacao": "ok",
        "data": date.today().isoformat(),
        "fontes": [] if df.empty else json.loads(df.to_json(orient="records")),
    }

class PedidoDeColeta(BaseModel):
    fontes: list[str] = Field(..., min_length=1)
    ano: int | None = None
    anos: list[int] | None = None
    nivel: str = "estado"
    uf: str | None = None
    trabalhadores: int = Field(6, ge=1, le=16)
    intervalo: float = Field(0.15, ge=0.0, le=5.0)
    sem_malhas: bool = False
    refazer_vazios: bool = False
    refazer_tudo: bool = False

class ChaveDeApi(BaseModel):
    chave: str = Field(..., min_length=1, max_length=500)

@router.get("/api/config")
def configuracao():
    chave = config.CHAVE_PORTAL_TRANSPARENCIA
    return {
        "portal_transparencia": {
            "configurada": bool(chave),
            "mascara": segredos.mascarar(chave),
            "onde_obter": "portaldatransparencia.gov.br/api-de-dados/cadastrar-email",
        }
    }

@router.post("/api/config/chave-portal")
def salvar_chave_portal(corpo: ChaveDeApi):
    try:
        chave = segredos.aplicar_chave_portal(corpo.chave)
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro

    aceita, mensagem = segredos.testar_chave_portal(chave)
    return {
        "salva": True,
        "mascara": segredos.mascarar(chave),
        "validada": aceita,
        "mensagem": mensagem,
    }

@router.get("/api/coleta/catalogo")
def catalogo_de_coleta():
    return tarefas.catalogo()

@router.post("/api/coleta", status_code=202)
def iniciar_coleta(pedido: PedidoDeColeta):
    desconhecidas = [f for f in pedido.fontes if f not in orquestrador.ORDEM]
    if desconhecidas:
        raise HTTPException(400, f"fonte desconhecida: {desconhecidas}")

    opcoes = orquestrador.Opcoes(
        ano=pedido.ano, anos=pedido.anos, nivel=pedido.nivel, uf=pedido.uf,
        trabalhadores=pedido.trabalhadores, intervalo=pedido.intervalo,
        sem_malhas=pedido.sem_malhas, refazer_vazios=pedido.refazer_vazios,
        refazer_tudo=pedido.refazer_tudo,
    )
    try:
        tarefa = tarefas.iniciar(pedido.fontes, opcoes)
    except tarefas.TarefaEmAndamento as erro:
        raise HTTPException(409, str(erro)) from erro
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro
    return tarefa.como_dicionario()

@router.get("/api/coleta")
def coleta_corrente():
    tarefa = tarefas.ultima()
    return tarefa.como_dicionario() if tarefa else {"situacao": "nenhuma"}

@router.get("/api/coleta/{id_tarefa}")
def coleta_por_id(id_tarefa: int):
    tarefa = tarefas.por_id(id_tarefa)
    if not tarefa:
        raise HTTPException(404, "tarefa não encontrada")
    return tarefa.como_dicionario()

@router.post("/api/recarregar")
def rota_recarregar():
    criadas = recarregar_views()
    return {"recarregadas": len(criadas), "views": criadas}


@router.get("/api/catalogo")
def obter_catalogo_tabelas(
    tabela: str | None = None,
    camada: str | None = None,
    ano: int | None = None,
    orgao: str | None = None,
    status: str | None = None,
):
    """Retorna inventário estruturado do acervo de dados com uma linha por tabela × ano e KPIs."""
    from ...nucleo.catalogo import salvar_catalogo, construir_catalogo
    
    condicoes = []
    params = []
    
    if tabela:
        condicoes.append("tabela ILIKE ?")
        params.append(f"%{tabela}%")
    if camada:
        condicoes.append("camada = ?")
        params.append(camada.lower())
    if ano:
        condicoes.append("ano = ?")
        params.append(ano)
    if orgao:
        condicoes.append("orgao_origem ILIKE ?")
        params.append(f"%{orgao}%")
    if status:
        condicoes.append("status_completude ILIKE ?")
        params.append(f"%{status}%")

    where_sql = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    
    try:
        linhas = _consultar(f"""
            SELECT * FROM dim_catalogo_tabela
            {where_sql}
            ORDER BY camada, tabela, ano DESC NULLS LAST
        """, params)
        resumo_geral = _consultar("""
            SELECT 
                COUNT(DISTINCT tabela) AS total_tabelas,
                COUNT(DISTINCT CASE WHEN camada = 'dim' THEN tabela END) AS total_dim,
                COUNT(DISTINCT CASE WHEN camada = 'fato' THEN tabela END) AS total_fato,
                SUM(total_linhas) AS total_linhas_global,
                COUNT(CASE WHEN status_completude = 'total' OR status_completude = 'total_ufs' THEN 1 END) AS qtd_total,
                COUNT(CASE WHEN status_completude ILIKE 'parcial%' THEN 1 END) AS qtd_parcial,
                COUNT(CASE WHEN status_completude ILIKE 'amostra%' THEN 1 END) AS qtd_amostra,
                COUNT(CASE WHEN status_completude = 'vigente' THEN 1 END) AS qtd_vigente,
                MIN(ano) AS ano_min,
                MAX(ano) AS ano_max,
                COUNT(DISTINCT ano) AS total_anos_distintos
            FROM dim_catalogo_tabela
        """)
    except Exception:
        # Se ainda não foi lida na view, gera sob demanda
        salvar_catalogo()
        recarregar_views()
        linhas = _consultar(f"""
            SELECT * FROM dim_catalogo_tabela
            {where_sql}
            ORDER BY camada, tabela, ano DESC NULLS LAST
        """, params)
        resumo_geral = _consultar("""
            SELECT 
                COUNT(DISTINCT tabela) AS total_tabelas,
                COUNT(DISTINCT CASE WHEN camada = 'dim' THEN tabela END) AS total_dim,
                COUNT(DISTINCT CASE WHEN camada = 'fato' THEN tabela END) AS total_fato,
                SUM(total_linhas) AS total_linhas_global,
                COUNT(CASE WHEN status_completude = 'total' OR status_completude = 'total_ufs' THEN 1 END) AS qtd_total,
                COUNT(CASE WHEN status_completude ILIKE 'parcial%' THEN 1 END) AS qtd_parcial,
                COUNT(CASE WHEN status_completude ILIKE 'amostra%' THEN 1 END) AS qtd_amostra,
                COUNT(CASE WHEN status_completude = 'vigente' THEN 1 END) AS qtd_vigente,
                MIN(ano) AS ano_min,
                MAX(ano) AS ano_max,
                COUNT(DISTINCT ano) AS total_anos_distintos
            FROM dim_catalogo_tabela
        """)

    tot = resumo_geral[0] if resumo_geral else {}
    total_linhas_filtradas = sum(int(l.get("total_linhas") or 0) for l in linhas)
    
    return {
        "kpis": {
            "total_tabelas": int(tot.get("total_tabelas") or 0),
            "total_dim": int(tot.get("total_dim") or 0),
            "total_fato": int(tot.get("total_fato") or 0),
            "total_linhas_global": int(tot.get("total_linhas_global") or 0),
            "qtd_total": int(tot.get("qtd_total") or 0),
            "qtd_parcial": int(tot.get("qtd_parcial") or 0),
            "qtd_amostra": int(tot.get("qtd_amostra") or 0),
            "qtd_vigente": int(tot.get("qtd_vigente") or 0),
            "ano_min": int(tot["ano_min"]) if tot.get("ano_min") is not None else 1996,
            "ano_max": int(tot["ano_max"]) if tot.get("ano_max") is not None else 2026,
            "total_anos_distintos": int(tot.get("total_anos_distintos") or 0),
        },
        "total_registros_catalogo": len(linhas),
        "total_linhas_filtradas": total_linhas_filtradas,
        "itens": linhas,
    }


@router.post("/api/catalogo/atualizar")
def atualizar_catalogo_acervo():
    """Gera novamente o arquivo Parquet e atualiza as views DuckDB do catálogo."""
    from ...nucleo.catalogo import salvar_catalogo
    p = salvar_catalogo()
    criadas = recarregar_views()
    return {"status": "ok", "caminho": str(p), "views_recarregadas": len(criadas)}


