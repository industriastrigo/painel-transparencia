"""Custos do Governo Federal — API do Tesouro Nacional.

Responde "quanto cada órgão federal custa" com dado **medido** pelo próprio
governo, e não com estimativa. A aba Custo do Estado calcula, para os demais
cargos, ocupantes × subsídio × 13,33 — uma conta, rotulada como conta. Aqui o
número é apurado no SIAFI e no SIAPE.

## Por que deixou de ser CSV

A primeira versão raspava CSVs de um catálogo CKAN. Três dos seis conjuntos
pararam de abrir — o arquivo mudou de formato e o coletor só sabia dizer "não
consegui ler como tabela".

O Tesouro publica os mesmos seis recortes numa API REST. Trocar reduziu
código: sem download, sem separador para adivinhar, sem encoding, sem URL que
muda de lugar. Um endpoint por recorte, JSON, filtro por ano e mês.

## O que este número É e o que NÃO é

Custo não é despesa orçamentária, e confundir os dois é o erro fácil aqui:

| | o que mede |
|---|---|
| despesa empenhada (SICONFI) | o compromisso assumido no orçamento |
| **custo (esta API)** | o consumo do período, por competência — com provisões, sem adiantamentos |

Os dois são certos e diferentes. Um órgão pode empenhar em dezembro um gasto
cujo custo é do ano seguinte.

E a granularidade é por **ÓRGÃO** (codificação SIORG), nunca por cargo:
responde "quanto custa o Ministério da Saúde", não "quanto custa um ministro".

## Campos

O Swagger descreve os parâmetros, não a resposta. Então nada é lido por um
nome só — `CAMPOS` traz os apelidos prováveis de cada coluna e o coletor
registra no log o primeiro registro recebido, para o nome real aparecer sem
ninguém precisar adivinhar (armadilha 2d).

## Freio

Documentado: **uma requisição por segundo**. A página de 250 itens é o
padrão do servidor, não um limite: ele honra `limit=10000`, e é isso que
separa horas de minutos por recorte. Medido, não suposto — veja PAGINA.
"""

from __future__ import annotations

import time
from datetime import date

from ..nucleo import armazem, config, controle, rede, tabela  # noqa: F401
from ..nucleo.registro import obter as obter_log
from ..nucleo.valores import inteiro, numero, opcional, texto

log = obter_log("coletores.tesouro")

FONTE = "tesouro"

# Um endpoint por recorte de custo. O nome do conjunto é o que vai para a
# coluna `conjunto` da tabela, e é ele que o painel usa para separar.
CONJUNTOS = {
    "pessoal_ativo": "pessoal_ativo",
    "pessoal_inativo": "pessoal_inativo",
    "pensionista": "pensionistas",
    "depreciacao": "depreciacao",
    "transferencia": "transferencias",
    "demais_custos": "demais",
}

# Nomes REAIS, lidos de uma resposta de verdade. Os que eu havia suposto a
# partir do Swagger erraram todos — o Swagger documenta os parâmetros, não a
# resposta.
#
# Duas irregularidades que nenhuma suposição alcançaria:
#
# 1. **O campo de valor tem nome diferente em cada endpoint**:
#    `va_custo_de_pessoal`, `va_custo_pessoal_inativo`, `va_custo_pensionistas`,
#    `va_custo_depreciacao`, `va_custo_transferencias`, `va_custo`. Por isso o
#    valor é procurado por PREFIXO (`va_`), não por lista.
#
# 2. **O endpoint `demais` usa outro vocabulário inteiro**: `co_siorg_n04..n07`
#    em vez de `co_organizacao_n0..n6`, e o nível do ministério muda de lugar —
#    é `n1` nos cinco primeiros e `n05` no `demais`.
CAMPOS = {
    # Nível do ministério. Nos cinco primeiros é n1; no `demais`, n05.
    "orgao_nome": ("ds_organizacao_n1", "ds_siorg_n05",
                   "ds_organizacao_n0", "ds_siorg_n04"),
    "orgao_codigo": ("co_organizacao_n1", "co_siorg_n05",
                     "co_organizacao_n0", "co_siorg_n04"),
    "orgao_n2": ("ds_organizacao_n2", "ds_siorg_n06"),
    "orgao_n3": ("ds_organizacao_n3", "ds_siorg_n07"),
    "item_custo": ("no_conta_contabil", "no_natureza_despesa_deta",
                   "ds_natureza_juridica"),
    "natureza_juridica": ("ds_natureza_juridica", "id_natureza_juridica_siorg"),
    "ano": ("an_lanc", "an_referencia", "an_emissao"),
    "mes": ("me_lanc", "me_referencia", "me_emissao"),
}


