# 07 — Operação e manutenção

## Pelo painel

A aba **Atualizar** lista as fontes em caixas de seleção. Marque o que quer,
clique em Atualizar e acompanhe o progresso e o log na própria tela — sem
console, sem `.bat`.

Câmara e Senado vêm marcados por padrão, que é a coleta do dia a dia.

### Cada fonte diz como ela atualiza

Debaixo de cada fonte a tela mostra quatro coisas, porque **"atualizar" não
significa o mesmo em duas fontes**:

| Campo | Responde |
|---|---|
| Cadência | de quanto em quanto tempo vale rodar |
| Recorte do ano | o que o campo Ano faz *nesta* fonte — ou que ela o ignora |
| Cada linha é | o grão do que entra no acervo |
| Costuma levar | quanto tempo esperar |

Mais o que precisa estar configurado antes (chave da CGU, liberação do
Tesouro) e a ressalva que importa — que a série de transferências é revisada,
que o TSE devolve vazio em ano sem eleição, que os votos da Câmara vêm dos
arquivos em lote e não da API.

Isso fica **sempre visível**, não atrás de um clique: é justamente a
informação que decide se vale marcar a caixa. Sem ela, marcar SICONFI e
Câmara juntas parece a mesma operação — e uma traz o dia de hoje enquanto a
outra depende de um exercício que só fecha meses depois.

O campo **Ano**, quando preenchido, força o mesmo ano em todas as fontes de
uma vez. Em branco, cada uma usa o padrão dela. As marcadas como "ignora o
campo Ano" não mudam de comportamento nos dois casos — e a tela diz quais
são, em vez de deixar você preencher achando que recorta.

## Chave do Portal da Transparência

As emendas parlamentares exigem uma chave gratuita da CGU. Na aba
**Atualizar** há um campo para colá-la: ele grava no `.env`, testa contra a
API e passa a valer na hora, sem reiniciar.

Aceita tanto a chave pura quanto o bloco que a CGU mostra na tela
(`[{"key":"chave-api-dados","value":"..."}]`). O texto de exemplo
(`chave_api`) é recusado com explicação — é o erro mais provável de colagem.

A chave fica só no `.env` da pasta, que está no `.gitignore`. O painel escuta
apenas em 127.0.0.1, então ela não sai da máquina.

## Antes de uma carga longa: ligue o arquivo bruto

Uma carga histórica é cara de repetir — o limite de uma requisição por segundo
faz dela horas de máquina ligada. E ela é exatamente o momento em que o
descarte silencioso dos campos não mapeados custa mais caro.

```bash
python -m src.scripts.carga --tudo --bruto
```

Cada resposta fica gravada inteira em `dados/bruto/`, antes de qualquer
contrato de colunas. Custa disco (alguns GB), não custa tempo. Depois:

```bash
python -m src.scripts.bruto                       # o que existe guardado
python -m src.scripts.bruto --campos siconfi rreo # TODOS os campos da fonte
python -m src.scripts.bruto --ver siconfi rreo    # uma resposta inteira
python -m src.scripts.bruto --reprocessar siconfi # sem tocar na rede
```

O `--reprocessar` roda o coletor lendo do disco. É como um campo que passou a
ser lido hoje entra no acervo típado a partir da resposta guardada ontem.

**Ligar o arquivo não pode custar a coleta**, e o desenho respeita isso: a
carga faz um ensaio de gravação antes de começar e, se ele falhar, segue **sem**
o arquivo em vez de arriscar a noite. Durante a coleta, qualquer falha de
arquivamento vira aviso no log. E há um teto (`PAINEL_BRUTO_LIMITE_GB`, padrão
40) para o disco não encher às 4h da manhã.

Pela tela: `CARGA HISTORICA.bat` pergunta se quer guardar, e
`CONSULTAR BRUTO.bat` consulta depois.

## Rotina sugerida

