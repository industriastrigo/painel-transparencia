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

A receita (Anexo I-C) tem a mesma estrutura: `1.0.0.0.00.0.0` (Receitas
Correntes) é o pai de `1.1.0.0.00.0.0`. O nível sai do código de outro jeito,
porque o formato é outro — conta-se quantos segmentos são diferentes de zero,
já que os zeros são sempre os finais. `testes/teste_receita.py` cobre isso com
uma amostra hierárquica, pelo mesmo motivo.

Cuidado irmão: a coluna da fonte é **Receitas Brutas Realizadas**. As deduções
(grupo 9 — FUNDEB, restituições) vêm no mesmo anexo e ficam de fora. Subtrair
metade delas produziria um número que não é nem bruto nem líquido, e nenhuma
fonte oficial confirmaria.


Terceira aparição da mesma armadilha: o RREO Anexo 02 traz a função `10`
(Saúde) e a subfunção `10.301` (Atenção Básica) também como irmãs.
`testes/teste_funcao.py` usa uma amostra em que Saúde 1.000 = 600 + 400, para
que somar tudo dê 3.600 — o dobro, e plausível.


---

## 2ag. Um anexo não se parece com o outro só porque é a mesma API

O DCA e o RREO saem do mesmo SICONFI, com a mesma cara de resposta. O Anexo
02 do RREO, porém, é outro bicho, e supor que fosse igual custou uma carga
histórica de **oito horas que voltou com zero linha em doze anos seguidos** —
sem um erro no log, porque cada ente aparecia como "sem dado publicado".

Quatro diferenças, e **cada uma sozinha bastava para o resultado ser zero**:

| | DCA | RREO Anexo 02 |
|---|---|---|
| periodicidade | não usa | `in_periodicidade=B` **obrigatório** |
| coluna | `Despesas Empenhadas` | `DESPESAS EMPENHADAS ATÉ O BIMESTRE (b)` |
| empenhado | uma coluna | **duas**: "no bimestre" e "até o bimestre" |
| `cod_conta` | hierárquico (`DO3.1.00…`) | `RREO2TotalDespesas` em **todas** as linhas |

A última é a mais séria. Não existe código de conta neste anexo: função,
subfunção e linha de total têm todas a mesma string. O que separa "Saúde" de
"Atenção Básica" é só o texto de `conta`.

O conserto não foi inventar uma heurística de indentação, e sim casar contra a
lista **normativa** — as 28 funções da Portaria MOG nº 42/1999. Fechada,
citável, auditável. Casou, é função (nível 1); não casou, é subfunção ou total
e fica fora de toda soma. Uma linha "TOTAL (III) = (I + II)" não pode inflar o
total por construção, porque nunca vai ser o nome de uma função.

E `cod_conta` faz parte da chave primária: com a mesma string em todas as
linhas, as trinta linhas do ente colapsariam numa só no merge. A chave passou
a compor bloco + nome da conta.

**Duas regras que ficam:**

1. Antes de escrever um coletor para um anexo novo, **olhe uma resposta
   real** — mesmo que seja a mesma API de onde três coletores já leem.
2. **Teste contra a resposta real, não contra o formato que você imagina.** A
   primeira versão de `teste_funcao.py` passava com folga usando contas
   numéricas hierárquicas inventadas, enquanto a coleta devolvia zero. Hoje o
   arquivo carrega a resposta verbatim, com a data em que foi conferida.



---

## 2aj. Chave que não distingue o que a fonte distingue

`transferencia_uniao` tinha chave `(cod_ibge, cod_transferencia, ano, mes)`. A
rota por estado do Tesouro não devolve código IBGE — só a sigla da UF. Com
`cod_ibge` nulo em todas as linhas, as **27 UFs colapsavam numa linha só** por
modalidade e mês, e o merge guardava a última que chegasse.

Resultado numa carga real: **840 linhas coletadas em 1997, 53 no acervo**.
Cerca de 94% do dado descartado — não pela fonte, pela nossa chave.

Duas correções, e a segunda é a que importa mais:

1. `nivel` e `uf` entraram na chave, e o `cod_ibge` do estado passa a ser
   derivado da sigla (o código da UF é fixo por norma do IBGE — traduzir não é
   inventar). Sem `cod_ibge`, o `vw_mapa` não junta nada e a métrica fica
   cinza com o dado no disco.
2. **O aviso foi para onde alguém lê.**

Sobre a segunda: o `preparar()` já avisava, e avisava com a frase exata — *"a
chave está descrevendo um grão mais grosso que o dado"*. Ele saiu **239 vezes**
num log de 1.476 linhas, junto de outros 343 avisos. Estava correto, estava
lá, e era invisível.