def _valor(linha: dict):
    """O custo, qualquer que seja o nome do campo neste endpoint.

    Cada recorte batizou o seu: `va_custo_de_pessoal`, `va_custo_pensionistas`,
    `va_custo`. Procurar por prefixo evita ter de descobrir um nome novo cada
    vez que o Tesouro publicar mais um recorte.
    """
    for chave, conteudo in linha.items():
        if chave.startswith("va_") and conteudo not in (None, ""):
            return conteudo
    return None

_campos_vistos: dict[str, set] = {}


def primeiro(linha: dict, *nomes: str):
    """Primeiro nome de campo presente na linha. Ver armadilha 2d."""
    for nome in nomes:
        if nome in linha and linha[nome] not in (None, ""):
            return linha[nome]
    return None


def _campo(linha: dict, chave: str):
    return primeiro(linha, *CAMPOS[chave])


# Tamanho de página, MEDIDO em 29/08/2026 contra o endpoint real
# (`scripts/medir_paginacao_custos.py`), não suposto a partir do Swagger:
#
#   limit  |  linhas  |  tempo  |  vazão
#   -------|----------|---------|---------------
#      250 |      250 |  1,2 s  |    208 linhas/s   <- o padrão do servidor
#     1000 |    1 000 |  1,3 s  |    769 linhas/s
#    10000 |   10 000 |  3,5 s  |  2 857 linhas/s
#
# O servidor honra o `limit` e devolve exatamente o pedido. Pagina de 250 era
# o padrão DELE, nunca uma escolha nossa: um ano de `pessoal_ativo` passa de
# um milhão de linhas, o que dava mais de 4 mil requisições e horas de rede
# por recorte-ano. Com 10 mil por página são ~120 requisições e minutos.
#
# `totalResults` NÃO é suportado: o endpoint devolve `null` sempre. Então não
# há como saber o tamanho do recorte antes de baixá-lo, e a única prova de que
# a coleta terminou é `hasMore: false`. É por isso que a retomada por posição
# abaixo não é conforto, é o que faz a carga convergir.
PAGINA = 10_000


