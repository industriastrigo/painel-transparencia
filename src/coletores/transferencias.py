"""Transferências constitucionais da União — Tesouro Nacional (API Aria).

Este coletor responde a pergunta que o painel não conseguia responder:
**quanto a União repassou para cada estado e cada município, e por qual
mecanismo** — FPM, FPE, FUNDEB, Lei Kandir, ITR, CIDE, royalties.

## Por que não é o mesmo número que o SICONFI já traz

O painel tem duas medidas de transferência, e elas NÃO batem — nem deveriam:

| | SICONFI (Anexo I-C) | esta API |
|---|---|---|
| quem declara | o próprio ente que recebeu | o Tesouro, que pagou |
| o que cobre | toda transferência recebida, de qualquer origem | só as obrigatórias da União |
| granularidade | anual, uma linha | mensal, por modalidade |
| regime | orçamentário do ente | caixa (registro no SIAFI) |

A diferença entre as duas é informação, não defeito: o que o estado repassa
aos municípios dele (25% do ICMS, 50% do IPVA) aparece no SICONFI do
município e nunca aqui, porque não passa pela União.

Rotular errado é o risco. As duas medidas moram em tabelas separadas e o
painel diz qual está mostrando.

## Catálogo primeiro, sempre

O endpoint `/custom/transferencias` é o dicionário de domínio: devolve o
código e o nome de cada modalidade, e é esse código que alimenta o parâmetro
das rotas de valor. O coletor **pergunta ao catálogo** em vez de trazer uma
lista de códigos escrita à mão — a lista muda (FPM 1% começou em julho/2025,
a Compensação ICMS da LC 201/2023 termina em dezembro/2025).

## Acesso

A documentação diz: "Para solicitar acesso, entrar em contato com
desenvolvimento@tesouro.gov.br". Se a API responder 401 ou 403, o coletor
levanta `ConfiguracaoAusente` com esse texto em vez de registrar um erro
genérico — é o terceiro estado, "falta configurar", e a tela mostra o que
fazer.
"""

from __future__ import annotations

import os
from datetime import date

from ..nucleo import armazem, config, controle, rede
from ..nucleo.erros import ConfiguracaoAusente
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import inteiro, numero, opcional, texto

log = obter_log("coletores.transferencias")

FONTE = "transferencias"

COMO_PEDIR_ACESSO = (
    "A API de Transferências Constitucionais do Tesouro pode exigir "
    "liberação. Peça acesso em desenvolvimento@tesouro.gov.br e, se vier "
    "uma chave, ponha CHAVE_TESOURO_ARIA no .env."
)

# Nomes que o Tesouro pode usar para o mesmo campo. O painel já se queimou uma
# vez com isto (a Situação das proposições ficou 100% vazia porque o lote da
# Câmara chama `ultimoStatus_descricaoSituacao` o que a API chama
# `descricaoSituacao`), então aqui nada é lido por um nome só.
CAMPOS = {
    "cod_ibge": ("co_ibge", "cod_ibge", "codigo_ibge", "co_municipio_ibge"),
    "cod_transferencia": ("codigo", "co_transferencia", "cod_transferencia"),
    "transferencia": ("transferencia", "no_transferencia", "nome"),
    "uf": ("uf", "sg_uf", "sigla_uf"),
    "municipio": ("municipio", "no_municipio", "nome"),
    "ano": ("ano", "an_referencia", "exercicio"),
    "mes": ("mes", "me_referencia", "mes_referencia"),
    "valor": ("valor", "vl_transferencia", "vl_valor", "montante"),
    "cod_siafi": ("co_siafi", "cod_siafi", "codigo_siafi"),
    "regiao": ("regiao", "no_regiao"),
}

_campos_vistos: set[str] = set()

# A rota municipal devolve `pageSize: 10` por padrão. Pedir páginas maiores
# reduz o número de requisições — e esta API não publica limite de taxa, mas o
# projeto respeita o freio de `config.INTERVALO_REQUISICOES` de qualquer jeito.
TAMANHO_DA_PAGINA = int(os.getenv("PAINEL_TRANSFERENCIAS_PAGINA", "1000"))

# Teto de páginas por consulta. Com 5.570 municípios × 12 meses numa
# modalidade, mil por página ainda pode passar de sessenta páginas.
TETO_DE_PAGINAS = int(os.getenv("PAINEL_TRANSFERENCIAS_TETO", "2000"))


