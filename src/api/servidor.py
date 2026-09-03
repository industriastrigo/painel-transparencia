"""API de leitura do Painel da Transparência.

FastAPI só lê as views DuckDB sobre os Parquet — nenhuma rota chama API
externa em tempo de renderização. Se a fonte estiver fora do ar, o painel
continua respondendo com o último dado coletado, e o rodapé mostra a data.
"""
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from ..nucleo import config
from ..nucleo.registro import obter as obter_log
from .auth import router as auth_router
from .db import _consultar, _registros, con, marcar_dados_alterados, recarregar_views, reiniciar_conexao
from .rotas import controle, entes, executivo, legislativo, politicos, explorador, judiciario, mp


log = obter_log("api.servidor")

app = FastAPI(
    title="Painel da Transparência",
    description="Dados políticos, socioeconômicos e orçamentários do Brasil",
    version="1.0.0",
)

def exige_autenticacao() -> bool:
    return os.getenv("EXIGE_AUTH", "0").strip() == "1"


async def verificar_autenticacao(request: Request, call_next):
    caminho = request.url.path
    
    # Rotas sempre liberadas (login, callback OAuth, documentação, saúde)
    rotas_publicas = (
        "/auth/login",
        "/auth/callback",
        "/auth/logout",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/saude",
        "/favicon.ico",
    )
    
    if not exige_autenticacao() or any(caminho.startswith(p) for p in rotas_publicas):
        return await call_next(request)
    
    # Obtém a sessão de forma resiliente
    session = request.scope.get("session", {}) if "session" in request.scope else {}
    usuario = session.get("usuario")
    if not usuario:
        # Se for chamada de API, devolve 401
        if caminho.startswith("/api/"):
            return JSONResponse(
                {"erro": "Não autenticado", "login_url": "/auth/login"},
                status_code=401
            )
        # Se for navegação web (HTML/Assets), redireciona para login
        return RedirectResponse(url="/auth/login")
    
    return await call_next(request)


# Adiciona o middleware de verificação (executado após a decodificação da sessão)
from starlette.middleware.base import BaseHTTPMiddleware
app.add_middleware(BaseHTTPMiddleware, dispatch=verificar_autenticacao)

# 1. Configuração de Sessão Criptografada (Cookie) - Camada mais externa
SESSION_SECRET = os.getenv("SESSION_SECRET_KEY", "chave-secreta-padrao-dev-trocar-em-uat-prd")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=86400 * 7,  # 7 dias de sessão
    same_site="lax",
    https_only=os.getenv("HTTPS_ONLY", "0") == "1",
)

# 2. Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Router de Autenticação
app.include_router(auth_router)


# 4. Inicialização de dados e views no startup
@app.on_event("startup")
def inicializar_dados():
    """Garante auto-semeadura dos dados essenciais e criação das views DuckDB."""
    try:
        from ..coletores.semeador import semear_se_vazio
        semear_se_vazio()
        recarregar_views()
    except Exception as erro:
        log.warning("Aviso durante inicialização de dados: %s", erro)


# 5. Rota de saúde para o Cloud Run / Balanceadores
@app.get("/saude", tags=["Monitoramento"])
def saude() -> dict:
    """Verifica se o servidor e as views estão operacionais."""
    return {"status": "ok", "ambiente": os.getenv("AMB", "dev"), "auth_ativa": exige_autenticacao()}


# 6. Inclusão dos routers de dados
app.include_router(controle.router)
app.include_router(executivo.router)
app.include_router(politicos.router)
app.include_router(legislativo.router)
app.include_router(entes.router)
app.include_router(explorador.router)
app.include_router(judiciario.router)
app.include_router(mp.router)


# 7. Ícone de favoritos e arquivos estáticos do frontend
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icone = Path(config.RAIZ) / "publico" / "ativos" / "logos" / "icone_trigo_transparente.png"
    if icone.exists():
        from fastapi.responses import FileResponse
        return FileResponse(icone, media_type="image/png")
    return JSONResponse({"erro": "sem favicon"}, status_code=204)

PUBLICO = Path(config.RAIZ) / "publico"
if PUBLICO.exists():
    app.mount("/", StaticFiles(directory=PUBLICO, html=True), name="publico")

@app.exception_handler(404)
def nao_encontrado(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    return JSONResponse({"erro": "recurso não encontrado"}, status_code=404)
