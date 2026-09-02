"""Diagnóstico de erros da API de Transferências."""
from __future__ import annotations

class ErroTransferencias(RuntimeError):
    """Erro base para transferências constitucionais."""

def diagnosticar_erro(erro: Exception, recurso: str) -> str:
    return f"Transferências ({recurso}): {erro}"
