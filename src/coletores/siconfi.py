"""Coletor SICONFI (Tesouro Nacional) — o "quem gasta mais".

API REST pública, sem autenticação, em apidatalake.tesouro.gov.br/ords/siconfi/tt/
cobrindo as 27 UFs e mais de 5.500 municípios. `id_ente` é o código IBGE, o
que faz a junção com o resto do projeto sair de graça.

Decisão de escopo: a despesa é agregada por FUNÇÃO de governo já na ingestão
(saúde, educação, previdência...). Guardar conta contábil folha a folha
levaria cada ano de ~150 mil para ~50 milhões de linhas sem responder nenhuma
pergunta a mais do painel.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from ..nucleo import armazem, config, controle, nomes, rede
from ..nucleo.valores import numero, opcional, texto
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.siconfi")

FONTE = "siconfi"

# Anexo 2 do DCA: despesa por função. É o recorte comparável entre entes.
ANEXO_DESPESA_FUNCAO = "DCA-Anexo I-D"

# Receitas orçamentárias. A coluna comparável é "Receitas Brutas Realizadas":
# BRUTAS, isto é, antes das deduções (FUNDEB, restituições). É o que o ente
# efetivamente arrecadou, e o painel rotula assim — chamar de "arrecadação
# líquida" seria um número diferente.
ANEXO_RECEITA = "DCA-Anexo I-C"

FUNCOES_DE_INTERESSE = {
    "10": "Saúde",
    "12": "Educação",
    "09": "Previdência Social",
    "06": "Segurança Pública",
    "26": "Transporte",
    "15": "Urbanismo",
    "08": "Assistência Social",
    "04": "Administração",
    "17": "Saneamento",
    "18": "Gestão Ambiental",
}


def _esfera(cod_ibge: str) -> str:
    if cod_ibge in ("0", "1"):
        return "uniao"
    return "estado" if len(str(cod_ibge)) == 2 else "municipio"


def coletar_dca(ano: int, cod_ibge: str) -> list[dict]:
    """Declaração de Contas Anuais de um ente."""
    corpo = rede.buscar(FONTE, f"{config.SICONFI}/dca", {
        "an_exercicio": ano,
        "no_anexo": ANEXO_DESPESA_FUNCAO,
        "id_ente": cod_ibge,
    })

    linhas = []
    for item in corpo.get("items", []):
        conta = texto(item.get("cod_conta"))
        coluna = texto(item.get("coluna"))
        # "Despesas Empenhadas" é a coluna comparável entre entes e anos
        if "Empenhada" not in coluna:
            continue
        valor = item.get("valor")
        if valor in (None, ""):
            continue
        funcao = conta.split(".")[0].zfill(2)
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": "anual",
            "cod_conta": conta,
            "cod_funcao": funcao,
            "funcao": FUNCOES_DE_INTERESSE.get(funcao, opcional(item.get("conta"))),
            "rotulo_conta": opcional(item.get("conta")),
            "estagio": coluna,
            "valor": numero(valor),
            "esfera": _esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-31",
        })
    return linhas


_contas_vistas: set[str] = set()


def coletar_dca_receita(ano: int, cod_ibge: str) -> list[dict]:
    """Receita orçamentária do ente — a arrecadação.

    As contas de receita são hierárquicas do mesmo jeito que as de despesa
    (`1.0.0.0.00.0.0` é o pai de `1.1.0.0.00.0.0`), então valem aqui as mesmas
    cautelas da armadilha 2j: quem somar tudo conta o mesmo real várias vezes.
    O nível é derivado do código na leitura, em `vw_receita_conta`.

    Na primeira execução o coletor registra no log as contas de primeiro nível
    que encontrou. Não é ruído: é como se confere, sem adivinhação, que a
    regra de nível corresponde ao que a fonte realmente devolve.
    """
    corpo = rede.buscar(FONTE, f"{config.SICONFI}/dca", {
        "an_exercicio": ano,
        "no_anexo": ANEXO_RECEITA,
        "id_ente": cod_ibge,
    })

    linhas = []
    for item in corpo.get("items", []):
        coluna = texto(item.get("coluna"))
        if "Realizada" not in coluna:
            continue
        valor = item.get("valor")
        if valor in (None, ""):
            continue
        conta = texto(item.get("cod_conta"))
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": "anual",
            "cod_conta": conta,
            "cod_funcao": None,
            "funcao": None,
            "rotulo_conta": opcional(item.get("conta")),
            "estagio": coluna,
            "valor": numero(valor),
            "esfera": _esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-12-31",
        })

    if linhas and not _contas_vistas:
        for linha in linhas:
            _contas_vistas.add(f"{linha['cod_conta']} {linha['rotulo_conta']}")
        log.info("SICONFI receita: contas devolvidas pelo ente %s — %s",
                 cod_ibge, " | ".join(sorted(_contas_vistas)[:12]))

    return linhas


# RREO Anexo 02: execução da despesa por FUNÇÃO e subfunção. É o recorte que
# o DCA não tem — o Anexo I-D dele é natureza da despesa (pessoal, juros,
# investimentos), não saúde e educação.
ANEXO_FUNCAO = "RREO-Anexo 02"

# A coluna do RREO Anexo 02 que interessa, em CAIXA ALTA como a fonte escreve.
#
# Três armadilhas numa linha só:
#
# 1. A fonte escreve "DESPESAS EMPENHADAS", maiúsculo. Um filtro por
#    "Empenhada" não casa — e devolve zero linha sem erro nenhum.
# 2. Há DUAS colunas de empenhado: "NO BIMESTRE" (os dois meses) e "ATÉ O
#    BIMESTRE" (acumulado no exercício). Somar as duas conta o bimestre
#    corrente duas vezes; escolher a errada troca o ano pelo bimestre.
# 3. **Os entes publicam em DOIS layouts.** A maioria manda o cabeçalho
#    inteiro, `DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)`; RN e BA mandam só
#    `Até o Bimestre (b)`, com o estágio implícito na posição da coluna. Casar
#    pelo cabeçalho inteiro descartava esses dois entes por completo, todos os
#    anos — e o log dizia, corretamente, "defeito de leitura, não ausência".
#
# O sufixo `(B)` é o que sobrevive aos dois layouts, e é ele que separa
# empenhada de liquidada: no layout curto a liquidada é `Até o Bimestre (d)`.
# Casar por "ATÉ O BIMESTRE" sem a letra pegaria as duas e somaria estágios
# diferentes do mesmo real — a armadilha 2j de novo, por outra porta.
COLUNA_EMPENHADA_ACUMULADA = "ATÉ O BIMESTRE (B)"

# As 28 funções de governo da **Portaria MOG nº 42, de 14/04/1999** — a norma
# que fixa a classificação funcional em todo o país, mais a Reserva de
# Contingência (99).
#
# Esta lista existe porque, no RREO Anexo 02, o `cod_conta` é a mesma string
# (`RREO2TotalDespesas`) em TODAS as linhas: função, subfunção e totais. Não há
# código para derivar nível nenhum — o que distingue "Saúde" de "Atenção
# Básica" é só o texto do campo `conta`.
#
# Como a lista de funções é fechada e normativa, casar contra ela é
# determinístico e auditável: o que está aqui é função (nível 1); o que não
# está é subfunção ou linha de total, e não entra em soma nenhuma. Uma linha
# "TOTAL (III) = (I + II)" não pode inflar o total por construção, porque
# nunca vai casar com um nome de função.
FUNCOES_OFICIAIS = {
    "01": "Legislativa",          "02": "Judiciária",
    "03": "Essencial à Justiça",  "04": "Administração",
    "05": "Defesa Nacional",      "06": "Segurança Pública",
    "07": "Relações Exteriores",  "08": "Assistência Social",
    "09": "Previdência Social",   "10": "Saúde",
    "11": "Trabalho",             "12": "Educação",
    "13": "Cultura",              "14": "Direitos da Cidadania",
    "15": "Urbanismo",            "16": "Habitação",
    "17": "Saneamento",           "18": "Gestão Ambiental",
    "19": "Ciência e Tecnologia", "20": "Agricultura",
    "21": "Organização Agrária",  "22": "Indústria",
    "23": "Comércio e Serviços",  "24": "Comunicações",
    "25": "Energia",              "26": "Transporte",
    "27": "Desporto e Lazer",     "28": "Encargos Especiais",
    "99": "Reserva de Contingência",
}

# Índice de busca: nome normalizado (sem acento, sem caixa) → código.
_POR_NOME = {nomes.chave_estrita(nome): cod
             for cod, nome in FUNCOES_OFICIAIS.items()}

# RGF: os dois anexos que respondem "quanto pesa a folha" e "quanto deve".
ANEXO_PESSOAL = "RGF-Anexo 01"
ANEXO_DIVIDA = "RGF-Anexo 02"

# ---------------------------------------------------------------- RGF
# NO RGF, O `cod_conta` SOZINHO NÃO DIZ O QUE O NÚMERO É. A mesma conta
# aparece em colunas diferentes, e é a COLUNA que dá o significado:
#
#     cod_conta=DespesaComPessoalTotal  coluna="Valor"                  → R$
#     cod_conta=DespesaComPessoalTotal  coluna="% sobre a RCL Ajustada" → 42,19
#
# Ignorar a coluna — como a primeira versão fazia — guarda um dos dois e
# descarta o outro, sem avisar. Foi o que deixou `percentual_pessoal` com 10
# linhas em 324 possíveis e `limite_maximo` com nenhuma.
#
# No Anexo 02 é pior: as colunas são "Até o 1º/2º/3º Quadrimestre" e "SALDO DO
# EXERCÍCIO ANTERIOR". Sem olhar a coluna, o saldo gravado podia ser o do ano
# PASSADO — um número plausível, do período errado, e ninguém veria.
#
# Por isso agora o grão é (indicador, MEDIDA), e o indicador é o `cod_conta`
# **verbatim**, sem tradução. Conta que eu não previ entra na tabela em vez de
# ser descartada: se amanhã faltar um conceito, é uma consulta, não uma
# recoleta de horas.
MEDIDA_VALOR = "valor"
MEDIDA_PERCENTUAL = "percentual"
MEDIDA_RESTOS = "restos_a_pagar"
MEDIDA_SALDO = "saldo"
MEDIDA_SALDO_ANTERIOR = "saldo_exercicio_anterior"

# Os conceitos que o painel lê, cada um como (cod_conta, medida). A lista de
# apelidos existe porque o nome mudou ao longo dos anos — mas errar um apelido
# hoje não perde mais dado nenhum, só deixa a view sem preencher aquela linha.
CONCEITOS_RGF = {
    "despesa_pessoal_bruta": (MEDIDA_VALOR, ("DespesaComPessoalBruta",)),
    "despesa_pessoal_liquida": (MEDIDA_VALOR, ("DespesaComPessoalLiquida",
                                               "DespesaLiquidaComPessoal")),
    "despesa_pessoal_total": (MEDIDA_VALOR, ("DespesaComPessoalTotal",)),
    "receita_corrente_liquida": (
        MEDIDA_VALOR, ("ReceitaCorrenteLiquidaAjustada",
                       "ReceitaCorrenteLiquidaLimiteLegal",
                       "RGF2ReceitaCorrenteLiquida")),
    # O percentual e os limites vivem TODOS na coluna de percentual.
    "percentual_pessoal": (MEDIDA_PERCENTUAL, ("DespesaComPessoalTotal",)),
    "limite_maximo": (MEDIDA_PERCENTUAL,
                      ("LimiteMaximoDespesaComPessoalTotal", "LimiteMaximo")),
    "limite_prudencial": (MEDIDA_PERCENTUAL,
                          ("LimitePrudencialDespesaComPessoalTotal",
                           "LimitePrudencial")),
    "limite_alerta": (MEDIDA_PERCENTUAL,
                      ("LimiteDeAlertaDespesaComPessoalTotal",)),
    # Anexo 02: saldo do quadrimestre pedido, nunca de outro.
    "divida_consolidada": (MEDIDA_SALDO, ("DividaConsolidada",)),
    "divida_consolidada_liquida": (MEDIDA_SALDO, ("DividaConsolidadaLiquida",)),
    "limite_divida": (MEDIDA_SALDO,
                      ("LimiteDefinidoPorResolucaoDoSenadoFederal",)),
    "percentual_divida": (MEDIDA_SALDO, ("PercentualDaDCLSobreARCL",)),
}

_ORDINAL = {1: "1º", 2: "2º", 3: "3º"}


def _medida_da_coluna(coluna: str, quadrimestre: int) -> str | None:
    """O que esta coluna mede — ou None se ela não interessa.

    Devolver None é uma decisão, não um descuido: as colunas `<MR-11>`…`<MR>`
    são o detalhamento mês a mês dos últimos doze meses. Guardá-las
    multiplicaria a tabela por doze sem responder nada que o painel pergunte.
    """
    limpa = texto(coluna).strip()
    alta = limpa.upper()

    if limpa.startswith("<MR"):
        return None
    if "% SOBRE A RCL" in alta:
        return MEDIDA_PERCENTUAL
    if "RESTOS A PAGAR" in alta:
        return MEDIDA_RESTOS
    if alta in ("VALOR", "TOTAL (ÚLTIMOS 12 MESES) (A)"):
        return MEDIDA_VALOR
    if "SALDO DO EXERCÍCIO ANTERIOR" in alta:
        return MEDIDA_SALDO_ANTERIOR
    # "Até o 3º Quadrimestre" — só o que foi pedido. As outras colunas são
    # períodos que têm marca própria; gravá-las aqui trocaria o período.
    if "QUADRIMESTRE" in alta:
        return (MEDIDA_SALDO
                if _ORDINAL.get(quadrimestre, "") in limpa else None)
    return MEDIDA_VALOR


_contas_funcao_vistas: set[str] = set()
_contas_rgf_vistas: set[str] = set()


def periodo_publicado(ano: int, passo: int, hoje: date | None = None) -> int:
    """Qual o último período do ano que já tem prazo de publicação vencido.

    O DCA fala de exercício fechado, então pedir "o ano" basta. O RREO e o
    RGF não: eles saem DURANTE o exercício, e pedir o 6º bimestre de um ano
    em curso devolve vazio — o que o painel leria como "ente não entregou",
    quando na verdade o prazo nem chegou.

    A LRF dá 30 dias após o fim de cada período. Em agosto, o 3º bimestre
    (fechado em junho, vencido em julho) é o último publicado; o 4º ainda
    está correndo. Ano passado devolve o último período do ano, sempre.

    `passo` é o tamanho do período em meses: 2 para bimestre, 4 para
    quadrimestre. Devolve 0 quando nada do ano venceu ainda.
    """
    hoje = hoje or date.today()
    if ano < hoje.year:
        return 12 // passo
    if ano > hoje.year:
        return 0
    return max(0, (hoje.month - 2) // passo)


def coletar_funcao(ano: int, bimestre: int, cod_ibge: str) -> list[dict]:
    """Despesa por função de governo, do RREO Anexo 02.

    Este é o número que o painel prometia e não tinha: quanto o ente gastou em
    saúde, em educação, em segurança. O DCA nunca respondeu isso — o anexo que
    coletávamos dele é natureza da despesa.

    **Este anexo não se parece com o DCA**, e supor que sim custou uma carga
    histórica inteira de 8 horas que voltou com zero linha em todos os 12 anos,
    sem um erro sequer no log. As quatro diferenças:

    1. `in_periodicidade='B'` é **obrigatório**. Sem ele a consulta não casa com
       nada e a resposta vem vazia — o que a varredura lê como "o ente não
       publicou". Doze anos × 27 UFs de "sem dado publicado".
    2. A coluna vem em CAIXA ALTA: `DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)`.
       Filtrar por `"Empenhada"` não casa com `EMPENHADAS`.
    3. Há duas colunas de empenhado — "NO BIMESTRE" e "ATÉ O BIMESTRE". A
       segunda é a acumulada no exercício, e é a que o painel usa.
    4. O `cod_conta` não tem hierarquia: o que separa a função "Saúde" da
       subfunção "Atenção Básica" é só o texto de `conta`. Por isso o nível
       vem de casar com a lista normativa (`FUNCOES_OFICIAIS`). Ele TEM,
       porém, exatamente dois valores — `RREO2TotalDespesas` e
       `RREO2TotalDespesasIntra` —, e é essa distinção que separa a despesa
       exceto-intra da intra-orçamentária. Ver `_bloco_da_conta`.

    Vai para tabela PRÓPRIA. Misturar com o DCA em `financas_ente` faria as
    views de despesa somarem natureza e função juntas — dois recortes do mesmo
    dinheiro, um total que seria o dobro do real e pareceria plausível.
    """
    corpo = rede.buscar(FONTE, f"{config.SICONFI}/rreo", {
        "an_exercicio": ano,
        "in_periodicidade": "B",
        "nr_periodo": bimestre,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": ANEXO_FUNCAO,
        "id_ente": cod_ibge,
    })
    return interpretar_funcao(corpo.get("items", []), ano, bimestre, cod_ibge)


def interpretar_funcao(itens: list, ano: int, bimestre: int,
                       cod_ibge: str) -> list[dict]:
    """A leitura do Anexo 02, separada de quem foi buscá-lo.

    Existe porque o mesmo JSON chega por dois caminhos: a rede, na coleta, e
    o arquivo bruto, no reprocessamento. As quatro regras do docstring acima
    — periodicidade, caixa alta, coluna acumulada, hierarquia pela ordem —
    custaram uma carga de oito horas para serem descobertas. Se elas
    existissem em duas cópias, uma delas envelheceria sozinha, em silêncio, e
    o painel passaria a mostrar dois números diferentes conforme o caminho
    por onde o dado entrou.
    """
    linhas = []
    colunas_vistas = set()
    # A FUNÇÃO À QUAL A SUBFUNÇÃO PERTENCE só existe na ORDEM do documento.
    #
    # O Anexo 02 lista uma função e, logo abaixo, as subfunções dela. A
    # resposta não traz nenhum campo ligando uma à outra — e o nome da
    # subfunção se repete: "Administração Geral" e "Demais Subfunções"
    # aparecem sob Saúde, sob Educação e sob mais meia dúzia de funções.
    #
    # Sem a função-mãe na identidade da linha, essas repetições colidiam na
    # chave primária e o merge guardava só a última: **4.867 linhas legítimas
    # descartadas numa carga**. Sergipe ficou com UMA "Formação de Recursos
    # Humanos" onde o Acre — que prefixa o nome com o código da função e por
    # isso escapou — ficou com duas.
    #
    # Alguns entes prefixam ("FU06 - Administração Geral") e outros não. Não
    # dá para depender disso: quem carrega a hierarquia é a posição no
    # demonstrativo, e é dela que a função-mãe sai.
    funcao_mae = None
    bloco_atual = None

    for item in itens:
        coluna = texto(item.get("coluna"))
        colunas_vistas.add(coluna)
        if COLUNA_EMPENHADA_ACUMULADA not in coluna.upper():
            continue
        valor = item.get("valor")
        if valor in (None, ""):
            continue

        rotulo = opcional(item.get("conta"))
        bloco = _bloco_da_conta(item.get("cod_conta"))
        # O `rotulo` da fonte descreve o bloco por extenso ("Total das
        # Despesas Exceto Intra-Orçamentárias"), mas vem NULO em 15% das
        # linhas — e era ele que eu usava como discriminador. Onde vinha
        # nulo, a despesa intra e a exceto-intra da mesma função caíam na
        # mesma chave e uma apagava a outra: em Alagoas/2016, a Legislativa
        # exceto-intra (R$ 245,8 mi) e a intra (R$ 33,6 mi) viraram uma só.
        # 1.737 linhas perdidas assim numa reconstrução. Guardo o rótulo
        # como descrição, mas quem decide o bloco é `cod_conta`, que tem
        # exatamente dois valores e nunca falta.
        descricao_bloco = opcional(item.get("rotulo"))
        cod_funcao = _funcao_oficial(rotulo)

        # Bloco novo (intra × exceto-intra) recomeça a contagem: a primeira
        # subfunção do bloco seguinte não pertence à última função do anterior.
        if bloco != bloco_atual:
            bloco_atual, funcao_mae = bloco, None
        if cod_funcao:
            funcao_mae = cod_funcao

        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": f"bimestre_{bimestre}",
            # O `cod_conta` da fonte não identifica a linha (é sempre
            # `RREO2TotalDespesas`), e ele faz parte da chave primária. Quem
            # identifica é bloco + função-mãe + texto da conta.
            "cod_conta": f"{texto(bloco)}|{funcao_mae or '--'}|{rotulo}",
            "descricao_bloco": descricao_bloco,
            "cod_funcao": cod_funcao,
            "cod_funcao_mae": funcao_mae,
            "funcao": FUNCOES_OFICIAIS.get(cod_funcao or "", None),
            "funcao_mae": FUNCOES_OFICIAIS.get(funcao_mae or "", None),
            "rotulo_conta": rotulo,
            "bloco": bloco,
            "estagio": coluna,
            "valor": numero(valor),
            "esfera": _esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-{min(bimestre * 2, 12):02d}-01",
        })

    _conferir_funcao(cod_ibge, itens, linhas, colunas_vistas)
    return linhas


def _conferir_funcao(cod_ibge: str, itens: list, linhas: list,
                     colunas: set[str]) -> None:
    """Avisa quando a resposta veio, mas o filtro não deixou nada passar.

    É o aviso que teria economizado a madrugada. "27 entes sem dado publicado"
    e "27 entes cuja resposta eu não soube ler" são coisas muito diferentes, e
    o log precisa distinguir as duas — senão um erro nosso se disfarça de
    ausência da fonte.
    """
    if itens and not linhas:
        log.error(
            "RREO função, ente %s: a fonte devolveu %d linha(s), mas NENHUMA "
            "passou no filtro de coluna. Procurava %r; a resposta traz: %s. "
            "Isto é defeito de leitura, não ausência de dado.",
            cod_ibge, len(itens), COLUNA_EMPENHADA_ACUMULADA,
            " | ".join(sorted(colunas)[:8]))
        return

    if linhas and not _contas_funcao_vistas:
        for linha in linhas[:20]:
            _contas_funcao_vistas.add(
                f"{linha['rotulo_conta']}"
                f"{'' if linha['cod_funcao'] else ' (subfunção)'}")
        conhecidas = sum(1 for l in linhas if l["cod_funcao"])
        log.info("RREO função: ente %s devolveu %d linha(s), %d casaram com "
                 "função oficial — %s", cod_ibge, len(linhas), conhecidas,
                 " | ".join(sorted(_contas_funcao_vistas)[:10]))


def _bloco_da_conta(cod_conta) -> str:
    """Exceto-intra ou intra-orçamentária, a partir do `cod_conta` da fonte.

    O Anexo 02 lista as funções duas vezes: uma para a despesa comum e outra
    para a intra-orçamentária (o que um órgão do ente paga a outro órgão do
    mesmo ente). São valores diferentes da mesma função, e precisam de
    identidades diferentes — somá-los às cegas conta o mesmo dinheiro duas
    vezes; colidi-los na chave apaga um dos dois.

    A fonte marca isso no sufixo `Intra` do `cod_conta`, e só aí: o campo
    `rotulo`, que também descreve o bloco, falta em 15% das linhas.
    """
    texto_conta = texto(cod_conta)
    return "intra" if texto_conta.lower().endswith("intra") else "exceto_intra"


def _funcao_oficial(conta: str | None) -> str | None:
    """O código da função, se este texto for o nome de uma função de governo.

    Devolve `None` para subfunção e para linha de total — e é justamente esse
    `None` que impede a soma de inflar: `vw_despesa_por_funcao` só soma o que
    casou aqui. Uma linha "TOTAL (III) = (I + II)" nunca casa.
    """
    if not conta:
        return None
    return _POR_NOME.get(nomes.chave_estrita(conta))


def coletar_rgf(ano: int, quadrimestre: int, cod_ibge: str,
                poder: str = "E") -> list[dict]:
    """Despesa com pessoal e dívida consolidada, dos anexos 01 e 02 do RGF.

    Duas perguntas que nenhuma outra fonte do painel responde:

    - **A folha cabe no limite?** O RGF publica a despesa, a receita, o
      percentual E o limite aplicável. A resposta é do próprio ente — o painel
      não crava 60% no código, porque o limite muda por esfera e por poder.
    - **Quanto deve?** Dívida consolidada líquida é SALDO. O SADIPEM diz
      quanto o ente pediu para tomar emprestado; isto diz quanto ainda deve.

    **Grava tudo o que a fonte manda**, indicador por indicador, com o
    `cod_conta` verbatim e a medida derivada da coluna. Traduzir para uma lista
    curta de apelidos foi o que fez `limite_maximo` não existir no acervo: o
    nome real é `LimiteMaximoDespesaComPessoalTotal`, e o apelido esperado era
    `LimiteMaximo`. Guardando tudo, um apelido errado deixa uma view sem
    preencher — não apaga o dado.
    """
    linhas = []
    for anexo in (ANEXO_PESSOAL, ANEXO_DIVIDA):
        corpo = rede.buscar(FONTE, f"{config.SICONFI}/rgf", {
            "an_exercicio": ano,
            "in_periodicidade": "Q",
            "nr_periodo": quadrimestre,
            "co_tipo_demonstrativo": "RGF",
            "no_anexo": anexo,
            "co_poder": poder,
            "id_ente": cod_ibge,
        })
        linhas.extend(interpretar_rgf(corpo.get("items", []), ano,
                                      quadrimestre, cod_ibge, poder, anexo))
    return linhas


def interpretar_rgf(itens: list, ano: int, quadrimestre: int, cod_ibge: str,
                    poder: str, anexo: str) -> list[dict]:
    """A leitura de UM anexo do RGF, separada de quem foi buscá-lo.

    Mesma razão de `interpretar_funcao`: o reprocessamento a partir do
    arquivo bruto precisa da mesma regra, e a regra aqui é sutil — no RGF é a
    COLUNA que decide o significado, e a mesma conta aparece em `Valor` e em
    `% sobre a RCL Ajustada`.
    """
    linhas = []
    for item in itens:
        medida = _medida_da_coluna(texto(item.get("coluna")), quadrimestre)
        if medida is None:
            continue
        valor = numero(item.get("valor"))
        if valor is None:
            continue
        conta = texto(item.get("cod_conta"))
        if not conta:
            continue

        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": f"quadrimestre_{quadrimestre}",
            "poder": poder,
            "indicador": conta,
            "medida": medida,
            "rotulo": opcional(item.get("conta")),
            # A SEÇÃO do demonstrativo, campo `rotulo` da fonte. Não é
            # enfeite: `TransferenciasObrigatoriasDaUniao...` aparece nos
            # DOIS anexos, e contas se repetem entre seções do mesmo anexo.
            # Sem `anexo` e `secao` na chave, essas linhas colidiam e o merge
            # guardava a última — 953 numa carga.
            "secao": opcional(item.get("rotulo")),
            "anexo": anexo,
            "valor": valor,
            "esfera": _esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-{min(quadrimestre * 4, 12):02d}-01",
        })

    if linhas and not _contas_rgf_vistas:
        for linha in linhas[:40]:
            _contas_rgf_vistas.add(f"{linha['indicador']}/{linha['medida']}")
        log.info("RGF: ente %s devolveu %d linha(s) — %s",
                 cod_ibge, len(linhas),
                 " | ".join(sorted(_contas_rgf_vistas)[:12]))
    return linhas


def entregou(ano: int, cod_ibge: str) -> list[dict]:
    """O ente entregou os relatórios daquele exercício?

    Responde a ambiguidade mais incômoda do painel: **cinza no mapa significa
    "não coletamos" ou "o ente não prestou contas"?** As duas aparecem igual,
    e são coisas muito diferentes — a segunda é, ela mesma, um achado de
    transparência.

    Uma requisição por ente, então NUNCA é varredura completa: consulta-se só
    quem ficou sem dado, que é da ordem de dezenas, não de milhares.
    """
    corpo = rede.buscar(FONTE, f"{config.SICONFI}/extrato_entregas", {
        "id_ente": cod_ibge,
        "an_referencia": ano,
    })
    return [{
        "entregavel": opcional(item.get("entregavel")),
        "status": opcional(item.get("status_relatorio")),
        "periodo": item.get("periodo"),
        "data_status": opcional(item.get("data_status")),
    } for item in corpo.get("items", [])]


def explicar_ausencia(ano: int, entes: list[str]) -> dict[str, str]:
    """Para cada ente sem dado, o que o SICONFI diz sobre a entrega dele.

    Devolve `{cod_ibge: explicação}`. Três desfechos possíveis, e a diferença
    entre eles é a informação:

    - **não entregou** — o ente não prestou contas naquele exercício;
    - **entregou, e não coletamos** — o buraco é nosso, e é para consertar;
    - **a fonte não sabe dizer** — nem o extrato responde.
    """
    explicacoes = {}
    for cod in entes:
        try:
            entregas = entregou(ano, cod)
        except Exception as erro:  # noqa: BLE001
            explicacoes[cod] = f"não consegui perguntar ao SICONFI: {erro}"
            continue

        if not entregas:
            explicacoes[cod] = "o ente NÃO entregou relatório neste exercício"
            continue

        homologados = [e for e in entregas if (e["status"] or "").upper() == "HO"]
        if homologados:
            quais = ", ".join(sorted({e["entregavel"] or "?" for e in homologados}))
            explicacoes[cod] = (f"o ente ENTREGOU ({quais}) — a lacuna é da "
                                f"nossa coleta, não da prestação de contas")
        else:
            situacoes = ", ".join(sorted({e["status"] or "?" for e in entregas}))
            explicacoes[cod] = (f"entregou sem homologação (situação: "
                                f"{situacoes})")
    return explicacoes


def coletar_rreo(ano: int, bimestre: int, cod_ibge: str) -> list[dict]:
    """Relatório Resumido da Execução Orçamentária — visão bimestral."""
    corpo = rede.buscar(FONTE, f"{config.SICONFI}/rreo", {
        "an_exercicio": ano,
        "nr_periodo": bimestre,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": "RREO-Anexo 02",
        "id_ente": cod_ibge,
    })
    linhas = []
    for item in corpo.get("items", []):
        valor = item.get("valor")
        if valor in (None, ""):
            continue
        conta = texto(item.get("cod_conta"))
        linhas.append({
            "cod_ibge": str(cod_ibge),
            "ano": ano,
            "periodo": f"bimestre_{bimestre}",
            "cod_conta": conta,
            "cod_funcao": conta.split(".")[0].zfill(2),
            "funcao": item.get("conta"),
            "rotulo_conta": item.get("conta"),
            "estagio": item.get("coluna"),
            "valor": numero(valor),
            "esfera": _esfera(cod_ibge),
            "uf": opcional(item.get("uf")),
            "data_referencia": f"{ano}-{bimestre * 2:02d}-01",
        })
    return linhas


# ------------------------------------------------------------ varredura
def listar_entes(nivel: str, uf: str | None = None) -> list[str]:
    filtros = [f"nivel = '{nivel}'"]
    if uf:
        filtros.append(f"sigla_uf = '{uf.upper()}'")
    df = armazem.ler("dim_ente", filtro=" AND ".join(filtros),
                     colunas=["cod_ibge", "nome"])
    if df.empty:
        log.error("dim_ente vazia — rode o coletor do IBGE primeiro")
        return []
    return df["cod_ibge"].astype(str).tolist()


# Cada recurso tem tabela própria. Misturar função com natureza, ou o RGF
# com qualquer um dos dois, faria as views somarem recortes diferentes do
# mesmo dinheiro — o erro que separou as duas transferências.
TABELA_DE = {
    "dca": "financas_ente",
    "receita": "financas_ente",
    "rreo": "financas_ente",
    "funcao": "despesa_funcao",
    "rgf": "indicador_fiscal",
}


def varrer(
    ano: int,
    entes: list[str],
    recurso: str = "dca",
    bimestre: int = 6,
    quadrimestre: int = 3,
    trabalhadores: int = 6,
    intervalo: float = 1.0,
    lote: int = 500,
    amostra_inicial: int = 200,
    refazer_vazios: bool = False,
    refazer_tudo: bool = False,
) -> dict[str, int]:
    """Coleta uma lista grande de entes em paralelo, retomável.

    Três coisas fazem isso funcionar em 5.570 municípios:

    1. **Retomada por ente.** Cada ente tentado vira uma linha em
       `_ctl/coleta_ente`. Se a máquina hibernar no meio, a próxima execução
       começa de onde parou — e repete só os que deram erro.
    2. **Gravação em lotes.** Todos os municípios de um ano caem na MESMA
       partição (`ano=`, `esfera=municipio`), e cada merge reescreve o arquivo
       inteiro. Gravar de 500 em 500 troca 5.570 reescritas por 12.
    3. **Freio global, não por thread.** Os trabalhadores escondem a latência
       da resposta (~1s por ente); quem controla a taxa de saída é o freio em
       `nucleo.rede`. Paralelismo aqui não é para pedir mais rápido — é para
       não ficar parado esperando.
    """
    pendentes = controle.entes_pendentes(
        FONTE, recurso, ano, entes,
        refazer_vazios=refazer_vazios, refazer_tudo=refazer_tudo)

    ja_feitos = len(entes) - len(pendentes)
    if ja_feitos:
        log.info("SICONFI %s/%d: %d entes já resolvidos, %d pendentes",
                 recurso, ano, ja_feitos, len(pendentes))
    if not pendentes:
        log.info("SICONFI %s/%d: nada pendente", recurso, ano)
        return {"entes": 0, "linhas": 0, "erros": 0, "vazios": 0}

    rede.definir_intervalo(FONTE, intervalo)
    inicio = time.monotonic()
    total = {"entes": 0, "linhas": 0, "erros": 0, "vazios": 0}
    buffer_linhas: list[dict] = []
    buffer_controle: list[dict] = []
    trava = threading.Lock()
    desistir = threading.Event()
    # Só faz sentido desistir quando continuar custa caro. Numa lista de 27
    # UFs, seis respostas vazias não autorizam concluir nada sobre o ano; numa
    # de 5.570, duzentas autorizam.
    amostra = amostra_inicial
    pode_desistir = len(pendentes) > amostra * 2

    def descarregar() -> None:
        """Grava o que está no buffer. Chamado já com a trava tomada."""
        nonlocal buffer_linhas, buffer_controle
        if buffer_linhas:
            armazem.mesclar(TABELA_DE[recurso], buffer_linhas,
                            f"{FONTE}_{recurso}")
            buffer_linhas = []
        if buffer_controle:
            controle.registrar_entes(FONTE, recurso, ano, buffer_controle)
            buffer_controle = []

    def trabalhar(cod: str) -> None:
        if desistir.is_set():
            return
        try:
            if recurso == "dca":
                linhas = coletar_dca(ano, cod)
            elif recurso == "receita":
                linhas = coletar_dca_receita(ano, cod)
            elif recurso == "funcao":
                linhas = coletar_funcao(ano, bimestre, cod)
            elif recurso == "rgf":
                linhas = coletar_rgf(ano, quadrimestre, cod)
            else:
                linhas = coletar_rreo(ano, 6, cod)
            desfecho = {"cod_ibge": cod, "linhas": len(linhas),
                        "situacao": "ok" if linhas else "vazio"}
        except Exception as erro:  # noqa: BLE001
            linhas = []
            desfecho = {"cod_ibge": cod, "linhas": 0, "situacao": "erro",
                        "detalhe": str(erro)}

        with trava:
            buffer_linhas.extend(linhas)
            buffer_controle.append(desfecho)
            total["entes"] += 1
            total["linhas"] += len(linhas)
            if desfecho["situacao"] == "erro":
                total["erros"] += 1
            elif desfecho["situacao"] == "vazio":
                total["vazios"] += 1

            # Exercício não publicado: a amostra inicial voltou 100% vazia.
            # Continuar significaria mais 5.400 requisições para confirmar o
            # que já se sabe — foram 14 minutos de 2026 antes disto existir.
            if (pode_desistir and total["entes"] >= amostra
                    and total["linhas"] == 0 and total["erros"] == 0
                    and not desistir.is_set()):
                desistir.set()
                log.warning(
                    "SICONFI %s/%d: os %d primeiros entes vieram sem nenhum "
                    "dado. O exercício de %d provavelmente ainda não foi "
                    "publicado — abandonando a varredura dos %d restantes.",
                    recurso, ano, total["entes"], ano,
                    len(pendentes) - total["entes"])
                return

            if len(buffer_controle) >= lote:
                descarregar()
                decorrido = time.monotonic() - inicio
                restantes = len(pendentes) - total["entes"]
                ritmo = total["entes"] / max(decorrido, 0.001)
                log.info("SICONFI %s/%d: %d/%d entes · %d linhas · %d erros "
                         "· ~%.0f min restantes",
                         recurso, ano, total["entes"], len(pendentes),
                         total["linhas"], total["erros"],
                         restantes / max(ritmo, 0.001) / 60)

    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        try:
            list(executor.map(trabalhar, pendentes))
        except KeyboardInterrupt:
            log.warning("interrompido — o que já foi coletado está gravado; "
                        "rode de novo para retomar")
            raise
        finally:
            with trava:
                descarregar()

    minutos = (time.monotonic() - inicio) / 60

    if desistir.is_set():
        # As marcas de "vazio" gravadas até aqui fariam a próxima execução
        # pular tudo em silêncio quando o exercício finalmente for publicado.
        # Melhor não guardar nada do que guardar uma resposta que era só
        # "ainda não".
        esquecidas = controle.esquecer_entes(FONTE, recurso, ano)
        log.warning("SICONFI %s/%d abandonado em %.1f min. %d marcas "
                    "apagadas para não bloquear uma nova tentativa quando o "
                    "dado sair.", recurso, ano, minutos, esquecidas)
        controle.gravar_marca(
            FONTE, f"{recurso}_{ano}", None, 0, situacao="nao_publicado",
            detalhe=f"amostra de {amostra} entes sem nenhum dado")
        total["abandonado"] = 1
        return total

    log.info("SICONFI %s/%d concluído: %d entes em %.1f min · %d linhas · "
             "%d sem dado publicado · %d com erro",
             recurso, ano, total["entes"], minutos, total["linhas"],
             total["vazios"], total["erros"])
    # Zero linha nunca é "ok" sem justificativa explícita: `dca_2026` ficava
    # marcado ok com 0 linhas, indistinguível de uma coleta bem-sucedida.
    if total["erros"]:
        situacao = "parcial"
    elif total["linhas"] == 0:
        situacao = "sem_dado"
    else:
        situacao = "ok"

    controle.gravar_marca(FONTE, f"{recurso}_{ano}", ano, total["linhas"],
                          situacao=situacao,
                          detalhe=f"{total['erros']} entes com erro"
                          if total["erros"] else
                          ("nenhum ente publicou o exercício"
                           if situacao == "sem_dado" else ""))
    return total


def executar(ano: int | None = None, entes: list[str] | None = None,
             limite: int | None = None, nivel: str = "estado",
             uf: str | None = None, trabalhadores: int = 6,
             intervalo: float = 1.0, refazer_vazios: bool = False,
             refazer_tudo: bool = False,
             recursos: tuple[str, ...] = ("dca", "receita"),
             bimestre: int | None = None,
             quadrimestre: int | None = None) -> int:
    """Carrega os relatórios do ano.

    `nivel='estado'` (padrão) são 27 entes e leva menos de um minuto.
    `nivel='municipio'` são 5.570 e leva 15 a 25 minutos na primeira vez —
    depois, só os pendentes.

    `bimestre` e `quadrimestre` em branco significam "o último já publicado
    para este ano" — ver `periodo_publicado`. Passar o número na mão continua
    valendo, para reconstruir a série período a período.
    """
    ano = ano or date.today().year - 1
    if bimestre is None:
        bimestre = periodo_publicado(ano, 2)
    if quadrimestre is None:
        quadrimestre = periodo_publicado(ano, 4)

    if entes is None:
        alvos = (["estado", "municipio"] if nivel == "todos" else [nivel])
        entes = [cod for n in alvos for cod in listar_entes(n, uf)]
    if not entes:
        return 0
    if limite:
        entes = entes[:limite]

    # Despesa e receita são dois anexos, logo duas varreduras. Cada uma tem a
    # própria retomada em `_ctl/coleta_ente`, então interromper entre elas não
    # custa o que já foi feito.
    linhas = 0
    for recurso in recursos:
        # Pedir um período que ainda não venceu devolve vazio, e vazio aqui
        # seria lido como "ninguém entregou". Dizer que o prazo não chegou é
        # uma resposta melhor do que 5.570 linhas ausentes.
        if recurso == "funcao" and not bimestre:
            log.info("RREO de %s: nenhum bimestre venceu ainda — nada a "
                     "coletar. Peça o ano anterior.", ano)
            continue
        if recurso == "rgf" and not quadrimestre:
            log.info("RGF de %s: nenhum quadrimestre venceu ainda — nada a "
                     "coletar. Peça o ano anterior.", ano)
            continue
        total = varrer(ano, entes, recurso=recurso, bimestre=bimestre,
                       quadrimestre=quadrimestre,
                       trabalhadores=trabalhadores,
                       intervalo=intervalo, refazer_vazios=refazer_vazios,
                       refazer_tudo=refazer_tudo)
        linhas += total["linhas"]
    return linhas


if __name__ == "__main__":
    executar()