Agora `armazem.COLAPSOS` conta as linhas perdidas por tabela, e o RESUMO da
carga — a parte que alguém realmente lê de manhã — as lista como ERROR.

**Regra:** um diagnóstico que só aparece onde ninguém olha é um diagnóstico que
não existe. Aviso repetido em laço precisa virar contador com resumo no fim.

**Sintoma que denuncia a família inteira:** o merge dizendo "12 novos" quando
o coletor mandou 840 linhas.
---

## 2ai. A coluna é que diz o que o número significa

Irmã da 2ag, e mais perigosa, porque não devolve zero: devolve **o número
errado, plausível, sem erro nenhum**.

No RGF a mesma conta aparece em colunas diferentes:

```
cod_conta=DespesaComPessoalTotal  coluna="Valor"                  → R$ 85 bi
cod_conta=DespesaComPessoalTotal  coluna="% sobre a RCL Ajustada" → 42,19
```

A primeira versão do coletor lia só `cod_conta` e ignorava `coluna`. Como
`medida` também não estava na chave primária, as duas linhas colidiam no merge
e sobrava a última que chegasse. Resultado numa carga real de 12 anos:
`percentual_pessoal` com **10 linhas em 324 possíveis**, `limite_maximo` com
**nenhuma**, `despesa_pessoal_liquida` com **nenhuma**.

No Anexo 02 o mesmo defeito é pior. As colunas são `Até o 1º Quadrimestre`,
`Até o 2º`, `Até o 3º` e `SALDO DO EXERCÍCIO ANTERIOR`. Sem olhar a coluna, o
saldo gravado como "dívida de 2024" podia ser o de 2023. Um número bem
formado, do período errado, que nenhuma conferência de formato pegaria.

**Conserto em três partes:**

1. O grão passou a ser **(indicador, medida)**, e `medida` entrou na chave.
2. A medida sai da COLUNA (`valor`, `percentual`, `saldo`, `restos_a_pagar`),
   e a coluna de outro período é descartada em vez de gravada.
3. O `indicador` é o `cod_conta` **verbatim**, sem tradução para uma lista
   curta de apelidos nossos.

A terceira é a que mais importa. O apelido esperado era `LimiteMaximo`; o nome
real é `LimiteMaximoDespesaComPessoalTotal`, e a diferença apagou o dado do
acervo. Guardando verbatim, um apelido errado deixa uma view sem preencher —
e o conserto vira uma consulta ao que já está no disco, não outra madrugada de
coleta.

**Regra:** num demonstrativo, a célula é identificada por linha **e** coluna.
Chave que só usa a linha está descrevendo um grão mais grosso que o dado — e o
sintoma é o merge "perdendo" linhas que a fonte mandou.
---

## 2ah. Vazio da fonte e vazio do nosso filtro na mesma linha de log

O que fez as oito horas passarem despercebidas não foi o defeito: foi o log.
"27 entes sem dado publicado" cobria dois casos muito diferentes — o ente não
publicou, e a resposta veio cheia mas nenhuma linha passou no nosso filtro.

O primeiro é um fato sobre o ente. O segundo é um defeito nosso se disfarçando
de fato sobre o ente.

`_conferir_funcao` separa os dois: resposta com itens e zero linhas aproveitadas
vira **ERROR**, com quantos itens vieram, o que se procurava e quais colunas a
resposta realmente traz. É a mensagem que teria dado o diagnóstico no primeiro
minuto do primeiro ano, em vez de na manhã seguinte.

**Regra:** todo filtro que pode zerar um lote precisa saber dizer se o lote
chegou vazio ou se foi ele que esvaziou.
---

## 2ac. Relatório acumulado somado período a período

O RREO e o RGF são **acumulados no exercício**: o 6º bimestre já contém
janeiro. Somar os seis bimestres conta janeiro seis vezes, e nenhuma linha
individual está errada — o erro nasce inteiro na agregação.

`vw_funcao_ultimo_periodo` e o `QUALIFY` de `vw_lrf_pessoal` pegam
`MAX(periodo)` por ente e ano. Nunca `SUM` sobre período em relatório
acumulado.

Parente do 2j: nos dois casos o dado está certo e a soma é que mente. A regra
geral é olhar se o demonstrativo é *de fluxo do período* ou *de saldo
acumulado* antes de escrever qualquer `SUM`.

---

## 2ad. Pedir um período que ainda não venceu

Pedir o 6º bimestre de um ano em curso devolve lista vazia. Vazio aqui não
quer dizer "o ente não entregou" — quer dizer "o prazo nem chegou", e o painel
pintaria 5.570 municípios de cinza por causa disso.

A LRF dá 30 dias após o fim de cada período. `siconfi.periodo_publicado(ano,
passo)` devolve o último período vencido, e é ele o padrão quando ninguém
passa o número na mão. Em janeiro e fevereiro devolve 0, e a coleta diz na
tela que não há o que buscar em vez de varrer o país inteiro à toa.