def _paginar(recurso: str, parametros: dict, consumir, offset: int = 0,
             tamanho: int = PAGINA,
             max_paginas: int | None = None) -> tuple[int, bool]:
    """Percorre as páginas a partir de `offset`, entregando cada uma a
    `consumir`. Devolve `(offset_alcançado, completo)`.

    Streaming, e não acumulação, por um motivo de memória: um ano de
    `pessoal_ativo` tem mais de um milhão de registros brutos, e a versão
    anterior guardava todos numa lista para só então agregar. Quem chama
    agrega página a página e descarta o bruto — o que fica na memória é o
    resultado, que tem dezenas de milhares de linhas, não milhões.
    """
    inicio = time.monotonic()
    paginas = 0

    while True:
        consulta = dict(parametros)
        consulta["limit"] = tamanho
        if offset:
            consulta["offset"] = offset

        try:
            corpo = rede.buscar(FONTE, f"{config.TESOURO_CUSTOS}/{recurso}",
                                consulta)
        except Exception as erro:  # noqa: BLE001
            if not paginas:
                raise
            # Perder o que já veio porque a página seguinte falhou é
            # desperdício que a pessoa paga em minutos de espera. O `offset`
            # devolvido é o ponto exato de retomada.
            log.warning("Custos %s: a conexão falhou no offset %d (%s). "
                        "Guardando o que veio e marcando para retomar daqui.",
                        recurso, offset, str(erro)[:80])
            return offset, False

        if isinstance(corpo, list):        # endpoint sem envelope
            consumir(corpo)
            return offset + len(corpo), True
        if not isinstance(corpo, dict):
            log.warning("Custos %s: resposta %s, esperava objeto",
                        recurso, type(corpo).__name__)
            return offset, False

        itens = corpo.get("items")
        if itens is None:
            for valor in corpo.values():
                if isinstance(valor, list):
                    itens = valor
                    break
        if not isinstance(itens, list):
            log.warning("Custos %s: sem lista na resposta. Chaves: %s",
                        recurso, list(corpo)[:8])
            return offset, False

        # O servidor pode não honrar o tamanho pedido. Quem manda é o que ele
        # DEVOLVEU: adotar o valor dele evita um laço que anda menos do que
        # pensa que anda — e que, com página vazia, não andaria nunca.
        aplicado = corpo.get("limit")
        if isinstance(aplicado, int) and aplicado and aplicado != tamanho:
            log.info("Custos %s: pedi limit=%d e o servidor aplicou %d; "
                     "seguindo com o dele.", recurso, tamanho, aplicado)
            tamanho = aplicado

        consumir(itens)
        paginas += 1
        if max_paginas is not None and paginas >= max_paginas:
            # Só o diagnóstico usa isto: ele quer os NOMES dos campos, e a
            # primeira página já responde. Não é `completo`, e dizer que é
            # gravaria "recorte inteiro coletado" sobre uma amostra.
            return offset + len(itens), False

        if not itens:
            # Página vazia com `hasMore` verdadeiro é laço infinito disfarçado.
            log.warning("Custos %s: página vazia no offset %d com hasMore=%s "
                        "— parando aqui em vez de girar em falso.",
                        recurso, offset, corpo.get("hasMore"))
            return offset, False

        offset += len(itens)

        if not corpo.get("hasMore"):
            return offset, True

        if paginas % 20 == 0:
            decorrido = time.monotonic() - inicio
            log.info("Custos %s: %d páginas, %d linhas, %.0f s (%.0f linhas/s)",
                     recurso, paginas, offset, decorrido,
                     offset / decorrido if decorrido else 0)


def _agregador(conjunto: str, ano: int):
    """Acumula (órgão, item, ano, mês) → valor, página a página.

    `pessoal_ativo` vem quebrado por sexo, escolaridade, faixa etária e área
    de atuação. O painel pergunta "quanto custa este órgão", não "quanto custa
    este órgão para servidores de tal faixa etária": somar enquanto lê descarta
    a explosão combinatória sem perder a resposta.
    """
    somas: dict[tuple, float] = {}
    codigos: dict[tuple, str | None] = {}

    def consumir(brutos: list[dict]) -> None:
        for bruto in brutos:
            valor = numero(_valor(bruto))
            if valor is None:
                continue
            mes_linha = inteiro(_campo(bruto, "mes"))
            chave = (
                texto(_campo(bruto, "orgao_nome"), 200) or "(sem órgão)",
                opcional(_campo(bruto, "item_custo")) or conjunto,
                inteiro(_campo(bruto, "ano")) or ano,
                mes_linha if mes_linha is not None else 0,
            )
            somas[chave] = somas.get(chave, 0.0) + valor
            codigos.setdefault(chave, opcional(_campo(bruto, "orgao_codigo")))

    def linhas() -> list[dict]:
        return [{
            "conjunto": conjunto,
            "orgao_nome": orgao,
            "orgao_codigo": codigos.get((orgao, item, ano_linha, mes_linha)),
            "item_custo": item,
            "ano": ano_linha,
            "mes": mes_linha,
            "valor": valor,
            "data_referencia": f"{ano_linha}-{(mes_linha or 12):02d}-01",
        } for (orgao, item, ano_linha, mes_linha), valor in somas.items()]

    return consumir, linhas, somas, codigos