| Quando | Comando |
|---|---|
| Diário, 06:00 | `python -m src.scripts.coletar camara senado` |
| Mensal, dia 5 | `python -m src.scripts.coletar siconfi portal_transparencia --ano <ano>` |
| Mensal, dia 6 | `python -m src.scripts.coletar siconfi --nivel municipio --ano <ano>` (~3 h, retomável) |
| Bimestral, dia 5 | `python -m src.scripts.coletar siconfi_funcao` — saúde e educação, do RREO |
| Quadrimestral, dia 5 | `python -m src.scripts.coletar siconfi_rgf` — pessoal e dívida, do RGF |
| Anual, agosto | `python -m src.scripts.coletar ibge` |
| Pós-eleição | `python -m src.scripts.coletar tse --anos <ano>` |

`ATUALIZAR DADOS.bat` traz o mesmo menu com uma opção **0 — TUDO**, que roda
todas as fontes na ordem certa perguntando só o ano (e se deve incluir os
5.570 municípios, que têm cadência própria). Uma fonte que falhar não derruba
as outras.

As três entradas do SICONFI são o mesmo coletor pedindo relatórios
diferentes, e cada uma tem a própria retomada — marcar as três não refaz o
trabalho das outras. Elas aparecem separadas porque as cadências são
diferentes de verdade: o DCA só fecha o exercício anterior, enquanto o RREO e
o RGF saem *durante* o ano corrente. São as únicas fontes fiscais do ente que
não ficam um ano atrasadas.

**Deixe o ano em branco quando não quiser forçá-lo.** Cada fonte tem o ano
natural dela: Câmara e Senado o corrente, SICONFI o exercício anterior, TSE as
duas últimas eleições. Escrever um ano vale para todas de uma vez — útil para
recompor um exercício antigo, ruim para a coleta do dia a dia.

`AGENDAR ATUALIZACAO.bat` cria a tarefa diária no Windows (rode como
administrador). O agendamento é o ponto: coleta que depende de você lembrar de
rodar é coleta que para de acontecer.

## Carga histórica

```
CARGA HISTORICA.bat
python -m src.scripts.carga --tudo
```

Traz a série inteira de cada fonte, e é feita para rodar de madrugada. Três
propriedades sustentam isso:

**Retomável.** Cada recorte concluído vira uma marca em `_ctl/ingestao`. Se a
rede cair na terceira hora, a próxima execução começa da quarta. Rodar duas
noites seguidas compõe — não recomeça.

**Só `ok` é terminal.** Recorte vazio, parcial ou com erro é retentado na
execução seguinte. `sem_dado` pode virar dado quando o exercício for
publicado; `parcial` é incompleto por definição.

**A máquina não dorme.** Um coletor com freio de 1 req/s passa quase todo o
tempo esperando rede, e para o Windows isso é ociosidade — ele suspenderia a
máquina no meio. O processo pede para adiar a suspensão enquanto roda (a tela
pode apagar normalmente) e libera ao terminar.

### Quanto tempo leva, honestamente

O freio de 1 requisição por segundo é publicado pelas fontes, não é escolha
nossa. Ele é que manda:

| Fonte | Volume | Tempo |
|---|---|---|
| SADIPEM | 27 UFs | ~2 min |
| Transferências da União | 18 modalidades × 2 níveis × ano | ~40 min por década |
| Custos — cinco recortes | 5 consultas por ano | ~1 min por ano |
| Custos — `pessoal_ativo` | +100 mil linhas por mês | **~80 min por ano** |
| SICONFI municipal | 5.570 entes × 2 anexos | **~3 h por ano** |

A opção **1 (padrão)** leva de uma a duas horas e cabe numa noite.

A opção **2 (completa)**, com `pessoal_ativo` desde 2015, passa de quinze
horas — **não cabe numa noite**, e é exatamente para isso que a retomada
existe. Rode quantas noites forem necessárias; cada uma avança.

`pessoal_ativo` é caro porque vem quebrado por sexo, escolaridade, faixa
etária e área de atuação. O painel agrega tudo isso na leitura — o custo está
no tráfego, não no acervo.

### De manhã

O resumo final lista, por etapa, quantas linhas entraram e o que falhou; e
depois dele, os recortes que **não** concluíram, um por linha. Rodar de novo
tenta só esses.

## Quando um número não aparece na tela

```bash
python -m src.scripts.coletar --diagnostico
```

Responde as três perguntas, numa tela só:

