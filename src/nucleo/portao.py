"""Portão de qualidade da carga — asserções sobre o RESULTADO, não sobre o código.

A suíte de testes verifica **forma**: se o coletor lê o CSV, se a chave é
única, se a view devolve as colunas do contrato. Ela passou inteira na noite
de 26/08 enquanto a carga gravava zero linha, porque zero linha é uma forma
perfeitamente válida.

Este módulo verifica outra coisa: o que a carga PRODUZIU, comparado com o que
ela recebeu e com o que existia antes. São perguntas que nenhum teste de
unidade responde, porque a resposta depende do acervo:

  1. **Volume.** A fonte mandou N linhas; o armazém gravou N? A diferença tem
     nome (colapso de chave, partição nula) e precisa caber num limiar.
  2. **Preenchimento.** A coluna `situacao` estava 98% preenchida ontem e está
     3% hoje? O formato continua válido, o dado morreu.
  3. **Registro-ouro.** Um município, um ano, um valor conferido à mão contra
     o documento publicado. É o único teste que prova que o número está certo,
     e não apenas presente.

E, principalmente, o portão **barra**. Um contador que aparece no resumo é da
mesma família do aviso que saiu 239 vezes e ninguém leu: informação correta
onde ninguém decide nada com ela. Aqui, achado de bloqueio devolve código de
saída diferente de zero, e quem chamou decide se publica.

    from src.nucleo import portao
    veredito = portao.avaliar()
    veredito.relatar()
    if veredito.bloqueia:
        return 2
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import duckdb

from . import armazem, config, controle
from .esquema import COLUNAS_CONTROLE, TABELAS, obter
from .registro import obter as obter_log

log = obter_log("nucleo.portao")


# ---------------------------------------------------------------- limiares
# Perda tolerada entre o que a fonte mandou e o que o armazém gravou.
# Não é zero por um motivo concreto: o descarte de partição nula é legítimo em
# fontes que publicam linha sem data. É baixo porque, acima disso, a hipótese
# mais provável deixa de ser "a fonte veio suja" e passa a ser "a chave da
# tabela está errada".
PERDA_TOLERADA = 0.005

# Queda de preenchimento, em pontos da taxa (0 a 1), que caracteriza
# regressão. 0,20 pega o caso real (98% -> 3%) com folga e não dispara em
# variação normal de cobertura entre exercícios.
QUEDA_TOLERADA = 0.20

# Abaixo disto a taxa é ruído: uma tabela com 12 linhas oscila 8 pontos com
# uma linha a mais.
MINIMO_PARA_PERFILAR = 200

_IGNORAR_COLUNA = set(COLUNAS_CONTROLE) | {"sk"}

# Colunas cujo preenchimento na fonte oficial é estruturalmente parcial por
# desenho do demonstrativo (ex: agregadores do RREO Anexo 02 sem função,
# anexos do RGF sem coluna quadrimestral, despesas federais sem natureza jurídica).
# Quedas nessas colunas geram aviso informativo no portão, sem bloquear a publicação.
_COLUNAS_OPCIONAIS_NORMA = {
    "custo_orgao.natureza_juridica",
    "despesa_funcao.cod_funcao",
    "despesa_funcao.funcao",
    "despesa_funcao.cod_funcao_mae",
    "despesa_funcao.funcao_mae",
    "despesa_funcao.descricao_bloco",
    "indicador_ente.unidade",
    "indicador_ente.data_referencia",
    "indicador_fiscal.coluna",
    "transferencia_uniao.cod_siafi",
    "transferencia_uniao.nome_ente",
}


# ----------------------------------------------------------------- achados
@dataclass(frozen=True)
class Achado:
    """Um problema encontrado. `bloqueia` decide se a carga pode publicar."""

    regra: str
    alvo: str
    bloqueia: bool
    mensagem: str


@dataclass
class Veredito:
    achados: list[Achado] = field(default_factory=list)

    @property
    def bloqueios(self) -> list[Achado]:
        return [a for a in self.achados if a.bloqueia]

    @property
    def avisos(self) -> list[Achado]:
        return [a for a in self.achados if not a.bloqueia]

    @property
    def bloqueia(self) -> bool:
        return bool(self.bloqueios)

    def relatar(self) -> None:
        """Escreve o veredito no log, com o bloqueio em primeiro lugar."""
        if not self.achados:
            log.info("PORTÃO: nenhuma regra violada.")
            return
        if self.bloqueios:
            log.error("=" * 60)
            log.error("PORTÃO BLOQUEOU A CARGA — %d regra(s) violada(s):",
                      len(self.bloqueios))
            for a in self.bloqueios:
                log.error("   [%s] %s: %s", a.regra, a.alvo, a.mensagem)
        for a in self.avisos:
            log.warning("[portão/%s] %s: %s", a.regra, a.alvo, a.mensagem)


# ------------------------------------------------------------- 1. volume
def conferir_volume(perda_tolerada: float = PERDA_TOLERADA) -> list[Achado]:
    """Linhas recebidas × linhas gravadas, tabela a tabela.

    Os contadores são alimentados por `armazem` durante a própria carga, então
    esta conferência não relê nada do disco e custa microssegundos. É de
    propósito: a regra que teria matado o defeito das transferências em
    segundos não pode ser a que só roda quando alguém lembra.
    """
    achados: list[Achado] = []
    for tabela, medida in sorted(armazem.MEDIDAS.items()):
        recebidas = medida.get("recebidas", 0)
        gravadas = medida.get("gravadas", 0)
        if recebidas == 0:
            continue

        perdidas = recebidas - gravadas
        if perdidas <= 0:
            continue

        fracao = perdidas / recebidas
        motivos = []
        if medida.get("colapsadas"):
            motivos.append(f"{medida['colapsadas']} por colisão de chave")
        if medida.get("particao_nula"):
            motivos.append(f"{medida['particao_nula']} por partição nula")
        porque = "; ".join(motivos) or "causa não identificada"

        achados.append(Achado(
            regra="volume",
            alvo=tabela,
            bloqueia=fracao > perda_tolerada,
            mensagem=(
                f"a fonte mandou {recebidas} linha(s), o armazém gravou "
                f"{gravadas} ({fracao:.1%} perdidas: {porque}). "
                f"Perda acima de {perda_tolerada:.1%} quase sempre significa "
                f"chave de grão mais grosso que o dado."),
        ))

    # Tabela que recebeu zero em toda a carga é o caso de 26/08: a suíte passa,
    # a fonte respondeu, e nada entrou.
    for tabela, medida in sorted(armazem.MEDIDAS.items()):
        if medida.get("recebidas", 0) == 0 and medida.get("tentativas", 0):
            achados.append(Achado(
                regra="volume", alvo=tabela, bloqueia=True,
                mensagem="a carga chamou o merge desta tabela e nenhuma linha "
                         "chegou. Coletor respondendo vazio ou contrato de "
                         "colunas sem correspondência na resposta."))
    return achados


# ------------------------------------------------------- 2. preenchimento
def _colunas_de(con: duckdb.DuckDBPyConnection, leitura: str) -> list[str]:
    try:
        descricao = con.execute(f"DESCRIBE SELECT * FROM {leitura}").fetchall()
    except duckdb.Error:
        return []
    return [linha[0] for linha in descricao if linha[0] not in _IGNORAR_COLUNA]


def perfil(nome_tabela: str,
           con: duckdb.DuckDBPyConnection | None = None) -> dict[str, float]:
    """Taxa de preenchimento (0 a 1) de cada coluna da tabela.

    Uma única varredura agregada: o Parquet é colunar, então isto lê só os
    metadados e as páginas necessárias, não o acervo inteiro.
    """
    tabela = obter(nome_tabela)
    padrao = armazem.padrao_leitura(tabela)
    if tabela.camada == "fato":
        if not any(armazem.caminho_base(tabela).rglob("*.parquet")):
            return {}
        leitura = (f"read_parquet('{padrao}', hive_partitioning=1, "
                   f"union_by_name=1)")
    else:
        if not Path(padrao).exists():
            return {}
        leitura = f"read_parquet('{padrao}')"

    proprio = con is None
    con = con or armazem.conectar()
    try:
        colunas = _colunas_de(con, leitura)
        if not colunas:
            return {}
        campos = ", ".join(f'COUNT("{c}") AS "{c}"' for c in colunas)
        linha = con.execute(
            f"SELECT COUNT(*) AS _total, {campos} FROM {leitura}").fetchone()
        total = linha[0] or 0
        if total == 0:
            return {}
        return {c: (v or 0) / total for c, v in zip(colunas, linha[1:])} | {
            "_total": float(total)}
    finally:
        if proprio:
            con.close()


def _perfil_anterior() -> dict[tuple[str, str], dict]:
    df = armazem.ler("qualidade")
    if df.empty:
        return {}
    return {(r["tabela"], r["coluna"]): r for _, r in df.iterrows()}


def conferir_preenchimento(
    tabelas: Sequence[str] | None = None,
    queda_tolerada: float = QUEDA_TOLERADA,
    gravar: bool = True,
) -> list[Achado]:
    """Compara a taxa de preenchimento de cada coluna com a REFERÊNCIA.

    A comparação é contra a melhor taxa já observada, não contra a carga
    anterior. Comparar com a anterior tem um buraco: a primeira carga ruim
    vira a nova referência e a segunda passa. Uma coluna que já esteve 98%
    preenchida tem de voltar a 98%, ou continuar acusando.
    """
    achados: list[Achado] = []
    anterior = _perfil_anterior()
    alvos = list(tabelas) if tabelas else [
        n for n, t in TABELAS.items() if t.camada in ("dim", "fato")]

    novas_linhas = []
    momento = datetime.now(timezone.utc)
    con = armazem.conectar()
    try:
        for nome in sorted(alvos):
            atual = perfil(nome, con)
            if not atual:
                continue
            total = int(atual.pop("_total", 0))
            if total < MINIMO_PARA_PERFILAR:
                continue

            for coluna, taxa in atual.items():
                antes = anterior.get((nome, coluna))
                # Se a referência anterior foi gravada sobre uma amostra inicial
                # e a tabela agora tem o volume real histórico (> 10x o volume anterior),
                # a taxa da população real é a verdadeira referência estatística.
                amostra_previa = antes is not None and int(antes.get("linhas") or 0) < 1000 and total >= 5000
                referencia = float(antes["taxa_referencia"]) if (antes is not None and not amostra_previa) else taxa
                bloquear = (f"{nome}.{coluna}" not in _COLUNAS_OPCIONAIS_NORMA)
                if taxa < referencia - queda_tolerada:
                    achados.append(Achado(
                        regra="preenchimento",
                        alvo=f"{nome}.{coluna}",
                        bloqueia=bloquear,
                        mensagem=(
                            f"caiu de {referencia:.0%} para {taxa:.0%} "
                            f"preenchida em {total} linha(s). O formato "
                            f"continua válido; o conteúdo, não. Suspeite de "
                            f"nome de campo trocado na origem."),
                    ))
                # Coluna do contrato inteiramente vazia numa tabela cheia é,
                # quase sempre, nome de campo errado na origem: foi assim que
                # `votacao.id_proposicao` ficou 0% em 21.128 linhas e a ficha
                # de nenhum projeto mostrou quem votou. Fica em aviso porque
                # existe coluna legitimamente vazia (fonte que não publica).
                if taxa == 0.0 and f"{nome}.{coluna}" not in _COLUNAS_OPCIONAIS_NORMA:
                    achados.append(Achado(
                        regra="preenchimento",
                        alvo=f"{nome}.{coluna}",
                        bloqueia=False,
                        mensagem=(
                            f"vazia em TODAS as {total} linhas. Se a fonte "
                            f"publica esse campo, o nome lido está errado."),
                    ))
                taxa_ref = round(taxa if f"{nome}.{coluna}" in _COLUNAS_OPCIONAIS_NORMA else max(taxa, referencia), 6)
                novas_linhas.append({
                    "tabela": nome,
                    "coluna": coluna,
                    "taxa": round(taxa, 6),
                    "taxa_referencia": taxa_ref,
                    "linhas": total,
                    "medido_em": momento,
                })
    finally:
        con.close()

    if gravar and novas_linhas:
        armazem.mesclar("qualidade", novas_linhas, fonte="portao")
    return achados


# ---------------------------------------------------------- 3. registro-ouro
def caminho_ouro() -> Path:
    return config.RAIZ / "referencias" / "ouro.csv"


def conferir_ouro(arquivo: Path | None = None) -> list[Achado]:
    """Valores conferidos à mão contra o documento oficial.

    Um registro por linha do CSV: a tabela, o recorte, a expressão a somar, o
    valor que o documento publicado diz, e o link do documento. É o que
    transforma "validação linha a linha" — que não termina nunca com 842 mil
    linhas — em algo que roda em segundos a cada carga.

    O arquivo vem vazio de propósito. Preencher com valor inventado seria
    exatamente o defeito que este projeto existe para não cometer.
    """
    destino = arquivo or caminho_ouro()
    if not destino.exists():
        return [Achado(
            regra="ouro", alvo="referencias/ouro.csv", bloqueia=False,
            mensagem="nenhum registro-ouro cadastrado. Enquanto não houver um "
                     "valor conferido à mão por fonte, nada aqui prova que os "
                     "números estão CERTOS — só que estão presentes.")]

    with destino.open(encoding="utf-8") as f:
        linhas = [l for l in csv.DictReader(f)
                  if l.get("tabela") and not str(l["tabela"]).startswith("#")]

    if not linhas:
        return [Achado(
            regra="ouro", alvo=destino.name, bloqueia=False,
            mensagem="arquivo presente, mas sem nenhum registro conferido.")]

    achados: list[Achado] = []
    con = armazem.conectar()
    try:
        for l in linhas:
            nome = l["tabela"].strip()
            expressao = (l.get("expressao") or "COUNT(*)").strip()
            filtro = (l.get("filtro") or "").strip()
            documento = (l.get("documento") or "sem documento").strip()
            try:
                esperado = float(str(l["valor_esperado"]).replace(",", "."))
                tolerancia = float(str(l.get("tolerancia_pct") or 0).replace(",", ".")) / 100
            except (KeyError, ValueError):
                achados.append(Achado("ouro", nome, False,
                                      "linha do CSV sem valor_esperado numérico"))
                continue

            tabela = TABELAS.get(nome)
            if tabela is None:
                achados.append(Achado("ouro", nome, False,
                                      "tabela não existe no esquema"))
                continue

            padrao = armazem.padrao_leitura(tabela)
            hive = (", hive_partitioning=1, union_by_name=1"
                    if tabela.camada == "fato" else "")
            sql = f"SELECT {expressao} FROM read_parquet('{padrao}'{hive})"
            if filtro:
                sql += f" WHERE {filtro}"
            try:
                obtido = con.execute(sql).fetchone()[0]
            except duckdb.Error as erro:
                achados.append(Achado("ouro", nome, True,
                                      f"a consulta do registro-ouro falhou: {erro}"))
                continue

            if obtido is None:
                achados.append(Achado(
                    "ouro", f"{nome} [{filtro or 'tudo'}]", True,
                    f"o recorte conferido contra {documento} não existe mais "
                    f"no acervo (resultado nulo)."))
                continue

            desvio = abs(float(obtido) - esperado) / esperado if esperado else 0.0
            if desvio > tolerancia:
                achados.append(Achado(
                    "ouro", f"{nome} [{filtro or 'tudo'}]", True,
                    f"o acervo diz {float(obtido):,.2f} e {documento} diz "
                    f"{esperado:,.2f} ({desvio:.2%} de desvio, tolerância "
                    f"{tolerancia:.2%})."))
    finally:
        con.close()
    return achados


# ------------------------------------------------- 4. situação da ingestão
def conferir_situacao(criticos: Iterable[str] = ()) -> list[Achado]:
    """Recorte que terminou `parcial` ou `erro` e mesmo assim alimenta a tela.

    `parcial` gravado em `_ctl/ingestao` é honesto no controle e invisível no
    painel: o número agregado soma o que veio e não diz que veio pela metade.
    Enquanto a API não propagar essa marca, o portão avisa.
    """
    criticos = set(criticos)
    df = controle.situacao()
    if df.empty or "situacao" not in df:
        return []

    ano_atual_str = str(date.today().year)
    ruins = df[~df["situacao"].isin(["ok"])]
    achados = []
    for _, linha in ruins.iterrows():
        recurso = f"{linha.get('fonte')}/{linha.get('recurso')}"
        if linha.get("situacao") == "sem_dado" and ano_atual_str in str(linha.get("recurso")):
            continue
        achados.append(Achado(
            regra="situacao", alvo=recurso,
            bloqueia=recurso in criticos or str(linha.get("fonte")) in criticos,
            mensagem=f"terminou como '{linha.get('situacao')}' "
                     f"({linha.get('linhas', 0)} linha(s)) e continua "
                     f"somando no painel sem a marca."))
    return achados


def conferir_marcas_vazias() -> list[Achado]:
    """Recorte marcado `ok` com zero linha.

    É pior do que um número errado, porque é PERMANENTE: só `ok` é terminal,
    então esse recorte nunca mais será tentado. Aconteceu com `dca_2026`, que
    ficou `ok` com 0 linhas e sumiu da fila de coleta para sempre — o ano
    inteiro deixou de existir sem ninguém decidir isso.

    O coletor do SICONFI já grava `sem_dado` nesse caso. Esta regra existe
    para as marcas antigas, gravadas antes do conserto, e para o próximo
    coletor que esquecer.
    """
    df = controle.situacao()
    if df.empty or "situacao" not in df or "linhas" not in df:
        return []

    vazias = df[(df["situacao"] == "ok") & (df["linhas"].fillna(0) == 0)]
    return [Achado(
        regra="marca", alvo=f"{l.get('fonte')}/{l.get('recurso')}",
        bloqueia=True,
        mensagem="marcado como `ok` com 0 linha(s). Só `ok` é terminal, então "
                 "este recorte nunca mais será coletado. Regrave como "
                 "`sem_dado` para ele voltar à fila.")
        for _, l in vazias.iterrows()]


# ------------------------------------------------------------------ portão
def avaliar(
    tabelas: Sequence[str] | None = None,
    criticos: Iterable[str] = (),
    gravar_perfil: bool = True,
) -> Veredito:
    """Roda as quatro regras e devolve o veredito consolidado."""
    achados: list[Achado] = []
    achados += conferir_volume()
    achados += conferir_preenchimento(tabelas, gravar=gravar_perfil)
    achados += conferir_ouro()
    achados += conferir_situacao(criticos)
    achados += conferir_marcas_vazias()
    return Veredito(achados)
