"""Coletor TSE — quem ocupa cada cargo, do presidente ao vereador.

Regra do projeto: a carga vem dos arquivos em LOTE do Portal de Dados Abertos
(CSV zipado por ano/UF). A API do DivulgaCandContas é usada só para consulta
pontual, com intervalo entre requisições, porque bloqueia IP em rajada.

Limite honesto de escopo, que precisa estar visível no painel: votação nominal
estruturada só existe no Congresso Nacional. Para estadual e municipal este
coletor entrega CADASTRO (quem é, por qual partido, com quantos votos) — não
o histórico de votos em projetos. São 27 assembleias e 5.570 câmaras, cada uma
com seu próprio site e formato.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd

from ..nucleo import armazem, config, controle, rede, tabela
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import opcional, texto
from . import de_para

log = obter_log("coletores.tse")

FONTE = "tse"

SITUACOES_ELEITO = {"ELEITO", "ELEITO POR QP", "ELEITO POR MÉDIA", "MÉDIA"}

# Códigos do TSE. Faltavam os vices e os suplentes: `cargo_12` vazava na
# interface como se fosse um cargo, com 5.566 ocupantes — o mesmo número de
# prefeitos, porque era o vice-prefeito.
CARGOS = {
    "1": ("presidente", "0"),
    "2": ("vice_presidente", "0"),
    "3": ("governador", "uf"),
    "4": ("vice_governador", "uf"),
    "5": ("senador", "uf"),
    "6": ("deputado_federal", "uf"),
    "7": ("deputado_estadual", "uf"),
    "8": ("deputado_distrital", "uf"),
    "9": ("suplente_senador_1", "uf"),
    "10": ("suplente_senador_2", "uf"),
    "11": ("prefeito", "municipio"),
    "12": ("vice_prefeito", "municipio"),
    "13": ("vereador", "municipio"),
}


def catalogo_cargos() -> int:
    linhas = [{
        "cod_cargo": codigo,
        "cargo": nome,
        "nivel_ente": nivel,
        "poder": "executivo" if nome in ("presidente", "governador", "prefeito")
                 else "legislativo",
    } for codigo, (nome, nivel) in CARGOS.items()]
    armazem.mesclar("dim_cargo", linhas, FONTE)
    return len(linhas)


_cache: dict[int, pd.DataFrame] = {}


def _baixar_consulta_cand(ano: int) -> pd.DataFrame:
    """O zip do TSE tem centenas de MB. Baixa uma vez por execução."""
    if ano in _cache:
        return _cache[ano]

    url = f"{config.TSE_DADOS}/consulta_cand/consulta_cand_{ano}.zip"
    log.info("baixando %s (arquivo grande, pode levar minutos)", url)
    conteudo = rede.buscar(FONTE, url, formato="binario")

    # O ZIP traz um CSV por UF e mais um BRASIL.csv que repete todos —
    # somá-lo dobraria cada candidatura.
    _cache[ano] = tabela.de_zip(conteudo, origem=f"TSE {ano}",
                                ignorar=("BRASIL",))
    return _cache[ano]


def _codigos_uf() -> dict[str, str]:
    """Sigla da UF → código IBGE de 2 dígitos."""
    df = armazem.ler("dim_ente", filtro="nivel = 'estado'",
                     colunas=["cod_ibge", "sigla_uf"])
    if df.empty:
        return {}
    return dict(zip(df["sigla_uf"].astype(str), df["cod_ibge"].astype(str)))


def construir_de_para(eleitos: pd.DataFrame) -> dict[str, str]:
    """Extrai as unidades eleitorais municipais e as casa com o IBGE."""
    cargos_municipais = {c for c, (_, nivel) in CARGOS.items()
                         if nivel == "municipio"}
    municipais = eleitos[eleitos["CD_CARGO"].astype(str).isin(cargos_municipais)]
    if municipais.empty:
        return {}

    unidades = (municipais[["SG_UE", "NM_UE", "SG_UF"]]
                .drop_duplicates("SG_UE")
                .rename(columns={"SG_UE": "id_origem", "NM_UE": "nome",
                                 "SG_UF": "sigla_uf"}))
    log.info("TSE: casando %d unidades eleitorais municipais com o IBGE",
             len(unidades))
    de_para.construir(unidades, fonte=FONTE)
    return de_para.mapa(FONTE)


def coletar_eleitos(ano: int) -> int:
    df = _baixar_consulta_cand(ano)
    if df.empty:
        return 0

    situacao = df.get("DS_SIT_TOT_TURNO", pd.Series(dtype=str)).str.upper()
    eleitos = df[situacao.isin(SITUACOES_ELEITO)].copy()
    log.info("TSE %d: %d candidaturas, %d eleitos", ano, len(df), len(eleitos))

    if eleitos.empty and len(df):
        # Candidaturas registradas e nenhum eleito significa, quase sempre,
        # que a eleição ainda não foi apurada. Dizer isso é melhor do que
        # deixar dois "lote vazio, nada a fazer" no log.
        log.warning(
            "TSE %d tem %d candidaturas mas nenhum eleito — a apuração de %d "
            "provavelmente ainda não saiu. Use um ano de eleição já apurada "
            "(ex.: --anos 2022 2024).", ano, len(df), ano)
        controle.gravar_marca(FONTE, f"eleitos_{ano}", None, 0,
                              situacao="nao_apurado",
                              detalhe=f"{len(df)} candidaturas, 0 eleitos")
        return 0

    ue_para_ibge = construir_de_para(eleitos)
    uf_para_ibge = _codigos_uf()

    politicos, mandatos, desconhecidos = [], [], set()
    for _, c in eleitos.iterrows():
        cod_cargo = str(c.get("CD_CARGO"))
        nome_cargo, nivel = CARGOS.get(cod_cargo, (f"cargo_{cod_cargo}", "uf"))
        if nome_cargo.startswith("cargo_"):
            desconhecidos.add(cod_cargo)
        id_origem = str(c.get("SQ_CANDIDATO"))

        politicos.append({
            "fonte_origem": FONTE,
            "id_origem": id_origem,
            "nome": c.get("NM_CANDIDATO"),
            "nome_eleitoral": c.get("NM_URNA_CANDIDATO"),
            "sigla_partido": c.get("SG_PARTIDO"),
            "sigla_uf": c.get("SG_UF"),
            "id_legislatura": str(ano),
            "email": c.get("DS_EMAIL"),
            "url_foto": None,
            "casa": None,
            "cargo": nome_cargo,
            "genero": c.get("DS_GENERO"),
            "cor_raca": c.get("DS_COR_RACA"),
            "grau_instrucao": c.get("DS_GRAU_INSTRUCAO"),
            "ocupacao": c.get("DS_OCUPACAO"),
            "data_nascimento": c.get("DT_NASCIMENTO"),
        })

        # `cod_ue` é o que a fonte fornece e entra na chave primária.
        # `cod_ibge` é o que o de-para resolveu — pode faltar sem quebrar nada.
        cod_ue = texto(c.get("SG_UE"))
        if nivel == "municipio":
            cod_ibge = ue_para_ibge.get(cod_ue)
        elif nivel == "uf":
            cod_ibge = uf_para_ibge.get(texto(c.get("SG_UF")))
        else:
            cod_ibge = "0"

        mandatos.append({
            "sk_politico": id_origem,
            "cod_cargo": cod_cargo,
            "cargo": nome_cargo,
            "cod_ue": cod_ue,
            "cod_ibge": cod_ibge,
            "sigla_uf": c.get("SG_UF"),
            "nome_ente": c.get("NM_UE"),
            "ano_inicio": int(ano) + 1,
            "ano_fim": int(ano) + 5 if nome_cargo != "senador" else int(ano) + 9,
            "data_inicio": f"{int(ano) + 1}-01-01",
            "nome": c.get("NM_URNA_CANDIDATO"),
            "sigla_partido": c.get("SG_PARTIDO"),
            "ano_eleicao": int(ano),
        })

    armazem.mesclar("dim_politico", politicos, f"{FONTE}_cand")
    armazem.mesclar("mandato", mandatos, f"{FONTE}_cand")

    if desconhecidos:
        # Código sem nome vira `cargo_12` na tela do usuário. Melhor gritar
        # aqui do que deixar o código bruto vazar para a interface.
        log.warning("TSE %d: códigos de cargo sem tradução: %s — acrescente "
                    "em CARGOS, senão aparecem como `cargo_N` no painel",
                    ano, sorted(desconhecidos))

    sem_ente = sum(1 for m in mandatos if not m["cod_ibge"])
    if sem_ente:
        log.warning("%d mandatos sem código IBGE — veja "
                    "`de_para.pendencias()`", sem_ente)
    controle.gravar_marca(FONTE, f"eleitos_{ano}", ano, len(mandatos),
                          detalhe=f"{sem_ente} sem código IBGE")
    return len(mandatos)


def coletar_partidos(ano: int) -> int:
    df = _baixar_consulta_cand(ano)
    if df.empty:
        return 0
    partidos = (df[["SG_PARTIDO", "NM_PARTIDO", "NR_PARTIDO"]]
                .drop_duplicates("SG_PARTIDO").dropna(subset=["SG_PARTIDO"]))
    linhas = [{
        "sigla": p["SG_PARTIDO"],
        "nome": p["NM_PARTIDO"],
        "numero": p["NR_PARTIDO"],
        "ano_referencia": ano,
    } for _, p in partidos.iterrows()]
    armazem.mesclar("dim_partido", linhas, FONTE)
    return len(linhas)


def executar(anos: list[int] | None = None) -> None:
    catalogo_cargos()
    # Eleição geral e municipal mais recentes.
    anos = anos or [2022, 2024]
    for ano in anos:
        try:
            coletar_partidos(ano)
            coletar_eleitos(ano)
        except Exception as erro:  # noqa: BLE001
            log.error("TSE %d falhou: %s", ano, erro)
            controle.gravar_marca(FONTE, f"eleitos_{ano}", None,
                                  situacao="erro", detalhe=str(erro))


if __name__ == "__main__":
    executar()