1. **Onde** o projeto está lendo o acervo. `PAINEL_DADOS` pode estar no
   `.env`, numa variável de ambiente do Windows, ou em lugar nenhum — e o
   painel lê um lugar enquanto você olha outro. Mover a pasta `dados/` sem
   apontar o novo caminho deixa o projeto olhando para uma estrutura de pastas
   vazia que ele mesmo recria ao iniciar.
2. **O que tem dentro**: arquivos e tamanho por tabela.
3. **O que as views enxergam**: contagem por view e uma amostra de como a
   fonte nomeia a conta.

É o primeiro comando a rodar antes de suspeitar do código.

## Conferir o que a fonte devolveu, sem supor

```bash
python -m src.scripts.coletar --amostra 29 --ano 2025
```

Imprime as contas de um ente como elas estão no armazém: quais colunas
(estágios) vieram, se o `cod_conta` é hierárquico com pontos ou textual, e se
houve código repetido — que no merge significa **linha descartada**.

Vale rodar sempre que um total parecer estranho. As views derivam o nível da
conta do próprio código; se o código não for o que se supõe, a agregação erra
em silêncio, e foi assim que a despesa dos estados apareceu inflada em 5×.

## Conferir se está tudo em dia

```bash
python -m src.scripts.coletar --situacao
```

Ou a aba **Fontes** do painel. Uma fonte com `situacao=erro` ou `lido_em`
antigo é o sinal de que algo parou — não o painel estar vazio, que pode ser só
recorte sem dado.

## Depois de coletar com o painel aberto

As views são criadas quando a API sobe. Se a tabela ainda não existia, a view
nasceu vazia. Duas saídas:

```bash
curl -X POST http://127.0.0.1:8000/api/recarregar
```

ou simplesmente reabra o painel. (A API também se recupera sozinha: uma
consulta que falha por coluna inexistente recria as views e repete uma vez.)

## Backup

Basta copiar a pasta `dados/`. É o acervo inteiro — sem banco, sem dump, sem
serviço rodando. Uma cópia semanal para outro disco resolve.

`.env` tem a chave da CGU e **não** vai para o git.

## Reprocessar uma fonte

Porque as chaves são determinísticas, reprocessar é seguro: rode o coletor de
novo e o merge resolve. Nada duplica.

Para começar do zero numa tabela específica:

```python
from src.nucleo import armazem
armazem.remover("financas_ente")     # apaga só essa tabela
```

Para reprocessar um ano só, apague a partição correspondente:
`dados/fato/financas_ente/ano=2024/`.

## Espaço em disco

| Tabela | Ordem de grandeza (10 anos) |
|---|---|
| `despesa_parlamentar` | 1,5 – 3 GB |
| `voto` | ~40 MB |
| `financas_ente` | ~200 MB |
| `indicador_ente` | ~50 MB |
| demais | < 50 MB |

Total: **2 a 5 GB**. Para mover o acervo para outro disco, defina
`PAINEL_DADOS=D:\dados-painel` no `.env`.

## Logs

`logs/painel-AAAA-MM-DD.log`, um por dia, com o mesmo conteúdo do console.
Limpe periodicamente — nada os apaga sozinho.

## Sintomas e causas