def _semear(conjunto: str, ano: int, somas: dict, codigos: dict) -> int:
    """Carrega no agregador o que já foi gravado deste recorte.

    Sem isto, retomar do offset N gravaria apenas a soma do trecho [N, fim), e
    a tela mostraria MENOS do que já mostrava. Com a semente, cada execução
    continua a soma anterior — e como os trechos são disjuntos por construção,
    somar é exato, não aproximado.
    """
    try:
        df = armazem.ler("custo_orgao",
                         filtro=f"conjunto = '{conjunto}' AND ano = {int(ano)}")
    except Exception as erro:  # noqa: BLE001
        log.warning("Custos %s/%d: não consegui ler o que já havia (%s); "
                    "recomeçando do zero.", conjunto, ano, str(erro)[:80])
        return 0
    if df.empty:
        return 0
    for linha in df.to_dict("records"):
        chave = (linha["orgao_nome"], linha["item_custo"],
                 int(linha["ano"]), int(linha["mes"] or 0))
        somas[chave] = somas.get(chave, 0.0) + float(linha["valor"] or 0.0)
        codigos.setdefault(chave, linha.get("orgao_codigo"))
    return len(df)


def coletar(conjunto: str, ano: int, mes: int | None = None,
            offset: int = 0,
            retomar: bool = False) -> tuple[list[dict], bool, int]:
    """Um recorte de custo. Devolve `(linhas, completo, offset_alcançado)`."""
    recurso = CONJUNTOS[conjunto]
    parametros: dict = {"ano": ano}
    if mes:
        parametros["mes"] = mes

    consumir, montar, somas, codigos = _agregador(conjunto, ano)
    if retomar and offset:
        semeadas = _semear(conjunto, ano, somas, codigos)
        log.info("Custos %s/%d: retomando do offset %d sobre %d linha(s) já "
                 "gravadas.", conjunto, ano, offset, semeadas)

    alcancado, completo = _paginar(recurso, parametros, consumir, offset=offset)
    if not completo:
        log.warning("Custos %s/%s: PARCIAL no offset %d. O total é um piso; a "
                    "próxima execução continua daqui, não do começo.",
                    conjunto, ano, alcancado)
    return montar(), completo, alcancado


# A série começa em 2015, segundo a documentação de todos os seis recortes.
PRIMEIRO_ANO = 2015


def anos_disponiveis() -> list[int]:
    """Do início da série até o ano passado.

    O ano corrente fica de fora por padrão: ele está incompleto por
    construção, e coletá-lo grava um total que muda no mês seguinte.
    """
    return list(range(PRIMEIRO_ANO, date.today().year))


def _retomada(conjunto: str, ano: int) -> int:
    """O offset gravado pela execução anterior, ou 0.

    Marca de execução antiga (que guardava o ano) não serve como posição, e
    tratá-la como tal pularia o começo do recorte. Só retoma o que esta versão
    escreveu.
    """
    marca = controle.ler_marca(FONTE, f"{conjunto}_{ano}")
    if not marca or not str(marca).startswith("offset="):
        return 0
    try:
        return max(0, int(str(marca).split("=", 1)[1]))
    except ValueError:
        return 0


