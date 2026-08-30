"""SADIPEM — operações de crédito de estados e municípios (Tesouro Nacional).

Fecha a terceira pergunta do painel. Já havia **quanto entra** (receita) e
**quanto sai** (despesa); falta **quanto o ente tomou emprestado, de quem e
para quê** — e essa é a pergunta cuja resposta compromete os orçamentos dos
próximos prefeitos, não o atual.

O que a fonte publica é o **PVL — Pedido de Verificação de Limites**: o
pedido que um ente faz ao Tesouro para contrair dívida. Cada PVL traz o
credor, a finalidade, o valor e o desfecho.

## O erro que este coletor não pode cometer

**PVL não é dívida.** É pedido. Somar o valor de todos os PVLs de um município
e chamar o resultado de "dívida" seria errado três vezes:

1. pedido **indeferido** nunca virou dinheiro;
2. pedido deferido **não contratado** também não — a autorização vence;
3. o valor do PVL é o do pleito, não o saldo devedor de hoje, que já foi
   amortizado por anos de pagamento.

Por isso o coletor guarda o `status` e o indicador de contratação em todas as
linhas, e as views separam o que foi **autorizado** do que foi **pedido**.
O painel nunca escreve "dívida" — escreve "operações de crédito autorizadas",
que é o que o dado sustenta. Ver armadilha 2o.

## Formato de data

O mesmo registro mistura `data_protocolo` com ano de dois dígitos ("14/08/02")
e `data_status` com quatro ("14/03/2019"). `nucleo.valores.data_br` resolve os
dois com regra de corte explícita, e devolve None em vez de chutar — data
errada é pior que data ausente, porque entra nos filtros como se fosse
verdade.

## Freio

A documentação é explícita: **uma requisição por segundo**. A coleta é por UF
(27 requisições mais paginação), não por ente — 5.570 requisições a 1/s seriam
uma hora e meia para o mesmo dado.
"""

from __future__ import annotations

from ..nucleo import armazem, config, controle, rede
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import ano_de, data_br, inteiro, numero, opcional, texto

log = obter_log("coletores.sadipem")

FONTE = "sadipem"

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
       "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
       "SE", "SP", "TO"]

# A API devolve 5.000 itens por página. O teto de páginas existe pelo mesmo
# motivo que no Portal da CGU: uma resposta que nunca diz "acabou" viraria
# laço infinito, e truncar em silêncio viraria um total com cara de completo.
TETO_PAGINAS = 60


def _pagina(parametros: dict, offset: int) -> tuple[list[dict], bool]:
    corpo = rede.buscar(FONTE, f"{config.SADIPEM}/pvl",
                        {**parametros, "offset": offset} if offset else parametros)
    if not isinstance(corpo, dict):
        return (corpo if isinstance(corpo, list) else []), False
    itens = corpo.get("items", [])
    return itens, bool(corpo.get("hasMore"))


