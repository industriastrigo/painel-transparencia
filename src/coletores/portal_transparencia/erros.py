"""Diagnóstico de erros do Portal da Transparência."""
from __future__ import annotations
from ...nucleo.erros import ConfiguracaoAusente

class ErroPortalTransparencia(RuntimeError):
    """Erro base para chamadas ao Portal da Transparência."""

def diagnosticar_erro(erro: Exception, recurso: str, ano: int) -> str:
    msg = str(erro)
    if "401" in msg or "403" in msg or "sem_chave" in msg:
        return f"Portal da Transparência ({recurso}/{ano}): Chave de API inválida, ausente ou expirada."
    if "429" in msg:
        return f"Portal da Transparência ({recurso}/{ano}): Limite de requisições excedido."
    return f"Portal da Transparência ({recurso}/{ano}): {msg}"
