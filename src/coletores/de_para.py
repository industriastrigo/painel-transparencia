"""De-para entre identificadores de fonte e o código IBGE.

Este é o ponto que liga as duas metades do painel. Sem ele, o projeto sabe
quanto o município de código 3550308 gastou e sabe que Fulano é prefeito da
unidade eleitoral 71072 — e não consegue dizer que é a mesma cidade.

O casamento acontece em quatro passos, do mais seguro ao menos, e **cada linha
guarda por qual passo entrou**. Isso importa: um match aproximado que ninguém
consegue auditar depois é pior do que um município sem prefeito na tela.

    1. exceção   — grafias que nenhuma regra concilia (Mogi/Moji), escritas à mão
    2. exata     — mesma UF, chave estrita igual
    3. frouxa    — mesma UF, chave sem pontuação nem preposições
    4. aproximada — mesma UF, similaridade acima do limiar, e sem empate

Ambiguidade nunca vira chute. Se duas cidades da mesma UF disputam o mesmo
nome, ou se o segundo colocado está perto demais do primeiro, a linha fica
como pendência e aparece no relatório.
"""

from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

from ..nucleo import armazem
from ..nucleo.nomes import chave_estrita, chave_frouxa, similaridade
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.de_para")

FONTE = "tse"

# Grafias que nenhuma normalização concilia — divergência real de grafia
# oficial, não de formatação. Chave: (UF, nome como a fonte escreve).
EXCECOES: dict[tuple[str, str], str] = {
    ("SP", "MOJI MIRIM"): "Mogi Mirim",
    ("SP", "MOJI-MIRIM"): "Mogi Mirim",
    ("SP", "SAO LUIZ DO PARAITINGA"): "São Luiz do Paraitinga",
    ("SP", "FLORINEA"): "Florínea",
    ("SP", "EMBU"): "Embu das Artes",
    ("MG", "BRASOPOLIS"): "Brazópolis",
    ("MG", "PASSA VINTE"): "Passa-Vinte",
    ("MG", "SAO THOME DAS LETRAS"): "São Tomé das Letras",
    ("PA", "ELDORADO DOS CARAJAS"): "Eldorado do Carajás",
    ("PA", "SANTA IZABEL DO PARA"): "Santa Izabel do Pará",
    ("RN", "AUGUSTO SEVERO"): "Campo Grande",
    ("RN", "PRESIDENTE JUSCELINO"): "Serra Caiada",
    ("RS", "SANTANA DO LIVRAMENTO"): "Sant'Ana do Livramento",
    ("RS", "VESPASIANO CORREA"): "Vespasiano Correa",
    ("TO", "SAO VALERIO DA NATIVIDADE"): "São Valério",
    ("TO", "FORTALEZA DO TABOCAO"): "Tabocão",
    ("BA", "SANTA TERESINHA"): "Santa Teresinha",
    # Três pendências vistas na coleta de 25/08/2026. Duas são mudança de
    # nome sancionada por lei; a terceira é grafia divergente entre TSE e IBGE.
    ("BA", "CAMACA"): "Camacan",
    ("RN", "BOA SAUDE"): "Januário Cicco",
    ("RR", "SAO LUIZ"): "São Luiz",
    ("PB", "SAO DOMINGOS DE POMBAL"): "São Domingos",
    ("PB", "CAMPO DE SANTANA"): "Tacima",
    ("PB", "SERIDO"): "São Vicente do Seridó",
    ("PE", "IGUARACI"): "Iguaraci",
    ("PE", "LAGOA DO ITAENGA"): "Lagoa de Itaenga",
    ("SC", "PICARRAS"): "Balneário Piçarras",
    ("SC", "PRESIDENTE CASTELO BRANCO"): "Presidente Castello Branco",
    ("MS", "BATAGUASSU"): "Bataguassu",
    ("GO", "IPORA"): "Iporá",
}

LIMIAR_APROXIMADO = 0.88
MARGEM_DESEMPATE = 0.04


def _indexar_ibge(municipios: pd.DataFrame) -> dict:
    """Monta os índices por UF, uma vez, em vez de varrer 5.570 por consulta."""
    indice: dict = {}
    for _, m in municipios.iterrows():
        uf = str(m["sigla_uf"]).upper()
        alvo = indice.setdefault(uf, {"estrita": {}, "frouxa": {}, "lista": []})
        nome = str(m["nome"])
        cod = str(m["cod_ibge"])

        alvo["estrita"].setdefault(chave_estrita(nome), []).append((cod, nome))
        alvo["frouxa"].setdefault(chave_frouxa(nome), []).append((cod, nome))
        alvo["lista"].append((cod, nome, chave_frouxa(nome)))
    return indice


