"""Normalização de nomes de município.

O TSE e o IBGE escrevem o mesmo município de formas diferentes, e a diferença
raramente é aleatória — segue padrões:

    IBGE                          TSE
    Sant'Ana do Livramento        SANTANA DO LIVRAMENTO
    Espigão D'Oeste               ESPIGAO DO OESTE
    Biritiba-Mirim                BIRITIBA MIRIM
    Olho-d'Água do Borges         OLHO D'AGUA DO BORGES
    Mogi Mirim                    MOJI MIRIM

Por isso são duas chaves, não uma:

- **estrita**: só tira acento e caixa. Casa a maioria e não corre risco.
- **frouxa**: tira também pontuação, espaços e preposições (de/da/do/das/dos/e).
  "Espigão D'Oeste" e "ESPIGAO DO OESTE" viram ambos `espigaooeste`.

A frouxa é agressiva de propósito, e por isso só é usada depois da estrita e
sempre dentro da mesma UF. Grafias genuinamente distintas (Mogi/Moji) não
cedem a nenhuma regra e ficam na tabela de exceções, que é explícita e
auditável — melhor do que um algoritmo esperto errando em silêncio.
"""

from __future__ import annotations

import re
import unicodedata

PREPOSICOES = {"de", "da", "do", "das", "dos", "e", "d"}

_NAO_ALFANUM = re.compile(r"[^a-z0-9\s]")
_ESPACOS = re.compile(r"\s+")


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def chave_estrita(nome: str) -> str:
    """Minúsculas, sem acento, pontuação virando espaço, espaços colapsados."""
    if not nome:
        return ""
    base = sem_acento(str(nome)).lower()
    base = _NAO_ALFANUM.sub(" ", base)
    return _ESPACOS.sub(" ", base).strip()


def chave_frouxa(nome: str) -> str:
    """Sem preposições e sem espaços — absorve hífen, apóstrofo e 'do/da/de'."""
    estrita = chave_estrita(nome)
    if not estrita:
        return ""
    palavras = [p for p in estrita.split(" ") if p not in PREPOSICOES]
    return "".join(palavras) or estrita.replace(" ", "")


def similaridade(a: str, b: str) -> float:
    """Razão de Levenshtein normalizada, entre 0 e 1.

    Escrita à mão em vez de `difflib.SequenceMatcher` porque o SequenceMatcher
    usa blocos comuns e é generoso demais com nomes curtos: "Bonito" e
    "Brejinho" saem parecidos demais para o gosto de quem não quer chute.
    """
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0

    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(
                anterior[j] + 1,        # remoção
                atual[j - 1] + 1,       # inserção
                anterior[j - 1] + (ca != cb),  # substituição
            ))
        anterior = atual

    distancia = anterior[-1]
    return 1.0 - distancia / max(len(a), len(b))
