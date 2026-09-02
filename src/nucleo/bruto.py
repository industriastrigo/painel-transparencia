"""Arquivo bruto: a resposta da fonte, inteira, antes de qualquer contrato.

## O problema que isto resolve

Todo coletor deste projeto **projeta** a resposta da API num contrato de
colunas declarado em `esquema.py`. Isso é bom: dá tipo, chave, partição e
idempotência. Mas tem um custo que só aparece meses depois — **o que não foi
mapeado é descartado no ato**. Se amanhã a pergunta for "e a modalidade de
licitação?", e o campo estava na resposta mas não no contrato, a única saída é
coletar tudo de novo.

E "tudo de novo" aqui não é barato: o SICONFI e o SADIPEM limitam a **uma
requisição por segundo**, então a série histórica dos 5.570 municípios é
medida em horas de máquina ligada.

O arquivo bruto quebra esse acoplamento. Cada resposta que passa por
`rede.buscar` é gravada **verbatim**, e a partir daí a pergunta nova se
responde no disco, em segundos, sem tocar na rede.

## Por que ele NÃO é uma tabela do `esquema.py`

Registrar `bruto` como tabela lhe daria exatamente aquilo que ele existe para
evitar: um contrato de colunas. E o merge por partição do `armazem` faz
leitura-modificação-escrita a cada lote — correto para 150 mil linhas por ano,
inviável para o volume de respostas de uma carga histórica.

Aqui o modelo é outro: **diário append-only**. Escreve, nunca reescreve, nunca
relê para gravar. O envelope (fonte, url, parâmetros, quando) tem colunas
fixas porque é metadado da CAPTURA; a `carga` é texto livre, porque é onde
mora o dado que ainda não sabemos como vamos querer ler.

Repetir uma coleta acrescenta linhas em vez de substituí-las, e isso é
deliberado: quando o Tesouro revisa a série, as duas versões ficam, e dá para
ver o que mudou. Quem lê é que decide — `vw_bruto` entrega só a mais recente
de cada `sk`.

## A regra que atravessa o módulo

**Guardar o bruto nunca pode derrubar a coleta.** Disco cheio, JSON estranho,
arquivo travado: tudo vira aviso no log e a coleta segue. Perder o arquivo
bruto custa uma recoleta; perder a coleta da madrugada custa a madrugada.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .registro import obter as obter_log

log = obter_log("nucleo.bruto")

# Uma linha por RESPOSTA, não por registro. Uma página de 500 registros é uma
# linha só, com o corpo inteiro em `carga` — Parquet com zstd comprime JSON
# repetitivo muito bem, e o número de arquivos fica administrável.
COLUNAS = [
    "sk",           # md5 do corpo — repetição idêntica não vira dado novo
    "fonte",        # partição
    "recurso",      # partição — o endpoint, tirado do fim da URL
    "dia",          # partição — quando foi capturado
    "url",
    "parametros",   # JSON dos parâmetros da consulta
    "formato",      # json | texto | binario
    "carga",        # A RESPOSTA INTEIRA, verbatim
    "arquivo",      # para binário: caminho do .bin guardado ao lado
    "bytes",
    "coletado_em",
]

# Quantas respostas ficam na memória antes de virar arquivo. Baixo demais
# produz milhares de Parquet minúsculos; alto demais perde muito quando o
# processo morre. 500 respostas é da ordem de um punhado de MB.
LOTE = int(os.getenv("PAINEL_BRUTO_LOTE", "500"))

# Teto do acervo bruto. Não é enfeite: a carga histórica roda de madrugada,
# sozinha, e um disco cheio às 4h da manhã derrubaria a coleta inteira — não
# só o arquivo. Ao bater o teto, PARA de arquivar e deixa a coleta seguir.
LIMITE_GB = float(os.getenv("PAINEL_BRUTO_LIMITE_GB", "40"))

# Corpo binário (ZIP do TSE, CSV em lote da Câmara) não entra no Parquet: são
# centenas de MB por arquivo e a fonte os republica inteiros a cada coleta.
# Por padrão fica só o registro de que passaram por aqui.
GUARDAR_BINARIO = os.getenv("PAINEL_BRUTO_BINARIO", "0") == "1"
LIMITE_BINARIO = int(os.getenv("PAINEL_BRUTO_BINARIO_MB", "64")) * 1024 * 1024

# Teto de memória das CONSULTAS ao arquivo. Acima dele o DuckDB derrama para o
# disco em vez de o processo morrer — e ler o arquivo bruto é justamente a
# hora em que se está mexendo com gigabytes de JSON.
LIMITE_MEMORIA = os.getenv("PAINEL_BRUTO_MEMORIA", "2GB")

_ativo = os.getenv("PAINEL_BRUTO", "0") == "1"
_trava = threading.Lock()
_memoria: list[dict[str, Any]] = []
_contador = 0
_id_processo = f"{os.getpid():d}"
_avisou_limite = False
_bytes_gravados = 0


# ------------------------------------------------------------------ ligar
def ativo() -> bool:
    return _ativo


def ligar(sim: bool = True) -> None:
    """Liga ou desliga o arquivamento em tempo de execução.

    A coleta do dia a dia não precisa dele — o que ela busca já está no
    acervo típado. Quem liga é a carga histórica, que é cara de repetir.
    """
    global _ativo
    if sim and not _ativo:
        log.info("arquivo bruto LIGADO — cada resposta será guardada inteira "
                 "em %s. Consulta depois: python -m src.scripts.bruto",
                 raiz().as_posix())
    _ativo = sim


def raiz() -> Path:
    return config.DADOS / "bruto"


def tamanho_gb() -> float:
    base = raiz()
    if not base.exists():
        return 0.0
    total = sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
    return total / (1024 ** 3)


# ------------------------------------------------------------------ escrita
def _texto_de(corpo: Any, formato: str) -> str:
    if formato == "json":
        # `separators` sem espaço e `ensure_ascii=False` mantêm o texto o mais
        # próximo possível do que a fonte mandou, e menor no disco.
        return json.dumps(corpo, ensure_ascii=False, separators=(",", ":"))
    return corpo if isinstance(corpo, str) else str(corpo)


def _recurso_de(url: str) -> str:
    """O último pedaço da URL, que na prática é o nome do endpoint.

    Tirar daqui em vez de exigir que cada coletor informe evita mexer nos dez
    coletores — e mexer em dez coletores na véspera de uma carga histórica é
    justamente o tipo de coisa que quebra a carga histórica.
    """
    pedaco = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    limpo = "".join(c if c.isalnum() or c in "-_." else "_" for c in pedaco)
    return limpo[:60] or "raiz"


def guardar(fonte: str, url: str, parametros: dict | None, formato: str,
            corpo: Any, recurso: str | None = None) -> None:
    """Enfileira uma resposta para o arquivo bruto. Nunca levanta exceção."""
    if not _ativo:
        return
    try:
        _guardar(fonte, url, parametros, formato, corpo, recurso)
    except Exception as erro:  # noqa: BLE001
        log.warning("não consegui arquivar a resposta de %s (%s) — a coleta "
                    "segue normalmente", fonte, erro)


def _guardar(fonte: str, url: str, parametros: dict | None, formato: str,
             corpo: Any, recurso: str | None) -> None:
    global _avisou_limite

    if _no_limite():
        if not _avisou_limite:
            _avisou_limite = True
            log.warning("arquivo bruto atingiu %.1f GB (limite %.1f) — "
                        "PAREI de arquivar. A coleta continua. Para elevar o "
                        "teto, defina PAINEL_BRUTO_LIMITE_GB no .env.",
                        tamanho_gb(), LIMITE_GB)
        return

    arquivo = ""
    if formato in ("json", "texto"):
        texto = _texto_de(corpo, formato)
        tamanho = len(texto.encode("utf-8"))
    else:
        bytes_corpo = corpo if isinstance(corpo, (bytes, bytearray)) else b""
        tamanho = len(bytes_corpo)
        texto = ""
        if GUARDAR_BINARIO and 0 < tamanho <= LIMITE_BINARIO:
            arquivo = _gravar_binario(fonte, bytes_corpo)
        formato = "binario"

    linha = {
        "sk": hashlib.md5(
            f"{fonte}|{url}|{json.dumps(parametros or {}, sort_keys=True)}|"
            f"{texto}".encode("utf-8")).hexdigest(),
        "fonte": fonte,
        "recurso": recurso or _recurso_de(url),
        "dia": date.today().isoformat(),
        "url": url,
        "parametros": json.dumps(parametros or {}, ensure_ascii=False,
                                 sort_keys=True, default=str),
        "formato": formato,
        "carga": texto,
        "arquivo": arquivo,
        "bytes": tamanho,
        "coletado_em": datetime.now(timezone.utc),
    }

    with _trava:
        _memoria.append(linha)
        cheio = len(_memoria) >= LOTE
    if cheio:
        descarregar()


def _no_limite() -> bool:
    # Conferir o tamanho a cada resposta seria varrer a árvore mil vezes por
    # minuto. Basta somar o que este processo escreveu desde que começou.
    return LIMITE_GB > 0 and _bytes_gravados / (1024 ** 3) >= LIMITE_GB


def _gravar_binario(fonte: str, conteudo: bytes) -> str:
    """Guarda o binário como arquivo, nomeado pelo conteúdo.

    Nome = sha256 do próprio conteúdo, então baixar o mesmo ZIP duas vezes
    ocupa espaço uma vez só — sem precisar de índice nenhum para saber disso.
    """
    digest = hashlib.sha256(conteudo).hexdigest()
    destino = raiz() / "arquivos" / fonte / f"{digest}.bin"
    if destino.exists():
        return destino.relative_to(raiz()).as_posix()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".bin.tmp")
    temporario.write_bytes(conteudo)
    os.replace(temporario, destino)
    return destino.relative_to(raiz()).as_posix()


def descarregar() -> int:
    """Grava o que está na memória. Chamada no lote cheio e no fim do processo.

    Um Parquet novo por descarga, nunca reescrita: append-only é o que torna
    isto barato o suficiente para ficar ligado durante uma carga de horas.
    """
    global _contador, _bytes_gravados

    with _trava:
        if not _memoria:
            return 0
        lote, _memoria[:] = list(_memoria), []

    # DuckDB e não `pandas.to_parquet`: é o mesmo escritor que o `armazem`
    # usa, com a mesma compressão configurada, e poupa uma segunda dependência
    # de escrita de Parquet fazendo a mesma coisa com outros padrões.
    from . import armazem  # noqa: PLC0415  (evita ciclo no import)

    try:
        df = pd.DataFrame(lote, columns=COLUNAS)
        gravados = 0
        con = armazem.conectar()
        try:
            for (fonte, recurso, dia), grupo in df.groupby(
                    ["fonte", "recurso", "dia"], dropna=False):
                with _trava:
                    _contador += 1
                    sequencia = _contador
                destino = (raiz() / f"fonte={fonte}" / f"recurso={recurso}"
                           / f"dia={dia}"
                           / f"part-{_id_processo}-{sequencia:06d}.parquet")
                destino.parent.mkdir(parents=True, exist_ok=True)
                temporario = destino.with_suffix(".parquet.tmp")
                # Sem as colunas de partição dentro do arquivo: elas já estão
                # no caminho, e o `hive_partitioning` as devolve na leitura.
                corpo = grupo.drop(columns=["fonte", "recurso", "dia"])
                con.register("lote_bruto", corpo)
                con.execute(f"""
                    COPY (SELECT * FROM lote_bruto)
                      TO '{temporario.as_posix()}'
                      (FORMAT PARQUET, COMPRESSION {config.COMPRESSAO},
                       COMPRESSION_LEVEL {config.NIVEL_COMPRESSAO})
                """)
                con.unregister("lote_bruto")
                # Escreve no temporário e renomeia: se o processo morrer no
                # meio da madrugada, não sobra meio Parquet no acervo. O
                # `_renomear` do armazém repete quando o OneDrive ou o
                # antivírus estão com o arquivo aberto — no Windows isso
                # acontece.
                armazem._renomear(temporario, destino)
                gravados += len(grupo)
                _bytes_gravados += destino.stat().st_size
        finally:
            con.close()
        return gravados
    except Exception as erro:  # noqa: BLE001
        log.warning("falha ao gravar %d resposta(s) do arquivo bruto (%s) — "
                    "a coleta segue", len(lote), erro)
        return 0


atexit.register(descarregar)


# ------------------------------------------------------------------ leitura
def caminho_leitura() -> str:
    return str(raiz() / "**" / "*.parquet")


def existe() -> bool:
    base = raiz()
    return base.exists() and any(base.rglob("*.parquet"))


def consultar(sql: str, fonte: str | None = None,
              recurso: str | None = None, unico: bool = True) -> pd.DataFrame:
    """Roda SQL sobre o arquivo bruto, com `bruto` já registrado como tabela.

    `fonte` e `recurso` entram no CAMINHO do Parquet, não num `WHERE`. A
    diferença não é estilo: a view aplica `QUALIFY ROW_NUMBER() OVER
    (PARTITION BY sk)` para ficar com a captura mais recente de cada resposta,
    e uma janela **materializa tudo o que enxerga antes de qualquer filtro**.
    Sobre um acervo de 2 GB de JSON isso estoura a memória — o próprio
    `--campos` morria com "Out of Memory" no arquivo que ele criou.

    Podando pelo caminho, o Hive descarta as partições irrelevantes ANTES de
    ler. Mas podar não basta sozinho: `pessoal_ativo` é UMA partição de 920 MB
    comprimidos, e a janela sobre ela estoura do mesmo jeito. Por isso
    `unico=False` existe — quem só quer uma AMOSTRA (que campos existem, como
    é uma resposta) não precisa de deduplicação nenhuma, e sem a janela o
    `LIMIT` desce até a leitura do arquivo.

    A regra que fica: **nunca varrer a coluna `carga` inteira**. Ou se filtra
    por partição, ou se amostra — de preferência as duas.

    A coleta pode estar rodando enquanto isto é chamado: como nada é
    reescrito, o pior que acontece é ler um instante atrás.
    """
    from . import armazem  # noqa: PLC0415  (evita ciclo no import)

    descarregar()
    padrao = (raiz() / f"fonte={fonte}" if fonte else raiz())
    if fonte and recurso:
        padrao = padrao / f"recurso={recurso}"
    caminho = str(padrao / "**" / "*.parquet")

    con = armazem.conectar(somente_leitura=True)
    try:
        # Teto de memória explícito: sem ele o DuckDB tenta usar a máquina
        # inteira e o processo morre em vez de derramar para o disco.
        con.execute(f"SET memory_limit='{LIMITE_MEMORIA}'")
        con.execute("SET preserve_insertion_order=false")
        # O derrame para disco NÃO pode cair na pasta montada do projeto: ela
        # não permite remoção de arquivo, e o DuckDB morre ao limpar o
        # temporário — "Could not remove file ... Operation not permitted".
        # Fora do acervo, o sistema operacional cuida.
        con.execute(f"SET temp_directory='{tempfile.gettempdir()}'")
        dedup = ("""
             QUALIFY ROW_NUMBER() OVER (PARTITION BY sk
                                        ORDER BY coletado_em DESC) = 1
        """ if unico else "")
        con.execute(f"""
            CREATE OR REPLACE VIEW bruto AS
            SELECT * FROM read_parquet('{caminho}',
                                       hive_partitioning=1, union_by_name=1)
            {dedup}
        """)
        return con.execute(sql).df()
    finally:
        con.close()


def inventario() -> pd.DataFrame:
    """O que existe no arquivo: fonte, recurso, respostas, tamanho, período."""
    if not existe():
        return pd.DataFrame()
    # `unico=False`: o inventário conta respostas, e a janela de dedup
    # obrigaria a materializar a `carga` de todo o acervo só para somar
    # `bytes`. Repetição idêntica aparece como resposta a mais, o que para um
    # inventário é a leitura certa.
    return consultar("""
        SELECT fonte, recurso,
               COUNT(*)                       AS respostas,
               COUNT(DISTINCT sk)             AS distintas,
               SUM(bytes) / 1048576.0         AS mb,
               MIN(dia)                       AS de,
               MAX(dia)                       AS ate
          FROM bruto
         GROUP BY ALL
         ORDER BY fonte, recurso
    """, unico=False)


def campos(fonte: str, recurso: str, limite: int = 25) -> pd.DataFrame:
    """TODOS os nomes de campo que aparecem nas respostas guardadas.

    É a pergunta que o arquivo bruto existe para responder: *o que veio junto
    e a gente jogou fora?* Sem ele, só recoletando para descobrir.

    A amostra é pequena de propósito. Uma resposta de Custos tem ~450 KB e
    milhares de registros; 200 delas são 90 MB de JSON para explodir em
    memória — e a pergunta "que campos existem" se responde com 25. O padrão
    antigo (200) estourava a memória na maior partição.
    """
    if not existe():
        return pd.DataFrame()
    return consultar(f"""
        WITH amostra AS (
            SELECT carga FROM bruto WHERE formato = 'json' LIMIT {limite}
        ),
        linhas AS (
            SELECT unnest(_lista) AS registro FROM (
                SELECT CASE
                         WHEN json_type(carga) = 'ARRAY'
                           THEN json_extract(carga, '$[*]')
                         WHEN json_type(json_extract(carga, '$.items')) = 'ARRAY'
                           THEN json_extract(carga, '$.items[*]')
                         ELSE [carga::JSON] END AS _lista
                  FROM amostra)
        ),
        -- O `unnest` precisa de um passo próprio: agrupar direto sobre ele
        -- é erro de binder no DuckDB.
        chaves AS (
            SELECT unnest(json_keys(registro)) AS campo FROM linhas
        )
        SELECT campo, COUNT(*) AS vezes
          FROM chaves
         GROUP BY ALL
         ORDER BY vezes DESC, campo
    """, fonte, recurso, unico=False)


def registros(fonte: str, recurso: str, filtro: str = "") -> pd.DataFrame:
    """Explode as respostas guardadas em uma linha por registro, sem contrato.

    Devolve `registro` como JSON. Daí em diante é `json_extract` sobre o campo
    que se quiser — inclusive um que nenhum coletor jamais leu.
    """
    if not existe():
        return pd.DataFrame()
    onde = f"WHERE {filtro}" if filtro else ""
    return consultar(f"""
        SELECT url, parametros, coletado_em,
               unnest(CASE
                        WHEN json_type(carga) = 'ARRAY'
                          THEN json_extract(carga, '$[*]')
                        WHEN json_type(json_extract(carga, '$.items')) = 'ARRAY'
                          THEN json_extract(carga, '$.items[*]')
                        ELSE [carga::JSON] END) AS registro
          FROM (SELECT * FROM bruto WHERE formato = 'json') {onde}
    """, fonte, recurso)


# ------------------------------------------------------------------ replay
_replay = os.getenv("PAINEL_REPLAY", "0") == "1"
_cache_replay: dict[str, str] | None = None


def replay_ativo() -> bool:
    return _replay


def ligar_replay(sim: bool = True) -> None:
    """Faz `rede.buscar` responder pelo arquivo em vez de pela rede.

    É o que torna o arquivo bruto útil e não só volumoso: recoletar sem
    recoletar. Rodar um coletor inteiro em replay reprocessa a resposta
    guardada com o código de HOJE — o campo que passou a ser lido entra no
    acervo típado sem uma requisição sequer.
    """
    global _replay, _cache_replay
    _replay = sim
    _cache_replay = None


def _chave(fonte: str, url: str, parametros: dict | None) -> str:
    return (f"{fonte}|{url}|"
            f"{json.dumps(parametros or {}, ensure_ascii=False, sort_keys=True, default=str)}")


def _carregar_replay() -> dict[str, str]:
    global _cache_replay
    if _cache_replay is not None:
        return _cache_replay

    _cache_replay = {}
    if not existe():
        log.warning("replay pedido, mas não há arquivo bruto em %s",
                    raiz().as_posix())
        return _cache_replay

    df = consultar("""
        SELECT fonte, url, parametros, carga FROM bruto
         WHERE formato IN ('json', 'texto')
    """)
    for linha in df.itertuples(index=False):
        _cache_replay[f"{linha.fonte}|{linha.url}|{linha.parametros}"] = linha.carga
    log.info("replay: %d resposta(s) carregada(s) do arquivo bruto",
             len(_cache_replay))
    return _cache_replay


def buscar_do_arquivo(fonte: str, url: str, parametros: dict | None,
                      formato: str) -> tuple[bool, Any]:
    """(achou, corpo). Nunca inventa: não achou devolve (False, None)."""
    if not _replay:
        return False, None
    texto = _carregar_replay().get(_chave(fonte, url, parametros))
    if texto is None:
        return False, None
    if formato == "json":
        try:
            return True, json.loads(texto)
        except json.JSONDecodeError:
            return False, None
    return True, texto


# ------------------------------------------------------------------ ensaio
def autoteste() -> tuple[bool, str]:
    """Grava e relê uma resposta de mentira, para descobrir AGORA se o
    arquivamento funciona nesta máquina.

    Existe porque a carga histórica roda de madrugada, sozinha. Descobrir às
    3h que o Parquet não grava — pasta sem permissão, OneDrive segurando o
    arquivo, disco cheio — seria descobrir tarde demais. Aqui a resposta vem
    em menos de um segundo, antes de a coleta começar.

    Nunca levanta exceção: devolve (deu certo, explicação).
    """
    global _memoria

    marca = f"autoteste-{_id_processo}"
    antes, _memoria = _memoria, []
    try:
        _guardar("_ensaio", f"https://exemplo.invalido/{marca}", {"n": 1},
                 "json", {"items": [{"campo_qualquer": marca}]}, None)
        if not descarregar():
            return False, "nada foi gravado"
        achou = consultar(
            f"SELECT carga FROM bruto WHERE fonte = '_ensaio'")
        if achou.empty or marca not in achou["carga"][0]:
            return False, "gravou mas não releu"
    except Exception as erro:  # noqa: BLE001
        return False, str(erro)[:200]
    finally:
        with _trava:
            _memoria = antes
        # O ensaio não fica no acervo: seria uma fonte falsa no inventário.
        import shutil  # noqa: PLC0415
        shutil.rmtree(raiz() / "fonte=_ensaio", ignore_errors=True)

    return True, "ok"
