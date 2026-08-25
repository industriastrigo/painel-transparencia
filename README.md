# Painel da Transparência

**Dar à população clareza sobre o que os poderes fazem com o dinheiro
público — com número que se pode conferir na fonte.**

O Brasil publica quase tudo. Orçamento, votação nominal, cota parlamentar,
emendas, folha de pagamento: está lá, em dezenas de portais, formatos e
cadências diferentes. Só que estar publicado não é a mesma coisa que estar
claro. Um cidadão que queira saber quanto o seu município gasta em saúde, quem
é o deputado que votou contra determinado projeto ou quanto custa a máquina do
Estado precisa hoje de tempo, prática e paciência que ninguém tem.

Este projeto junta essas fontes num lugar só e responde em linguagem direta:

- **Quem governa** cada município, estado e o país
- **Quanto cada ente arrecada e gasta**, e em quê
- **Quem votou a favor e contra**, nominalmente, em cada projeto de lei
- **Quanto custa cada função do Estado** — e a diferença entre o salário de um
  cargo e o que a função realmente consome dos cofres

Roda na sua máquina. Sem servidor, sem conta, sem nuvem.

---

## O compromisso com o número

Um painel de transparência vive de ser conferível. Por isso três regras
atravessam o projeto inteiro:

**Número que não veio da fonte não aparece.** Ente sem dado fica cinza, nunca
zero. Zero é uma afirmação sobre o mundo; ausência é uma afirmação sobre o
acervo. Trocar um pelo outro produz mapas convincentes e errados.

**Toda tela diz de onde o número veio e de quando ele é.** A aba Fontes mostra
linha a linha o que entrou, quando, e o que falhou. Valor transcrito de norma
aparece com a norma ao lado e um aviso enquanto não for conferido.

**O que não dá para saber, o painel diz que não sabe.** Votação nominal
estruturada só existe no Congresso Nacional — são 27 assembleias e 5.570
câmaras municipais sem padrão nacional. O painel afirma isso na tela em vez de
fingir cobertura.

`docs/08-armadilhas.md` documenta cada erro já cometido aqui, com a causa e o
conserto. Vários deles produziram números que *pareciam* certos — o mais grave
inflou a despesa dos estados em 5×, e só foi pego quando alguém comparou com a
lei orçamentária.

---

## Instalação em dois cliques

1. `INSTALAR.bat` — cria o ambiente, instala dependências e faz a primeira carga
2. `ABRIR PAINEL.bat` — sobe a API e abre o navegador

Requisito: Python 3.10 ou superior no PATH.

Sem Windows:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.scripts.instalar --carga
python -m src.scripts.painel
```

---

## O que ele faz

| Aba | Conteúdo |
|---|---|
| **Mapa** | Brasil → estado → município, colorido por despesa per capita, despesa total ou população. Clique num estado e o mapa troca para os municípios dele; clique num município e abre a ficha — quem governa, em que gasta, indicadores. |
| **Políticos** | Quantos existem e quem são, do presidente ao vereador, por UF, cargo e partido. |
| **Projetos de lei** | Proposição, autor, ementa, todas as etapas de tramitação e, em cada votação, quem votou a favor e contra — nominalmente. Filtros por situação, tipo, texto e período. |
| **Fontes** | Quando cada fonte foi lida pela última vez, quantas linhas trouxe e o que falhou. |
| **Custo do Estado** | Subsídio por cargo com a norma ao lado, custo estimado, despesa real por função e total. Valor não conferido aparece marcado. |
| **Atualizar** | Marque as fontes que quer e clique em Atualizar. Progresso e log ao vivo, sem abrir console. É onde também se cola a chave gratuita da CGU. |

---

## De onde vêm os dados

Todas as fontes são oficiais e abertas:

| Camada | Fonte |
|---|---|
| Geografia, população e PIB | IBGE — Localidades, Malhas v3 e Agregados/SIDRA |
| Finanças de estados e municípios | SICONFI — Tesouro Nacional |
| Custo apurado do governo federal | Tesouro Transparente — SIC |
| Deputados, projetos, votos e cota | Câmara dos Deputados — dados abertos |
| Senadores e votações | Senado Federal — dados abertos |
| Eleitos, do presidente ao vereador | TSE — dados abertos |
| Emendas parlamentares | Portal da Transparência — CGU |
| Subsídios por cargo | normas, transcritas em `referencias/subsidios.csv` |

---

## Como os dados chegam aqui

```
coletores/   1 por fonte, idempotentes
    ↓
