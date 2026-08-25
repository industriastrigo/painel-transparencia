"""Exceções do projeto.

`ConfiguracaoAusente` existe por causa de um relatório enganoso: o coletor de
emendas não tem a chave da CGU, registra um aviso, devolve zero e o painel
mostrava a fonte como **ok**. Não é ok — é uma fonte que não coletou nada e
que só volta a funcionar depois de uma ação sua.

Também não é erro: não houve falha nenhuma. É um terceiro estado —
"falta configurar" — e ele merece nome próprio, para a tela poder dizer
exatamente o que fazer em vez de mostrar um tique verde.
"""

from __future__ import annotations


class ConfiguracaoAusente(RuntimeError):
    """Falta algo que só o usuário pode providenciar (chave, credencial)."""

    def __init__(self, mensagem: str, como_resolver: str = ""):
        super().__init__(mensagem)
        self.como_resolver = como_resolver

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} {self.como_resolver}".strip()
