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
| `/dca` | Declaração de Contas Anuais — o anexo escolhe o assunto |
| `/rreo` | Relatório Resumido da Execução Orçamentária — bimestral |
| `/rgf` | Relatório de Gestão Fiscal — pessoal, dívida |

Quatro relatórios são coletados, e o parâmetro `no_anexo` é o que os separa:

| Endpoint | `no_anexo` | Conteúdo | Coluna usada | Tabela |
|---|---|---|---|---|
| `/dca` | `DCA-Anexo I-D` | despesa por NATUREZA (pessoal, custeio, investimento) | `Despesas Empenhadas` | `financas_ente` |
| `/dca` | `DCA-Anexo I-C` | receitas orçamentárias | `Receitas Brutas Realizadas` | `financas_ente` |
| `/rreo` | `RREO-Anexo 02` | despesa por FUNÇÃO de governo (saúde, educação) | `Despesas Empenhadas` | `despesa_funcao` |
| `/rgf` | `RGF-Anexo 01` · `RGF-Anexo 02` | pessoal sobre a RCL, limites da LRF, dívida | — | `indicador_fiscal` |

**O nome do Anexo I-D engana.** Ele diz "despesa por função" no título mas
traz natureza da despesa. A despesa por função de verdade só existe no RREO,
e por isso vai para tabela SEPARADA: são dois recortes do mesmo dinheiro, e
somar os dois dá o dobro do real.

**O RREO Anexo 02 não se parece com o DCA.** Mesma API, resposta de cara
igual, regras diferentes — ver armadilha 2ag:

- `in_periodicidade=B` é **obrigatório**; sem ele a resposta vem vazia.
- A coluna é `DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)`, em caixa alta, e existe
  também uma `NO BIMESTRE` que é outra coisa (os dois meses, não o acumulado).
- O `cod_conta` é `RREO2TotalDespesas` em **todas** as linhas. Não há código de
  conta nem hierarquia embutida: função, subfunção e total têm a mesma string.
  O nível vem de casar o texto de `conta` contra as 28 funções da **Portaria
  MOG nº 42/1999**.

**O RGF identifica a célula por linha E coluna.** `DespesaComPessoalTotal`
aparece na coluna `Valor` (R$) e na `% sobre a RCL Ajustada` (o percentual da
LRF) — são dois números diferentes com o mesmo `cod_conta`. No Anexo 02 as
colunas são os quadrimestres e o saldo do exercício anterior. Ver armadilha
2ai. O coletor grava o `cod_conta` verbatim e deriva a medida da coluna.

**Período.** O DCA fala de exercício fechado; o RREO e o RGF saem *durante* o
exercício. Pedir o 6º bimestre de um ano em curso devolve vazio, que o painel
leria como "o ente não entregou" — quando o prazo nem venceu. Por isso
`siconfi.periodo_publicado(ano, passo)` calcula o último período com prazo
vencido (a LRF dá 30 dias após o fim de cada período) e é ele o padrão. E os
dois relatórios são **acumulados no exercício**: o 6º bimestre já contém o
1º, então as views usam `MAX(periodo)` e nunca somam os períodos.

A coluna importa tanto quanto o anexo: cada linha vem repetida por estágio
(empenhada, liquidada, paga) e misturar dois estágios soma o mesmo real duas
vezes. Empenhada é a comparável entre entes e anos.

As contas dos dois anexos são **hierárquicas** — ver a armadilha 2j.

**Limite publicado: uma requisição por segundo**, e a documentação diz isso na
primeira tela. É piso no projeto (`config.INTERVALO_REQUISICOES`), não padrão
— ver armadilha 2r. Com os dois anexos, a varredura dos 5.570 municípios leva
cerca de **3 horas** na primeira vez; é retomável, então interromper não custa
o que já foi feito.

Outros endpoints que a documentação expõe e o projeto ainda não usa:

| Endpoint | O que traz | Situação |
|---|---|---|
| `/extrato_entregas` | se o ente entregou o relatório naquele exercício | **usado**, mas só na linha de comando — `coletar --explicar-cinza ANO` |
| `/entes` | cadastro com `cod_ibge`, população, CNPJ, capital | não usado: o cadastro do IBGE já é a base, e uma segunda verdade sobre o mesmo ente convida a divergência |
| `/msc_*` | Matriz de Saldos Contábeis, conta a conta | não usado: granularidade muito acima do que o painel pergunta |

O `/extrato_entregas` fica fora da API do painel de propósito. Nenhuma rota
HTTP chama fonte externa em tempo de renderização (`docs/01-arquitetura.md`),
e responder "por que este ente está cinza" exige perguntar ao SICONFI na
hora. Então ele mora no CLI:

```bash
python -m src.scripts.coletar --explicar-cinza 2024
```

A resposta separa três coisas que o mapa cinza confundia numa só: o ente
**não entregou** o relatório, o ente **entregou e não coletamos**, ou o
**prazo ainda não venceu**.

**Atenção ao endereço.** O Swagger atual documenta
`apidatalake.tesouro.gov.br/ords/**cdwhprd**/siconfi/tt`. O projeto usa o
caminho sem `cdwhprd`, que continua respondendo e é com o qual todo o acervo
foi coletado. `PAINEL_SICONFI` no `.env` troca, para testar o novo sem editar
código.