Regra que generaliza: **antes de tratar vazio como ausência, pergunte se a
fonte já tinha obrigação de ter publicado.**

---

## 2ae. Dois recortes do mesmo dinheiro na mesma tabela

Despesa por natureza (pessoal, custeio, investimento) e despesa por função
(saúde, educação, segurança) são o **mesmo dinheiro** visto de dois ângulos.
Se caírem na mesma tabela, qualquer view que agregue por ente soma os dois e
devolve o dobro do real — de novo um número plausível, de novo sem nenhuma
linha errada.

Por isso `despesa_funcao` é tabela própria, e não uma coluna a mais em
`financas_ente`. Mesmo raciocínio que separou `transferencia_recebida`
(declarada pelo ente ao SICONFI) de `transferencia_uniao` (paga pelo Tesouro)
— ver 2n.

O teste que protege isso carrega as duas tabelas ao mesmo tempo e confere que
`vw_despesa_total` continua valendo 1.800, não 3.600.
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

## 2l. Pedir um número que a fonte não produz

"Quanto cada estado transferiu para os outros estados" parece uma pergunta de
transparência legítima, e não tem resposta — **porque a transferência entre
entes federados de mesmo nível não existe** no arranjo fiscal brasileiro.
O fluxo é vertical: a União repassa a estados e municípios (FPE, FPM), e cada
estado repassa aos municípios **dele** (25% do ICMS, 50% do IPVA).

O que o painel mostra, porque existe no Anexo I-C, é a **transferência
recebida** por cada ente — e a fatia da arrecadação que ela representa. Num
município pequeno passa de 90%, e é esse número que explica a dependência do
FPM.

Construir um "transferido para outros estados" a partir do que existe daria um
número inventado com aparência de apurado. Num painel de transparência, isso é
pior do que a lacuna.

---

## 2x. O nome do campo pode estar errado NA FONTE

O SADIPEM devolve o indicador de contratação assim:

    "pvl_contradado_credor": 0

**"contradado"** — erro de digitação da própria API. O coletor lia
`pvl_contratado_credor`, o nome correto, e recebia `None` em 100% das linhas.
O painel mostraria **zero contratado para o país inteiro**, com todos os
outros números certos ao lado.

É o item 2d na forma mais crua: o campo existe, o dado existe, o nome é que
está torto. E não há documentação que avise — só a resposta real avisa.

Ler por lista de apelidos deixa de ser precaução e vira requisito. E vale ler
**os dois**: quando a fonte corrigir a digitação, o coletor não pode quebrar.

---

## 2y. Nome de campo que muda a cada endpoint da mesma API

Na API de Custos, o campo de valor tem nome diferente em cada recorte:

    va_custo_de_pessoal · va_custo_pessoal_inativo · va_custo_pensionistas
    va_custo_depreciacao · va_custo_transferencias · va_custo

E o endpoint `demais` usa outro vocabulário inteiro — `co_siorg_n04..n07` em
vez de `co_organizacao_n0..n6` —, com o nível do ministério mudando de lugar:
`n1` nos cinco primeiros, `n05` neste.

Uma lista de nomes envelhece a cada recorte novo. **Procurar por prefixo**
(`va_`) resolve para sempre o campo de valor; para os demais, a lista precisa
cobrir os dois vocabulários.

Nenhuma dessas irregularidades aparece no Swagger, que documenta os
parâmetros da consulta e não a forma da resposta.

---

## 2aa. Diagnóstico que custa mais que a coleta

`descobrir()` existe para responder uma pergunta barata: **quais são os nomes
dos campos?** A primeira linha da primeira página responde.

Ele usava a mesma função de paginação da coleta e, em `pessoal_ativo`, chegou
ao offset 58.000 — 232 páginas, quatro minutos de rede — antes de a conexão
cair. Para descobrir nomes de campo.

Ferramenta de diagnóstico tem de ser **barata por construção**, senão ninguém
roda; e quando roda, compete com a coleta pelo mesmo limite de requisições.

---

## 2ab. Falha na última página apaga as anteriores

A conexão caiu na página 232 e as 231 anteriores foram descartadas junto com
a exceção. Quatro minutos de rede — e de limite de requisições — jogados fora
por um erro que chegou no fim.

O que já veio volta, marcado como **parcial**, e quem chama decide o que
fazer. Duas condições tornam isso seguro:

- se **nenhuma** linha chegou, o erro continua subindo — engolir seria
  reportar "coletei nada com sucesso", a armadilha 2e;
- o aviso diz que o total é **um piso**, não o valor do período.

Parcial declarado é informação. Parcial silencioso é mentira.

---