def _inteiro_ou(valor, padrao: int) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def _base() -> str:
    return f"{config.TESOURO_ARIA}/v1/transferencias_constitucionais"


def primeiro(linha: dict, *nomes: str):
    """Primeiro nome de campo presente na linha, SEM olhar a caixa.

    A comparação era exata, e as duas rotas desta mesma API escrevem em caixas
    diferentes: `/custom/por_estados` manda `uf`, `valor`, `mes`;
    `/custom/por_estado_municipio` manda `UF`, `VALOR`, `MES`, `CO_IBGE`.

    Com busca exata, NENHUM campo da rota municipal casava — nem sequer o
    valor. Toda linha caía no `if valor is None: continue`, e o acervo ficou
    com zero município enquanto o arquivo bruto mostrava as linhas chegando.
    Foi assim que o painel passou a ter transferências só de estado, sem que
    nada no log parecesse errado.
    """
    if not isinstance(linha, dict):
        return None
    por_minuscula = {str(k).lower(): v for k, v in linha.items()}
    for nome in nomes:
        valor = por_minuscula.get(nome.lower())
        if valor not in (None, ""):
            return valor
    return None


def _campo(linha: dict, chave: str):
    return primeiro(linha, *CAMPOS[chave])


def _pedir(rota: str, parametros: dict | None = None) -> list[dict]:
    """GET numa rota da API, já lidando com o envelope e com a paginação.

    APEX/ORDS devolve `{"items": [...], "hasMore": true, "offset": n}`. Alguns
    endpoints devolvem a lista crua. Os dois casos são aceitos.
    """
    parametros = dict(parametros or {})
    if config.CHAVE_TESOURO_ARIA:
        parametros.setdefault("chave", config.CHAVE_TESOURO_ARIA)

    coletadas: list[dict] = []
    offset = 0
    for _ in range(TETO_DE_PAGINAS):
        pagina = dict(parametros)
        if offset:
            pagina["offset"] = offset
        try:
            corpo = rede.buscar(FONTE, f"{_base()}{rota}", pagina)
        except Exception as erro:  # noqa: BLE001
            codigo = getattr(erro, "codigo", None) or getattr(erro, "status", None)
            if codigo in (401, 403):
                raise ConfiguracaoAusente(
                    f"Transferências: acesso negado (HTTP {codigo}).",
                    COMO_PEDIR_ACESSO) from erro
            # O log precisa dizer QUAL chamada falhou, com os parâmetros: sem
            # isso, um nome de parâmetro errado vira "erro na fonte" e ninguém
            # descobre qual.
            log.error("Transferências: falhou %s%s com %s — %s",
                      _base(), rota, pagina, erro)
            raise

        itens = _lista_da_resposta(corpo, rota)
        if itens is None:
            return coletadas

        coletadas.extend(itens)

        # DUAS convenções de paginação nesta mesma API, e o coletor só
        # conhecia uma. O ORDS usa `hasMore` + `offset`; a rota municipal usa
        # `page`/`pageSize`/`next` e **nunca manda `hasMore`** — então o laço
        # parava sempre na primeira página, com `pageSize: 10`.
        #
        # Dez linhas por consulta, num universo de 5.570 municípios × 18
        # modalidades × 12 meses. O arquivo bruto mostrou o tamanho do buraco:
        # 2.340 registros municipais capturados contra 55.214 estaduais,
        # quando a municipal deveria ser a maior de longe.
        if isinstance(corpo, dict) and corpo.get("hasMore"):
            offset += len(itens) or 1
            continue

        proxima = corpo.get("next") if isinstance(corpo, dict) else None
        # `next` vem preenchido MESMO quando a página veio vazia — seguir por
        # ele sem olhar o conteúdo é laço infinito até o teto de páginas.
        if not (proxima and itens):
            break
        pagina_atual = _inteiro_ou(corpo.get("page"), 1)
        parametros["page"] = pagina_atual + 1
        parametros.setdefault("pageSize", TAMANHO_DA_PAGINA)
        offset = 0

    if coletadas and not _campos_vistos:
        _campos_vistos.update(coletadas[0].keys())
        log.info("Transferências: campos devolvidos por %s — %s. "
                 "Primeiro registro: %s",
                 rota, ", ".join(sorted(_campos_vistos)),
                 str(coletadas[0])[:300])
    return coletadas


