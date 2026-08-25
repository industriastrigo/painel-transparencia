# 09 — Roteiro

## Onde o projeto está

Pipeline, armazém, API e painel funcionam ponta a ponta. O que existe:

- Núcleo idempotente com merge por partição e rename atômico — testado
- Seis coletores escritos: IBGE, SICONFI, Câmara, Senado, TSE, CGU
- API com mapa, ranking, políticos, proposições, tramitações e voto nominal
- Painel com drill-down país → estado → município e ficha do ente
- De-para TSE → IBGE ligando "quem governa" a "quanto gasta"
- 230 testes (216 Python, 14 JavaScript)

O que **não** existe ainda está abaixo, em ordem de valor.

---

## Feito depois da primeira entrega

- **Varredura municipal do SICONFI** — paralela, com freio global e retomada
  ente a ente em `_ctl/coleta_ente`. 5.570 municípios em 15 a 25 minutos, e
  interromper no meio deixou de custar caro.
- **Porta do painel escolhida em execução** — o Windows reserva faixas via
  Hyper-V/WinNAT e recusava a 8000 com `[Errno 13]`.
- **`--situacao` e `--tudo` sozinhos** — o argparse validava o valor padrão de
  um `nargs="*"` contra os `choices` e morria com "invalid choice: []".
- **De-para TSE → IBGE** — `dim_de_para_ente`, quatro passos de casamento
  (exceção, exata, frouxa, aproximada) com ambiguidade virando pendência
  visível em vez de chute. Destravou a ficha do ente: prefeito, governador,
  presidente, despesa por função e indicadores numa chamada só. Ver
  `10-de-para.md`.
- **Botão Atualizar no painel** — caixas de seleção por fonte, coleta em
  segundo plano, progresso por etapa e log ao vivo. Uma tarefa por vez (409 na
  segunda), porque duas varreduras disputariam o mesmo freio de rede.
- **Quatro defeitos da primeira coleta real** — NaN de célula vazia quebrando
  proposições e votos (NaN é truthy, então `or ""` não protegia); 404 da cota
  parlamentar repetido quatro vezes com espera exponencial; URL da cota
  desatualizada; e o pior, erro capturado pelo coletor virando "concluído com
  0 falha(s)".
- **Ano natural por fonte** — a coleta diária da Câmara buscava o ano passado.
- **Segunda rodada de defeitos reais** (log de 24/08): o NaN voltava pelo
  `iterrows()` mesmo com o DataFrame limpo — a proteção migrou para
  `nucleo.valores`, no ponto de uso; `ideDocumento` sozinho descartava ~1.300
  notas por ano como duplicata; a variável 593 do agregado 5938 não existe e o
  SIDRA responde 500, gastando 36 requisições — agora os metadados são
  validados antes e o PIB per capita é **derivado** de PIB ÷ população; a
  varredura do SICONFI desiste quando os 200 primeiros entes vêm vazios (2026
  custou 14 minutos e 5.571 requisições), apagando as marcas para não
  bloquear uma tentativa futura; e o TSE avisa quando a eleição não foi
  apurada em vez de deixar dois "lote vazio" no log.

- **Filtro de situação nas proposições** — e o motivo de a coluna estar vazia:
  o lote da Câmara nomeia o campo `ultimoStatus_descricaoSituacao`, não
  `descricaoSituacao`. Junto vieram órgão atual, tramitação atual e regime.
- **"Falta configurar" deixou de ser "ok"** — o Portal da Transparência sem a
  chave da CGU aparecia como fonte concluída com sucesso.

- **Chave da CGU pelo painel** — campo que grava no `.env`, testa contra a API
  e aplica sem reiniciar. A chave nunca volta inteira numa resposta nem
  aparece no log; as sessões HTTP de todas as threads são invalidadas por
  contador de geração, senão salvar não teria efeito na coleta seguinte.

- **Terceiro relatório mentiroso** — "concluído com problema" numa coleta
  perfeita: o contador somava erros da API. Junto, dois defeitos vizinhos: o
  painel escondia justamente os erros que contava, e o teto de 200 páginas do
  Portal truncava as emendas em 3.000 linhas com cara de total.
- **Coluna nova sobre acervo antigo** — a view agora completa com NULL o que o
  contrato declara e o Parquet ainda não tem.

- **Aba Custo do Estado** — três medidas separadas de propósito: subsídio
  (norma), custo estimado (ocupantes × subsídio × 13,33, rotulado como conta)
  e despesa real por função (SICONFI). Valor transcrito e não conferido
  aparece com ⚠ e o link da norma.
- **Coletor Tesouro/SIC** — pergunta ao catálogo CKAN onde está o arquivo e
  detecta as colunas, em vez de cravar URL e adivinhar nomes.