## 2z. Dimensão que multiplica linhas sem responder pergunta nenhuma

`pessoal_ativo` vem quebrado por sexo, escolaridade, faixa etária e área de
atuação. Um **único mês** de 2025 passou de 100 mil linhas e estourou o teto
de 400 páginas — e o aviso de truncamento salvou o total de virar um número
incompleto com cara de completo.

O painel pergunta "quanto custa este órgão", não "quanto custa este órgão
para servidores de tal faixa etária". **Somar na leitura**, enquanto pagina,
descarta a explosão combinatória sem perder a resposta — e sem carregar um
milhão de linhas na memória para depois agregar.

A pergunta que o painel faz é que decide o grão de gravação. Guardar o grão
mais fino "por precaução" custa espaço, tempo e teto de página.

---

## 2w. `latin-1` nunca falha — e é por isso que ele é perigoso

Ao ler um CSV de fonte desconhecida, a ordem das tentativas de codificação
não é detalhe de desempenho:

**`latin-1` mapeia qualquer byte para algum caractere.** Ele nunca levanta
`UnicodeDecodeError`. Posto como primeira tentativa, ele "consegue ler" um
arquivo UTF-8 e devolve `SÃ£o Paulo` no lugar de `São Paulo` — sem falha, sem
aviso, com a tabela inteira parecendo correta.

O acento quebrado então atravessa o pipeline: vira nome de município no mapa,
nome de deputado na votação, chave de de-para que não casa. E ninguém
consegue mais dizer de onde veio.

**UTF-8 primeiro, sempre.** Ele recusa byte inválido, então se valida sozinho;
`latin-1` fica como último recurso, que é o papel certo de uma codificação que
aceita tudo. O TSE, que publica em latin-1 de verdade, continua funcionando —
o UTF-8 recusa aqueles bytes e a tentativa seguinte pega.

A mesma lógica vale para o separador: parar na primeira combinação que produz
**mais de uma coluna**. Uma coluna só quase nunca é uma tabela de uma coluna —
é o separador errado com tudo grudado dentro.

---

## 2s. O código da conta tem prefixo, e a documentação não diz

O SICONFI devolve a conta assim:

    cod_conta = "RO1.0.0.0.00.0.0"
    conta     = "1.0.0.0.00.0.0 - Receitas Correntes"

O **`RO`** na frente não aparece em nenhum exemplo do Swagger. Só se descobriu
vendo o log de uma coleta real.

Com ele, o cálculo de nível — que parte o código em pontos e conta segmentos
não-zerados — devolvia 0 para a conta de primeiro nível, e o filtro
`cod_conta LIKE '1%'` nunca casava. Resultado: `vw_receita_total` **vazia**.
373 mil linhas coletadas em uma hora, gravadas corretamente no disco, e o
painel dizendo "não coletado".

Nenhum erro. Nenhum aviso. A coleta reportou sucesso, porque foi bem-sucedida.

**Derive sempre do código NUMÉRICO**, extraído do fim da string:

```sql
regexp_extract(cod_conta, '([0-9][0-9.]*)$', 1)
```

E a lição maior: **campo de código de fonte externa é texto até prova em
contrário.** Supor o formato a partir do exemplo da documentação é o mesmo
erro do item 2d, com outra roupa.

---

## 2t. Conta textual convivendo com contas de função

No mesmo anexo aparecem linhas de código numérico (`10` = Saúde) e linhas de
código textual (`TotalGeralDaDespesa`). Somar as duas conta o mesmo gasto duas
vezes; descartar a textual sempre deixaria sem despesa nenhuma o ente que só
entregou o total.

A regra decide pelo próprio dado, por ente e ano: **onde há conta numérica, a
textual sai; onde não há nenhuma, ela é tudo que existe e fica.**

Regra fixa nos dois sentidos estaria errada em metade dos entes.

---

## 2u. Partição nula chega ao sistema de arquivos

Um valor nulo na coluna de partição vira o texto `<NA>` no caminho:

    dados/fato/operacao_credito/ano=<NA>/part-000.parquet

No Windows, `<` e `>` são proibidos em nome de pasta, e o erro que chega é:

    [WinError 123] A sintaxe do nome do arquivo ... está incorreta

que não menciona tabela, coluna nem partição. Derrubou o coletor do SADIPEM
inteiro quando o formato da data mudou.

`armazem.mesclar` agora separa essas linhas antes de tocar no disco, registra
erro dizendo tabela, coluna, quantas e um exemplo, e grava o resto. Descartar
é deliberado: partição é o eixo de leitura do painel, e linha fora de todo
recorte de tempo é linha que ninguém encontra de novo.

---

## 2v. `os.replace` não é imune a trava de arquivo

