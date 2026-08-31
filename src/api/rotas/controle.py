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