| Sintoma | Causa provável |
|---|---|
| `ModuleNotFoundError: No module named 'uvicorn'` | a pasta do projeto foi renomeada ou movida e o `activate.bat` do `.venv` guardava o caminho antigo — corrigido: os `.bat` chamam `.venv\Scripts\python.exe` direto (ver `08`) |
| Clicar no estado não abre nada depois de aproximar | corrigido: o `setPointerCapture` do arrasto desviava o clique para o SVG (ver `08`) |
| `WinError 123` / pasta `ano=<NA>` | corrigido: linha sem valor de partição é descartada com erro claro, em vez de virar caminho inválido (ver `08`) |
| `WinError 5` no `.parquet.tmp` | arquivo travado — tire `dados/` do OneDrive, feche o painel durante a coleta, ou exclua a pasta do antivírus |
| Arrecadação vazia mesmo depois de coletar | corrigido: o `cod_conta` vem com prefixo (`RO1.0.0…`) e o cálculo de nível partia da string inteira |
| Mapa todo cinza | SICONFI não coletado, ou ano selecionado sem dado |
| Arrecadação "não coletada" na dica | o acervo é anterior ao Anexo I-C; recolete o SICONFI |
| Nome de município não aparece no mapa | ele é estreito demais para o nome caber na escala atual — aproxime, ou troque **Nomes** para "sempre" |
| Municípios cinzas ao entrar num estado | só as UFs foram coletadas; rode `--nivel municipio` |
| "0 de 27 UFs com dados" | a carga do SICONFI falhou; veja o log |
| Votos vazios numa votação recente | use o coletor em lote, não a API (ver `08`) |
| `Falha definitiva em ...` | fonte fora do ar ou IP freado; tente mais tarde |
| Emendas sempre zeradas | `CHAVE_PORTAL_TRANSPARENCIA` vazia no `.env` — a fonte aparece como ⚙ "falta configurar" |
| Coluna Situação toda em "—" | corrigido; recolete a Câmara para preencher |
| Município some do mapa | conferir o de-para de código IBGE (ver `08`) |
| `.parquet.tmp` sobrando | processo morreu no meio; pode apagar, a partição está íntegra |
| "concluído sem erros" mas faltou dado | corrigido: erro registrado pelo coletor agora conta como falha parcial |
| Cota parlamentar em 404 | corrigido: tenta `.csv.zip`, `.csv` e o espelho de dados abertos |
| "N sem dado publicado" para o ano corrente | normal: o exercício não fechou. A varredura desiste sozinha depois de 200 entes vazios |
| TSE com 0 eleitos | a eleição do ano pedido ainda não foi apurada; use 2022/2024 |
| `Binder Error: Referenced column ... not found` | corrigido: a view completa com NULL o que o acervo antigo não tem; recolete para preencher |
| Emendas paradas em 3.000 linhas | era o teto de páginas; agora avisa e a marca fica como `truncado` |
| Subsídio com ⚠ "a conferir" | valor transcrito por mim; confira a norma e troque `conferido` para `sim` em `referencias/subsidios.csv` |
| `Could not convert string ... to INT32` | partições com tipos diferentes; corrigido na leitura (`union_by_name`) e na escrita (tipo declarado). Recolete para curar o acervo |
| Despesa de um estado muito acima da LOA | corrigido: a view somava função + subfunções. Recarregue o painel |
| Filtro com opções `undefined` | corrigido: conexão compartilhada trocava respostas entre requisições |
| `[Errno 13]` ao subir o painel | porta reservada pelo Windows — ver abaixo |

## Porta recusada no Windows (`[Errno 13]`)

```
error while attempting to bind on address ('127.0.0.1', 8000):
foi feita uma tentativa de acesso a um soquete de uma maneira que é
proibida pelas permissões de acesso
```

Não é "porta ocupada", é "porta proibida". O Hyper-V / WinNAT — instalado junto
com Docker Desktop, WSL ou Área de Trabalho Remota — reserva faixas inteiras de
portas, e a 8000 cai numa delas com frequência. Para ver as faixas:

```cmd
netsh int ipv4 show excludedportrange protocol=tcp
```

`src/scripts/painel.py` já trata isso: testa a porta preferida, cai para
8080, 8123, 8765, 9000, 5500, 3333, 4321 e, em último caso, deixa o sistema
sortear uma livre. O endereço final sempre aparece no cabeçalho impresso ao
subir — use esse, não o 8000 de cabeça.

Para fixar uma porta:

```bash
python -m src.scripts.painel --porta 8123
```

ou defina `PAINEL_API_PORTA=8123` no `.env`.

Se quiser mesmo liberar a 8000 (requer administrador e reinício):

```cmd
net stop winnat
net start winnat
```

## Testes antes de mexer

```bash
python -m pytest                     # 360 testes: núcleo, API, varredura, de-para, coleta, chave, CLI
node --test testes/teste_mapa.mjs    # 38 testes: projeção, cor, contraste, escape
```

Cada arquivo de teste roda num armazém temporário próprio (`testes/conftest.py`).
Para confirmar que continuam isolados, rode-os fora de ordem:

```bash
python -m pytest testes/teste_cli.py testes/teste_de_para.py testes/teste_api.py
```

Se algum falhar só nessa ordem, é acoplamento entre testes — não um bug do
código.

Os testes do núcleo cobrem exatamente o que não pode quebrar em silêncio:
idempotência, detecção de alteração real, preservação de `_criado_em` e
partição Hive correta.