def coletar_uf(uf: str) -> list[dict]:
    """Todos os PVLs de uma UF — do estado e dos municípios dele."""
    brutos: list[dict] = []
    offset = 0
    for pagina in range(TETO_PAGINAS):
        itens, tem_mais = _pagina({"uf": uf}, offset)
        brutos.extend(itens)
        if not tem_mais:
            break
        offset += len(itens) or 1
        if pagina == TETO_PAGINAS - 1:
            log.warning("SADIPEM %s: teto de %d páginas atingido — o total "
                        "está TRUNCADO, não completo", uf, TETO_PAGINAS)

    linhas = []
    for bruto in brutos:
        id_pleito = inteiro(bruto.get("id_pleito"))
        if id_pleito is None:
            continue
        cod_ibge = texto(bruto.get("cod_ibge"))
        protocolo = data_br(bruto.get("data_protocolo"))
        linhas.append({
            "id_pleito": id_pleito,
            "cod_ibge": cod_ibge or None,
            "uf": opcional(bruto.get("uf")) or uf,
            "tipo_interessado": opcional(bruto.get("tipo_interessado")),
            "interessado": opcional(bruto.get("interessado")),
            "num_pvl": opcional(bruto.get("num_pvl")),
            "num_processo": opcional(bruto.get("num_processo")),
            "status": opcional(bruto.get("status")),
            "tipo_operacao": opcional(bruto.get("tipo_operacao")),
            "finalidade": opcional(bruto.get("finalidade")),
            "tipo_credor": opcional(bruto.get("tipo_credor")),
            "credor": opcional(bruto.get("credor")),
            "moeda": opcional(bruto.get("moeda")),
            "valor": numero(bruto.get("valor")),
            # `pvl_contradado_credor` — com o erro de digitação da própria
            # fonte, "contradado" por "contratado". Ler só o nome correto
            # devolvia None em 100% das linhas, e o painel mostraria zero
            # contratado para o país inteiro. Armadilha 2d na forma mais crua:
            # o campo existe, o nome é que está torto.
            "contratado": inteiro(bruto.get("pvl_contradado_credor",
                                            bruto.get("pvl_contratado_credor"))),
            "data_protocolo": protocolo,
            "data_status": data_br(bruto.get("data_status")),
            "ano": ano_de(bruto.get("data_protocolo")),
            "data_referencia": protocolo,
        })

    # Duas coisas diferentes, e confundi-las manda a investigação para o lado
    # errado: a fonte mandou NULO (não há o que reconhecer) ou mandou um texto
    # que o projeto não soube ler (aí sim é defeito nosso).
    nulos = [b for b in brutos if b.get("data_protocolo") in (None, "")]
    ilegiveis = [b for b in brutos
                 if b.get("data_protocolo") not in (None, "")
                 and ano_de(b.get("data_protocolo")) is None]

    if nulos:
        log.info("SADIPEM %s: %d de %d pleitos sem data de protocolo NA FONTE "
                 "— serão descartados por não terem partição",
                 uf, len(nulos), len(brutos))
    if ilegiveis:
        log.warning("SADIPEM %s: %d pleitos com data que o projeto não soube "
                    "ler. Valores crus: %s", uf, len(ilegiveis),
                    [b.get("data_protocolo") for b in ilegiveis[:3]])
    return linhas


def executar(anos: list[int] | None = None, ufs: list[str] | None = None,
             refazer: bool = False) -> int:
    """Varre as 27 UFs.

    `anos` é aceito para o orquestrador chamar como chama as outras fontes,
    mas a API não filtra por ano: o PVL é histórico e vem inteiro. Filtrar
    aqui descartaria dado já baixado — quem recorta é o painel.
    """
    alvos = list(ufs or UFS)
    if not refazer:
        pendentes = set(controle.recortes_pendentes(
            FONTE, [f"pvl_{u}" for u in alvos]))
        feitas = len(alvos) - len(pendentes)
        alvos = [u for u in alvos if f"pvl_{u}" in pendentes]
        if feitas:
            log.info("SADIPEM: %d UF(s) já concluídas, %d pendentes",
                     feitas, len(alvos))
    if not alvos:
        log.info("SADIPEM: nada pendente")
        return 0

    total = 0
    for indice, uf in enumerate(alvos, 1):
        log.info("SADIPEM %s — %d de %d", uf, indice, len(alvos))
        try:
            linhas = coletar_uf(uf)
        except Exception as erro:  # noqa: BLE001
            log.error("SADIPEM %s falhou: %s", uf, erro)
            controle.gravar_marca(FONTE, f"pvl_{uf}", None, 0,
                                  situacao="erro", detalhe=str(erro)[:200])
            continue

        if linhas:
            armazem.mesclar("operacao_credito", linhas, FONTE)
            total += len(linhas)
        log.info("SADIPEM %s: %d pleitos", uf, len(linhas))

        # A marca é POR UF: se a rede cair na décima, as nove anteriores não
        # precisam ser refeitas.
        controle.gravar_marca(
            FONTE, f"pvl_{uf}", None, len(linhas),
            situacao="ok" if linhas else "sem_dado",
            detalhe="" if linhas else "a UF não devolveu pleito")
    return total


if __name__ == "__main__":
    executar()
