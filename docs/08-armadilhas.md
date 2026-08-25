# 08 — Armadilhas

O que vai custar dias se for ignorado.

---

## 1. Votos da Câmara pela API vêm vazios

`GET /votacoes/{id}/votos` retorna `[]` para votações posteriores a maio/2024,
enquanto as anteriores funcionam normalmente. Quem modelar em cima da API vai
descobrir isso tarde — e vai descobrir como "o painel não mostra votação
nenhuma deste ano".

**Solução adotada:** carga histórica **e** delta pelos arquivos em lote
(`dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{ano}.csv`),
atualizados diariamente. A função `votos_por_api()` existe como plano B e
registra aviso quando vem vazia.

Valide você mesmo antes de mudar isso.

---

## 2. Chave de junção entre TSE, SICONFI e IBGE

Os três usam identificadores diferentes para município. O TSE tem código
próprio de unidade eleitoral; o SICONFI usa código IBGE; o IBGE é a referência.

**Adote código IBGE como identificador único de ente em absolutamente tudo** e
construa a tabela de-para **cedo**. Descobrir isso depois de ter cinco tabelas
carregadas significa reprocessar todas.

**Resolvido** em `src/coletores/de_para.py` — ver `10-de-para.md`. `mandato`
guarda `cod_ue` (o que a fonte dá) na chave primária e `cod_ibge` (o que o
de-para resolveu) como coluna anulável. O que não casa vira pendência visível
em `--pendencias`, nunca um chute.

---

## 2b. Limpar o DataFrame não protege quem lê com `iterrows()`

Célula vazia de CSV vira `float('nan')`, e **`NaN` é truthy** — então
`(linha.get("ementa") or "")` devolve o NaN, e o `[:2000]` seguinte estoura
com `'float' object is not subscriptable`.

A primeira correção trocou NaN por None no DataFrame inteiro. O teste
confirmava que funcionava, e mesmo assim o coletor continuou quebrando em
produção. O motivo:

```python
limpo.iloc[1]["ementa"]              # None   ✅  ← o que o teste olhava
next(limpo.iterrows())[1].get(...)   # nan    ❌  ← o que o coletor usa
```

`iterrows()` reconstrói cada linha como uma Series tipada, e o pandas
converte aquele None de volta para NaN.

**Proteja no ponto de USO**, com `nucleo.valores.texto()` / `opcional()` /
`numero()` — é o único lugar que não depende de como o pandas resolveu tipar
a linha. E escreva o teste passando pelo mesmo caminho que o código usa: um
teste que acessa o dado por outra via pode passar enquanto o bug continua
vivo.

---

## 2c. Chave curta que descarta dado em silêncio

`ideDocumento` da cota parlamentar não é único: reembolso parcelado repete o
mesmo documento em várias linhas. Com a PK só em `(casa, id_documento)`, o
merge avisava "1.307 linhas duplicadas no lote — mantendo a última" e seguia.

Não eram duplicatas: eram 1.307 notas fiscais jogadas fora por ano. A chave
passou a incluir `num_parcela` e `num_ressarcimento`.

O aviso de duplicata do merge **não é ruído**. Toda vez que ele aparecer,
confira se a chave está descrevendo o grão real do dado.

---

## 2d. O mesmo campo com dois nomes

A API v2 da Câmara chama de `descricaoSituacao`; o arquivo em lote chama de
`ultimoStatus_descricaoSituacao`. O coletor lia só o nome da API, então a
coluna Situação do painel ficou **inteira em "—"**, sem um erro sequer no log.

Falha silenciosa é a pior espécie: nada quebra, e o campo simplesmente não
existe. Use `camara.primeiro(linha, "nome_no_lote", "nome_na_api")` sempre que
o mesmo dado puder vir das duas origens — e desconfie de uma coluna 100% vazia
antes de culpar a fonte.

---

## 2e. "Falta configurar" não é sucesso nem erro

