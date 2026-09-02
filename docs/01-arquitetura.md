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
│ bruto/ a resposta INTEIRA, sem contrato (opcional)         │
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

## Decisão 2b — guardar a resposta inteira, ao lado do acervo típado

O `mesclar()` projeta a resposta num contrato de colunas declarado em
`esquema.py`. Isso dá tipo, chave, partição e idempotência — e descarta, no
ato, todo campo que o contrato não menciona.

Na maior parte dos projetos isso é irrelevante: é só coletar de novo. Aqui
não. O SICONFI e o SADIPEM publicam o limite de **uma requisição por segundo**,
então a série histórica dos 5.570 municípios é medida em horas de máquina
ligada. Descobrir em novembro que a resposta de agosto trazia o campo que
faltava significa passar mais uma madrugada coletando o que já esteve na
memória do processo.

`nucleo.bruto` grava cada resposta **verbatim**, antes de qualquer projeção, em
`dados/bruto/`. É um diário append-only: escreve, nunca reescreve, nunca relê
para gravar. Não é tabela do `esquema.py` de propósito — registrá-la lhe daria
justamente o contrato de colunas que ela existe para evitar.

O gancho fica em `rede.buscar`, o único ponto por onde os dez coletores falam
com a rede. Uma linha ali serve a todos eles, e nenhum coletor precisou mudar.

E o mesmo gancho serve na direção contrária: em modo **replay**, `rede.buscar`
responde pelo disco. Rodar um coletor inteiro em replay reprocessa as respostas
guardadas com o código de hoje — o campo que passou a ser lido entra no acervo
típado sem uma requisição sequer.

Três regras o mantêm honesto:

- **Arquivar nunca derruba a coleta.** Disco cheio, JSON estranho, arquivo
  travado: vira aviso no log e a coleta segue. Perder o arquivo custa uma
  recoleta; perder a coleta da madrugada custa a madrugada.
- **Teto de disco.** Ao bater `PAINEL_BRUTO_LIMITE_GB`, o arquivamento para
  sozinho, em silêncio, e a coleta continua.
- **O replay não inventa.** Requisição que não está no arquivo vai para a rede,
  como sempre. Devolver vazio viraria "a fonte não tem", que é uma afirmação
  sobre o mundo.

Desligado por padrão: a coleta do dia a dia não precisa dele.

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
               bruto (resposta verbatim) · tabela · valores · energia · segredos
  coletores/   um por fonte
  api/         vistas.py (views) + servidor.py (rotas)
  scripts/     instalar · coletar · painel · carga · verificar · bruto
publico/       index.html · painel.js · mapa.js · estilo.css
dados/         dim/ fato/ _ctl/ malhas/ bruto/   (fora do git)
docs/          esta documentação
testes/        pytest (Python) + node:test (JS)
logs/          um arquivo por dia               (fora do git)
```
