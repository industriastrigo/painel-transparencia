"""Diagnóstico e classificação de erros da API SICONFI."""
from __future__ import annotations

class ErroSiconfi(RuntimeError):
    """Exceção base para falhas do SICONFI."""

ErroSICONFI = ErroSiconfi
FalhaExtracaoSICONFI = ErroSiconfi

class ErroInstabilidadeSiconfi(ErroSiconfi):
    """Servidor do Tesouro caiu ou retornou 502/503/504 ou conexão abortada."""

class ErroRateLimitSiconfi(ErroSiconfi):
    """API do Tesouro retornou HTTP 429 (Muitas requisições)."""

class EnteNaoHomologou(ErroSiconfi):
    """O ente não entregou ou não homologou o demonstrativo no exercício."""

def diagnosticar_erro(erro: Exception, cod_ibge: str, recurso: str, ano: int) -> str:
    msg = str(erro)
    if "502" in msg or "Bad Gateway" in msg:
        return f"SICONFI ({recurso}/{ano}) para ente {cod_ibge}: Servidor do Tesouro em instabilidade temporária (HTTP 502)."
    if "429" in msg or "Too Many Requests" in msg:
        return f"SICONFI ({recurso}/{ano}) para ente {cod_ibge}: Limite de taxa atingido (HTTP 429). Reduza trabalhadores ou aumente intervalo."
    if "Connection aborted" in msg or "Remote end closed" in msg:
        return f"SICONFI ({recurso}/{ano}) para ente {cod_ibge}: Conexão encerrada pelo servidor do Tesouro."
    if "11001" in msg or "getaddrinfo failed" in msg:
        return f"SICONFI ({recurso}/{ano}) para ente {cod_ibge}: Falha temporária de resolução DNS."
    return f"SICONFI ({recurso}/{ano}) para ente {cod_ibge}: {msg}"