O coletor de emendas sem a chave da CGU registrava um aviso, devolvia zero, e
o painel mostrava a fonte como **ok** — com um tique verde e nenhuma linha
coletada.

Não é erro (nada falhou) e não é sucesso (nada entrou). É um terceiro estado.
`nucleo.erros.ConfiguracaoAusente` carrega junto o *como resolver*, e a tela
mostra ⚙ "falta configurar" com a instrução, em vez de esconder a pendência
atrás de um tique.

---

## 2f. Coluna nova sobre acervo antigo

Acrescentar um campo ao `SELECT` da API derruba a rota inteira para quem
coletou antes: `Binder Error: Referenced column "tramitacao_atual" not found`.
O Parquet de ontem não conhece a coluna de hoje.

A view é o lugar de honrar o contrato: `vistas._completar_colunas()` compara
o que existe no Parquet com o que `esquema.py` declara e expõe o que falta
como `CAST(NULL AS ...)`. Quem coletou antes vê o campo vazio e recoleta
quando quiser — em vez de ficar com o painel fora do ar até reprocessar tudo.

---

## 2g. Contar erro que não é seu

O contador de erros da coleta ficava pendurado no logger **raiz**, então
somava qualquer ERROR do processo durante a janela: uma rota da API, o
uvicorn, o httpx. E o painel consulta a API a cada dois segundos enquanto
coleta.

Resultado: uma coleta que gravou 3.000 linhas sem um erro sequer foi
reportada como "concluído com problema". Agora o contador só aceita
`coletores.*` e `nucleo.*`.

## 2h. Contar sem mostrar

Pior que o item acima: o espelho de log do painel **escondia** os registros
de `api.*`, mas o contador os **somava**. Deu um "problema" sem uma única
linha de erro visível na tela — impossível de diagnosticar de dentro do
painel.

Filtre ruído de ROTINA (INFO), nunca aviso e erro. Se algo conta, aparece.

---

## 2i. Coluna toda nula ganha o tipo errado

Se numa partição uma coluna não tem **nenhum** valor, o pandas não tem como
saber que era texto e o Parquet a grava como `int32`. Quando outra partição
traz a mesma coluna preenchida, ler as duas juntas estoura:

    Could not convert string 'Aguardando Providências Internas' to INT32

Aconteceu com `situacao`: coletada nula por semanas (nome de coluna errado,
item 2d), virou `int32` em 2024 e brigou com 2026 assim que passou a vir
preenchida. Derrubou `/api/proposicoes` e o filtro de situação inteiros.

Dois consertos, em camadas diferentes:

- **Na escrita**, `armazem.tipar()` força o tipo declarado em `esquema.py`.
  O tipo já estava no contrato; faltava usá-lo na gravação. Partição nova
  nasce compatível com as antigas por construção.
- **Na leitura**, `union_by_name=1` combina o esquema de todos os arquivos em
  vez de tirá-lo do primeiro. É o que faz um acervo gravado por versões
  diferentes do projeto continuar abrindo — sem reprocessar nada.

Recoletar cura a partição: o merge reescreve com o tipo certo.

---

## 2j. Somar contas hierárquicas

O DCA traz a função (`10`) e suas subfunções (`10.301`, `10.302`) como linhas
**irmãs** no mesmo demonstrativo. Somar todas conta o mesmo gasto duas ou três
vezes.

Inflou a despesa dos estados em ~5×: o Acre aparecia com R$ 66,9 bilhões
contra R$ 12,15 bilhões da LOA de 2025. E o pior é que o número *parecia* bem
formado — a população batia com o IBGE e o per capita era aritmeticamente
coerente, então nada na tela denunciava o erro.

Sinal para desconfiar: **~103 linhas por ente** onde existem ~28 funções.

`vw_financas_funcao` filtra `nivel_conta = 1`, com o nível derivado do próprio
`cod_conta` na view — não numa coluna nova — para o acervo já coletado ser
corrigido na leitura, sem recoleta.