O rename atômico protege contra processo morto no meio da escrita. Não protege
contra **outro programa segurando o arquivo de destino**:

    [WinError 5] Acesso negado: part-000.parquet.tmp -> part-000.parquet

Três suspeitos, nesta ordem: a pasta `dados/` dentro do OneDrive ou Dropbox,
que sincroniza arquivo a arquivo; o antivírus varrendo o Parquet recém-escrito;
e o próprio painel, porque o DuckDB da API mantém os Parquet abertos enquanto
alguém navega.

Quase sempre é trava passageira: repetir com espera curta resolve. Quando não
resolve, a mensagem precisa listar os três suspeitos — `WinError 5` sozinho
manda a pessoa procurar permissão de pasta, que não é o problema.

**Acervo de dados não deve morar em pasta sincronizada.** São gigabytes
reescritos a cada coleta, e o conteúdo é reproduzível: sincronizar é pagar
banda e travas por um backup que os coletores refazem de graça.

---

## 2r. Rodar acima do limite publicado sem perceber

O SICONFI e o SADIPEM dizem, na primeira tela da documentação: **uma
requisição por segundo**. O projeto declarava 0,5 s para o SICONFI em
`config`, e a função `varrer` sobrescrevia com `definir_intervalo(FONTE,
0.15)` — o padrão do próprio parâmetro. Com seis trabalhadores em paralelo, a
varredura municipal saía a cerca de **6,7 requisições por segundo**: quase sete
vezes o limite declarado, por meses, sem um aviso.

Ninguém errou uma conta. O que aconteceu foi um valor de conveniência
(0,15 s, escolhido para a varredura ser rápida) sobrepondo-se a um limite da
fonte, três arquivos adiante de onde o limite estava escrito.

`config.INTERVALO_REQUISICOES` passou a ser **piso**, não padrão:
`rede.definir_intervalo` recusa qualquer pedido menor e registra por quê.
Nenhum caminho — CLI, painel, orquestrador — consegue descer abaixo dele.

O preço é real: a varredura dos 5.570 municípios, com dois anexos, sai de ~28
minutos para cerca de 3 horas. É o custo de respeitar um limite publicado, e a
alternativa é o IP ser bloqueado no meio de uma coleta de 11 mil requisições.

**Limite publicado por uma fonte não é sugestão de desempenho.** É a condição
para continuar podendo coletar.

---

## 2q. Valor padrão que anula a regra que existe acima dele

`anos_de()` foi escrito para dar a cada fonte o ano natural dela — a Câmara
publica o ano corrente todo dia, o SICONFI só fecha o anterior. Ele começa
assim:

```python
if opcoes.ano:
    return [opcoes.ano]
```

E o argumento da linha de comando era:

```python
p.add_argument("--ano", type=int, default=date.today().year - 1)
```

`args.ano` **nunca** era None. Toda execução chegava com um ano explícito, o
`if` acima vencia sempre, e a coleta diária da Câmara voltava a buscar o ano
passado — o defeito que `anos_de` tinha sido escrito para corrigir, de volta
por um `default=` a três arquivos de distância.

Um padrão conveniente num parser pode desligar, em silêncio, a lógica que
depende de "não foi informado". Quando existir regra para o caso não
informado, o padrão tem de ser `None`.

---

## 2p. Dois jeitos de matar o clique do mapa

O mesmo sintoma — a dica aparece, o estado não abre — teve **duas** causas
independentes, e consertar a primeira não resolveu.

**Reordenar o DOM no `mouseenter`.** Para o contorno realçado não ficar
coberto pelo vizinho desenhado depois, o ente era movido para o fim da fila
com `insertBefore`. Mover um nó refaz o hit-test do ponteiro, o que dispara
`mouseleave` + `mouseenter` de novo, que move o nó de novo — e cada
reinserção reinicia a sequência que o navegador usa para decidir que houve
clique. O `click` nunca chegava.

A correção não é mover menos: é **não mover**. Um `<path>` separado, sem
preenchimento e com `pointer-events: none`, recebe o `d` do ente sob o cursor.
Fica por cima de todos, inerte, e a árvore dos entes não muda nunca.

**`setPointerCapture` no `<svg>`.** Capturar o ponteiro para o arrasto
sobreviver fora da moldura faz o `click` seguinte ter o **`<svg>`** como alvo,
não o `<path>`. E o defeito era condicional — a captura só ligava com zoom >
1 —, então clicar funcionava no mapa inteiro e parava depois de aproximar.
Parece problema do zoom, e é do ponteiro.

Ouvintes de `pointermove`/`pointerup` no `document` resolvem sem capturar. A
trava que impede o arrasto de virar clique também precisa ser desarmada no
`pointerdown` seguinte: um arrasto que termina fora da janela nunca dispara o
`click` que a limparia, e ela engoliria o próximo clique legítimo.

