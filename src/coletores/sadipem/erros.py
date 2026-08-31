"""Diagnóstico de erros do SADIPEM."""
from __future__ import annotations

class ErroSADIPEM(RuntimeError):
    """Erro base para chamadas ao SADIPEM."""

def diagnosticar_erro(erro: Exception, uf: str) -> str:
    return f"SADIPEM ({uf}): {erro}"