**Nunca some um demonstrativo contábil sem antes olhar se as contas têm
níveis.** E teste a agregação contra uma amostra hierárquica: com contas
planas, somar tudo dá certo por acidente, e foi assim que meus testes
passaram.

---

## 2k. Conexão DuckDB compartilhada entre requisições

`execute()` e `.df()` são duas etapas, e a conexão guarda o resultado
corrente. Com a conexão compartilhada — e o FastAPI roda rotas síncronas num
pool de threads —, a requisição A pode buscar o resultado da requisição B, ou
receber `None`.

Sintoma observado: o filtro de Situação com 90 opções `undefined`, cujas
contagens batiam uma a uma com as de `/api/proposicoes/tipos`. Intermitente,
some ao recarregar — o pior perfil de defeito que existe.

Use `con.cursor()` por consulta: conexão-filha com estado próprio, enxergando
as mesmas views.

**E cuidado com o teste.** O meu verificava que consultas simultâneas não
levantavam EXCEÇÃO. Não levantavam — devolviam a resposta errada. Teste o
resultado, não a ausência de erro.

---

## 3. Prometer votação estadual e municipal

Votação nominal estruturada só existe no Congresso Nacional. São 27 assembleias
legislativas e 5.570 câmaras municipais, cada uma com seu site, seu formato e
sua política de publicação. Não há padrão nacional, e nenhum raspador sobrevive
a 5.597 layouts diferentes.

**Trate estadual e municipal como cadastro + finanças, não como votações.** O
painel diz isso na tela, na aba Políticos — porque prometer "todos os
políticos, todos os votos" na v1 é o caminho conhecido para o projeto morrer
sem entregar nada.

---

## 4. Particionar demais

Particionar `indicador_ente` por mês criaria milhares de arquivos de 20 KB — o
pior cenário possível para Parquet, que quer poucos arquivos grandes.

**Regra:** grão mais grosso primeiro; só desça a mês onde o volume justifica
(`voto`, `despesa_parlamentar`).

---

## 5. Malhas municipais de uma vez

As malhas dos 5.570 municípios somam centenas de MB. Carregar tudo no boot
trava o navegador.

**Solução:** malha do Brasil por UF no boot, malha da UF sob demanda no clique.
Sempre com `qualidade=minima`.

---

## 6. Confundir data do fato com data da ingestão

`data_referencia` é quando o fato aconteceu (a votação, a competência da
despesa) — é ela que alimenta os filtros do painel. `_criado_em` e
`_atualizado_em` são quando o pipeline soube, e servem só para auditoria.

Filtrar o painel por `_atualizado_em` produz relatórios que mudam sozinhos toda
vez que um coletor roda.

---

## 7. Chave sequencial

Se `sk` fosse um contador, reprocessar duplicaria tudo e você precisaria
lembrar exatamente o que já rodou. Com md5 dos campos de negócio, re-rodar é
seguro por construção. Não troque isso por "performance".

---

## 8. Escrever direto na partição final

Um processo morto no meio de um `COPY` deixa meio arquivo Parquet corrompido —
e você só descobre semanas depois, numa consulta que devolve erro estranho.

Escreva sempre em `.parquet.tmp` e faça `os.replace()` por cima. É atômico no
mesmo volume.

---

## 9. Declaração de bens pelo valor histórico

Limite do dado, não do código: a lei permite declarar bens pelo valor de
aquisição, não de mercado. Qualquer análise de patrimônio de político em cima
do TSE está estruturalmente subestimada.

Se o painel um dia mostrar patrimônio, precisa dizer isso na tela.

---

## 10. Preencher lacuna com zero

Ente sem dado não é ente com zero. Zero é uma afirmação sobre o mundo; ausência
é uma afirmação sobre o acervo. Trocar um pelo outro produz mapas
convincentes e errados — e num painel cujo propósito é transparência, isso é a
falha mais grave possível.

Cinza, sempre, com a contagem no rodapé.