**A lição das duas juntas:** num elemento clicável, desconfie de qualquer
coisa que mexa na identidade ou na posição dele durante o hover. O clique do
navegador depende de o alvo continuar o mesmo entre pressionar e soltar.


---

## 2o. Pedido não é dívida

O SADIPEM publica **PVL — Pedido de Verificação de Limites**: o pedido que um
ente faz ao Tesouro para poder tomar emprestado. Somar o valor de todos os
PVLs de um município e chamar isso de "dívida" erra três vezes de uma só:

1. **pedido indeferido nunca virou dinheiro** — e no acervo ele está lá, com
   valor cheio, do lado dos deferidos;
2. **deferido não é contratado** — a autorização vence sem virar contrato;
3. **o valor é o do pleito**, da época do protocolo, não o saldo devedor de
   hoje, que anos de amortização reduziram.

O número errado seria plausível: ordem de grandeza certa, moeda certa,
município certo. Nada na tela denunciaria.

Por isso `vw_credito_ente` devolve **três** colunas — pleiteado, deferido e
contratado — e o painel mostra as três lado a lado. A diferença entre elas é
a informação: um ente que pede muito e contrata pouco conta uma história
diferente de um que contrata tudo que pede.

E o painel nunca escreve "dívida". Escreve "operações de crédito", que é o
que o dado sustenta. Saldo devedor é outro demonstrativo (RGF), ainda não
coletado.

---

## 2n. Duas medidas com o mesmo nome popular

O painel tem agora dois números que qualquer um chamaria de "transferências":

| | de onde vem | o que cobre |
|---|---|---|
| `transferencia_recebida` | o ENTE declara ao SICONFI | tudo que recebeu, de qualquer origem, inclusive ICMS e IPVA repassados pelo estado |
| `transferencia_uniao` | a UNIÃO declara ao SIAFI | só as obrigatórias federais, mês a mês, por modalidade |

Elas **não batem, e nenhuma das duas está errada** — são regimes, recortes e
declarantes diferentes. Somar as duas conta o FPM duas vezes.

Ficam em tabelas separadas de propósito. Juntar na mesma tabela, ou numa
coluna só "para simplificar", é o convite para a soma acontecer seis meses
depois, quando ninguém lembrar por que havia duas.

Quando o painel mostra uma delas, diz qual.

---

## 2m. `activate.bat` guarda o caminho absoluto

Renomear a pasta do projeto quebra o ambiente virtual. `pyvenv.cfg` e
`activate.bat` gravam o caminho da criação, e depois do rename ele aponta
para uma pasta que não existe mais:

    set VIRTUAL_ENV=...\Trigo Labs\Painel_Transparencia\.venv

O `activate` então **não tem efeito e não reclama**. O `python` seguinte é o
do sistema, e o erro que chega ao usuário é:

    ModuleNotFoundError: No module named 'uvicorn'

que parece falta de instalação, manda a pessoa reinstalar dependências, e a
reinstalação não resolve — porque o ambiente certo estava lá o tempo todo.

**Chame `.venv\Scripts\python.exe` direto.** O Python descobre o ambiente pela
localização do próprio executável, então sobrevive a mover e renomear pasta.
`scripts\usar-python.bat` resolve o interpretador uma vez e os lançadores
usam `%PY%`.

Vale para qualquer caminho absoluto gravado em arquivo de configuração: se ele
existe, mover a pasta é uma operação que quebra em silêncio.


---

## 2af. Descartar na ingestão o que custa horas para buscar de novo

O coletor projeta a resposta num contrato de colunas e joga fora o resto. Isso
é certo — sem contrato não há tipo, chave nem partição. O erro é achar que o
descarte é reversível.

Não é, na prática: o SICONFI e o SADIPEM publicam o limite de **uma requisição
por segundo**, então recoletar a série histórica dos 5.570 municípios é medido
em horas de máquina ligada. Descobrir em novembro que a resposta de agosto
trazia o campo que faltava significa passar outra madrugada buscando um dado
que já esteve na memória do processo.

O conserto não é ampliar o contrato por precaução — ninguém acerta hoje a
pergunta de daqui a seis meses. É **guardar a resposta verbatim ao lado**
(`nucleo.bruto`), num diário append-only, e deixar a pergunta nova ser
respondida no disco.

Onde o gancho fica importa: em `rede.buscar`, o único ponto por onde os dez
coletores falam com a rede. Uma linha ali cobriu todos eles. A versão que
alterava cada coletor teria sido dez oportunidades de quebrar uma carga
histórica na véspera dela.

**Regra que generaliza:** quando recoletar é caro, o pipeline precisa de um
ponto onde o dado passa sem contrato. Contrato é para ler, não para receber.

---

## 2ak. Cor literal no meio da regra não tem contraparte no tema escuro

