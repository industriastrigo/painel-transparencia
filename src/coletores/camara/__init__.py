"""Módulo Câmara dos Deputados."""
from __future__ import annotations

from datetime import date
import pandas as pd

from ...nucleo import armazem, config, controle, rede, tabela
from ...nucleo.valores import inteiro, numero, opcional, texto
from ...nucleo.registro import obter as obter_log

from .cliente import buscar_api, baixar_csv
from .parser import primeiro, proposicao_ou_nada as _proposicao_ou_nada, chave_parcela as _chave_parcela, TIPOS_DELIBERATIVOS
from .erros import ErroCamara, ErroDownloadArquivo, diagnosticar_erro

log = obter_log("coletores.camara")
FONTE = "camara"
CASA = "camara"

def _sem_nan(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)

def _csv(url: str, **kwargs) -> pd.DataFrame:
    conteudo = rede.buscar(FONTE, url, formato="binario")
    return tabela.ler(conteudo, origem=url)

def _csv_da_cota(ano: int) -> pd.DataFrame:
    candidatas = [
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip", "zip"),
        (f"https://www.camara.leg.br/cotas/Ano-{ano}.csv", "csv"),
        (f"{config.CAMARA_ARQUIVOS}/despesasParlamentares/csv/despesasParlamentares-{ano}.csv", "csv"),
    ]
    erros = []
    for url, tipo in candidatas:
        try:
            if tipo == "csv":
                return _csv(url)
            conteudo = rede.buscar(FONTE, url, formato="binario")
            return tabela.de_zip(conteudo, origem=url)
        except Exception as erro:  # noqa: BLE001
            erros.append(f"{url}: {erro}")
            continue
    raise RuntimeError(f"cota parlamentar de {ano} indisponível em todas as URLs conhecidas. " + " | ".join(erros))

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

def coletar_autores(ano: int) -> pd.DataFrame:
    try:
        df = _csv(f"{config.CAMARA_ARQUIVOS}/proposicoesAutores/csv/proposicoesAutores-{ano}.csv")
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
        "ordem_assinatura": pd.to_numeric(df.get("ordemAssinatura", 1), errors="coerce").fillna(99),
    })

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
            "identificador": f"{texto(p.get('siglaTipo'))} {texto(p.get('numero'))}/{texto(p.get('ano'))}".strip(),
            "ementa": texto(p.get("ementa"), 2000),
            "tema": opcional(p.get("keywords")),
            "data_apresentacao": opcional(p.get("dataApresentacao")),
            "situacao": primeiro(p, "ultimoStatus_descricaoSituacao", "descricaoSituacao"),
            "tramitacao_atual": primeiro(p, "ultimoStatus_descricaoTramitacao", "descricaoTramitacao"),
            "orgao_atual": primeiro(p, "ultimoStatus_siglaOrgao", "siglaOrgao"),
            "regime": primeiro(p, "ultimoStatus_regime", "regime"),
            "data_ultimo_status": primeiro(p, "ultimoStatus_dataHora"),
            "ultimo_status": primeiro(p, "ultimoStatus_despacho", "despacho", limite=1000),
            "url": primeiro(p, "urlInteiroTeor", "uriInteiroTeor"),
            "id_autor": None if principal is None else opcional(principal["id_autor"]),
            "nome_autor": None if principal is None else opcional(principal["nome_autor"]),
            "partido_autor": None if principal is None else opcional(principal["partido_autor"]),
            "uf_autor": None if principal is None else opcional(principal["uf_autor"]),
            "qtd_autores": 0 if autores.empty else int((autores["id_proposicao"] == idp).sum()),
            "ano": int(ano),
        })

    armazem.mesclar("proposicao", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"proposicoes_{ano}", ano, len(linhas))
    return len(linhas)

def coletar_tramitacoes(id_proposicao: str) -> int:
    dados = buscar_api(f"proposicoes/{id_proposicao}/tramitacoes").get("dados", [])
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
        "id_proposicao": _proposicao_ou_nada(v.get("ultimaApresentacaoProposicao_idProposicao")),
        "url": opcional(v.get("uri")),
        "ano": int(ano),
    } for _, v in df.iterrows()]

    armazem.mesclar("votacao", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"votacoes_{ano}", ano, len(linhas))
    return len(linhas)