# O envelope varia entre APIs do Tesouro. A do ORDS usa `items`; a Aria
# respondeu `{"registros": [...], "status": ...}` — descoberto na primeira
# coleta real, não na documentação. Em vez de cravar mais um nome, procura-se
# o primeiro campo que CONTÉM uma lista.
CHAVES_DE_LISTA = ("items", "registros", "dados", "data", "results", "resultado")


def _lista_da_resposta(corpo, rota: str) -> list[dict] | None:
    if isinstance(corpo, list):
        return corpo
    if not isinstance(corpo, dict):
        log.warning("Transferências: %s devolveu %s, não um objeto",
                    rota, type(corpo).__name__)
        return None

    for chave in CHAVES_DE_LISTA:
        if isinstance(corpo.get(chave), list):
            return corpo[chave]

    for chave, valor in corpo.items():
        if isinstance(valor, list):
            log.info("Transferências: lista encontrada no campo '%s' de %s — "
                     "acrescente-o a CHAVES_DE_LISTA", chave, rota)
            return valor

    # Nem lista nem erro HTTP: o log precisa mostrar a resposta, senão a
    # próxima execução repete o mesmo mistério.
    log.warning("Transferências: %s não trouxe lista nenhuma. Chaves: %s. "
                "Resposta: %s", rota, list(corpo)[:10], str(corpo)[:400])
    return None


def catalogar() -> list[dict]:
    """As modalidades de transferência, com o código que as rotas de valor
    esperam. Ponto de partida obrigatório."""
    linhas = _pedir("/custom/transferencias")
    catalogo = []
    for linha in linhas:
        codigo = _campo(linha, "cod_transferencia")
        if codigo in (None, ""):
            continue
        catalogo.append({
            "cod_transferencia": texto(codigo),
            "transferencia": texto(_campo(linha, "transferencia")),
        })
    log.info("Transferências: %d modalidades no catálogo — %s",
             len(catalogo), ", ".join(c["transferencia"] for c in catalogo[:8]))
    return catalogo


_COD_UF = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16",
    "TO": "17", "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
    "PE": "26", "AL": "27", "SE": "28", "BA": "29", "MG": "31", "ES": "32",
    "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43", "MS": "50",
    "MT": "51", "GO": "52", "DF": "53",
}


def _linhas(brutas: list[dict], nivel: str, ano: int,
            modalidade: dict) -> list[dict]:
    saida = []
    for bruta in brutas:
        valor = numero(_campo(bruta, "valor"))
        if valor is None:
            continue
        uf = opcional(_campo(bruta, "uf"))
        cod_ibge = _campo(bruta, "cod_ibge")
        # A rota municipal traz `CO_IBGE` de sete dígitos — a junção com
        # `dim_ente` sai de graça. A derivação pela sigla abaixo é só para a
        # rota por ESTADO, que manda a sigla e não o código.
        if cod_ibge in (None, "") and nivel == "estado" and uf:
            # A rota por estado não devolve código IBGE, só a sigla. O código
            # da UF é fixo por norma do IBGE, então derivá-lo aqui é tradução,
            # não invenção — e é o que liga estas linhas ao mapa. Sem ele o
            # `vw_mapa` não junta nada e a métrica fica cinza com o dado no
            # disco.
            cod_ibge = _COD_UF.get(str(uf).strip().upper())
        saida.append({
            "cod_ibge": texto(cod_ibge) if cod_ibge is not None else None,
            "nivel": nivel,
            "uf": uf,
            "nome_ente": opcional(_campo(bruta, "municipio")),
            "cod_transferencia": modalidade["cod_transferencia"],
            "transferencia": modalidade["transferencia"],
            "ano": inteiro(_campo(bruta, "ano")) or ano,
            "mes": inteiro(_campo(bruta, "mes")),
            "valor": valor,
            "cod_siafi": opcional(_campo(bruta, "cod_siafi")),
            "data_referencia": f"{ano}-12-31",
        })
    return saida


