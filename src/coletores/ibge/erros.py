"""Diagnóstico de erros do IBGE."""
from __future__ import annotations

class ErroIBGE(RuntimeError):
    """Erro base para chamadas ao IBGE."""

def diagnosticar_erro(erro: Exception, recurso: str) -> str:
    return f"IBGE ({recurso}): {erro}"
