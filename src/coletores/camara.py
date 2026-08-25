"""Coletor Câmara dos Deputados.

Armadilha conhecida e já paga em dias de trabalho: o endpoint
`/votacoes/{id}/votos` retorna lista vazia para votações posteriores a
maio/2024, enquanto as anteriores funcionam. Por isso a carga histórica E o
delta vêm dos ARQUIVOS EM LOTE (dadosabertos.camara.leg.br/arquivos/...),
atualizados diariamente; a API REST fica para cadastro e consulta pontual.

Se um dia a API voltar a devolver votos, `votos_por_api()` já está pronta —
mas o padrão continua sendo o CSV, porque ele é auditável e reexecutável.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pandas as pd

from ..nucleo import armazem, config, controle, rede
from ..nucleo.valores import inteiro, numero, opcional, texto
from ..nucleo.registro import obter as obter_log

log = obter_log("coletores.camara")

FONTE = "camara"
CASA = "camara"


def _sem_nan(df: pd.DataFrame) -> pd.DataFrame:
    """Troca NaN por None no DataFrame.

    Ajuda em operações no nível do quadro, mas **não é suficiente**: o
    `iterrows()` reconstrói cada linha como Series tipada e devolve o NaN de
    volta. A proteção que vale é `nucleo.valores.texto()` no ponto de uso —
    veja o comentário lá.
    """
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)


def _csv(url: str, **kwargs) -> pd.DataFrame:
    corpo = rede.buscar(FONTE, url, formato="texto")
    df = pd.read_csv(io.StringIO(corpo), sep=";", dtype=str,
                     keep_default_na=False, na_values=[""], **kwargs)
    return _sem_nan(df)


def _ano_de(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce", format="mixed").dt.year


def primeiro(linha, *colunas: str, limite: int | None = None) -> str | None:
    """Primeiro valor preenchido entre vários nomes de coluna.

    A API v2 e os arquivos em lote dão nomes diferentes ao MESMO campo: o que
    a API chama de `descricaoSituacao`, o CSV chama de
    `ultimoStatus_descricaoSituacao`. Ler só o nome da API devolvia None em
    todas as linhas — a coluna Situação do painel ficou inteira em "—" sem
    nenhum erro no log, que é a pior forma de um campo faltar.
    """
    for coluna in colunas:
        valor = opcional(linha.get(coluna), limite)
        if valor is not None:
            return valor
    return None


# ------------------------------------------------------------------ deputados
def coletar_deputados(legislatura: int | None = None) -> int:
    parametros = {"ordem": "ASC", "ordenarPor": "nome"}
    if legislatura:
        parametros["idLegislatura"] = legislatura

    linhas = []
    for d in rede.paginar_camara(f"{config.CAMARA}/deputados", parametros):
        linhas.append({
            "fonte_origem": FONTE,
            "id_origem": str(d["id"]),
            "nome": opcional(d.get("nome")),
            "nome_eleitoral": opcional(d.get("nomeEleitoral")) or opcional(d.get("nome")),
            "sigla_partido": opcional(d.get("siglaPartido")),
            "sigla_uf": opcional(d.get("siglaUf")),
            "id_legislatura": texto(d.get("idLegislatura")),
            "email": opcional(d.get("email")),
            "url_foto": opcional(d.get("urlFoto")),
            "casa": CASA,
            "cargo": "deputado_federal",
        })

    armazem.mesclar("dim_politico", linhas, FONTE)
    controle.gravar_marca(FONTE, "deputados", date.today().isoformat(), len(linhas))
    return len(linhas)


# ------------------------------------------------------------------ proposições
def coletar_proposicoes(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/proposicoes/csv/proposicoes-{ano}.csv")
    if df.empty:
        return 0

    autores = coletar_autores(ano)
    dono = (autores.sort_values("ordem_assinatura")
                   .drop_duplicates("id_proposicao")
                   .set_index("id_proposicao")) if not autores.empty else None

    linhas = []
    for _, p in df.iterrows():
        idp = str(p["id"])
        principal = dono.loc[idp] if dono is not None and idp in dono.index else None
        linhas.append({
            "casa": CASA,
            "id_proposicao": idp,
            "sigla_tipo": opcional(p.get("siglaTipo")),
            "numero": opcional(p.get("numero")),
            "ano_proposicao": opcional(p.get("ano")),
            "identificador": f"{texto(p.get('siglaTipo'))} "
                             f"{texto(p.get('numero'))}/{texto(p.get('ano'))}".strip(),
            "ementa": texto(p.get("ementa"), 2000),
            "tema": opcional(p.get("keywords")),
            "data_apresentacao": opcional(p.get("dataApresentacao")),
            # No CSV em lote esses campos vêm com o prefixo `ultimoStatus_`.
            "situacao": primeiro(p, "ultimoStatus_descricaoSituacao",
                                 "descricaoSituacao"),
            "tramitacao_atual": primeiro(p, "ultimoStatus_descricaoTramitacao",
                                         "descricaoTramitacao"),
            "orgao_atual": primeiro(p, "ultimoStatus_siglaOrgao", "siglaOrgao"),
            "regime": primeiro(p, "ultimoStatus_regime", "regime"),
            "data_ultimo_status": primeiro(p, "ultimoStatus_dataHora"),
            "ultimo_status": primeiro(p, "ultimoStatus_despacho", "despacho",
                                      limite=1000),
            "url": primeiro(p, "urlInteiroTeor", "uriInteiroTeor"),
            "id_autor": None if principal is None else opcional(principal["id_autor"]),
            "nome_autor": None if principal is None else opcional(principal["nome_autor"]),
            "partido_autor": None if principal is None
                             else opcional(principal["partido_autor"]),
            "uf_autor": None if principal is None else opcional(principal["uf_autor"]),
            "qtd_autores": 0 if autores.empty else int(
                (autores["id_proposicao"] == idp).sum()),
            "ano": int(ano),
        })

    armazem.mesclar("proposicao", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"proposicoes_{ano}", ano, len(linhas))
    return len(linhas)


def coletar_autores(ano: int) -> pd.DataFrame:
    try:
        df = _csv(f"{config.CAMARA_ARQUIVOS}/proposicoesAutores/csv/"
                  f"proposicoesAutores-{ano}.csv")
    except Exception as erro:  # noqa: BLE001
        log.warning("autores de %d indisponíveis: %s", ano, erro)
        return pd.DataFrame()

    if df.empty:
        return df
    return pd.DataFrame({
        "id_proposicao": df["idProposicao"].astype(str),
        "id_autor": df.get("idDeputadoAutor", pd.Series(dtype=str)).astype(str),
        "nome_autor": df.get("nomeAutor"),
        "partido_autor": df.get("siglaPartidoAutor"),
        "uf_autor": df.get("siglaUFAutor"),
        "ordem_assinatura": pd.to_numeric(
            df.get("ordemAssinatura", 1), errors="coerce").fillna(99),
    })


# ------------------------------------------------------------------ tramitações
def coletar_tramitacoes(id_proposicao: str) -> int:
    """Etapas de UMA proposição, via API (o lote anual é grande demais)."""
    dados = rede.buscar(
        FONTE, f"{config.CAMARA}/proposicoes/{id_proposicao}/tramitacoes"
    ).get("dados", [])

    linhas = [{
        "casa": CASA,
        "id_proposicao": str(id_proposicao),
        "seq_tramitacao": texto(t.get("sequencia")),
        "data_hora": opcional(t.get("dataHora")),
        "orgao": opcional(t.get("siglaOrgao")),
        "descricao_tramitacao": opcional(t.get("descricaoTramitacao")),
        "descricao_situacao": opcional(t.get("descricaoSituacao")),
        "despacho": texto(t.get("despacho"), 1000),
        "ano": int(str(t.get("dataHora", ""))[:4] or date.today().year),
    } for t in dados]

    if linhas:
        armazem.mesclar("tramitacao", linhas, FONTE)
    return len(linhas)


# ------------------------------------------------------------------ votações
def coletar_votacoes(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/votacoes/csv/votacoes-{ano}.csv")
    if df.empty:
        return 0

    linhas = [{
        "casa": CASA,
        "id_votacao": texto(v["id"]),
        "data_hora": opcional(v.get("dataHoraRegistro")) or opcional(v.get("data")),
        "sigla_orgao": opcional(v.get("siglaOrgao")),
        "descricao": texto(v.get("descricao"), 2000),
        "aprovada": opcional(v.get("aprovacao")),
        "votos_sim": numero(v.get("votosSim")),
        "votos_nao": numero(v.get("votosNao")),
        "votos_outros": numero(v.get("votosOutros")),
        "id_proposicao": opcional(v.get("ultimaAberturaVotacao_idProposicao"))
                          or opcional(v.get("idProposicaoObjeto")),
        "url": opcional(v.get("uriVotacao")),
        "ano": int(ano),
    } for _, v in df.iterrows()]

    armazem.mesclar("votacao", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"votacoes_{ano}", ano, len(linhas))
    return len(linhas)


def coletar_votos(ano: int) -> int:
    """Voto individual — o produto do painel. Sempre pelo arquivo em lote."""
    df = _csv(f"{config.CAMARA_ARQUIVOS}/votacoesVotos/csv/"
              f"votacoesVotos-{ano}.csv")
    if df.empty:
        return 0

    data_hora = pd.to_datetime(df.get("dataHoraVoto"), errors="coerce",
                               format="mixed")
    df = df.assign(
        _ano=data_hora.dt.year.fillna(ano).astype(int),
        _mes=data_hora.dt.month.fillna(1).astype(int),
    )

    linhas = [{
        "casa": CASA,
        "id_votacao": texto(v["idVotacao"]),
        "id_politico": texto(v.get("deputado_id")),
        "nome_politico": opcional(v.get("deputado_nome")),
        "sigla_partido": opcional(v.get("deputado_siglaPartido")),
        "sigla_uf": opcional(v.get("deputado_siglaUf")),
        "voto": texto(v.get("voto")),
        "data_hora": opcional(v.get("dataHoraVoto")),
        "ano": int(v["_ano"]),
        "mes": int(v["_mes"]),
    } for _, v in df.iterrows()]

    armazem.mesclar("voto", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"votos_{ano}", ano, len(linhas))
    return len(linhas)


def votos_por_api(id_votacao: str) -> list[dict]:
    """Plano B. Valide o retorno: para votações recentes costuma vir vazio."""
    dados = rede.buscar(
        FONTE, f"{config.CAMARA}/votacoes/{id_votacao}/votos"
    ).get("dados", [])
    if not dados:
        log.warning("votação %s devolveu 0 votos pela API — use o lote",
                    id_votacao)
    return dados


# ------------------------------------------------------------------ despesas
def _csv_da_cota(ano: int) -> pd.DataFrame:
    """A cota parlamentar mudou de endereço e de embalagem ao longo do tempo.

    `Ano-{ano}.csv` devolve 404 para os anos recentes; hoje o arquivo é
    zipado. Em vez de fixar uma URL que volta a quebrar, tenta as conhecidas
    em ordem e usa a primeira que responder.
    """
    candidatas = [
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", "zip"),
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv", "csv"),
        (f"{config.CAMARA_ARQUIVOS}/despesasParlamentares/csv/"
         f"despesasParlamentares-{ano}.csv", "csv"),
    ]

    erros = []
    for url, tipo in candidatas:
        try:
            if tipo == "csv":
                return _csv(url)
            conteudo = rede.buscar(FONTE, url, formato="binario")
            with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
                nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                with z.open(nome) as f:
                    return _sem_nan(pd.read_csv(
                        f, sep=";", dtype=str, keep_default_na=False,
                        na_values=[""], low_memory=False))
        except Exception as erro:  # noqa: BLE001
            erros.append(f"{url}: {erro}")
            continue

    raise RuntimeError(
        f"cota parlamentar de {ano} indisponível em todas as URLs conhecidas. "
        + " | ".join(erros))


def coletar_despesas(ano: int) -> int:
    """Cota parlamentar, nota a nota. Único dado guardado no grão bruto."""
    df = _csv_da_cota(ano)
    if df.empty:
        return 0

    # `ideDocumento` sozinho não é único: reembolso parcelado repete o mesmo
    # documento. A chave usa `numParcela` e `numRessarcimento` para separar —
    # mas se o arquivo não tiver essas colunas, todas viram "0" e as
    # duplicatas voltam em silêncio. Melhor dizer qual coluna faltou do que
    # deixar ~1.300 notas serem descartadas todo mês sem explicação.
    ausentes = [c for c in ("numParcela", "numRessarcimento")
                if c not in df.columns]
    if ausentes:
        log.warning(
            "cota de %d: colunas %s não existem neste arquivo, então a chave "
            "não consegue separar parcelas e notas podem ser descartadas como "
            "duplicatas. Colunas disponíveis: %s",
            ano, ausentes, ", ".join(list(df.columns)[:30]))

    emissao = pd.to_datetime(df.get("datEmissao"), errors="coerce",
                             format="mixed")
    linhas = [{
        "casa": CASA,
        "id_documento": texto(d.get("ideDocumento")),
        # `ideDocumento` sozinho NÃO é único: reembolso parcelado repete o
        # mesmo documento em várias linhas. Sem estes dois campos na chave,
        # 1.307 notas eram silenciosamente descartadas como "duplicadas".
        "num_parcela": texto(d.get("numParcela"), padrao="0"),
        "num_ressarcimento": texto(d.get("numRessarcimento"), padrao="0"),
        "id_politico": texto(d.get("numDeputadoId")) or texto(d.get("ideCadastro")),
        "nome_politico": opcional(d.get("txNomeParlamentar")),
        "sigla_partido": opcional(d.get("sgPartido")),
        "sigla_uf": opcional(d.get("sgUF")),
        "tipo_despesa": opcional(d.get("txtDescricao")),
        "fornecedor": opcional(d.get("txtFornecedor")),
        "cnpj_cpf_fornecedor": opcional(d.get("txtCNPJCPF")),
        "valor_documento": numero(d.get("vlrDocumento")),
        "valor_liquido": numero(d.get("vlrLiquido")),
        "data_emissao": opcional(d.get("datEmissao")),
        "url_documento": opcional(d.get("urlDocumento")),
        "ano": inteiro(d.get("numAno"), ano),
        "mes": inteiro(d.get("numMes"), 1),
    } for _, d in df.assign(_e=emissao).iterrows()]

    armazem.mesclar("despesa_parlamentar", linhas, f"{FONTE}_cota")
    controle.gravar_marca(FONTE, f"despesas_{ano}", ano, len(linhas))
    return len(linhas)


# ------------------------------------------------------------------ execução
def executar(anos: list[int] | None = None, com_despesas: bool = True) -> None:
    anos = anos or [date.today().year]
    coletar_deputados()
    for ano in anos:
        for nome, funcao in (
            ("proposições", coletar_proposicoes),
            ("votações", coletar_votacoes),
            ("votos", coletar_votos),
        ):
            try:
                funcao(ano)
            except Exception as erro:  # noqa: BLE001
                log.error("Câmara %s %d falhou: %s", nome, ano, erro)
        if com_despesas:
            try:
                coletar_despesas(ano)
            except Exception as erro:  # noqa: BLE001
                log.error("Câmara despesas %d falhou: %s", ano, erro)


if __name__ == "__main__":
    executar()
