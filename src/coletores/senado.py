"""Coletor Senado Federal.

Dados abertos em legis.senado.leg.br/dadosabertos. O Senado devolve JSON com
uma árvore mais aninhada que a da Câmara, então cada função achata na mesma
forma que o resto do projeto usa — casa/id_votacao/id_politico/voto.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..nucleo import armazem, config, controle, rede
from ..nucleo.valores import opcional, texto
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.senado")

FONTE = "senado"
CASA = "senado"

_MAPA_VOTO = {
    "Sim": "Sim", "Não": "Não", "NCom": "Não compareceu",
    "AP": "Ausente (presidindo)", "P-NRV": "Presente (não votou)",
    "Abstenção": "Abstenção", "LP": "Licença particular",
}


def _caminho(corpo: Any, *chaves: str, padrao: Any = None) -> Any:
    atual = corpo
    for chave in chaves:
        if not isinstance(atual, dict) or chave not in atual:
            return padrao
        atual = atual[chave]
    return atual


def coletar_senadores() -> int:
    corpo = rede.buscar(FONTE, f"{config.SENADO}/senador/lista/atual.json")
    parlamentares = _caminho(
        corpo, "ListaParlamentarEmExercicio", "Parlamentares", "Parlamentar",
        padrao=[],
    )

    linhas = []
    for p in parlamentares:
        ident = p.get("IdentificacaoParlamentar", {})
        mandato = p.get("Mandato", {})
        linhas.append({
            "fonte_origem": FONTE,
            "id_origem": str(ident.get("CodigoParlamentar")),
            "nome": ident.get("NomeCompletoParlamentar"),
            "nome_eleitoral": ident.get("NomeParlamentar"),
            "sigla_partido": ident.get("SiglaPartidoParlamentar"),
            "sigla_uf": ident.get("UfParlamentar"),
            "id_legislatura": texto(mandato.get("CodigoMandato")),
            "email": ident.get("EmailParlamentar"),
            "url_foto": ident.get("UrlFotoParlamentar"),
            "casa": CASA,
            "cargo": "senador",
        })

    armazem.mesclar("dim_politico", linhas, FONTE)
    controle.gravar_marca(FONTE, "senadores", date.today().isoformat(), len(linhas))
    return len(linhas)


def coletar_votacoes_materia(codigo_materia: str) -> int:
    corpo = rede.buscar(
        FONTE, f"{config.SENADO}/materia/votacoes/{codigo_materia}.json"
    )
    votacoes = _caminho(corpo, "VotacaoMateria", "Materia", "Votacoes",
                        "Votacao", padrao=[])
    if isinstance(votacoes, dict):
        votacoes = [votacoes]

    cabecalhos, votos = [], []
    for v in votacoes:
        id_votacao = str(v.get("CodigoSessaoVotacao"))
        data_hora = f"{v.get('SessaoPlenaria', {}).get('DataSessao', '')}"
        ano = int(str(data_hora)[:4] or date.today().year)
        cabecalhos.append({
            "casa": CASA,
            "id_votacao": id_votacao,
            "data_hora": data_hora,
            "sigla_orgao": "PLEN",
            "descricao": v.get("DescricaoVotacao"),
            "aprovada": v.get("IndicadorVotacaoSecreta") != "Sim"
                        and v.get("Resultado"),
            "votos_sim": None, "votos_nao": None, "votos_outros": None,
            "id_proposicao": str(codigo_materia),
            "url": None,
            "ano": ano,
        })

        parlamentares = _caminho(v, "Votos", "VotoParlamentar", padrao=[])
        if isinstance(parlamentares, dict):
            parlamentares = [parlamentares]
        for vp in parlamentares:
            bruto = texto(vp.get("Voto"))
            votos.append({
                "casa": CASA,
                "id_votacao": id_votacao,
                "id_politico": str(vp.get("CodigoParlamentar")),
                "nome_politico": vp.get("NomeParlamentar"),
                "sigla_partido": vp.get("SiglaPartido"),
                "sigla_uf": vp.get("SiglaUF"),
                "voto": _MAPA_VOTO.get(bruto, bruto),
                "data_hora": data_hora,
                "ano": ano,
                "mes": int(str(data_hora)[5:7] or 1),
            })

    if cabecalhos:
        armazem.mesclar("votacao", cabecalhos, FONTE)
    if votos:
        armazem.mesclar("voto", votos, FONTE)
    return len(votos)


def executar() -> None:
    coletar_senadores()
    log.info("votações do Senado são coletadas por matéria — chame "
             "coletar_votacoes_materia(codigo) a partir de proposicao")


if __name__ == "__main__":
    executar()
