# 01 — Arquitetura

## As quatro camadas

```
┌─ coletores/ ──────────────────────────────────────────────┐
│ ibge · siconfi · camara · senado · tse · portal            │
│ 1 arquivo por fonte · idempotentes · rodáveis isolados     │
└───────────────────────────┬───────────────────────────────┘
                            │ mesclar()
┌─ dados/ ───────────────────▼──────────────────────────────┐
│ dim/   sem partição, sobrescrita total (tabelas pequenas)  │
│ fato/  Hive: ano=/mes=/esfera=                             │
│ _ctl/  marca-d'água por fonte                              │
│ malhas/ GeoJSON do IBGE                                    │
└───────────────────────────┬───────────────────────────────┘
                            │ views DuckDB
┌─ api/ ─────────────────────▼──────────────────────────────┐
│ FastAPI · só lê views · nunca chama fonte externa          │
└───────────────────────────┬───────────────────────────────┘
                            │ JSON
┌─ publico/ ─────────────────▼──────────────────────────────┐
│ HTML + SVG puro · sem framework · sem CDN · abre offline   │
└───────────────────────────────────────────────────────────┘
```

## Decisão 1 — não consumir API na renderização

Toda fonte externa é lida por um coletor, gravada em Parquet e só então
consultada. Isso compra três coisas:

- **O painel não cai quando a fonte cai.** Responde com o último dado, e a aba
  Fontes diz de quando ele é.
- **O número é reproduzível.** Dois usuários vendo o painel no mesmo dia veem
  o mesmo número, porque veem o mesmo arquivo.
- **Ninguém apanha do freio das fontes.** TSE e SICONFI bloqueiam IP em
  rajada. Um coletor com intervalo declarado resolve isso uma vez, no lugar
  certo, em vez de a cada clique do usuário.

## Decisão 2 — Parquet + DuckDB, sem processo de banco

O acervo é analítico e quase só de leitura. O DuckDB agrega 5.570 municípios ×
10 anos direto do disco em milissegundos, sem servidor rodando, sem porta
aberta, sem senha para gerenciar. O acervo completo cabe em 2 a 5 GB.

Postgres entraria se houvesse contas de usuário e escrita concorrente. Não há.

**A consequência que define tudo:** Parquet não faz UPDATE. Atualizar é
reescrever a partição inteira — logo, o particionamento não é só performance,
é a unidade de transação. Ver `02-modelo-de-dados.md`.

## Decisão 3 — a API só enxerga views

`src/api/vistas.py` cria uma view por tabela sobre o glob de Parquet, mais as
views derivadas (`vw_mapa`, `vw_placar_votacao`, …). Nenhuma rota conhece
caminho de arquivo.

Trocar o layout físico — particionar por mês, migrar para Delta Lake, mudar a
compressão — não toca em nenhuma rota.

Tabela ainda não coletada vira uma view **vazia porém tipada**, montada a
partir do contrato de colunas declarado em `esquema.py`. Por isso o painel
abre na primeira execução, antes de qualquer coleta, e mostra "sem dados" em
vez de estourar erro 500.

## Decisão 4 — SVG puro no front

Nenhuma biblioteca de mapa, nenhum CDN. A geometria vem do IBGE e é projetada
em Albers no navegador, em ~90 linhas de JavaScript. O painel abre offline,
não quebra quando um CDN muda de versão, e não carrega megabytes para desenhar
27 polígonos.

## Cadências

Não rode tudo no mesmo job — as fontes mudam em ritmos muito diferentes:

| Fonte | Cadência | Por quê |
|---|---|---|
| Câmara, Senado | diária | arquivos em lote atualizados todo dia |
| SICONFI | mensal (RREO) / anual (DCA) | prazos legais de publicação |
| Portal da Transparência | mensal | execução orçamentária |
| IBGE | anual | estimativas e PIB saem uma vez por ano |
| TSE | eleitoral | muda a cada dois anos |

## Estrutura de pastas

```
src/
  nucleo/      config · chaves · armazem · controle · rede · esquema · registro
  coletores/   um por fonte
  api/         vistas.py (views) + servidor.py (rotas)
  scripts/     instalar · coletar · painel
publico/       index.html · painel.js · mapa.js · estilo.css
dados/         dim/ fato/ _ctl/ malhas/     (fora do git)
docs/          esta documentação
testes/        pytest (Python) + node:test (JS)
logs/          um arquivo por dia               (fora do git)
```