def coletar_votacoes_proposicoes(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/votacoesProposicoes/csv/votacoesProposicoes-{ano}.csv")
    if df.empty:
        return 0

    linhas = []
    for _, v in df.iterrows():
        id_proposicao = _proposicao_ou_nada(v.get("proposicao_id"))
        id_votacao = texto(v.get("idVotacao"))
        if not id_proposicao or not id_votacao:
            continue
        linhas.append({
            "casa": CASA,
            "id_votacao": id_votacao,
            "id_proposicao": id_proposicao,
            "titulo": primeiro(v, "proposicao__titulo", "proposicao_titulo"),
            "sigla_tipo": opcional(v.get("proposicao_siglaTipo")),
            "numero": opcional(v.get("proposicao_numero")),
            "ano_proposicao": inteiro(v.get("proposicao_ano")),
            "descricao": texto(v.get("descricao"), 2000),
            "data": opcional(v.get("data")),
            "ano": int(ano),
        })

    if linhas:
        armazem.mesclar("votacao_proposicao", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"votacoes_proposicoes_{ano}", ano, len(linhas))
    return len(linhas)

def coletar_votos(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/votacoesVotos/csv/votacoesVotos-{ano}.csv")
    if df.empty:
        return 0

    data_hora = pd.to_datetime(df.get("dataHoraVoto"), errors="coerce", format="mixed")
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

def coletar_orientacoes(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/votacoesOrientacoes/csv/votacoesOrientacoes-{ano}.csv")
    if df.empty:
        return 0

    linhas = [{
        "casa": CASA,
        "id_votacao": texto(v["idVotacao"]),
        "sigla_bancada": texto(v.get("siglaBancada")),
        "orientacao": opcional(v.get("orientacao")),
        "sigla_orgao": opcional(v.get("siglaOrgao")),
        "ano": int(ano),
    } for _, v in df.iterrows()]

    armazem.mesclar("orientacao_bancada", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"orientacoes_{ano}", ano, len(linhas))
    return len(linhas)

def coletar_eventos(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/eventos/csv/eventos-{ano}.csv")
    if df.empty:
        return 0

    linhas = []
    for _, v in df.iterrows():
        tipo = texto(v.get("descricaoTipo")) or ""
        linhas.append({
            "casa": CASA,
            "id_evento": texto(v["id"]),
            "data_hora_inicio": opcional(v.get("dataHoraInicio")),
            "data_hora_fim": opcional(v.get("dataHoraFim")),
            "descricao_tipo": tipo or None,
            "descricao": texto(v.get("descricao"), 2000),
            "situacao": opcional(v.get("situacao")),
            "local": primeiro(v, "localCamara_nome", "localExterno", limite=300),
            "deliberativo": any(marca in tipo.lower() for marca in TIPOS_DELIBERATIVOS),
            "ano": int(ano),
        })

    armazem.mesclar("evento", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"eventos_{ano}", ano, len(linhas))
    return len(linhas)

def coletar_presenca(ano: int) -> int:
    df = _csv(f"{config.CAMARA_ARQUIVOS}/eventosPresencaDeputados/csv/eventosPresencaDeputados-{ano}.csv")
    if df.empty:
        return 0

    inicio = pd.to_datetime(df.get("dataHoraInicio"), errors="coerce", format="mixed")
    df = df.assign(
        _ano=inicio.dt.year.fillna(ano).astype(int),
        _mes=inicio.dt.month.fillna(1).astype(int),
    )

    linhas = [{
        "casa": CASA,
        "id_evento": texto(v["idEvento"]),
        "id_politico": texto(v["idDeputado"]),
        "data_hora_inicio": opcional(v.get("dataHoraInicio")),
        "ano": int(v["_ano"]),
        "mes": int(v["_mes"]),
    } for _, v in df.iterrows()]

    armazem.mesclar("presenca_evento", linhas, f"{FONTE}_lote")
    controle.gravar_marca(FONTE, f"presenca_{ano}", ano, len(linhas))
    return len(linhas)

def votos_por_api(id_votacao: str) -> list[dict]:
    dados = buscar_api(f"proposicoes/{id_votacao}/votos").get("dados", [])
    if not dados:
        log.warning("votação %s devolveu 0 votos pela API — use o lote", id_votacao)
    return dados

def coletar_despesas(ano: int) -> int:
    df = _csv_da_cota(ano)
    if df.empty:
        return 0
    if "numParcela" not in df.columns:
        log.warning("Câmara CEAP %d: CSV não contém a coluna numParcela. Colunas disponíveis: %s", ano, list(df.columns))

    emissao = pd.to_datetime(df.get("datEmissao"), errors="coerce", format="mixed")
    linhas = [{
        "casa": CASA,
        "id_documento": texto(d.get("ideDocumento")),
        "num_parcela": _chave_parcela(d.get("numParcela")),
        "num_ressarcimento": _chave_parcela(d.get("numRessarcimento")),
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

def executar(anos: list[int] | None = None, com_despesas: bool = True) -> None:
    anos = anos or [date.today().year]
    coletar_deputados()
    for ano in anos:
        for nome, funcao in (
            ("proposições", coletar_proposicoes),
            ("votações", coletar_votacoes),
            ("votação → proposição", coletar_votacoes_proposicoes),
            ("votos", coletar_votos),
            ("orientações", coletar_orientacoes),
            ("eventos", coletar_eventos),
            ("presença", coletar_presenca),
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
