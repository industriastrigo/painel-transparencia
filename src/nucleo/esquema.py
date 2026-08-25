"""Esquema lógico do banco — que vive dentro dos Parquet.

Cada tabela declara: camada (dim/fato), campos que formam a chave de negócio,
colunas de partição Hive e a coluna de data que alimenta os filtros do painel.

Convenção obrigatória em TODAS as tabelas:
  primeira coluna : sk               (md5 dos campos de negócio)
  últimas colunas : _hash_registro, _fonte, _criado_em, _atualizado_em
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

COLUNAS_CONTROLE = ["_hash_registro", "_fonte", "_criado_em", "_atualizado_em"]


@dataclass(frozen=True)
class Tabela:
    nome: str
    camada: str  # "dim" ou "fato"
    campos_pk: tuple[str, ...]
    particoes: tuple[str, ...] = ()
    data_referencia: str | None = None
    descricao: str = ""
    cadencia: str = ""
    campos_negocio: tuple[str, ...] = field(default=())
    # Contrato mínimo de colunas: o que as views e a API precisam encontrar.
    # Serve para criar uma view VAZIA porém TIPADA quando a tabela ainda não
    # foi coletada — assim o painel abre e mostra "sem dados" em vez de 500.
    colunas: tuple[tuple[str, str], ...] = field(default=())

    @property
    def caminho_relativo(self) -> str:
        return f"{self.camada}/{self.nome}"


TABELAS: dict[str, Tabela] = {}


def _registrar(t: Tabela) -> Tabela:
    TABELAS[t.nome] = t
    return t


# --------------------------------------------------------------- dimensões
# Pequenas, sem partição, sobrescritas por inteiro a cada carga.

dim_ente = _registrar(Tabela(
    nome="dim_ente",
    camada="dim",
    campos_pk=("cod_ibge",),
    descricao="País, 27 UFs e 5.570 municípios. Código IBGE é a chave de "
              "junção de TODO o projeto.",
    cadencia="anual",
))

dim_politico = _registrar(Tabela(
    nome="dim_politico",
    camada="dim",
    campos_pk=("fonte_origem", "id_origem"),
    descricao="Pessoa que ocupa ou disputou cargo. Um registro por "
              "(fonte, id) — a consolidação por CPF vira o de-para.",
    cadencia="diária (Câmara/Senado) · eleitoral (TSE)",
))

dim_partido = _registrar(Tabela(
    nome="dim_partido",
    camada="dim",
    campos_pk=("sigla",),
    descricao="Partidos com registro no TSE.",
    cadencia="anual",
))

dim_metrica = _registrar(Tabela(
    nome="dim_metrica",
    camada="dim",
    campos_pk=("cod_metrica",),
    descricao="Catálogo de indicadores (população, PIB, IDHM, despesa por "
              "função). Esquema longo: métrica nova não exige migração.",
    cadencia="manual",
))

dim_de_para_ente = _registrar(Tabela(
    nome="dim_de_para_ente",
    camada="dim",
    campos_pk=("fonte_origem", "id_origem"),
    descricao="Ponte entre o identificador de cada fonte e o código IBGE. "
              "É o que permite cruzar 'quem governa' (TSE) com 'quanto o ente "
              "gasta' (SICONFI). Guarda o método do casamento e a "
              "similaridade, para que um match aproximado seja auditável em "
              "vez de invisível.",
    cadencia="eleitoral",
))

dim_cargo_publico = _registrar(Tabela(
    nome="dim_cargo_publico",
    camada="dim",
    campos_pk=("cod_cargo",),
    descricao="Cargos públicos além dos eletivos: ministros de Estado, "
              "ministros do STF, magistrados por ramo.",
    cadencia="manual",
))

dim_subsidio = _registrar(Tabela(
    nome="dim_subsidio",
    camada="dim",
    campos_pk=("cod_cargo", "vigencia_inicio"),
    descricao="Subsídio por cargo e vigência, TRANSCRITO de norma — não há "
              "API. Cada linha carrega a norma que o fixa e um marcador "
              "`conferido`: valor não conferido aparece no painel com aviso, "
              "porque salário sem fonte datada é número indefensável.",
    cadencia="a cada reajuste",
))

dim_cargo = _registrar(Tabela(
    nome="dim_cargo",
    camada="dim",
    campos_pk=("cod_cargo",),
    descricao="Presidente, governador, prefeito, deputado federal, "
              "deputado estadual, senador, vereador.",
    cadencia="manual",
))

# --------------------------------------------------------------- fatos

indicador_ente = _registrar(Tabela(
    nome="indicador_ente",
    camada="fato",
    campos_pk=("cod_ibge", "cod_metrica", "ano"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Um valor por ente × métrica × ano. Formato longo.",
    cadencia="anual",
))

financas_ente = _registrar(Tabela(
    nome="financas_ente",
    camada="fato",
    campos_pk=("cod_ibge", "ano", "periodo", "cod_conta"),
    particoes=("ano", "esfera"),
    data_referencia="data_referencia",
    descricao="SICONFI já agregado por função de governo (saúde, educação, "
              "previdência). Guardar conta contábil folha a folha levaria de "
              "~150 mil para ~50 milhões de linhas por ano sem ganho.",
    cadencia="mensal (RREO/RGF) · anual (DCA)",
))

mandato = _registrar(Tabela(
    nome="mandato",
    camada="fato",
    campos_pk=("sk_politico", "cod_cargo", "cod_ue", "ano_inicio"),
    particoes=("ano_inicio",),
    data_referencia="data_inicio",
    descricao="Quem ocupa cada cargo, em cada ente, em cada legislatura. "
              "A PK usa `cod_ue` (unidade eleitoral do TSE), que é o "
              "identificador que a fonte realmente fornece; `cod_ibge` é "
              "preenchido pelo de-para e pode ficar nulo sem quebrar a "
              "chave — chave primária não pode depender de um casamento que "
              "talvez não aconteça.",
    cadencia="eleitoral",
))

proposicao = _registrar(Tabela(
    nome="proposicao",
    camada="fato",
    campos_pk=("casa", "id_proposicao"),
    particoes=("ano",),
    data_referencia="data_apresentacao",
    descricao="PL, PEC, MP e afins. `sk_autor` liga ao dono da proposição.",
    cadencia="diária",
))

tramitacao = _registrar(Tabela(
    nome="tramitacao",
    camada="fato",
    campos_pk=("casa", "id_proposicao", "seq_tramitacao"),
    particoes=("ano",),
    data_referencia="data_hora",
    descricao="Cada etapa por onde a proposição passou.",
    cadencia="diária",
))

votacao = _registrar(Tabela(
    nome="votacao",
    camada="fato",
    campos_pk=("casa", "id_votacao"),
    particoes=("ano",),
    data_referencia="data_hora",
    descricao="Sessão de votação nominal.",
    cadencia="diária",
))

voto = _registrar(Tabela(
    nome="voto",
    camada="fato",
    campos_pk=("casa", "id_votacao", "id_politico"),
    particoes=("ano", "mes"),
    data_referencia="data_hora",
    descricao="Voto individual — o produto do painel. 513 deputados × ~1.500 "
              "votações/ano ≈ 770 mil linhas, ~4 MB em Parquet.",
    cadencia="diária",
))

despesa_parlamentar = _registrar(Tabela(
    nome="despesa_parlamentar",
    camada="fato",
    campos_pk=("casa", "id_documento", "num_parcela", "num_ressarcimento"),
    particoes=("ano", "mes"),
    data_referencia="data_emissao",
    descricao="Cota parlamentar, nota a nota. Único dado guardado no grão "
              "bruto, por decisão de escopo. `ideDocumento` sozinho NÃO é "
              "único — reembolso parcelado repete o documento em várias "
              "linhas —, e a chave curta descartava ~1.300 notas por ano "
              "como se fossem duplicatas.",
    cadencia="mensal",
))

custo_orgao = _registrar(Tabela(
    nome="custo_orgao",
    camada="fato",
    campos_pk=("conjunto", "orgao_nome", "item_custo", "ano", "mes"),
    particoes=("ano", "conjunto"),
    data_referencia="data_referencia",
    descricao="Custo apurado do Governo Federal por órgão e item, do SIC "
              "(Tesouro Transparente). É o dado MEDIDO que responde 'quanto "
              "essa função tira dos cofres' — substitui a estimativa "
              "ocupantes × subsídio na esfera federal.",
    cadencia="mensal",
))

emenda_parlamentar = _registrar(Tabela(
    nome="emenda_parlamentar",
    camada="fato",
    campos_pk=("ano", "codigo_emenda"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Emendas individuais, de bancada, de comissão e transferências "
              "especiais (Pix), do Portal da Transparência.",
    cadencia="mensal",
))

# --------------------------------------------------------------- controle

ingestao = Tabela(
    nome="ingestao",
    camada="_ctl",
    campos_pk=("fonte", "recurso"),
    descricao="Marca-d'água por fonte: até onde cada coletor já leu.",
)
TABELAS[ingestao.nome] = ingestao

coleta_ente = Tabela(
    nome="coleta_ente",
    camada="_ctl",
    campos_pk=("fonte", "recurso", "ano", "cod_ibge"),
    descricao="Uma linha por ente já tentado numa coleta em massa. É o que "
              "permite retomar 5.570 municípios de onde parou, em vez de "
              "recomeçar do zero quando a máquina hiberna no meio.",
)
TABELAS[coleta_ente.nome] = coleta_ente


# --------------------------------------------------------------- contratos
# Só as colunas que as views e a API consultam. Coletor pode trazer mais.

_COLUNAS: dict[str, tuple[tuple[str, str], ...]] = {
    "dim_ente": (
        ("cod_ibge", "VARCHAR"), ("nivel", "VARCHAR"), ("nome", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("cod_uf", "VARCHAR"), ("regiao", "VARCHAR"),
    ),
    "dim_politico": (
        ("fonte_origem", "VARCHAR"), ("id_origem", "VARCHAR"), ("nome", "VARCHAR"),
        ("nome_eleitoral", "VARCHAR"), ("sigla_partido", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("casa", "VARCHAR"), ("cargo", "VARCHAR"),
        ("url_foto", "VARCHAR"),
    ),
    "dim_partido": (("sigla", "VARCHAR"), ("nome", "VARCHAR"), ("numero", "VARCHAR")),
    "dim_metrica": (
        ("cod_metrica", "VARCHAR"), ("rotulo", "VARCHAR"), ("unidade", "VARCHAR"),
        ("fonte_origem", "VARCHAR"),
    ),
    "dim_cargo": (("cod_cargo", "VARCHAR"), ("cargo", "VARCHAR"),
                  ("nivel_ente", "VARCHAR"), ("poder", "VARCHAR")),
    "dim_cargo_publico": (
        ("cod_cargo", "VARCHAR"), ("cargo", "VARCHAR"), ("poder", "VARCHAR"),
        ("esfera", "VARCHAR"), ("ramo", "VARCHAR"),
    ),
    "dim_subsidio": (
        ("cod_cargo", "VARCHAR"), ("vigencia_inicio", "VARCHAR"),
        ("valor_mensal", "DOUBLE"), ("norma", "VARCHAR"),
        ("url_norma", "VARCHAR"), ("conferido", "BOOLEAN"),
        ("observacao", "VARCHAR"),
    ),
    "dim_de_para_ente": (
        ("fonte_origem", "VARCHAR"), ("id_origem", "VARCHAR"),
        ("cod_ibge", "VARCHAR"), ("sigla_uf", "VARCHAR"),
        ("nome_origem", "VARCHAR"), ("nome_ibge", "VARCHAR"),
        ("metodo", "VARCHAR"), ("similaridade", "DOUBLE"),
    ),
    "indicador_ente": (
        ("cod_ibge", "VARCHAR"), ("cod_metrica", "VARCHAR"), ("ano", "INTEGER"),
        ("valor", "DOUBLE"), ("unidade", "VARCHAR"), ("data_referencia", "VARCHAR"),
    ),
    "financas_ente": (
        ("cod_ibge", "VARCHAR"), ("ano", "INTEGER"), ("periodo", "VARCHAR"),
        ("cod_conta", "VARCHAR"), ("cod_funcao", "VARCHAR"), ("funcao", "VARCHAR"),
        ("estagio", "VARCHAR"), ("valor", "DOUBLE"), ("esfera", "VARCHAR"),
        ("data_referencia", "VARCHAR"),
    ),
    "mandato": (
        ("sk_politico", "VARCHAR"), ("cod_cargo", "VARCHAR"), ("cargo", "VARCHAR"),
        ("cod_ue", "VARCHAR"), ("cod_ibge", "VARCHAR"), ("sigla_uf", "VARCHAR"),
        ("nome_ente", "VARCHAR"), ("nome", "VARCHAR"),
        ("sigla_partido", "VARCHAR"), ("ano_inicio", "INTEGER"),
        ("ano_fim", "INTEGER"), ("data_inicio", "VARCHAR"),
        ("ano_eleicao", "INTEGER"),
    ),
    "proposicao": (
        ("casa", "VARCHAR"), ("id_proposicao", "VARCHAR"), ("sigla_tipo", "VARCHAR"),
        ("identificador", "VARCHAR"), ("ementa", "VARCHAR"),
        ("data_apresentacao", "VARCHAR"), ("situacao", "VARCHAR"),
        ("tramitacao_atual", "VARCHAR"), ("orgao_atual", "VARCHAR"),
        ("regime", "VARCHAR"), ("data_ultimo_status", "VARCHAR"),
        ("nome_autor", "VARCHAR"), ("partido_autor", "VARCHAR"),
        ("uf_autor", "VARCHAR"), ("qtd_autores", "INTEGER"), ("url", "VARCHAR"),
        ("ano", "INTEGER"),
    ),
    "tramitacao": (
        ("casa", "VARCHAR"), ("id_proposicao", "VARCHAR"),
        ("seq_tramitacao", "VARCHAR"), ("data_hora", "VARCHAR"),
        ("orgao", "VARCHAR"), ("descricao_tramitacao", "VARCHAR"),
        ("descricao_situacao", "VARCHAR"), ("despacho", "VARCHAR"),
        ("ano", "INTEGER"),
    ),
    "votacao": (
        ("casa", "VARCHAR"), ("id_votacao", "VARCHAR"), ("data_hora", "VARCHAR"),
        ("sigla_orgao", "VARCHAR"), ("descricao", "VARCHAR"),
        ("aprovada", "VARCHAR"), ("id_proposicao", "VARCHAR"), ("ano", "INTEGER"),
    ),
    "voto": (
        ("casa", "VARCHAR"), ("id_votacao", "VARCHAR"), ("id_politico", "VARCHAR"),
        ("nome_politico", "VARCHAR"), ("sigla_partido", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("voto", "VARCHAR"), ("data_hora", "VARCHAR"),
        ("ano", "INTEGER"), ("mes", "INTEGER"),
    ),
    "despesa_parlamentar": (
        ("casa", "VARCHAR"), ("id_documento", "VARCHAR"),
        ("num_parcela", "VARCHAR"), ("num_ressarcimento", "VARCHAR"),
        ("id_politico", "VARCHAR"),
        ("nome_politico", "VARCHAR"), ("sigla_partido", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("tipo_despesa", "VARCHAR"),
        ("fornecedor", "VARCHAR"), ("valor_liquido", "DOUBLE"),
        ("data_emissao", "VARCHAR"), ("ano", "INTEGER"), ("mes", "INTEGER"),
    ),
    "custo_orgao": (
        ("conjunto", "VARCHAR"), ("orgao_nome", "VARCHAR"),
        ("orgao_codigo", "VARCHAR"), ("item_custo", "VARCHAR"),
        ("ano", "INTEGER"), ("mes", "INTEGER"), ("valor", "DOUBLE"),
        ("data_referencia", "VARCHAR"),
    ),
    "emenda_parlamentar": (
        ("ano", "INTEGER"), ("codigo_emenda", "VARCHAR"), ("tipo_emenda", "VARCHAR"),
        ("autor", "VARCHAR"), ("funcao", "VARCHAR"), ("valor_empenhado", "DOUBLE"),
        ("valor_pago", "DOUBLE"), ("localidade", "VARCHAR"),
    ),
}

for _nome, _cols in _COLUNAS.items():
    TABELAS[_nome] = replace(TABELAS[_nome], colunas=_cols)
    globals()[_nome] = TABELAS[_nome]


def obter(nome: str) -> Tabela:
    if nome not in TABELAS:
        raise KeyError(f"tabela desconhecida: {nome}")
    return TABELAS[nome]


def selecao_vazia(tabela: Tabela) -> str:
    """SELECT tipado que devolve zero linhas — view de tabela ainda não coletada."""
    colunas = tabela.colunas or (("sk", "VARCHAR"),)
    campos = ", ".join(f"CAST(NULL AS {tipo}) AS {nome}" for nome, tipo in colunas)
    controle = ", ".join([
        "CAST(NULL AS VARCHAR) AS _hash_registro",
        "CAST(NULL AS VARCHAR) AS _fonte",
        "CAST(NULL AS TIMESTAMPTZ) AS _criado_em",
        "CAST(NULL AS TIMESTAMPTZ) AS _atualizado_em",
    ])
    return (f"SELECT * FROM (SELECT CAST(NULL AS VARCHAR) AS sk, {campos}, "
            f"{controle}) WHERE FALSE")
