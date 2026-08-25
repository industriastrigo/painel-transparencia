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

from ..nucleo import armazem, config, controle, rede
from ..nucleo.valores import numero, opcional, texto
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.siconfi")

FONTE = "siconfi"

# Anexo 2 do DCA: despesa por função. É o recorte comparável entre entes.
ANEXO_DESPESA_FUNCAO = "DCA-Anexo I-D"

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


def varrer(
    ano: int,
    entes: list[str],
    recurso: str = "dca",
    trabalhadores: int = 6,
    intervalo: float = 0.15,
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
            armazem.mesclar("financas_ente", buffer_linhas, f"{FONTE}_{recurso}")
            buffer_linhas = []
        if buffer_controle:
            controle.registrar_entes(FONTE, recurso, ano, buffer_controle)
            buffer_controle = []

    def trabalhar(cod: str) -> None:
        if desistir.is_set():
            return
        try:
            linhas = (coletar_dca(ano, cod) if recurso == "dca"
                      else coletar_rreo(ano, 6, cod))
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
             intervalo: float = 0.15, refazer_vazios: bool = False,
             refazer_tudo: bool = False) -> int:
    """Carrega o DCA do ano.

    `nivel='estado'` (padrão) são 27 entes e leva menos de um minuto.
    `nivel='municipio'` são 5.570 e leva 15 a 25 minutos na primeira vez —
    depois, só os pendentes.
    """
    ano = ano or date.today().year - 1

    if entes is None:
        alvos = (["estado", "municipio"] if nivel == "todos" else [nivel])
        entes = [cod for n in alvos for cod in listar_entes(n, uf)]
    if not entes:
        return 0
    if limite:
        entes = entes[:limite]

    total = varrer(ano, entes, trabalhadores=trabalhadores,
                   intervalo=intervalo, refazer_vazios=refazer_vazios,
                   refazer_tudo=refazer_tudo)
    return total["linhas"]


if __name__ == "__main__":
    executar()
