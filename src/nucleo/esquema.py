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

dim_transferencia = _registrar(Tabela(
    nome="dim_transferencia",
    camada="dim",
    campos_pk=("cod_transferencia",),
    descricao="Modalidades de transferências constitucionais e legais da União.",
    cadencia="estática",
))

dim_magistrado = _registrar(Tabela(
    nome="dim_magistrado",
    camada="dim",
    campos_pk=("sk",),
    descricao="Juízes, desembargadores e ministros dos tribunais brasileiros (CNJ/STF/STJ/TST).",
    cadencia="mensal",
    colunas=(
        ("sk", "VARCHAR"),
        ("id_origem", "VARCHAR"),
        ("nome", "VARCHAR"),
        ("cargo", "VARCHAR"),
        ("cargo_descricao", "VARCHAR"),
        ("tribunal", "VARCHAR"),
        ("ramo", "VARCHAR"),
        ("grau", "VARCHAR"),
        ("sigla_uf", "VARCHAR"),
        ("orgao_lotacao", "VARCHAR"),
        ("data_posse", "VARCHAR"),
        ("situacao", "VARCHAR"),
        ("url_foto", "VARCHAR"),
    ),
))

dim_membro_mp = _registrar(Tabela(
    nome="dim_membro_mp",
    camada="dim",
    campos_pk=("sk",),
    descricao="Promotores e Procuradores de Justiça do Ministério Público (MPU e MPEs / CNMP).",
    cadencia="mensal",
    colunas=(
        ("sk", "VARCHAR"),
        ("id_origem", "VARCHAR"),
        ("nome", "VARCHAR"),
        ("cargo", "VARCHAR"),
        ("cargo_descricao", "VARCHAR"),
        ("orgao_mp", "VARCHAR"),
        ("ramo", "VARCHAR"),
        ("grau", "VARCHAR"),
        ("sigla_uf", "VARCHAR"),
        ("lotacao", "VARCHAR"),
        ("data_posse", "VARCHAR"),
        ("situacao", "VARCHAR"),
        ("url_foto", "VARCHAR"),
    ),
))

dim_catalogo_tabela = _registrar(Tabela(
    nome="dim_catalogo_tabela",
    camada="dim",
    campos_pk=("tabela", "ano_particao", "camada"),
    descricao="Catálogo e inventário do acervo de dados coletados por tabela e ano.",
    cadencia="a cada carga",
    colunas=(
        ("sk", "VARCHAR"),
        ("tabela", "VARCHAR"),
        ("camada", "VARCHAR"),
        ("ano_particao", "VARCHAR"),
        ("ano", "INTEGER"),
        ("total_linhas", "BIGINT"),
        ("fontes", "VARCHAR"),
        ("status_completude", "VARCHAR"),
        ("orgao_origem", "VARCHAR"),
        ("descricao_recurso", "VARCHAR"),
        ("endpoint_recurso", "VARCHAR"),
        ("granularidade", "VARCHAR"),
        ("data_atualizacao", "VARCHAR"),
    ),
))

# --------------------------------------------------------------- fatos

fato_remuneracao_magistrado = _registrar(Tabela(
    nome="fato_remuneracao_magistrado",
    camada="fato",
    campos_pk=("sk_magistrado", "ano", "mes"),
    particoes=("ano",),
    descricao="Folha de pagamento detalhada dos magistrados e ministros (Painel CNJ).",
    cadencia="mensal",
    colunas=(
        ("sk", "VARCHAR"),
        ("sk_magistrado", "VARCHAR"),
        ("ano", "INTEGER"),
        ("mes", "INTEGER"),
        ("subsidio", "DOUBLE"),
        ("vantagens_pessoais", "DOUBLE"),
        ("indenizacoes", "DOUBLE"),
        ("gratificacoes", "DOUBLE"),
        ("total_bruto", "DOUBLE"),
        ("retencao_teto", "DOUBLE"),
        ("descontos_legais", "DOUBLE"),
        ("total_liquido", "DOUBLE"),
    ),
))

