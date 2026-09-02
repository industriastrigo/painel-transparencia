"""Diagnóstico de erros da Câmara dos Deputados."""
from __future__ import annotations

class ErroCamara(RuntimeError):
    """Erro base para chamadas da Câmara."""

class ErroDownloadArquivo(ErroCamara):
    """Arquivo em lote CSV ou ZIP indisponível."""

def diagnosticar_erro(erro: Exception, recurso: str, ano: int | None = None) -> str:
    msg = str(erro)
    if "404" in msg:
        return f"Câmara ({recurso}/{ano}): Arquivo em lote ou endpoint ainda não disponível no portal de dados abertos."
    if "ParserError" in msg or "truncado" in msg:
        return f"Câmara ({recurso}/{ano}): Download do arquivo foi corrompido ou truncado pela metade."
    return f"Câmara ({recurso}/{ano}): {msg}"