def executar(anos: list[int] | None = None,
             conjuntos: list[str] | None = None,
             por_mes: bool = False,
             refazer: bool = False) -> int:
    """Coleta os seis recortes, retomando de onde parou.

    Cada par (recorte, ano) vira uma marca em `_ctl/ingestao`. Numa carga
    histórica de horas, isso é o que separa "a rede caiu, rode de novo" de
    "a rede caiu, perdeu tudo". `refazer=True` ignora as marcas.
    """
    anos = anos or [date.today().year - 1]
    conjuntos = conjuntos or list(CONJUNTOS)

    alvos = [(conjunto, ano) for ano in anos for conjunto in conjuntos]
    if not refazer:
        pendentes = set(controle.recortes_pendentes(
            FONTE, [f"{c}_{a}" for c, a in alvos]))
        feitos = len(alvos) - len(pendentes)
        alvos = [(c, a) for c, a in alvos if f"{c}_{a}" in pendentes]
        if feitos:
            log.info("Custos: %d recorte-ano já concluídos, %d pendentes",
                     feitos, len(alvos))
    if not alvos:
        log.info("Custos: nada pendente")
        return 0

    total = 0
    for indice, (conjunto, ano) in enumerate(alvos, 1):
        log.info("Custos %s/%d — %d de %d", conjunto, ano, indice, len(alvos))
        # Onde a execução anterior parou. Sem isto, cada carga rebaixava o
        # mesmo prefixo e batia no mesmo limite: 24 h de rede para terminar
        # exatamente onde a véspera terminou.
        retomada = _retomada(conjunto, ano) if not refazer else 0
        try:
            if por_mes:
                linhas, completo = [], True
                for mes in range(1, 13):
                    parte, inteiro_mes, _ = coletar(conjunto, ano, mes)
                    linhas.extend(parte)
                    completo = completo and inteiro_mes
                alcancado = 0
            else:
                linhas, completo, alcancado = coletar(
                    conjunto, ano, offset=retomada, retomar=bool(retomada))
        except Exception as erro:  # noqa: BLE001
            log.error("Custos %s/%d falhou: %s", conjunto, ano, erro)
            controle.gravar_marca(FONTE, f"{conjunto}_{ano}", ano, 0,
                                  situacao="erro", detalhe=str(erro)[:200])
            continue

        if linhas:
            armazem.mesclar("custo_orgao", linhas, f"{FONTE}_{conjunto}")
            total += len(linhas)

        # Três desfechos, três marcas. Só `ok` é terminal — `parcial` e
        # `sem_dado` são retentados na próxima execução, que é o que permite
        # a carga histórica ser retomada sem refazer o que ficou pronto.
        if not linhas:
            situacao, detalhe = "sem_dado", "a API não devolveu linha para o ano"
        elif not completo:
            situacao, detalhe = "parcial", "paginação interrompida — total é um piso"
        else:
            situacao, detalhe = "ok", ""

        log.info("Custos %s/%d: %d linhas (%s)",
                 conjunto, ano, len(linhas), situacao)
        # A marca guarda a POSIÇÃO quando ficou pela metade. `ler_marca` só
        # entende o que ela mesma escreveu, então o formato é explícito.
        marca = f"offset={alcancado}" if situacao == "parcial" else str(ano)
        controle.gravar_marca(FONTE, f"{conjunto}_{ano}", marca, len(linhas),
                              situacao=situacao, detalhe=detalhe)
    return total


def descobrir(ano: int | None = None) -> dict[str, dict]:
    """Que campos cada recorte devolve, sem gravar nada.

    Devolve, por conjunto, `{"campos": [...], "erro": ""}`. Campos vazios COM
    erro é fonte fora do ar; campos vazios SEM erro é exercício não publicado.
    Achatar os dois em "vazio" seria repetir a armadilha 2e num diagnóstico —
    logo no lugar cujo trabalho é distinguir uma coisa da outra.
    """
    ano = ano or date.today().year - 1
    achados: dict[str, dict] = {}
    for conjunto, recurso in CONJUNTOS.items():
        try:
            # UMA página: o diagnóstico quer os nomes dos campos, não o
            # recorte inteiro. Paginar tudo aqui custou quatro minutos de rede
            # para responder o que a primeira linha responde.
            # UMA página curta: `_paginar` pararia sozinho só no fim do
            # recorte, e aqui basta a primeira linha.
            amostra: list[dict] = []
            _paginar(recurso, {"ano": ano, "mes": 1}, amostra.extend,
                     tamanho=1, max_paginas=1)
            achados[conjunto] = {
                "campos": sorted(amostra[0]) if amostra else [], "erro": ""}
        except Exception as erro:  # noqa: BLE001
            log.error("Custos %s: %s", conjunto, erro)
            achados[conjunto] = {"campos": [], "erro": str(erro)[:160]}
    return achados


if __name__ == "__main__":
    executar()