`button.principal` fixava `color: #fff` enquanto o fundo vinha de token. No
tema claro o par dá 6,3:1; no escuro o verde clareia e o mesmo par cai para
**2,18:1** — o botão de Atualizar e o de Salvar, quase ilegíveis. O amarelo dos
avisos (`#b8860b`, repetido em cinco regras) reprovava no claro, a 3,03:1.

Nenhum dos dois "parecia" errado. É por isso que a lição não é sobre cor:

**Contraste não se revisa de olho — se calcula.** `testes/teste_mapa.mjs`
mede onze pares nos dois temas e falha abaixo de AA. A regra que evita a
família inteira: valor literal no meio de uma regra é valor que não tem
contraparte no outro tema.

O mesmo defeito, em outra forma, no mapa: a rampa de cor era **constante nos
dois temas**. No escuro o rótulo quase branco caía sobre a faixa quase branca
(1,01:1) e o cinza de `--sem-dado` ficava mais escuro que qualquer valor — o
olho lendo ausência como o extremo da escala, com o rodapé dizendo "cinza =
sem dado coletado". O mapa afirmando o contrário da legenda.

---

## 2al. `flex: 1` é `flex-basis: 0`

O diálogo da ficha abria com a cortina escura na tela e **nada dentro**.

`#detalhe-conteudo { flex: 1 }` — o atalho significa `flex-grow:1;
flex-shrink:1; flex-basis:0`. Num contêiner de altura automática, o único
filho parte do zero, a altura do pai depende do filho, o filho depende do pai,
e a circularidade resolve em zero. `flex: 1 1 auto` conserta.

O que importa aqui não é o CSS: é que **isso só apareceu abrindo a página**.
Nenhuma leitura do arquivo pegaria, e a suíte inteira passava. Redesenho que
não foi aberto num navegador é redesenho não verificado.

---

## 2am. Falha de servidor renderizada como ausência de dado

A tela dizia *"Nenhuma proposição coletada. Use a aba Atualizar"* quando o
acervo estava cheio e quem tinha caído era a API. Todo chamador fazia
`.catch(() => [])`, e lista vazia caía no mesmo texto de "não há dados" —
mandando o usuário recoletar horas de dado que já estava no disco.

Ausência é uma afirmação sobre o acervo; falha é uma afirmação sobre o
servidor. É a mesma família de erro que trocar cinza por zero no mapa
(item 10), agora do lado do cliente.

Agravante que fazia o defeito durar: `trocarAba` só recarregava a aba quando o
`tbody` estivesse vazio, e **todo caminho de erro insere uma linha**. Primeira
visita falhou → a aba nunca mais tentava, só recarregando a página. Hoje o que
se marca é o SUCESSO, não a ausência de linhas.

---

## 2an. Diagnóstico correto, no lugar onde ninguém olha

Repetido aqui porque reapareceu no front: o aviso de colisão de chave (2aj)
saiu 239 vezes num log de 1.476 linhas e ninguém viu. O mesmo tipo de coisa
acontece na tela quando um corte é silencioso — o ranking mostrava 60 de 585
municípios sem dizer, e a busca parava em 300 sem avisar.

**Todo corte precisa aparecer na tela onde o corte acontece.**

---

## 2ao. Chave que muda de forma sem o dado mudar

O oposto exato da 2aj — lá a chave era grossa demais e apagava linhas; aqui
ela é FINA demais e duplica.

`despesa_parlamentar` tem chave `(casa, id_documento, num_parcela,
num_ressarcimento)`. Os dois últimos entraram por um bom motivo: reembolso
parcelado repete o mesmo documento, e sem eles 1.307 notas por ano eram
descartadas.

Só que uma versão do coletor deixava esses campos **nulos** quando a fonte
mandava vazio, e a versão seguinte passou a gravar `"0"`. Nulo e `"0"` são
chaves diferentes. A mesma nota, coletada nas duas épocas, virou duas linhas:
**96.407 documentos duplicados**, e a cota parlamentar de 2026 saltou de
R$ 121,5 milhões para R$ 242,2 milhões. O dobro exato.

O que denunciou não foi o log — foi conferir contra a fonte. A página oficial
de um deputado mostrava R$ 67.682,70 no ano; o acervo dizia R$ 135.365,52.
Desduplicado, R$ 67.682,76 — os seis centavos são arredondamento de exibição.

**Três consertos, e a ordem importa:**

1. `vw_cota_parlamentar` desduplica na LEITURA. É o único que conserta o
   acervo que já existe — coletor consertado não desfaz linha gravada.
2. `_chave_parcela` normaliza na ENTRADA: nulo, vazio, espaço, `"00"`, `0.0`
   e o `nan` do pandas viram todos `"0"`. Eram seis formas de dizer a mesma
   coisa e seis chaves distintas.