- **Tipo divergente entre partições** — coluna toda nula virava `int32` e
  brigava com a partição preenchida. Corrigido na escrita (tipo declarado) e
  na leitura (`union_by_name`).

- **Auditoria externa de caixa-preta (24/08)** — 31 achados. Corrigidos os
  cinco críticos e os de maior risco: despesa inflada ~5× por somar função com
  subfunções; conexão DuckDB compartilhada devolvendo a resposta de outra
  requisição; "R$ 0" onde não há dado (`Number(null)` é 0); valores da CGU em
  formato brasileiro virando texto; `cargo_12` vazando na tela; resumo verde
  escondendo etapa parcial; log da coleta sumindo no F5; legenda de quantis
  se apresentando como mínimo e máximo; máscara da chave expondo início e fim.

- **Publicação no GitHub** — README com o propósito do projeto, licença MIT,
  CI rodando os 230 testes a cada push (e um job que recusa segredo
  versionado), `.bat` de um clique para publicar e para enviar alterações, e
  trava local que aborta o commit se `.env` ou `dados/` entrarem.

- **Arrecadação e transferências** — o DCA passou a trazer também o Anexo I-C
  (receitas). Com isso o painel responde "quanto entra" ao lado de "quanto
  sai", e a fatia da arrecadação que veio de transferência — o número que
  explica a dependência do FPM num município pequeno. Vale a mesma cautela
  hierárquica da despesa, testada com amostra de pai e filhas.
- **Mapa legível** — sigla nos estados, nome nos municípios (só onde couber,
  no centroide de área do maior anel), zoom com roda e arrasto, ampliação para
  a tela inteira e dica ao passar o mouse com população, arrecadação, despesa
  e transferências. Campo sem dado diz "não coletado", nunca R$ 0.

## Próximo passo — tramitação em massa

`coletar_tramitacoes()` hoje busca uma proposição por vez pela API. Para o
painel mostrar etapas de milhares de PLs, precisa de:

- carga em lote a partir do arquivo anual de tramitações da Câmara
- watermark por proposição, para o delta diário não reler tudo

---

## Fatia 2 — módulo de emendas

O coletor da CGU já traz `emenda_parlamentar`. Falta a leitura no painel:

- emendas por autor, cruzadas com `dim_politico`
- emendas por município de destino, no mapa
- separar **Transferências Especiais (Pix)** das demais — são as de menor
  rastreabilidade e por isso as mais relevantes num painel de transparência

---

## Fatia 4 — métricas de desenvolvimento

O painel hoje responde "quem gasta mais por habitante", não "quem é mais
desenvolvido" — que era a pergunta original. Faltam:

- IDHM (Atlas Brasil), PIB per capita já coletado mas não exposto no mapa
- proporção da despesa em saúde e educação, que `vw_financas_funcao` já
  calcula
- deflacionar por IPCA antes de comparar anos: em reais correntes, uma série
  de 10 anos mostra inflação, não decisão política

---

## Fatia 5 — perfil demográfico do poder

O TSE já traz gênero, cor/raça autodeclarada, grau de instrução e ocupação de
cada eleito. Cruzar com a PNAD Contínua do IBGE produz a comparação direta
entre a composição da Câmara e a da população.

É o tipo de número que só existe porque alguém juntou duas bases públicas — e
o mais forte que este painel pode entregar.

Cuidado obrigatório: são dados sensíveis. Mostrar agregado, com a fonte e o
ano visíveis, e sem construir perfil individual.

---

## Fatia 6 — comparação temporal

Hoje o painel mostra um ano por vez. Falta:

- série histórica por ente (o mesmo município ao longo de 10 anos)
- variação ano a ano no mapa (mapa divergente, com escala centrada em zero)

A tabela `indicador_ente` já é longa e suporta isso sem migração — foi
desenhada assim de propósito.

---

## Talvez, se o pipeline crescer

- **Delta Lake** por cima do Parquet: MERGE nativo, time travel e ACID,
  eliminando a coreografia de rename. O DuckDB lê Delta direto. Vale a partir
  de 8 a 10 fontes.
- **`mapshaper` no build** para simplificar geometria, se as malhas municipais
  pesarem no navegador.
- **Publicação estática**: o painel é HTML puro; com os JSONs pré-gerados ele
  vira um site estático hospedável em qualquer lugar, sem a API.

---

## Fora do escopo, conscientemente

- **Votação nominal estadual e municipal** — não existe padrão nacional
  (ver `08-armadilhas.md`)
- **Lobby e portas giratórias** — não há base de dados pública estruturada
- **Patrimônio real de políticos** — a lei permite declarar pelo valor de
  aquisição, então o dado disponível é estruturalmente subestimado
