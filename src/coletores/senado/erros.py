"""Diagnóstico de erros do Senado Federal."""
from __future__ import annotations

class ErroSenado(RuntimeError):
    """Erro base para chamadas ao Senado."""

def diagnosticar_erro(erro: Exception, recurso: str) -> str:
    return f"Senado ({recurso}): {erro}"