fato_remuneracao_mp = _registrar(Tabela(
    nome="fato_remuneracao_mp",
    camada="fato",
    campos_pk=("sk_membro_mp", "ano", "mes"),
    particoes=("ano",),
    descricao="Folha de pagamento detalhada dos membros do Ministério Público (CNMP).",
    cadencia="mensal",
    colunas=(
        ("sk", "VARCHAR"),
        ("sk_membro_mp", "VARCHAR"),
        ("ano", "INTEGER"),
        ("mes", "INTEGER"),
        ("subsidio", "DOUBLE"),
        ("vantagens_pessoais", "DOUBLE"),
        ("indenizacoes", "DOUBLE"),
        ("gratificacoes", "DOUBLE"),
        ("total_bruto", "DOUBLE"),
        ("retencao_teto", "DOUBLE"),
        ("descontos_legais", "DOUBLE"),
        ("total_liquido", "DOUBLE"),
    ),
))

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

# Transferências obrigatórias da União para estados e municípios.
# Tabela SEPARADA de `financas_ente` de propósito: é outra medida da mesma
# realidade — quem pagou declara aqui, quem recebeu declara lá, em regimes e
# recortes diferentes. Juntar as duas na mesma tabela convidaria a somá-las.
transferencia_uniao = _registrar(Tabela(
    nome="transferencia_uniao",
    camada="fato",
    # `nivel`, `uf`, `nome_ente` e `transferencia` ENTRAM na chave para que as
    # diferentes modalidades e entes federativos não colidam no merge mensal.
    campos_pk=("cod_ibge", "nivel", "uf", "nome_ente", "cod_transferencia", "transferencia", "ano", "mes"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="FPM, FPE, FUNDEB, Lei Kandir, ITR, CIDE e royalties repassados "
              "pela União, por ente e por mês. Fonte: Tesouro/SIAFI, regime "
              "de caixa — não confundir com a transferência RECEBIDA que o "
              "próprio ente declara no SICONFI.",
    cadencia="mensal",
))

# Despesa por FUNÇÃO de governo — saúde, educação, segurança.
# Tabela separada de `financas_ente` de propósito: aquela guarda o DCA anual
# por NATUREZA (pessoal, juros, investimentos), esta guarda o RREO bimestral
# por FUNÇÃO. São recortes diferentes do mesmo dinheiro, e somá-los contaria
# tudo duas vezes — a mesma razão que separou as duas transferências.
despesa_funcao = _registrar(Tabela(
    nome="despesa_funcao",
    camada="fato",
    # `cod_conta` aqui é composto pelo coletor: bloco + função-mãe + conta.
    # A fonte manda `RREO2TotalDespesas` em todas as linhas, e o nome da
    # subfunção se repete sob várias funções — sem a função-mãe na identidade,
    # 4.867 linhas por carga colidiam e o merge guardava só a última.
    campos_pk=("cod_ibge", "ano", "periodo", "cod_conta"),
    particoes=("ano", "esfera"),
    data_referencia="data_referencia",
    descricao="RREO Anexo 02: execução da despesa por função e subfunção. "
              "Bimestral, então traz o exercício CORRENTE — o DCA só fecha o "
              "anterior.",
    cadencia="bimestral",
))

# Indicadores da Lei de Responsabilidade Fiscal.
indicador_fiscal = _registrar(Tabela(
    nome="indicador_fiscal",
    camada="fato",
    # `medida` ENTRA na chave: a mesma conta aparece em R$ e em % sobre a
    # RCL, e sem ela as duas colidiriam — o merge guardaria a última que
    # chegasse, que é como o percentual sumia do acervo.
    # `anexo`, `secao`, `coluna` e `rotulo` na chave: a mesma conta aparece nos
    # anexos do RGF e se repete entre seções e colunas do demonstrativo.
    campos_pk=("cod_ibge", "ano", "periodo", "poder", "indicador", "medida",
               "anexo", "secao", "coluna", "rotulo"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="RGF: despesa com pessoal sobre a receita corrente líquida (o "
              "limite da LRF) e dívida consolidada líquida. Responde 'quanto "
              "deve' com saldo, não com pedido como o SADIPEM.",
    cadencia="quadrimestral",
))

# Pedidos de Verificação de Limites: o pedido que um ente faz ao Tesouro para
# contrair dívida. NÃO é saldo devedor — ver a armadilha 2o.
operacao_credito = _registrar(Tabela(
    nome="operacao_credito",
    camada="fato",
    campos_pk=("id_pleito",),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="PVL do SADIPEM: quem pediu para tomar emprestado, de qual "
              "credor, para qual finalidade, quanto, e qual foi o desfecho. "
              "O valor é o do PLEITO, não o saldo devedor de hoje.",
    cadencia="mensal",
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

votacao_proposicao = _registrar(Tabela(
    nome="votacao_proposicao",
    camada="fato",
    campos_pk=("casa", "id_votacao", "id_proposicao"),
    particoes=("ano",),
    data_referencia="data",
    descricao="Que proposições foram votadas em cada votação. É N para N: uma "
              "votação pode decidir sobre várias proposições, e a mesma "
              "proposição volta em várias votações. Sem esta tabela, a ficha "
              "de um projeto nunca mostra quem votou a favor e contra — que é "
              "a promessa central do painel.",
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

evento = _registrar(Tabela(
    nome="evento",
    camada="fato",
    campos_pk=("casa", "id_evento"),
    particoes=("ano",),
    data_referencia="data_hora_inicio",
    descricao="Sessão, audiência ou reunião. Existe para dar DENOMINADOR à "
              "presença: sem saber quantas sessões deliberativas houve, "
              "'compareceu a 120' não quer dizer nada.",
    cadencia="diária",
))

presenca_evento = _registrar(Tabela(
    nome="presenca_evento",
    camada="fato",
    campos_pk=("casa", "id_evento", "id_politico"),
    particoes=("ano", "mes"),
    data_referencia="data_hora_inicio",
    descricao="Registro de presença de um deputado num evento já ocorrido. "
              "ATENÇÃO: a fonte só publica quem ESTEVE. Ausência é inferida "
              "pela ausência de linha, e por isso só pode ser calculada "
              "dentro da janela em que o deputado estava em exercício — "
              "quem tomou posse em março não faltou às sessões de fevereiro.",
    cadencia="diária",
))

orientacao_bancada = _registrar(Tabela(
    nome="orientacao_bancada",
    camada="fato",
    campos_pk=("casa", "id_votacao", "sigla_bancada"),
    particoes=("ano",),
    data_referencia=None,
    descricao="O voto que a liderança recomendou à sua bancada. Cruzado com "
              "`voto`, revela quem votou contra a orientação do próprio "
              "partido — que é o dado que nenhum painel comum mostra.",
    cadencia="diária",
))

despesa_parlamentar = _registrar(Tabela(
    nome="despesa_parlamentar",
    camada="fato",
    campos_pk=("casa", "id_politico", "id_documento", "num_parcela", "num_ressarcimento", "ano", "mes"),
    particoes=("ano", "mes"),
    data_referencia="data_emissao",
    descricao="Cota parlamentar, nota a nota. Único dado guardado no grão "
              "bruto, por decisão de escopo. `ideDocumento` sozinho NÃO é "
              "único — reembolso parcelado repete o documento em várias "
              "linhas, e despesas internas (como telefonia) têm id_documento=0.",
    cadencia="mensal",
))

custo_orgao = _registrar(Tabela(
    nome="custo_orgao",
    camada="fato",
    campos_pk=("ano", "mes", "conjunto", "orgao_codigo", "orgao_nome", "orgao_n2", "orgao_n3", "item_custo", "natureza_juridica"),
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
    campos_pk=("ano", "codigo_emenda", "funcao", "localidade"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Emendas individuais, de bancada, de comissão e transferências "
              "especiais (Pix), do Portal da Transparência.",
    cadencia="mensal",
))

cartao_corporativo = _registrar(Tabela(
    nome="cartao_corporativo",
    camada="fato",
    campos_pk=("ano", "mes", "codigo_orgao", "cpf_portador", "data_transacao", "cnpj_cpf_favorecido", "valor"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Gastos do Cartão de Pagamento do Governo Federal (CPGF) / Cartões Corporativos do Executivo.",
    cadencia="mensal",
))

viagem_servico = _registrar(Tabela(
    nome="viagem_servico",
    camada="fato",
    campos_pk=("ano", "id_viagem", "codigo_orgao", "cpf_viajante", "data_inicio"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Diárias, passagens e viagens a serviço do Governo Federal (PCDP / CGU).",
    cadencia="mensal",
))

bem_declarado = _registrar(Tabela(
    nome="bem_declarado",
    camada="fato",
    campos_pk=("id_politico", "ano_eleicao", "sequencial_candidato", "tipo_bem", "descricao_bem", "valor_bem"),
    particoes=("ano_eleicao",),
    data_referencia="data_referencia",
    descricao="Declaração de bens e evolução patrimonial de políticos e candidatos (TSE).",
    cadencia="eleitoral",
))

contrato_governo = _registrar(Tabela(
    nome="contrato_governo",
    camada="fato",
    campos_pk=("ano", "id_contrato", "codigo_orgao", "cnpj_fornecedor"),
    particoes=("ano",),
    data_referencia="data_referencia",
    descricao="Contratos públicos, licitações, dispensas e fornecedores (PNCP / Compras.gov.br / CGU).",
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

qualidade = Tabela(
    nome="qualidade",
    camada="_ctl",
    campos_pk=("tabela", "coluna"),
    descricao="Taxa de preenchimento por coluna, com a MELHOR taxa já vista. "
              "É a linha de base do portão: coluna que já esteve 98% cheia e "
              "voltar a 3% acusa, mesmo que a carga ruim tenha rodado antes.",
)
TABELAS[qualidade.nome] = qualidade

log_auditoria_carga = Tabela(
    nome="log_auditoria_carga",
    camada="_ctl",
    campos_pk=("id_auditoria",),
    descricao="Histórico de auditoria, validação origem x tabela e reprocessamento inteligente de cargas.",
)
TABELAS[log_auditoria_carga.nome] = log_auditoria_carga



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
    "dim_transferencia": (
        ("cod_transferencia", "VARCHAR"),
        ("nome", "VARCHAR"),
    ),
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
        # `rotulo_conta` e `uf` eram gravados pelo coletor e NÃO estavam no
        # contrato. Enquanto a tabela tinha dado, ninguém notou — o Parquet
        # trazia as colunas. Numa instalação nova, porém, a view nasce do
        # contrato, e três views de despesa quebravam com
        # `Binder Error: Referenced column "rotulo_conta" not found`.
        # Coluna que o coletor grava PRECISA estar declarada aqui.
        ("rotulo_conta", "VARCHAR"), ("uf", "VARCHAR"),
        ("estagio", "VARCHAR"), ("valor", "DOUBLE"), ("esfera", "VARCHAR"),
        ("data_referencia", "VARCHAR"),
    ),
    "transferencia_uniao": (
        ("cod_ibge", "VARCHAR"), ("nivel", "VARCHAR"), ("uf", "VARCHAR"),
        ("nome_ente", "VARCHAR"), ("cod_transferencia", "VARCHAR"),
        ("transferencia", "VARCHAR"), ("ano", "INTEGER"), ("mes", "INTEGER"),
        ("valor", "DOUBLE"), ("cod_siafi", "VARCHAR"),
        ("data_referencia", "VARCHAR"),
    ),
    "despesa_funcao": (
        ("cod_ibge", "VARCHAR"), ("ano", "INTEGER"), ("periodo", "VARCHAR"),
        ("cod_conta", "VARCHAR"), ("cod_funcao", "VARCHAR"),
        ("funcao", "VARCHAR"),
        # A função a que a subfunção pertence. Só existe na ORDEM do
        # demonstrativo — a resposta não liga uma à outra.
        ("cod_funcao_mae", "VARCHAR"), ("funcao_mae", "VARCHAR"),
        ("rotulo_conta", "VARCHAR"),
        # O bloco do demonstrativo: `exceto_intra` ou `intra`. São dois
        # universos que se SOMAM para dar o total do ente — guardar o bloco é
        # o que permite conferir isso em vez de torcer.
        #
        # Vem do sufixo `Intra` do `cod_conta` da fonte, não do campo
        # `rotulo`: o rótulo descreve o mesmo bloco por extenso, mas falta em
        # 15% das linhas, e onde faltava as duas despesas da mesma função
        # colidiam na chave — uma apagava a outra, em silêncio.
        ("bloco", "VARCHAR"),
        # O rótulo por extenso, quando a fonte manda. É descrição, não chave.
        ("descricao_bloco", "VARCHAR"),
        ("estagio", "VARCHAR"), ("valor", "DOUBLE"), ("esfera", "VARCHAR"),
        ("uf", "VARCHAR"), ("data_referencia", "VARCHAR"),
    ),
    "indicador_fiscal": (
        ("cod_ibge", "VARCHAR"), ("ano", "INTEGER"), ("periodo", "VARCHAR"),
        ("poder", "VARCHAR"),
        # O `cod_conta` do RGF, VERBATIM — sem tradução para uma lista curta
        # de apelidos nossos. Conta não prevista entra no acervo em vez de
        # ser descartada, e vira consulta em vez de recoleta.
        ("indicador", "VARCHAR"),
        # O que o número é: valor em R$, percentual sobre a RCL, saldo do
        # quadrimestre. No RGF isso vem da COLUNA, não da conta.
        ("medida", "VARCHAR"),
        ("rotulo", "VARCHAR"),
        # Seção do demonstrativo (campo `rotulo` da fonte), não a descrição.
        ("secao", "VARCHAR"), ("anexo", "VARCHAR"), ("coluna", "VARCHAR"),
        ("valor", "DOUBLE"), ("esfera", "VARCHAR"), ("uf", "VARCHAR"),
        ("data_referencia", "VARCHAR"),
    ),
    "operacao_credito": (
        ("id_pleito", "INTEGER"), ("cod_ibge", "VARCHAR"), ("uf", "VARCHAR"),
        ("tipo_interessado", "VARCHAR"), ("interessado", "VARCHAR"),
        ("num_pvl", "VARCHAR"), ("num_processo", "VARCHAR"),
        ("status", "VARCHAR"), ("tipo_operacao", "VARCHAR"),
        ("finalidade", "VARCHAR"), ("tipo_credor", "VARCHAR"),
        ("credor", "VARCHAR"), ("moeda", "VARCHAR"), ("valor", "DOUBLE"),
        ("contratado", "INTEGER"), ("data_protocolo", "VARCHAR"),
        ("data_status", "VARCHAR"), ("ano", "INTEGER"),
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
        ("numero", "VARCHAR"), ("identificador", "VARCHAR"), ("ementa", "VARCHAR"),
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
    "votacao_proposicao": (
        ("casa", "VARCHAR"), ("id_votacao", "VARCHAR"),
        ("id_proposicao", "VARCHAR"), ("titulo", "VARCHAR"),
        ("sigla_tipo", "VARCHAR"), ("numero", "VARCHAR"),
        ("ano_proposicao", "INTEGER"), ("descricao", "VARCHAR"),
        ("data", "VARCHAR"), ("ano", "INTEGER"),
    ),
    "voto": (
        ("casa", "VARCHAR"), ("id_votacao", "VARCHAR"), ("id_politico", "VARCHAR"),
        ("nome_politico", "VARCHAR"), ("sigla_partido", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("voto", "VARCHAR"), ("data_hora", "VARCHAR"),
        ("ano", "INTEGER"), ("mes", "INTEGER"),
    ),
    "evento": (
        ("casa", "VARCHAR"), ("id_evento", "VARCHAR"),
        ("data_hora_inicio", "VARCHAR"), ("data_hora_fim", "VARCHAR"),
        ("descricao_tipo", "VARCHAR"), ("descricao", "VARCHAR"),
        ("situacao", "VARCHAR"), ("local", "VARCHAR"),
        ("deliberativo", "BOOLEAN"), ("ano", "INTEGER"),
    ),
    "presenca_evento": (
        ("casa", "VARCHAR"), ("id_evento", "VARCHAR"),
        ("id_politico", "VARCHAR"), ("data_hora_inicio", "VARCHAR"),
        ("ano", "INTEGER"), ("mes", "INTEGER"),
    ),
    "orientacao_bancada": (
        ("casa", "VARCHAR"), ("id_votacao", "VARCHAR"),
        ("sigla_bancada", "VARCHAR"), ("orientacao", "VARCHAR"),
        ("sigla_orgao", "VARCHAR"), ("ano", "INTEGER"),
    ),
    "despesa_parlamentar": (
        ("casa", "VARCHAR"), ("id_documento", "VARCHAR"),
        ("num_parcela", "VARCHAR"), ("num_ressarcimento", "VARCHAR"),
        ("id_politico", "VARCHAR"),
        ("nome_politico", "VARCHAR"), ("sigla_partido", "VARCHAR"),
        ("sigla_uf", "VARCHAR"), ("tipo_despesa", "VARCHAR"),
        ("fornecedor", "VARCHAR"),
        # CNPJ e link do documento existiam no COLETOR e não no contrato: a
        # view podia tê-los ou não conforme o que estivesse no disco, e numa
        # instalação nova a consulta por fornecedor quebrava. São eles que
        # tornam a nota auditável — sem CNPJ não dá para reconhecer o mesmo
        # fornecedor em gabinetes diferentes.
        ("cnpj_cpf_fornecedor", "VARCHAR"),
        ("valor_documento", "DOUBLE"), ("url_documento", "VARCHAR"),
        ("valor_liquido", "DOUBLE"),
        ("data_emissao", "VARCHAR"), ("ano", "INTEGER"), ("mes", "INTEGER"),
    ),
    "custo_orgao": (
        ("conjunto", "VARCHAR"), ("orgao_nome", "VARCHAR"),
        ("orgao_codigo", "VARCHAR"), ("orgao_n2", "VARCHAR"),
        ("orgao_n3", "VARCHAR"), ("item_custo", "VARCHAR"),
        ("natureza_juridica", "VARCHAR"),
        ("ano", "INTEGER"), ("mes", "INTEGER"), ("valor", "DOUBLE"),
        ("data_referencia", "VARCHAR"),
    ),
    "emenda_parlamentar": (
        ("ano", "INTEGER"), ("codigo_emenda", "VARCHAR"), ("tipo_emenda", "VARCHAR"),
        ("autor", "VARCHAR"), ("funcao", "VARCHAR"), ("valor_empenhado", "DOUBLE"),
        ("valor_pago", "DOUBLE"), ("localidade", "VARCHAR"),
    ),
    "cartao_corporativo": (
        ("ano", "INTEGER"), ("mes", "INTEGER"),
        ("codigo_orgao", "VARCHAR"), ("nome_orgao", "VARCHAR"),
        ("nome_portador", "VARCHAR"), ("cpf_portador", "VARCHAR"),
        ("nome_favorecido", "VARCHAR"), ("cnpj_cpf_favorecido", "VARCHAR"),
        ("tipo_cartao", "VARCHAR"), ("data_transacao", "VARCHAR"),
        ("valor", "DOUBLE"), ("data_referencia", "VARCHAR"),
    ),
    "viagem_servico": (
        ("ano", "INTEGER"), ("mes", "INTEGER"), ("id_viagem", "VARCHAR"),
        ("codigo_orgao", "VARCHAR"), ("nome_orgao", "VARCHAR"),
        ("nome_viajante", "VARCHAR"), ("cpf_viajante", "VARCHAR"), ("cargo_viajante", "VARCHAR"),
        ("origem", "VARCHAR"), ("destino", "VARCHAR"), ("motivo", "VARCHAR"),
        ("data_inicio", "VARCHAR"), ("data_fim", "VARCHAR"),
        ("valor_diarias", "DOUBLE"), ("valor_passagens", "DOUBLE"),
        ("valor_outros", "DOUBLE"), ("valor_total", "DOUBLE"),
        ("data_referencia", "VARCHAR"),
    ),
    "bem_declarado": (
        ("id_politico", "VARCHAR"), ("ano_eleicao", "INTEGER"),
        ("sequencial_candidato", "VARCHAR"), ("cargo", "VARCHAR"),
        ("tipo_bem", "VARCHAR"), ("descricao_bem", "VARCHAR"),
        ("valor_bem", "DOUBLE"), ("data_referencia", "VARCHAR"),
    ),
    "contrato_governo": (
        ("ano", "INTEGER"), ("id_contrato", "VARCHAR"), ("numero_contrato", "VARCHAR"),
        ("codigo_orgao", "VARCHAR"), ("nome_orgao", "VARCHAR"),
        ("cnpj_fornecedor", "VARCHAR"), ("nome_fornecedor", "VARCHAR"),
        ("modalidade_licitacao", "VARCHAR"), ("objeto", "VARCHAR"),
        ("valor_inicial", "DOUBLE"), ("valor_atualizado", "DOUBLE"),
        ("data_inicio_vigencia", "VARCHAR"), ("data_fim_vigencia", "VARCHAR"),
        ("data_referencia", "VARCHAR"),
    ),
    "log_auditoria_carga": (
        ("id_auditoria", "VARCHAR"),
        ("data_hora", "VARCHAR"),
        ("tabela", "VARCHAR"),
        ("camada", "VARCHAR"),
        ("ano_particao", "VARCHAR"),
        ("status_validacao", "VARCHAR"),
        ("linhas_anterior", "INTEGER"),
        ("linhas_origem", "INTEGER"),
        ("linhas_atual", "INTEGER"),
        ("linhas_incluidas", "INTEGER"),
        ("linhas_excluidas", "INTEGER"),
        ("detalhe_mudanca", "VARCHAR"),
        ("duracao_ms", "INTEGER"),
        ("fonte_origem", "VARCHAR"),
        ("endpoint", "VARCHAR"),
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
