"""Chaves determinísticas e hash de registro.

Regra do projeto: nenhuma tabela usa chave sequencial. A chave primária `sk`
é o md5 dos campos de negócio, então reprocessar o mesmo dado duas vezes
produz a mesma linha — o pipeline é idempotente por construção e não depende
de ninguém lembrar o que já rodou.
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Sequence

SEPARADOR = "|"
NULO = "\x00"


def _texto(valor: Any) -> str:
    if valor is None:
        return NULO
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, float):
        # evita que 1.0 e 1 gerem chaves diferentes
        return format(valor, ".10g")
    return str(valor).strip()


def concatenar(valores: Iterable[Any]) -> str:
    return SEPARADOR.join(_texto(v) for v in valores)


def sk(registro: Mapping[str, Any], campos_pk: Sequence[str]) -> str:
    """Chave primária determinística (32 hex) a partir dos campos de negócio."""
    if not campos_pk:
        raise ValueError("campos_pk não pode ser vazio")
    faltando = [c for c in campos_pk if c not in registro]
    if faltando:
        raise KeyError(f"campos da PK ausentes no registro: {faltando}")
    bruto = concatenar(registro[c] for c in campos_pk)
    return hashlib.md5(bruto.encode("utf-8")).hexdigest()


def hash_registro(
    registro: Mapping[str, Any], campos_negocio: Sequence[str] | None = None
) -> str:
    """Hash curto (16 hex) do conteúdo de negócio da linha.

    Serve para detectar alteração real: sem ele, todo re-run marcaria a linha
    inteira como alterada e `_atualizado_em` perderia o sentido.
    Colunas de controle (prefixo `_`) nunca entram no hash.
    """
    campos = campos_negocio or [c for c in registro if not c.startswith("_")]
    bruto = concatenar(registro[c] for c in sorted(campos))
    return hashlib.md5(bruto.encode("utf-8")).hexdigest()[:16]
