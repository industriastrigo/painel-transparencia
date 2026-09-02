"""Diagnóstico de erros do Tesouro."""
from __future__ import annotations

class ErroTesouro(RuntimeError):
    """Erro base para chamadas ao Tesouro."""

def diagnosticar_erro(erro: Exception, recurso: str, ano: int) -> str:
    return f"Tesouro Custos ({recurso}/{ano}): {erro}"
