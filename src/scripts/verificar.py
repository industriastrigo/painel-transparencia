"""Verificação rápida: as fontes respondem, e respondem o quê?

Existe porque quatro coletores foram consertados sem serem executados depois,
e continuar empilhando código sobre correção não verificada foi exatamente
como os defeitos da semana se acumularam.

**Não coleta nada.** Faz cerca de dez requisições, imprime o que cada fonte
devolveu — os nomes reais dos campos, o primeiro registro, o formato das
datas — e não grava uma linha no armazém. É barato de rodar e responde as
perguntas que hoje só se respondem adivinhando:

- os apelidos de campo que escrevi no coletor de Custos batem com a resposta?
- o catálogo de transferências abre agora que o envelope é `registros`?
- a data do SADIPEM é mesmo ISO, como o conserto supõe?
- o acervo está onde o projeto procura, e as views enxergam o que deveriam?

Saída pensada para ser lida por outra pessoa (ou colada numa conversa), não
para ser bonita.

    python -m src.scripts.verificar
"""

from __future__ import annotations

import sys
import traceback
from datetime import date
from pathlib import Path

ANO = date.today().year - 1


class _Espelho:
    """Escreve na tela E no arquivo, ao mesmo tempo.

    A primeira versão redirecionava tudo para o arquivo pelo `.bat`. O efeito
    prático foi uma janela muda por um minuto — e quem está olhando não tem
    como distinguir "trabalhando" de "travado", então interrompe. Foi o que
    aconteceu.

    O `type` no fim não resolve: a informação de que ALGO está acontecendo
    precisa chegar enquanto acontece.

    O arquivo é aberto em UTF-8 explicitamente: redirecionado, o Python no
    Windows grava na codificação do console e os acentos viram lixo.
    """

    def __init__(self, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        self.arquivo = open(destino, "w", encoding="utf-8")

    def write(self, texto: str) -> int:
        sys.__stdout__.write(texto)
        sys.__stdout__.flush()          # sem isto o Windows segura o buffer
        self.arquivo.write(texto)
        self.arquivo.flush()
        return len(texto)

    def flush(self) -> None:
        sys.__stdout__.flush()
        self.arquivo.flush()

    def close(self) -> None:
        try:
            self.arquivo.close()
        except Exception:  # noqa: BLE001
            pass


def _passo(texto: str) -> None:
    """Diz o que vai fazer ANTES de fazer. Numa etapa que espera rede, é a
    diferença entre 'está rodando' e 'travou'."""
    print(f"  ... {texto}", flush=True)


def _titulo(texto: str) -> None:
    print()
    print("=" * 68)
    print(f"  {texto}")
    print("=" * 68, flush=True)


def _erro(o_que: str, erro: Exception) -> None:
    print(f"  [x] {o_que} falhou: {type(erro).__name__}: {erro}")
    linhas = traceback.format_exc().strip().splitlines()
    for linha in linhas[-3:]:
        print(f"      {linha}")


def onde_esta_o_acervo() -> None:
    _titulo("1. ONDE O PROJETO ESTÁ LENDO")
    from .coletar import _diagnostico  # noqa: PLC0415
    try:
        _diagnostico()
    except Exception as erro:  # noqa: BLE001
        _erro("diagnóstico", erro)


def custos_responde() -> None:
    """Os apelidos de campo batem com o que a API devolve?"""
    _titulo("2. CUSTOS — que campos a API devolve")
    from ..coletores import tesouro  # noqa: PLC0415

    _passo(f"consultando os seis recortes de custo de {ANO}/01 "
           f"(1 requisição por segundo, ~10 s)")
    try:
        achados = tesouro.descobrir(ANO)
    except Exception as erro:  # noqa: BLE001
        _erro("Custos", erro)
        return

    for conjunto, achado in achados.items():
        campos, erro = achado["campos"], achado["erro"]
        if erro:
            print(f"  {conjunto:<18} [x] NÃO RESPONDEU — {erro}")
            continue
        if not campos:
            print(f"  {conjunto:<18} respondeu, sem linha em {ANO}/01")
            continue
        print(f"  {conjunto:<18} {', '.join(campos)}")

        # O que importa de verdade: os apelidos escritos no coletor acertaram?
        exemplo = {c: "" for c in campos}
        for chave in ("orgao_nome", "valor", "ano", "mes", "item_custo"):
            achou = next((n for n in tesouro.CAMPOS[chave] if n in exemplo), None)
            marca = "ok" if achou else "NÃO ENCONTRADO"
            print(f"      {chave:<14} → {achou or '—':<26} {marca}")
        break   # os seis têm o mesmo formato; um basta para conferir


def transferencias_responde() -> None:
    _titulo("3. TRANSFERÊNCIAS DA UNIÃO — o catálogo abre?")
    from ..coletores import transferencias  # noqa: PLC0415

    _passo("pedindo o catálogo de modalidades")
    try:
        catalogo = transferencias.catalogar()
    except Exception as erro:  # noqa: BLE001
        _erro("Transferências", erro)
        return

    print(f"  {len(catalogo)} modalidade(s)")
    for item in catalogo[:12]:
        print(f"    {item['cod_transferencia']:<10} {item['transferencia']}")
    if not catalogo:
        print("  (vazio — veja o aviso acima, que mostra a resposta crua)")


def sadipem_responde() -> None:
    """A data vem em ISO, como o conserto supõe?"""
    _titulo("4. SADIPEM — formato da data de protocolo")
    from ..coletores import sadipem  # noqa: PLC0415
    from ..nucleo.valores import ano_de, data_br  # noqa: PLC0415

    _passo("pedindo os pleitos do Acre")
    try:
        brutos = sadipem._pagina({"uf": "AC"}, 0)[0]
    except Exception as erro:  # noqa: BLE001
        _erro("SADIPEM", erro)
        return

    print(f"  {len(brutos)} pleito(s) no Acre")
    if not brutos:
        return

    print(f"  campos: {', '.join(sorted(brutos[0]))}")
    print()
    print("  como a fonte devolve a data  →  como o projeto lê")
    for bruto in brutos[:5]:
        cru = bruto.get("data_protocolo")
        print(f"    {str(cru):<28} → {data_br(cru)}  (ano {ano_de(cru)})")

    # Distinguir os dois casos importa: "a fonte não mandou data" é limite do
    # dado; "não soube ler o texto" é defeito nosso. A versão anterior somava
    # os dois e acusava o conserto de não ter pego.
    nulos = sum(1 for b in brutos if b.get("data_protocolo") in (None, ""))
    ilegiveis = sum(1 for b in brutos
                    if b.get("data_protocolo") not in (None, "")
                    and ano_de(b.get("data_protocolo")) is None)
    lidas = len(brutos) - nulos - ilegiveis

    print(f"  [ok] {lidas} data(s) lidas corretamente")
    if nulos:
        print(f"  [–] {nulos} vieram NULAS da fonte (limite do dado, não defeito)")
    if ilegiveis:
        print(f"  [!] {ilegiveis} em formato que o projeto NÃO soube ler")

    if "pvl_contradado_credor" in brutos[0]:
        print("  [!] a fonte escreve `pvl_contradado_credor` (com erro de "
              "digitação dela) — o coletor lê os dois nomes")


def painel_enxerga() -> None:
    _titulo("5. O QUE O PAINEL ENXERGA HOJE")
    from ..api import vistas  # noqa: PLC0415

    _passo("montando as views sobre o acervo")
    try:
        con = vistas.conexao_leitura()
    except Exception as erro:  # noqa: BLE001
        _erro("views", erro)
        return

    perguntas = (
        ("entes com despesa", "SELECT COUNT(*) FROM vw_despesa_total"),
        ("entes com arrecadação", "SELECT COUNT(*) FROM vw_receita_total"),
        ("entes com transferência recebida",
         "SELECT COUNT(*) FROM vw_transferencia_recebida"),
        ("repasses da União", "SELECT COUNT(*) FROM transferencia_uniao"),
        ("pedidos de crédito", "SELECT COUNT(*) FROM operacao_credito"),
        ("linhas de custo federal", "SELECT COUNT(*) FROM custo_orgao"),
    )
    for rotulo, sql in perguntas:
        try:
            print(f"  {rotulo:<34} {con.execute(sql).fetchone()[0]}")
        except Exception as erro:  # noqa: BLE001
            print(f"  {rotulo:<34} erro: {str(erro)[:60]}")

    # A conferência que vale mais que a contagem: a soma das categorias
    # bate com o total que o próprio ente declarou?
    try:
        linha = con.execute("""
            SELECT COUNT(*) FILTER (WHERE ABS(somado - declarado)
                                        > GREATEST(1, ABS(declarado) * 0.001)),
                   COUNT(*)
              FROM vw_conferencia_despesa
             WHERE somado IS NOT NULL AND declarado IS NOT NULL""").fetchone()
        print()
        print(f"  conferência da despesa: {linha[0]} divergência(s) "
              f"em {linha[1]} ente-ano")
        if linha[0]:
            print("  [!] divergir significa regra de agregação quebrada")
    except Exception as erro:  # noqa: BLE001
        print(f"  conferência indisponível: {str(erro)[:60]}")


def principal() -> int:
    from ..nucleo import config  # noqa: PLC0415

    destino = Path(config.LOGS) / "verificacao.txt"
    espelho = _Espelho(destino)
    sys.stdout = espelho

    # Uma tentativa por chamada, e espera curta. A repetição com espera
    # exponencial existe para coleta; aqui ela transformaria "a fonte está
    # fora do ar" em minutos de silêncio, e o ponto desta verificação é
    # responder rápido.
    config.TENTATIVAS = 1
    config.TEMPO_LIMITE = min(getattr(config, "TEMPO_LIMITE", 30), 20)

    try:
        print("VERIFICAÇÃO DAS FONTES — nada é gravado no armazém")
        print(f"ano de referência: {ANO}")
        print(f"transcrição em: {destino}")

        onde_esta_o_acervo()
        custos_responde()
        transferencias_responde()
        sadipem_responde()
        painel_enxerga()

        _titulo("FIM")
        print("  Mande esta saída inteira para eu saber o que ajustar.")
        return 0
    except KeyboardInterrupt:
        # Ctrl+C no meio de uma espera de rede produzia um "Fatal Python
        # error: PyEval_SaveThread" — barulho de finalização, não defeito do
        # projeto, mas que assusta e esconde o que já tinha sido descoberto.
        print()
        print("  Interrompido. O que já foi verificado está no arquivo.")
        return 130
    finally:
        sys.stdout = sys.__stdout__
        espelho.close()


if __name__ == "__main__":
    sys.exit(principal())
