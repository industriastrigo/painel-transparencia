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

Documentado: **uma requisição por segundo**, e 250 itens por página.
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


# Teto de páginas por consulta. Não é folga arbitrária: era 400 e o volume de
# `pessoal_ativo` e `demais_custos` passou disso, então a coleta terminava
# `parcial` com o ano truncado — dado que a fonte mandou e nós não guardamos.
# O `completo=False` já denunciava; o teto é que estava baixo.
TETO_DE_PAGINAS = 1500


def _pedir(recurso: str, parametros: dict,
           paginas: int = TETO_DE_PAGINAS) -> tuple[list[dict], bool]:
    """Páginas do ORDS até acabar. Devolve `(linhas, completo)`.

    Três lições deste endpoint, todas caras:

    1. **`paginas=1` existe para o diagnóstico.** `descobrir()` só quer saber
       os NOMES dos campos e paginava o recorte inteiro: 232 páginas e quatro
       minutos de rede para responder uma pergunta que a primeira página já
       responde.

    2. **Falha no meio não pode zerar o que já veio.** A conexão caiu na
       página 232 e as 231 anteriores foram perdidas. Agora o que chegou é
       devolvido com `completo=False`, e quem chama decide.

    3. **Paginação longa precisa dar sinal de vida.** Sem log de progresso,
       onze minutos de coleta são indistinguíveis de travamento.
    """
    coletadas: list[dict] = []
    offset = 0
    TETO = paginas
    inicio = time.monotonic()

    for pagina in range(TETO):
        consulta = dict(parametros)
        if offset:
            consulta["offset"] = offset
        try:
            corpo = rede.buscar(FONTE, f"{config.TESOURO_CUSTOS}/{recurso}",
                                consulta)
        except Exception as erro:  # noqa: BLE001
            if not coletadas:
                raise
            # Perder 231 páginas porque a 232ª falhou é desperdício que a
            # pessoa paga em minutos de espera.
            log.warning("Custos %s: a conexão falhou na página %d (%s). "
                        "Devolvendo as %d linhas já recebidas, marcadas como "
                        "PARCIAIS.", recurso, pagina + 1, str(erro)[:80],
                        len(coletadas))
            return coletadas, False

        if isinstance(corpo, list):
            return coletadas + corpo, True
        if not isinstance(corpo, dict):
            log.warning("Custos %s: resposta %s, esperava objeto",
                        recurso, type(corpo).__name__)
            return coletadas, False

        itens = corpo.get("items")
        if itens is None:
            for valor in corpo.values():
                if isinstance(valor, list):
                    itens = valor
                    break
        if not isinstance(itens, list):
            log.warning("Custos %s: sem lista na resposta. Chaves: %s",
                        recurso, list(corpo)[:8])
            return coletadas, False

        coletadas.extend(itens)
        if not corpo.get("hasMore"):
            break
        offset += len(itens) or 1

        # Sinal de vida a cada 50 páginas. Sem isto, onze minutos de coleta
        # são indistinguíveis de travamento — e quem espera interrompe.
        if pagina and pagina % 50 == 0:
            decorrido = time.monotonic() - inicio
            log.info("Custos %s: %d páginas, %d linhas, %.0f s",
                     recurso, pagina, len(coletadas), decorrido)

        if pagina == TETO - 1:
            log.warning("Custos %s: teto de %d páginas — o resultado está "
                        "TRUNCADO, não completo", recurso, TETO)
            return coletadas, False

    if coletadas and recurso not in _campos_vistos:
        _campos_vistos[recurso] = set(coletadas[0])
        log.info("Custos %s: campos devolvidos — %s. Primeiro registro: %s",
                 recurso, ", ".join(sorted(coletadas[0])),
                 str(coletadas[0])[:300])
    return coletadas, True


def coletar(conjunto: str, ano: int,
            mes: int | None = None) -> tuple[list[dict], bool]:
    """Um recorte de custo, de um ano (ou de um mês dele)."""
    recurso = CONJUNTOS[conjunto]
    parametros: dict = {"ano": ano}
    if mes:
        parametros["mes"] = mes

    brutos, completo = _pedir(recurso, parametros)
    if not completo:
        log.warning("Custos %s/%s: resultado PARCIAL — o total abaixo é um "
                    "piso, não o valor do período. A marca fica como parcial "
                    "para a próxima execução tentar de novo.", conjunto, ano)

    # AGREGAÇÃO NA LEITURA, não depois. `pessoal_ativo` vem quebrado por sexo,
    # escolaridade, faixa etária e área de atuação: um único mês de 2025 passou
    # de 100 mil linhas e estourou o teto de páginas. O painel pergunta "quanto
    # custa este órgão", não "quanto custa este órgão para servidores de tal
    # faixa etária" — somar enquanto lê descarta a explosão combinatória sem
    # perder a resposta.
    somas: dict[tuple, float] = {}
    rotulos: dict[tuple, dict] = {}

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
        rotulos.setdefault(chave, {
            "orgao_codigo": opcional(_campo(bruto, "orgao_codigo"))})

    linhas = []
    for (orgao, item, ano_linha, mes_linha), valor in somas.items():
        linhas.append({
            "conjunto": conjunto,
            "orgao_nome": orgao,
            "orgao_codigo": rotulos[(orgao, item, ano_linha, mes_linha)]["orgao_codigo"],
            "item_custo": item,
            "ano": ano_linha,
            "mes": mes_linha,
            "valor": valor,
            "data_referencia": f"{ano_linha}-{(mes_linha or 12):02d}-01",
        })
    return linhas, completo


# A série começa em 2015, segundo a documentação de todos os seis recortes.
PRIMEIRO_ANO = 2015


def anos_disponiveis() -> list[int]:
    """Do início da série até o ano passado.

    O ano corrente fica de fora por padrão: ele está incompleto por
    construção, e coletá-lo grava um total que muda no mês seguinte.
    """
    return list(range(PRIMEIRO_ANO, date.today().year))


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
        try:
            if por_mes:
                linhas, completo = [], True
                for mes in range(1, 13):
                    parte, inteiro = coletar(conjunto, ano, mes)
                    linhas.extend(parte)
                    completo = completo and inteiro
            else:
                linhas, completo = coletar(conjunto, ano)
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
        controle.gravar_marca(FONTE, f"{conjunto}_{ano}", ano, len(linhas),
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
            amostra, _ = _pedir(recurso, {"ano": ano, "mes": 1}, paginas=1)
            achados[conjunto] = {
                "campos": sorted(amostra[0]) if amostra else [], "erro": ""}
        except Exception as erro:  # noqa: BLE001
            log.error("Custos %s: %s", conjunto, erro)
            achados[conjunto] = {"campos": [], "erro": str(erro)[:160]}
    return achados


if __name__ == "__main__":
    executar()