def _mostrar_campos(rota: str, brutas: list[dict]) -> None:
    """Registra, uma vez por rota, os campos que a fonte realmente devolve.

    O catálogo tinha esse diagnóstico; as rotas de VALOR não tinham. Quando
    `cod_ibge` veio nulo em todas as linhas, não havia no log uma única
    resposta real para conferir — e a única saída teria sido recoletar.
    """
    if rota in _campos_vistos or not brutas:
        return
    _campos_vistos.add(rota)
    log.info("Transferências: campos devolvidos por %s — %s. "
             "Primeiro registro: %s",
             rota, ", ".join(sorted(brutas[0])), str(brutas[0])[:400])


def coletar_ano(ano: int, catalogo: list[dict] | None = None,
                municipios: bool = True) -> int:
    """Uma passada por ano, uma requisição por modalidade e nível."""
    catalogo = catalogo if catalogo is not None else catalogar()
    if not catalogo:
        log.warning("Transferências: catálogo vazio — nada a coletar em %d", ano)
        return 0

    total = 0
    for modalidade in catalogo:
        parametros = {"p_transferencia": modalidade["cod_transferencia"],
                      "p_ano": ano}

        for rota, nivel in (("/custom/por_estados", "estado"),
                            ("/custom/por_estado_municipio", "municipio")):
            if nivel == "municipio" and not municipios:
                continue
            try:
                brutas = _pedir(rota, parametros)
            except ConfiguracaoAusente:
                raise
            except Exception:  # noqa: BLE001
                # Uma modalidade que não existe no ano pedido não pode derrubar
                # as outras vinte. O erro já foi registrado em `_pedir`.
                continue

            _mostrar_campos(rota, brutas)
            linhas = _linhas(brutas, nivel, ano, modalidade)
            if linhas:
                armazem.mesclar("transferencia_uniao", linhas,
                                f"{FONTE}_{nivel}")
                total += len(linhas)

    log.info("Transferências %d: %d linhas de %d modalidades",
             ano, total, len(catalogo))
    return total


# A série começa em 1997 para FPE, FPM, IPI-Exportação, IOF-Ouro, Lei Kandir
# e ITR — as demais modalidades entram depois, cada uma na sua data.
PRIMEIRO_ANO = 1997


def anos_disponiveis() -> list[int]:
    return list(range(PRIMEIRO_ANO, date.today().year + 1))


def executar(anos: list[int] | None = None, municipios: bool = True,
             refazer: bool = False) -> int:
    """Coleta por ano, retomando de onde parou.

    Cada ano vira uma marca. Numa carga histórica de trinta exercícios, é o
    que permite parar e continuar noutra noite sem refazer o que entrou.

    Uma exceção deliberada: o **ano corrente e o anterior** são sempre
    recoletados mesmo com marca `ok`, porque o Tesouro revisa a série e os
    valores podem mudar até o início do exercício em curso.
    """
    anos = anos or [date.today().year - 1]
    revisaveis = {date.today().year, date.today().year - 1}

    if not refazer:
        pendentes = set(controle.recortes_pendentes(
            FONTE, [f"ano_{a}" for a in anos]))
        alvos = [a for a in anos
                 if f"ano_{a}" in pendentes or a in revisaveis]
        if len(alvos) < len(anos):
            log.info("Transferências: %d ano(s) já concluídos, %d a coletar "
                     "(inclui os revisáveis)", len(anos) - len(alvos), len(alvos))
        anos = alvos

    if not anos:
        log.info("Transferências: nada pendente")
        return 0

    catalogo = catalogar()
    total = 0
    for indice, ano in enumerate(anos, 1):
        log.info("Transferências %d — %d de %d", ano, indice, len(anos))
        try:
            linhas = coletar_ano(ano, catalogo, municipios=municipios)
        except ConfiguracaoAusente:
            raise
        except Exception as erro:  # noqa: BLE001
            log.error("Transferências %d falhou: %s", ano, erro)
            controle.gravar_marca(FONTE, f"ano_{ano}", ano, 0,
                                  situacao="erro", detalhe=str(erro)[:200])
            continue

        total += linhas
        controle.gravar_marca(
            FONTE, f"ano_{ano}", ano, linhas,
            situacao="ok" if linhas else "sem_dado",
            detalhe="" if linhas else "nenhuma modalidade devolveu valor")
    return total


if __name__ == "__main__":
    executar()
