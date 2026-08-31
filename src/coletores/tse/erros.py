"""Diagnóstico de erros do TSE."""
from __future__ import annotations

class ErroTSE(RuntimeError):
    """Erro base para chamadas ao TSE."""

def diagnosticar_erro(erro: Exception, recurso: str, ano: int) -> str:
    return f"TSE ({recurso}/{ano}): {erro}"