3. `vw_conferencia_cota` compara o cru com o desduplicado, para a divergência
   aparecer em vez de somar em silêncio.

**Regra:** um campo só entra na chave primária se a sua FORMA for tão estável
quanto o seu significado. `None` e `"0"` significam o mesmo e escrevem
diferente — e o merge só enxerga a escrita.

---

## 2ap. Raspar HTML é dívida que vence sozinha

A página do deputado na Câmara mostra verba de gabinete, pessoal de gabinete
e presença em plenário. A **API de dados abertos não publica nenhum dos
três** — só a cota parlamentar, que sai em arquivo estruturado.

A saída tentadora é raspar a página. A saída certa é não raspar: raspagem
quebra em silêncio quando o site muda, e a tela passa a mostrar um número
velho ou nenhum, sem nada no log. Num painel cujo propósito é ser conferível,
um número que envelhece sem avisar é pior que um campo vazio.

A ficha do parlamentar **lista o que não tem**, diz por quê, e leva o cidadão
à página oficial. Custa um clique e não custa a confiança.
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

---

## 11. "Procurei e não achei" não é "não existe"

Durante semanas o painel afirmou, na ficha de cada deputado, que **presença e
faltas não existiam em dado aberto** — que só havia o HTML da página da
Câmara. A afirmação estava na tela, com todas as letras, para o cidadão ler.

Estava errada.

O erro de método foi este: procurei frequência onde ela seria óbvia
(`/deputados/{id}` e as rotas por deputado), não encontrei, e transformei a
busca fracassada numa conclusão sobre o mundo. O dado existe em
`arquivos/eventosPresencaDeputados/`, um registro por (evento, deputado),
publicado em lote como o resto.

A lição não é sobre a Câmara. É que **um item na lista "o que o painel não
tem" é uma afirmação factual e envelhece como qualquer outra** — só que
ninguém a revisa, porque ela não quebra nenhum teste e não aparece em log
nenhum. Hoje o `teste_api.py` afirma explicitamente que presença **não** está
mais nessa lista, com a data e o motivo, para que a correção não seja
silenciosamente desfeita.

Regra prática: antes de escrever "a fonte não publica X", procure X no
**índice de arquivos em lote**, não só na API REST. Nesta fonte as duas
coisas não têm o mesmo conteúdo — o que nos leva à armadilha seguinte.

---

## 12. Documentação não é contrato: rota documentada devolvendo vazio

O Swagger da Câmara documenta `/votacoes/{id}/orientacoes` e
`/votacoes/{id}/votos` com esquema completo de resposta. Conferido em
2026-08-28, contra votações reais de março e junho de 2026: **as duas
devolvem `dados: []`**. O mesmo dado, no arquivo em lote do mesmo ano, vem
completo.

`/deputados/{id}/despesas` faz o mesmo: documentado, com 16 campos no
esquema, e vazio na prática.

Um coletor escrito a partir do Swagger teria passado em todos os testes de
formato, rodado sem erro, gravado zero linha e deixado a tela mostrando "sem
dados" — o modo de falha mais caro deste projeto, já pago uma vez com as 8
horas da carga do RREO.

O próprio topo do Swagger avisa: *"Esta versão é ainda incompleta, sujeita a
mudanças e não substitui a versão original"*. Vale ler o aviso.

Regra: **nenhum coletor novo entra sem uma resposta real conferida**, e o
`_conferir_*` correspondente precisa gritar em ERROR quando a fonte devolve
itens mas nenhum passa no filtro — ou quando devolve zero item onde deveria
haver muitos.

---

## 13. Falta é subtração, e subtração precisa de janela

A fonte de presença publica **quem esteve**. Nunca quem faltou. A falta é uma
conta nossa, e uma conta nossa sobre uma pessoa nomeada.

A primeira versão da view dividia pelas sessões do ano inteiro. Um deputado
que assumiu como suplente em junho aparecia com **40% de presença e 39 faltas
que era impossível ele ter cometido**. O número estava pronto para ir à tela
ao lado do nome e da foto de uma pessoa real.

Três defesas, todas no código:

1. O denominador é a janela em que o parlamentar esteve ativo, não o ano.
2. `janela_aproximada` sai junto com o número e a tela imprime, em destaque,
   que aquela taxa **não se compara** com a de quem esteve o ano inteiro.
3. `teste_presenca.py::test_quem_assumiu_no_meio_do_ano_nao_falta_ao_passado`
   existe só para esse caso.

E o que continua faltando fica dito na tela: **não há justificativa no dado
aberto**. Licença médica, licença-maternidade e missão oficial ficam iguais a
falta seca. Um painel que mostra "13 faltas" sem essa frase está produzindo
uma acusação, não uma informação.
