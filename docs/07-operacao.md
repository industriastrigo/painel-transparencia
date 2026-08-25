# 07 — Operação e manutenção

## Pelo painel

A aba **Atualizar** tem as seis fontes em caixas de seleção e um botão. Marque
o que quer, clique em Atualizar e acompanhe o progresso e o log na própria
tela — sem console, sem `.bat`.

Câmara e Senado vêm marcados por padrão, que é a coleta do dia a dia.

## Chave do Portal da Transparência

As emendas parlamentares exigem uma chave gratuita da CGU. Na aba
**Atualizar** há um campo para colá-la: ele grava no `.env`, testa contra a
API e passa a valer na hora, sem reiniciar.

Aceita tanto a chave pura quanto o bloco que a CGU mostra na tela
(`[{"key":"chave-api-dados","value":"..."}]`). O texto de exemplo
(`chave_api`) é recusado com explicação — é o erro mais provável de colagem.

A chave fica só no `.env` da pasta, que está no `.gitignore`. O painel escuta
apenas em 127.0.0.1, então ela não sai da máquina.

## Rotina sugerida

| Quando | Comando |
|---|---|
| Diário, 06:00 | `python -m src.scripts.coletar camara senado` |
| Mensal, dia 5 | `python -m src.scripts.coletar siconfi portal_transparencia --ano <ano>` |
| Mensal, dia 6 | `python -m src.scripts.coletar siconfi --nivel municipio --ano <ano>` |
| Anual, agosto | `python -m src.scripts.coletar ibge` |
| Pós-eleição | `python -m src.scripts.coletar tse --anos <ano>` |

`AGENDAR ATUALIZACAO.bat` cria a tarefa diária no Windows (rode como
administrador). O agendamento é o ponto: coleta que depende de você lembrar de
rodar é coleta que para de acontecer.

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
| Mapa todo cinza | SICONFI não coletado, ou ano selecionado sem dado |
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
python -m pytest                     # 207 testes: núcleo, API, varredura, de-para, coleta, chave, CLI
node --test testes/teste_mapa.mjs    # 10 testes: projeção e cor
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
