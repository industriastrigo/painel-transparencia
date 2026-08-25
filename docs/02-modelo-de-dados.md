# 02 — Modelo de dados

O banco existe, só que dentro dos Parquet. `src/nucleo/esquema.py` é a fonte
única de verdade: chave de negócio, partições e contrato de colunas.

## Layout físico

```
dados/
  dim/                              sem partição, sobrescrita total
    dim_ente.parquet
    dim_politico.parquet
    dim_partido.parquet
    dim_metrica.parquet
    dim_de_para_ente.parquet
    dim_cargo.parquet
  fato/
    indicador_ente/      ano=2024/part-000.parquet
    financas_ente/       ano=2024/esfera=municipio/part-000.parquet
    mandato/             ano_inicio=2023/part-000.parquet
    proposicao/          ano=2026/part-000.parquet
    tramitacao/          ano=2026/part-000.parquet
    votacao/             ano=2026/part-000.parquet
    voto/                ano=2026/mes=08/part-000.parquet
    despesa_parlamentar/ ano=2026/mes=08/part-000.parquet
    emenda_parlamentar/  ano=2024/part-000.parquet
  _ctl/
    ingestao.parquet                marca-d'água por fonte
    coleta_ente.parquet             retomada da varredura em massa
  malhas/
    brasil-uf.json · uf-SP.json · …
```

Hive partitioning: `WHERE ano BETWEEN 2020 AND 2024` nem abre os arquivos dos
outros anos. Compressão zstd nível 3, `row_group_size` 122880.

**Regra do particionamento:** grão mais grosso primeiro, e só desça a mês onde
o volume justifica (`voto` e `despesa_parlamentar`). Particionar
`indicador_ente` por mês criaria milhares de arquivinhos de 20 KB — o pior
cenário possível para Parquet.

## Convenção obrigatória

Primeira coluna, sempre:

```
sk = md5(concat_ws('|', <campos de negócio da PK>))
```

Últimas quatro colunas, sempre nesta ordem:

| Coluna | Tipo | Papel |
|---|---|---|
| `_hash_registro` | VARCHAR(16) | md5 curto dos campos de negócio |
| `_fonte` | VARCHAR | `camara_lote`, `siconfi_dca`, `ibge_sidra`… |
| `_criado_em` | TIMESTAMPTZ | primeira vez que a linha entrou |
| `_atualizado_em` | TIMESTAMPTZ | último merge que a mudou de verdade |

Determinística e não sequencial é o ponto inteiro: reprocessar o mesmo dado
gera o mesmo `sk`, a deduplicação é natural e o pipeline é idempotente. Você
pode re-rodar qualquer coletor sem medo e sem lembrar do que já rodou.

## Chaves de negócio

| Tabela | PK de negócio | Partição | Grão |
|---|---|---|---|
| `dim_ente` | `cod_ibge` | — | país/UF/município |
| `dim_politico` | `fonte_origem` + `id_origem` | — | pessoa |
| `dim_partido` | `sigla` | — | partido |
| `dim_metrica` | `cod_metrica` | — | indicador |
| `dim_cargo` | `cod_cargo` | — | cargo |
| `indicador_ente` | `cod_ibge` + `cod_metrica` + `ano` | ano | métrica-ano-ente |
| `financas_ente` | `cod_ibge` + `ano` + `periodo` + `cod_conta` | ano, esfera | conta |
| `mandato` | `sk_politico` + `cod_cargo` + `cod_ue` + `ano_inicio` | ano_inicio | mandato |
| `dim_de_para_ente` | `fonte_origem` + `id_origem` | — | ponte fonte→IBGE |
| `proposicao` | `casa` + `id_proposicao` | ano | PL |
| `tramitacao` | `casa` + `id_proposicao` + `seq_tramitacao` | ano | etapa |
| `votacao` | `casa` + `id_votacao` | ano | sessão |
| `voto` | `casa` + `id_votacao` + `id_politico` | ano, mes | voto individual |
| `despesa_parlamentar` | `casa` + `id_documento` | ano, mes | nota fiscal |
| `emenda_parlamentar` | `ano` + `codigo_emenda` | ano | emenda |

## Sobre "não armazenar bruto"

Duas exceções deliberadas ao princípio de só guardar o processado:

**`voto` fica granular.** É literalmente o produto do painel — "quem votou a
favor e contra em todas as etapas". E é minúsculo: 513 deputados × ~1.500
votações/ano ≈ 770 mil linhas/ano, cerca de 4 MB em Parquet.

**`financas_ente` é agregado na ingestão.** Guarda despesa por função de
governo, não conta contábil folha a folha. Cai de ~50 milhões para ~150 mil
linhas por ano, sem responder uma pergunta a menos.

Estimativa do acervo completo com 10 anos: **2 a 5 GB**, dominado por
`despesa_parlamentar`.

## Três conceitos de data — não misture

| Coluna | O que é | Serve para |
|---|---|---|
| `data_referencia` | quando o fato aconteceu no mundo | **filtros do painel** |
| `ano` / `mes` | derivados de `data_referencia` | partição |
| `_criado_em` / `_atualizado_em` | quando o pipeline soube | auditoria |

`_atualizado_em` responde "esse número mudou desde a semana passada?". Nunca
use como filtro de usuário — o usuário quer a data da votação, não a data em
que você a baixou.

## O MERGE, passo a passo

```sql
-- 1. lê APENAS as partições tocadas pelo lote
CREATE TEMP VIEW atual AS
  SELECT * FROM read_parquet('dados/fato/voto/ano=2026/mes=08/part-000.parquet');

-- 2. mantém o antigo se inalterado, atualiza se o hash mudou, insere se novo
CREATE TEMP TABLE final AS
SELECT * FROM atual a
 WHERE NOT EXISTS (SELECT 1 FROM novo n WHERE n.sk = a.sk)
UNION ALL BY NAME
SELECT n.*,
       COALESCE(a._criado_em, now())                  AS _criado_em,
       CASE WHEN a.sk IS NULL
              OR a._hash_registro IS DISTINCT FROM n._hash_registro
            THEN now() ELSE a._atualizado_em END       AS _atualizado_em
  FROM novo n LEFT JOIN atual a USING (sk);

-- 3. grava em .tmp e faz rename atômico por cima
COPY (SELECT * FROM final ORDER BY sk) TO '....parquet.tmp' (FORMAT PARQUET, ...);
```

O rename atômico é o que garante que um processo morto no meio deixe a
partição íntegra, em vez de meio arquivo corrompido. Você não vai querer
depender de lembrar de conferir se o job terminou.

O `_hash_registro` é o que evita reescrever `_atualizado_em` numa linha que
não mudou. Sem ele, todo re-run marcaria tudo como alterado e o campo perderia
o sentido.

## Alternativa que vale reconsiderar

`deltalake` (Python) por cima do mesmo Parquet dá MERGE nativo, time travel e
transações ACID, eliminando a coreografia de rename — e o DuckDB lê Delta
direto. Custa uma dependência. Se o pipeline passar de 8 a 10 fontes, paga.
