"""Módulo de Autenticação Google OAuth 2.0 para UAT e PRD.

Permite login com contas Google corporativas ou pessoais, gerenciamento
de sessão criptografada em cookie e controle de acesso baseado em lista
de e-mails autorizados (whitelist).
"""
from __future__ import annotations

import os
from typing import Any

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..nucleo.registro import obter as obter_log

log = obter_log("api.auth")

router = APIRouter(prefix="/auth", tags=["Autenticação"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")


def emails_permitidos() -> set[str]:
    """Retorna o conjunto de e-mails autorizados em caixa baixa."""
    raw = os.getenv("EMAILS_PERMITIDOS", "")
    if not raw.strip():
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


oauth = OAuth()
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
else:
    log.warning("GOOGLE_CLIENT_ID ou GOOGLE_CLIENT_SECRET não configurados. Autenticação Google indisponível.")


@router.get("/login", summary="Iniciar login com Google")
async def login(request: Request) -> Any:
    """Inicia o fluxo de autorização OAuth 2.0 redirecionando para o Google."""
    if "google" not in oauth._registry:
        return HTMLResponse(
            """<!doctype html><html><head><meta charset="utf-8"><title>Configuração Pendente</title>
            <style>body{font-family:sans-serif;background:#0d1117;color:#c9d1d9;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
            .card{background:#161b22;padding:32px;border-radius:8px;border:1px solid #30363d;max-width:480px;text-align:center}
            h2{color:#f85149}code{background:#21262d;padding:3px 6px;border-radius:4px}</style></head>
            <body><div class="card"><h2>OAuth Não Configurado</h2>
            <p>As variáveis <code>GOOGLE_CLIENT_ID</code> e <code>GOOGLE_CLIENT_SECRET</code> precisam ser definidas no ambiente.</p>
            </div></body></html>""",
            status_code=500,
        )

    # Determina a URL de retorno (callback)
    if BASE_URL:
        redirect_uri = f"{BASE_URL}/auth/callback"
    else:
        redirect_uri = str(request.url_for("auth_callback"))

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", summary="Retorno do Google OAuth")
async def auth_callback(request: Request) -> Any:
    """Recebe o código do Google, troca por token e valida o usuário."""
    if "google" not in oauth._registry:
        raise HTTPException(status_code=500, detail="Google OAuth não configurado no servidor")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        log.error("Erro ao obter access token do Google: %s", e)
        raise HTTPException(status_code=400, detail=f"Falha na autenticação com Google: {e}")

    user_info = token.get("userinfo")
    if not user_info:
        log.error("Informações de usuário ausentes no token")
        raise HTTPException(status_code=400, detail="Não foi possível obter dados do perfil Google")

    email = str(user_info.get("email", "")).strip().lower()
    nome = user_info.get("name", "Usuário")
    foto = user_info.get("picture", "")

    permitidos = emails_permitidos()
    if permitidos and email not in permitidos:
        log.warning("Acesso negado para %s (não listado em EMAILS_PERMITIDOS)", email)
        return HTMLResponse(
            f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
            <title>Acesso Não Autorizado — UAT</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                       background: #0f172a; color: #f8fafc; display: flex; justify-content: center;
                       align-items: center; min-height: 100vh; margin: 0; padding: 20px; }}
                .box {{ background: #1e293b; padding: 36px; border-radius: 12px; max-width: 460px;
                       text-align: center; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                h2 {{ color: #ef4444; margin-top: 0; font-size: 22px; }}
                p {{ color: #94a3b8; font-size: 15px; line-height: 1.6; }}
                .badge {{ display: inline-block; background: #334155; color: #38bdf8; padding: 4px 10px;
                         border-radius: 6px; font-family: monospace; font-size: 14px; margin: 12px 0; }}
                a.btn {{ display: inline-block; background: #3b82f6; color: #fff; text-decoration: none;
                        padding: 10px 20px; border-radius: 8px; font-weight: 500; margin-top: 18px; }}
                a.btn:hover {{ background: #2563eb; }}
            </style></head>
            <body><div class="box">
                <h2>⛔ Acesso Não Autorizado</h2>
                <p>O ambiente de <b>UAT (Testes)</b> é restrito a usuários autorizados.</p>
                <div>Conta conectada:</div>
                <div class="badge">{email}</div>
                <p>Se você deveria ter acesso, solicite a inclusão do seu e-mail ao administrador do projeto.</p>
                <a href="/auth/logout" class="btn">Tentar outra conta Google</a>
            </div></body></html>""",
            status_code=403,
        )

    # Armazena na sessão
    request.session["usuario"] = {
        "email": email,
        "nome": nome,
        "foto": foto,
    }
    log.info("Usuário autenticado com sucesso: %s", email)

    return RedirectResponse(url="/", status_code=303)


@router.get("/logout", summary="Encerrar sessão")
async def logout(request: Request) -> RedirectResponse:
    """Limpa a sessão do usuário e redireciona para a tela de login."""
    usuario = request.session.get("usuario", {}).get("email", "anônimo")
    request.session.clear()
    log.info("Logout executado para %s", usuario)
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/me", summary="Dados do usuário logado")
async def obter_usuario_logado(request: Request) -> JSONResponse:
    """Devolve as informações do usuário armazenadas na sessão."""
    usuario = request.session.get("usuario")
    if not usuario:
        return JSONResponse({"autenticado": False, "usuario": None})
    return JSONResponse({"autenticado": True, "usuario": usuario})