dados/       Parquet particionado (Hive) + DuckDB como engine
    ↓
api/         FastAPI — só lê views, nunca chama API externa na renderização
    ↓
publico/     HTML + SVG puro, sem framework, sem CDN
```

Nenhuma rota do painel chama fonte externa em tempo de renderização. Se o TSE
ou a Câmara caírem, o painel continua respondendo com o último dado coletado —
e a aba Fontes mostra a data, para você saber o quanto ele está desatualizado.

### Por que Parquet e não um banco

O acervo é analítico e quase só de leitura: agregar 5.570 municípios × 10 anos
× N indicadores é trivial para o DuckDB lendo Parquet direto do disco, sem
processo de banco rodando. O acervo completo com 10 anos fica entre 2 e 5 GB.

A consequência que define o desenho inteiro: **Parquet não faz UPDATE**.
Atualizar significa reescrever a partição. Por isso a partição é a unidade de
transação, e o merge escreve num arquivo temporário antes do rename atômico —
se o processo morrer no meio, a partição continua íntegra.

### Idempotência

A chave primária `sk` é o md5 dos campos de negócio, não um sequencial.
Reprocessar o mesmo dado gera a mesma chave, então **qualquer coletor pode ser
re-rodado a qualquer momento sem duplicar nada e sem você precisar lembrar o
que já rodou**. O `_hash_registro` separa "linha que voltou igual" de "linha
que mudou de verdade", e só a segunda tem o `_atualizado_em` reescrito.

Toda tabela termina com as mesmas quatro colunas:

| Coluna | Papel |
|---|---|
| `_hash_registro` | hash do conteúdo de negócio — detecta alteração real |
| `_fonte` | qual coletor escreveu (`camara_lote`, `siconfi_dca`, …) |
| `_criado_em` | primeira vez que a linha entrou |
| `_atualizado_em` | último merge que efetivamente a mudou |

---

## Uso diário

Pelo painel: aba **Atualizar**, marque as fontes, clique no botão.

Pela linha de comando:

```bash
python -m src.scripts.coletar --situacao          # o que já foi lido, e quando
python -m src.scripts.coletar camara senado       # diária
python -m src.scripts.coletar siconfi --ano 2024  # 27 UFs, ~1 min
python -m src.scripts.coletar ibge                # anual
python -m src.scripts.coletar tse --anos 2022 2024  # a cada eleição
python -m src.scripts.coletar --pendencias        # cidades que não casaram

# 5.570 municípios: 15 a 25 min na primeira vez, retomável a qualquer momento
python -m src.scripts.coletar siconfi --nivel municipio --ano 2024
```

Cadências diferentes, jobs diferentes: não rode tudo no mesmo agendamento.

---

## Publicar no GitHub

```
CONFIGURAR GITHUB.bat     uma vez, na primeira publicação
SALVAR NO GITHUB.bat      a cada alteração que você quiser enviar
AGENDAR ENVIO.bat         opcional: envia sozinho todo dia às 19h
```

Passo a passo completo em `docs/11-github.md`. O `.env` (que guarda a chave da
CGU) e a pasta `dados/` **nunca** vão para o repositório — e há uma trava que
recusa o commit se isso for tentado.

---

## Testes

```bash
python -m pytest          # 207 testes
node --test testes/teste_mapa.mjs   # 10 testes
```

---

## Documentação

| Arquivo | Assunto |
|---|---|
| `docs/00-INSTALACAO-RAPIDA.md` | do zero ao painel aberto |
| `docs/01-arquitetura.md` | as quatro camadas e por quê |
| `docs/02-modelo-de-dados.md` | tabelas, chaves, partições |
| `docs/03-fontes-e-apis.md` | endpoint de cada fonte oficial |
| `docs/04-coletores.md` | como escrever um coletor novo |
| `docs/05-api.md` | rotas HTTP |
| `docs/06-painel-web.md` | mapa, projeção, cores |
| `docs/07-operacao.md` | rotina, backup, reprocessamento |
| `docs/08-armadilhas.md` | o que vai te custar dias se ignorar |
| `docs/09-roteiro.md` | o que vem depois |
| `docs/10-de-para.md` | como TSE e IBGE são conciliados |
| `docs/11-github.md` | publicar e manter o repositório |

---

## Licença

MIT — ver `LICENSE`. Dado público analisado com código aberto: qualquer pessoa
pode auditar como cada número desta tela foi produzido.

---

Indústrias Trigo · dados públicos, código próprio.