**Transferências Constitucionais — Tesouro Nacional (API Aria)**
`https://apiapex.tesouro.gov.br/aria/v1/transferencias_constitucionais`

FPM, FPE, FUNDEB, Lei Kandir, ITR, CIDE-Combustíveis, IOF-Ouro,
IPI-Exportação, royalties (ANP, FEP, PEA, Itaipu, CFH, CFEM), AFM/AFE,
Cessão Onerosa. Mensal e decendial, em R$ 1,00, de 1997 em diante, cobrindo
governos estaduais e municipais. O campo `co_ibge` casa direto com
`dim_ente` — sem de-para.

| Endpoint | O que traz |
|---|---|
| `/custom/transferencias` | catálogo das modalidades: código e nome. **Ponto de partida** — é esse código que alimenta as rotas de valor |
| `/custom/estados` · `/custom/municipios` | cadastro dos entes |
| `/custom/por_estados` | valores consolidados por UF |
| `/custom/por_estado_municipio` | valores consolidados por município |
| `…_detalhe` | as mesmas consultas separadas por decêndio |

**Exige liberação**: "Para solicitar acesso, entrar em contato com
desenvolvimento@tesouro.gov.br". Sem acesso, a fonte aparece no painel como
⚙ "falta configurar", com o e-mail na tela — nunca como erro nem como ok.

A série é **revisada**: os valores podem retroceder até o início do exercício
em curso. Recoletar é rotina, e por isso a chave primária inclui o mês —
revisão substitui, não soma.

**SADIPEM — operações de crédito**
`https://apidatalake.tesouro.gov.br/ords/cdwhprd/sadipem/tt`

Sistema de Análise da Dívida Pública, Operações de Crédito e Garantias.
Público, sem chave, licença Apache 2.0. **Limite explícito de 1 requisição
por segundo** — o freio do projeto respeita isso.

| Endpoint | O que traz |
|---|---|
| `/pvl` | Pedido de Verificação de Limites: interessado, credor, finalidade, valor, status. Filtros `uf`, `tipo_interessado`, `id_ente` |
| `/opc-cronograma-pagamentos` · `/opc-cronograma-liberacoes` | amortização, encargos e liberações por ano, de um pleito |
| `/opc-taxa-cambio` | taxas usadas no cronograma |
| `/res-cronograma-pagamentos` · `/res-cdp` | visão resumo do pleito |
| `/opnc-pvl-tramitacao-deferido` | outros pleitos do ente ainda não contratados |

Paginação de 5.000 itens, no padrão ORDS (`items` + `hasMore` + `offset`).

O coletor busca **por UF**, não por ente: 27 requisições em vez de 5.570, que
a 1/s seriam uma hora e meia para o mesmo dado. Os endpoints de detalhe são
por `id_pleito` — uma requisição cada — e por isso ficam de fora da coleta em
massa.

`cod_ibge` casa com `dim_ente`. Duas armadilhas na leitura: **PVL não é
dívida** (armadilha 2o) e o mesmo registro mistura data de dois e de quatro
dígitos no ano.

**Custos do Governo Federal — Tesouro Nacional**
`https://apidatalake.tesouro.gov.br/ords/cdwhprd/custos/tt`

Seis recortes de custo apurado, mensais, desde 2015. Público, sem chave.
**1 requisição por segundo**, 250 itens por página, envelope ORDS.

| Endpoint | O que traz |
|---|---|
| `/pessoal_ativo` | rendimento dos servidores da força de trabalho efetiva |
| `/pessoal_inativo` | aposentados do órgão |
| `/pensionistas` | pensões |
| `/depreciacao` | depreciação, amortização e exaustão |
| `/transferencias` | modalidades de aplicação indireta |
| `/demais` | os demais itens, do registro contábil no SIAFI |

Filtros: `ano`, `mes`, `natureza_juridica` e `organizacao_n1/n2/n3` (SIORG).

**Substituiu a raspagem de CSV do CKAN.** Três dos seis conjuntos pararam de
abrir quando o arquivo mudou de formato, e o coletor só sabia dizer "não
consegui ler como tabela". A API entrega o mesmo dado sem download, sem
separador para adivinhar e sem URL que muda de lugar.

**Custo não é despesa orçamentária.** A despesa empenhada do SICONFI mede o
compromisso assumido; o custo mede o consumo do período, por competência, com
provisões e sem adiantamentos. Um órgão pode empenhar em dezembro um gasto
cujo custo é do ano seguinte. E a granularidade é por **órgão**, nunca por
cargo.

**Teto de gastos — `.../ords/cdwhprd/teto_gastos/cesef/baseclassificada`**
Um endpoint só, com `Ano` obrigatório e `Mes_Inicial`/`Mes_Final` opcionais.
Devolve **CSV por padrão**, não JSON. Ainda não coletado: falta ver que
colunas traz. Quando entrar, entra como medida própria — teto, orçamento
autorizado e despesa executada são três números diferentes que todo mundo
chama de "gasto", e somá-los ou compará-los sem dizer qual é qual produz
manchete errada com número certo.

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