def _resolver(nome_origem: str, uf: str, indice: dict) -> dict:
    alvo = indice.get(uf.upper())
    if not alvo:
        return {"metodo": "sem_uf", "cod_ibge": None, "nome_ibge": None,
                "similaridade": 0.0}

    # 1. exceção conhecida
    nome_normalizado = chave_estrita(nome_origem).upper()
    esperado = EXCECOES.get((uf.upper(), nome_normalizado))
    if esperado:
        candidatos = alvo["estrita"].get(chave_estrita(esperado), [])
        if len(candidatos) == 1:
            cod, nome = candidatos[0]
            return {"metodo": "excecao", "cod_ibge": cod, "nome_ibge": nome,
                    "similaridade": 1.0}

    # 2. chave estrita
    candidatos = alvo["estrita"].get(chave_estrita(nome_origem), [])
    if len(candidatos) == 1:
        cod, nome = candidatos[0]
        return {"metodo": "exata", "cod_ibge": cod, "nome_ibge": nome,
                "similaridade": 1.0}
    if len(candidatos) > 1:
        return {"metodo": "ambiguo", "cod_ibge": None, "nome_ibge": None,
                "similaridade": 0.0}

    # 3. chave frouxa
    candidatos = alvo["frouxa"].get(chave_frouxa(nome_origem), [])
    if len(candidatos) == 1:
        cod, nome = candidatos[0]
        return {"metodo": "frouxa", "cod_ibge": cod, "nome_ibge": nome,
                "similaridade": 1.0}
    if len(candidatos) > 1:
        return {"metodo": "ambiguo", "cod_ibge": None, "nome_ibge": None,
                "similaridade": 0.0}

    # 4. aproximada, com desempate obrigatório
    chave = chave_frouxa(nome_origem)
    pontuados = sorted(
        ((similaridade(chave, ch), cod, nome) for cod, nome, ch in alvo["lista"]),
        reverse=True,
    )
    if not pontuados:
        return {"metodo": "sem_candidato", "cod_ibge": None, "nome_ibge": None,
                "similaridade": 0.0}

    melhor, cod, nome = pontuados[0]
    segundo = pontuados[1][0] if len(pontuados) > 1 else 0.0

    if melhor >= LIMIAR_APROXIMADO and (melhor - segundo) >= MARGEM_DESEMPATE:
        return {"metodo": "aproximada", "cod_ibge": cod, "nome_ibge": nome,
                "similaridade": round(melhor, 4)}

    return {"metodo": "pendente", "cod_ibge": None, "nome_ibge": None,
            "similaridade": round(melhor, 4)}


def construir(
    unidades: Iterable[Mapping[str, str]] | pd.DataFrame,
    fonte: str = FONTE,
    gravar: bool = True,
) -> pd.DataFrame:
    """Casa unidades eleitorais com municípios do IBGE.

    `unidades` = registros com `id_origem`, `nome` e `sigla_uf`.
    """
    df = (unidades if isinstance(unidades, pd.DataFrame)
          else pd.DataFrame(list(unidades)))
    if df.empty:
        log.warning("nenhuma unidade a casar")
        return pd.DataFrame()

    municipios = armazem.ler("dim_ente", filtro="nivel = 'municipio'",
                             colunas=["cod_ibge", "nome", "sigla_uf"])
    if municipios.empty:
        log.error("dim_ente sem municípios — rode o coletor do IBGE primeiro")
        return pd.DataFrame()

    indice = _indexar_ibge(municipios)

    linhas = []
    for _, u in df.iterrows():
        resultado = _resolver(str(u["nome"]), str(u["sigla_uf"]), indice)
        linhas.append({
            "fonte_origem": fonte,
            "id_origem": str(u["id_origem"]),
            "cod_ibge": resultado["cod_ibge"],
            "sigla_uf": str(u["sigla_uf"]).upper(),
            "nome_origem": str(u["nome"]),
            "nome_ibge": resultado["nome_ibge"],
            "metodo": resultado["metodo"],
            "similaridade": resultado["similaridade"],
        })

    resultado = pd.DataFrame(linhas)
    if gravar:
        armazem.mesclar("dim_de_para_ente", resultado, fonte)
    relatar(resultado)
    return resultado


def relatar(df: pd.DataFrame) -> dict[str, int]:
    """Diz o que casou e como. Pendência aparece no log, não some."""
    if df.empty:
        return {}

    contagem = df["metodo"].value_counts().to_dict()
    resolvidos = int(df["cod_ibge"].notna().sum())
    log.info("de-para: %d de %d unidades resolvidas (%.1f%%) — %s",
             resolvidos, len(df), 100 * resolvidos / len(df), contagem)

    aproximadas = df[df["metodo"] == "aproximada"]
    if not aproximadas.empty:
        log.warning("%d casamentos aproximados — confira em "
                    "dim_de_para_ente onde metodo='aproximada'", len(aproximadas))
        for _, l in aproximadas.head(10).iterrows():
            log.warning("  %s/%s → %s (%.2f)", l["sigla_uf"], l["nome_origem"],
                        l["nome_ibge"], l["similaridade"])

    pendentes = df[df["cod_ibge"].isna()]
    if not pendentes.empty:
        log.warning("%d unidades SEM código IBGE — o painel mostrará esses "
                    "mandatos sem ligá-los ao ente:", len(pendentes))
        for _, l in pendentes.head(15).iterrows():
            log.warning("  %s/%s (%s, melhor palpite %.2f)", l["sigla_uf"],
                        l["nome_origem"], l["metodo"], l["similaridade"])

    return contagem


def pendencias(fonte: str = FONTE) -> pd.DataFrame:
    """O que ainda não casou — para virar exceção escrita à mão."""
    df = armazem.ler("dim_de_para_ente", filtro=f"fonte_origem = '{fonte}'")
    if df.empty:
        return df
    return df[df["cod_ibge"].isna()][
        ["sigla_uf", "id_origem", "nome_origem", "metodo", "similaridade"]
    ].sort_values(["sigla_uf", "nome_origem"])


def mapa(fonte: str = FONTE) -> dict[str, str]:
    """Dicionário id_origem → cod_ibge, para os coletores usarem."""
    df = armazem.ler("dim_de_para_ente", filtro=f"fonte_origem = '{fonte}'",
                     colunas=["id_origem", "cod_ibge"])
    if df.empty:
        return {}
    validos = df[df["cod_ibge"].notna()]
    return dict(zip(validos["id_origem"].astype(str),
                    validos["cod_ibge"].astype(str)))
