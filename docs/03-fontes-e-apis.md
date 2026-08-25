# 03 — Fontes e APIs

O Brasil tem uma das melhores infraestruturas de dados abertos do mundo. O
truque é separar **o que é API pronta** do que é **ETL em cima de CSV gigante**.

## Escopo realista por camada

| Camada | Viabilidade |
|---|---|
| Federal — deputados, senadores, PLs, votos, gastos | API viva, praticamente tempo real |
| Estados — governadores, finanças, indicadores | dados existem, mas fragmentados |
| Municípios — prefeitos, finanças, PIB, população | cadastro e finanças sim; legislativo não |
| Deputados estaduais e vereadores — votos em PLs | **não existe padrão nacional** |

Esse último item é o ponto mais importante do projeto. Ver `08-armadilhas.md`.

---

## Geografia — a base de tudo

**IBGE Localidades**
`https://servicodados.ibge.gov.br/api/v1/localidades/estados`
`https://servicodados.ibge.gov.br/api/v1/localidades/municipios`

Cadastro canônico + código IBGE, que é a chave primária de junção do projeto
inteiro. Sem chave, sem limite prático.

**IBGE Malhas v3**
`.../api/v3/malhas/paises/BR?formato=application/vnd.geo+json&intrarregiao=UF`
`.../api/v3/malhas/estados/{UF}?formato=application/vnd.geo+json&intrarregiao=municipio`

GeoJSON pronto para o drill-down país → estado → município. Use
`qualidade=minima` — a diferença visual em tela é imperceptível e o arquivo cai
de dezenas de MB para centenas de KB.

## Indicadores socioeconômicos

**IBGE Agregados / SIDRA v3**
`.../api/v3/agregados/{id}/periodos/{p}/variaveis/{v}?localidades=N6[all]`

| Agregado | Variável | Conteúdo |
|---|---|---|
| 6579 | 9324 | população residente estimada |
| 5938 | 37 | PIB a preços correntes (municipal) |
| 5938 | 593 | PIB per capita |
| 4709 | 93 | população — Censo 2022 |

Níveis: `N1` Brasil, `N3` UFs, `N6` municípios.

**IPEAdata OData4** — `http://ipeadata.gov.br/api/odata4/` — séries históricas
longas, IDHM.

**Atlas Brasil (PNUD)** — IDHM municipal. Não tem API; download único. É dado
quase estático, então tudo bem.

## Finanças públicas — o "quem gasta mais"

**SICONFI — Tesouro Nacional**
`https://apidatalake.tesouro.gov.br/ords/siconfi/tt/`

REST público, sem autenticação, cobrindo as 27 UFs e mais de 5.500 municípios.
`id_ente` é o código IBGE — a junção sai de graça.

| Endpoint | O que traz |
|---|---|
| `/dca` | Declaração de Contas Anuais — despesa por função, comparável |
| `/rreo` | Relatório Resumido da Execução Orçamentária — bimestral |
| `/rgf` | Relatório de Gestão Fiscal — pessoal, dívida |

Freio recomendado: 0,5 s entre requisições.

**Portal da Transparência (CGU)**
`https://api.portaldatransparencia.gov.br/api-de-dados`

Gastos federais, emendas parlamentares, servidores. **Exige chave gratuita**
(cadastro com e-mail).

## Legislativo federal

**Câmara dos Deputados**

API: `https://dadosabertos.camara.leg.br/api/v2`
`/deputados` · `/proposicoes` · `/proposicoes/{id}/tramitacoes` ·
`/votacoes/{id}/votos` · `/deputados/{id}/despesas`

Arquivos em lote: `https://dadosabertos.camara.leg.br/arquivos/...`
`proposicoes-{ano}.csv` · `proposicoesAutores-{ano}.csv` ·
`votacoes-{ano}.csv` · `votacoesVotos-{ano}.csv`

Atualizados diariamente, em csv, xlsx, ods, json e xml. **A carga de votos vem
daqui, não da API** — ver `08-armadilhas.md`.

Cota parlamentar: `https://www.camara.leg.br/cotas/Ano-{ano}.csv`

**Senado Federal**
`https://legis.senado.leg.br/dadosabertos`
`/senador/lista/atual.json` · `/materia/votacoes/{codigo}.json`

JSON mais aninhado que o da Câmara; o coletor achata na mesma forma.

## Eleitos — do presidente ao vereador

**TSE — Portal de Dados Abertos**
`https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_{ano}.zip`

CSV em lote (latin-1, separador `;`), por UF. É a fonte definitiva de quem
ocupa cada cargo, com bens declarados, ocupação, grau de instrução, gênero e
autodeclaração de cor/raça.

**DivulgaCandContas** tem API REST, mas use-a **só** quando o dado não estiver
nos downloads, com intervalo entre requisições — ela bloqueia IP em rajada.

## Comportamento legislativo (fora do escopo automatizado)

Úteis para conferência manual, sem API pública estável:

- **Radar do Congresso** — comportamento em plenário
- **DIAP — "Radiografia do Novo Congresso"** — série histórica desde 1983,
  grau de renovação, frentes parlamentares
- **REDEM** — repositório acadêmico consolidando 14 eleições (1998–2024)
- **Transparência Brasil** e **Contas Abertas** — escrutínio de emendas

## Zonas de opacidade — o que nenhuma API entrega

Vale ter isso escrito, porque é limite do dado, não do código:

- **Declaração de bens pelo valor histórico de aquisição**, não de mercado.
  Distorção contábil legalizada que encobre o patrimônio real.
- **Lobby não regulamentado.** Sem base de dados de quem influencia o quê.
- **Emendas Pix** executadas sem plano de trabalho — não há como rastrear a
  conversão do recurso em benefício.
- **LGPD invocada contra a LAI** para negar beneficiário final de repasses.
