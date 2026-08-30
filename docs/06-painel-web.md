# 06 — Painel web

`publico/` — quatro arquivos, nenhuma dependência, nenhum CDN. Abre offline.

| Arquivo | Papel |
|---|---|
| `index.html` | estrutura e abas |
| `estilo.css` | tema claro/escuro por `prefers-color-scheme` |
| `mapa.js` | projeção, geometria e escala de cor (módulo puro, testável) |
| `painel.js` | busca na API, monta o DOM, trata cliques |

`mapa.js` não toca no DOM e não conhece a API — por isso é testado direto no
Node, sem navegador (`node --test testes/teste_mapa.mjs`).

## Projeção: Albers, não Mercator

Mercator infla o Rio Grande do Sul e achata o Amazonas. Num mapa que compara
áreas e valores isso é distorção pura. Albers cônica equivalente é o padrão do
IBGE para cartografia temática.

Parâmetros para o Brasil: `lon0 = -54`, `lat0 = -12`, paralelos padrão `-2` e
`-22`.

Detalhe que custou um teste vermelho: no hemisfério sul `n < 0` e a fórmula
devolve o eixo crescendo para o **norte**, enquanto o `y` do SVG cresce para
**baixo**. Sem negar o `y`, o Brasil aparece de cabeça para baixo. O teste
`Albers preserva a ordem norte-sul` existe para isso não voltar.

## Sistema visual: tudo é token

Nenhuma cor, medida ou sombra literal no meio das regras. Um valor solto é um
valor que **não tem contraparte no tema escuro**, e foi assim que dois defeitos
graves passaram despercebidos por meses:

- `button.principal` tinha `color: #fff` cravado enquanto o fundo era token.
  No escuro o verde clareia e o par caía para **2,18:1** — o botão de Atualizar
  e o de Salvar ficavam quase ilegíveis.
- `#b8860b` (os avisos "a conferir", "ignora o campo Ano", `WARNING` no log)
  aparecia literal em cinco regras, sem versão escura, a **3,03:1** no claro.

Hoje são `--sobre-realce` e `--atencao`, com valor nos dois temas, e
`testes/teste_mapa.mjs` calcula as razões de contraste de onze pares em ambos.
**Contraste não se revisa de olho — se calcula.**

As escalas de tipo (`--t-micro` … `--t-titulo`) e de espaçamento (`--e1` …
`--e8`, passos de 4) existem pelo mesmo motivo: número escolhido a olho, uma
regra por vez, é como uma tela fica quase alinhada em toda parte e alinhada em
lugar nenhum.

## Cor

Rampa **sequencial de matiz única** (verde-azulado, sete degraus), segura para
daltônicos e legível em impressão preto e branco. Nada de arco-íris: matiz
variável faz o olho ler categorias onde existe uma escala contínua.

**Duas rampas, uma por tema.** A rampa era constante e no escuro isso produzia
dois erros de uma vez: o rótulo (quase branco) caía sobre a primeira faixa
(quase branca) a **1,01:1**, e `--sem-dado` escurecia com o tema enquanto a
rampa continuava clara — o cinza de ausência ficava **mais escuro que qualquer
valor**. O olho lia ausência como o extremo da escala, enquanto o rodapé dizia
"cinza = sem dado coletado". Num painel de transparência é o pior tipo de erro:
o mapa afirmando o contrário do que a legenda promete.

**A tinta do rótulo é escolhida por FAIXA**, não por tema. Uma tinta só para
sete tons que vão de quase branco a quase preto é impossível: o pior caso
ficava em 1,7:1. Escolhendo escura sobre as faixas claras e clara sobre as
escuras (`tintaSobre`, limiar de luminância 0,19), o pior caso vira **4,2:1** —
e o halo volta a ser reforço em vez de ser a única coisa segurando a
legibilidade.

Quebras por **quantil**, não por intervalo igual. Dado municipal brasileiro é
dominado por outliers — um município com uma usina hidrelétrica destrói
qualquer escala linear, deixando 5.569 municípios na mesma cor.

**Cinza é sem dado, não zero.** Zero é uma afirmação sobre o mundo; cinza é
uma afirmação sobre o acervo. O rodapé sempre diz "X de Y entes com dado".

## Sobre 3D

Foi considerado e descartado. Mapa 3D com câmera livre é a pior forma conhecida
de comparar quantidades: estados na frente escondem os de trás, a perspectiva
encolhe o que está longe, e o usuário não consegue dizer se um valor é maior
que o outro. Fica bonito em captura de tela e inútil na decisão.

Se um dia quiser exploração 3D, `deck.gl` com `GeoJsonLayer` extrudado é o
caminho — mas como camada exploratória, jamais como o gráfico principal, e
sempre com o ranking ordenado ao lado, que é onde a leitura precisa acontece.

## Rótulos: sigla no país, nome na UF

No mapa do Brasil cada estado leva a **sigla** (SP, AM). Dentro de uma UF, cada
município leva o **nome**.

Duas decisões evitam que isso vire mancha:

**O rótulo vai no centroide de ÁREA do maior anel.** Não na média dos vértices
— ela é puxada para onde a costa tem mais pontos, e no Brasil isso significa
sempre o litoral. E não no primeiro anel do MultiPolygon, que pode ser uma
ilha: "SP" escrito sobre Ilhabela.

**Só aparece quem tem largura para caber.** O menor lado da caixa do ente é
comparado, já multiplicado pela escala do zoom, com um mínimo de 34 px. Por
isso os nomes vão surgindo conforme se aproxima — 5.570 nomes sobrepostos não
são informação. O seletor **Nomes** força "sempre" ou "nenhum" para quem
prefere decidir.

O texto fica dentro do grupo que escala, mas com `font-size` dividido pela
escala: é o mapa que amplia, não a tipografia. E leva halo (`paint-order:
stroke`) da cor do papel — sem ele, um rótulo sobre o verde escuro fica
ilegível justamente nos entes de valor mais alto.

**O corpo e o halo são definidos por `style` inline, nunca pelo CSS.** Uma
regra de folha de estilo vence o *atributo de apresentação* do SVG — a
compensação de zoom era escrita como atributo e simplesmente ignorada, e os
nomes cresciam junto com o mapa até um município tapar meio estado. O teste
`a folha de estilo não define o corpo do rótulo` lê o `estilo.css` e falha se
`font-size` ou `stroke-width` voltarem para lá.

**A largura do nome é medida, não estimada.** `getComputedTextLength()` dá o
comprimento real; a conta "0,52 do corpo por caractere" cobrava a largura de
um "M" para cada "i" e escondia nomes que cabiam — Salinas da Margarida foi o
caso que denunciou. Quando o elemento não está sendo desenhado (aba oculta) a
medida volta 0, e aí a estimativa ainda serve de reserva.

E sumir é o **último** recurso, não o primeiro. `encaixarRotulo()` tenta,
nesta ordem: tamanho cheio → 85% → duas linhas a 90% → duas linhas a 75%. A
quebra é no espaço mais próximo do meio, para dar "Salinas da / Margarida" e
não "Salinas / da Margarida"; e só onde há altura para duas linhas.

O **menor lado** ainda barra as fatias finas, mas com um piso baixo (16 px):
quem decide de verdade é a medida do nome contra a largura do ente.

## Divisas e foco

A divisa entre entes usa `vector-effect: non-scaling-stroke`: a espessura fica
em pixels de **tela** e não é multiplicada pelo zoom. Sem isso, aproximar 8×
engrossa a linha 8× e o mapa vira uma grade preta com manchas de cor no meio.

Realce e foco marcam o **contorno** do ente, engrossando o traço. O `outline`
do navegador desenha a caixa delimitadora — num estado recortado como a Bahia,
um retângulo que não tem relação nenhuma com a forma. Ele é desligado, e o
contorno o substitui: desligar sem substituir deixaria quem navega por teclado
sem indicação de foco.

O realce é um `<path>` **separado**, sem preenchimento e com `pointer-events:
none`, que recebe a forma do ente sob o cursor. Mover o próprio ente para o
fim da fila resolveria a sobreposição e quebrava o clique: reordenar o DOM
refaz o hit-test, o `mouseenter` dispara de novo, e a sequência que o
navegador usa para decidir que houve clique reinicia a cada movimento
(armadilha 2p).

## Tipografia

Montserrat, peso normal, com a fonte do sistema como reserva.

**Sem CDN.** Um `@import` do Google Fonts quebraria a promessa de abrir
offline e avisaria o Google a cada abertura do painel — num projeto de
transparência isso é o oposto do combinado. O `@font-face` procura, nesta
ordem: a fonte instalada na máquina (`local()`), depois
`publico/fontes/montserrat.woff2` se você quiser embutir. Sem nenhum dos dois,
cai para a fonte do sistema e o painel continua legível.

## Zoom, arrasto e ampliar

Roda do mouse aproxima no ponto sob o cursor; arrastar move; **Enquadrar**
volta ao início. O deslocamento é limitado à moldura, senão o mapa some da
tela e não há como trazê-lo de volta.

O arrasto usa ouvintes no `document`, **não** `setPointerCapture` — capturar
o ponteiro faz o clique seguinte ter o `<svg>` como alvo e o ente deixa de
abrir (armadilha 2p).

Arrasto só conta a partir de 4 px — sem essa folga, um clique com a mão trêmula
vira arrasto e a ficha do município não abre.

**Ampliar** não usa a API de fullscreen do navegador, de propósito: ela esconde
a barra de ano e métrica, que é justamente o que se quer mexer enquanto se
olha o mapa grande. É um `position: fixed` sobre a página, e `Esc` fecha.

## A dica ao passar o mouse

Mostra população, arrecadação, despesa, transferências recebidas e despesa por
habitante, mais a fatia da arrecadação que veio de transferência.

Campo sem dado escreve **"não coletado"**, em cinza — nunca `R$ 0`, nunca
linha omitida. Omitir seria pior que cinza: o leitor conclui que o ente não
tem aquela receita.

O `<title>` nativo do SVG foi removido dos polígonos: ele e a dica apareceriam
juntos dizendo a mesma coisa. O `aria-label` continua, para o leitor de tela.

## Drill-down

Um único estado (`estado.nivel`, `estado.uf`) governa o mapa. A malha do Brasil
por UF é carregada no boot; a malha dos municípios de uma UF só no clique.

**Nunca carregue as malhas dos 5.570 municípios de uma vez** — são centenas de
MB. Se um dia precisar de todas, simplifique a geometria com `mapshaper` no
build.

A migalha ("Brasil › SP") devolve ao nível anterior.

## Segurança: o painel monta HTML com template string

Todo texto vindo da API passa por `escapar()` antes de entrar num `innerHTML`,
e por `atributo()` antes de entrar num atributo. Não é paranoia: o conteúdo é
texto de terceiros **por definição** — ementa de projeto de lei escrita por
assessoria, nome de político do TSE, rótulo de conta do SICONFI, mensagem de
erro de coletor. Um `<` numa ementa já quebra a tabela em silêncio.

`endereco()` é mais estrito ainda: a API controla `url_norma` e a `url` da
proposição, e um `href` aceita `javascript:` — `rel="noopener"` não protege
contra isso. Só `http` e `https` passam.

## Três estados, não dois

Carregando, vazio e **falhou**. O terceiro faltava, e a consequência era séria:
falha de servidor era renderizada como "não há dados". A tela dizia *"Nenhuma
proposição coletada. Use a aba Atualizar"* quando o acervo estava cheio e quem
tinha caído era a API — mandando o usuário recoletar horas de dado que já
estava no disco.

Ausência é uma afirmação sobre o acervo; falha é uma afirmação sobre o
servidor. Trocar uma pela outra é a mesma família de erro que trocar cinza por
zero no mapa.

Correlato: `trocarAba` recarregava a aba quando o `tbody` estivesse vazio — só
que **todo caminho de erro insere uma linha**. Se a primeira visita falhou, a
aba nunca mais tentava de novo. Hoje o que se marca é o SUCESSO
(`abasCarregadas`), então falhar deixa a próxima visita tentar.

## Acessibilidade

- **Abas de verdade.** Havia `role="tablist"` com `aria-selected` em botões
  **sem** `role="tab"` — e `aria-selected` é inválido num botão comum, então o
  leitor de tela ignorava e nunca anunciava qual aba estava aberta. Meio
  caminho é pior que nenhum dos dois. Hoje há `role="tab"`, `aria-controls`,
  `role="tabpanel"`, setas ←/→ e *roving tabindex*: o conjunto é UMA parada de
  Tab, não seis.
- **Só quem age recebe foco no mapa.** `tabindex` em todo polígono punha 645
  paradas de Tab no mapa de SP e 853 no de MG, sem saída — e entes sem ação
  nem faziam nada ao receber o foco.
- **Teclado move o mapa.** Setas movem, `+`/`−` aproximam, `0` enquadra. Com
  escala 8× o Tab só alcançava o que estivesse enquadrado, e não havia como
  enquadrar outra coisa sem mouse: o zoom existia e era inutilizável.
- **A dica NÃO é `aria-live`.** Ela era reescrita a cada ente sob o cursor, e
  atravessar o mapa com o mouse enfileirava uma leitura por município. O
  leitor chega ao número pelo `aria-label` do próprio ente, que é onde o foco
  está — e esse rótulo carrega a métrica em vigor, não só o nome.
- **Sem `role="img"` no SVG.** Ele tornaria presentacional todo o conteúdo
  interno, inclusive os `<path>` focáveis: foco indo para nós que a árvore de
  acessibilidade não expõe. E o nome do mapa é reescrito a cada troca de UF e
  de métrica — antes dizia "Mapa do Brasil" mesmo dentro da Bahia.
- Enter e Espaço fazem o drill-down, igual ao clique — inclusive na linha da
  tabela de proposições, que era clicável só com mouse.
- Foco visível em anel único com respiro, sem depender só de cor.
- `prefers-reduced-motion` desliga transições; `prefers-contrast: more`
  engrossa as bordas.
- Rampa de matiz única, com tinta de rótulo escolhida por faixa.
- Toda tabela tem cabeçalho semântico e rola dentro do próprio contêiner —
  seis colunas empurravam a página inteira para o lado no celular.

## Toque

A dica existia só em `mouseenter`: no celular não há hover, e os oito valores
por ente eram **inalcançáveis**. Hoje ela responde a `pointerenter`, então o
toque mostra os números antes de o clique agir.

E a roda do mouse só chama `preventDefault` quando há zoom para dar: antes era
incondicional, e o dedo em cima do mapa prendia a rolagem da página.

## Desempenho

`aplicarZoom(true)` reposiciona sem reencaixar rótulo. Cada rótulo mede o
texto com `getComputedTextLength`, o que força layout síncrono, e são até
cinco medições por rótulo — no mapa de Minas, perto de **4.000 reflows por
chamada**. E a função era chamada a cada `pointermove` do arrasto, onde **a
escala não muda**: era trabalho inteiro jogado fora, 60 vezes por segundo.
O reencaixe acontece uma vez, ao soltar.

Outras três, do mesmo tipo:

- A malha por UF fica em cache: trocar de métrica não rebaixa e reprojeta
  5.570 polígonos de novo.
- O `find` linear dentro do laço de desenho era código morto — comparava
  exatamente o mesmo critério da chave do `Map` — mas materializava um array
  com todos os entes para cada forma sem correspondência.
- O log da coleta mostra as últimas 400 linhas. Numa coleta municipal de três
  horas o array só cresce, e ele era reconstruído inteiro a cada dois
  segundos.

## Corridas

- **Requisição do mapa tem geração.** Trocar a métrica depressa disparava
  vários `carregarMapa()`, e a resposta mais LENTA chegava por último —
  desenhando dados antigos por cima dos novos, sem sinal nenhum.
- **O polling da coleta tem trava.** `/api/coleta` durante uma coleta pesada
  leva mais de 2 s; os ticks se acumulavam e as respostas chegavam fora de
  ordem, fazendo a barra de progresso **andar para trás**.
- **E ele sabe parar.** Cinco falhas seguidas encerram o relógio com aviso na
  tela; antes, uma API caída no meio congelava o painel no último estado
  conhecido, para sempre, em silêncio.

## Formatação

`Intl.NumberFormat('pt-BR')` para tudo. Moeda em BRL sem centavos — em valores
orçamentários, centavo é ruído.

**A casa aparece a partir de um milhão**: `R$ 81,38 bi`, `R$ 149,16 mi`. Ler
"R$ 81.379.195.222" exige contar dígitos de três em três, e é aí que bilhão
vira milhão na cabeça de quem lê. Abaixo de um milhão fica o número inteiro —
"R$ 5,47 mil" é pior que "R$ 5.472" para despesa por habitante, porque esconde
reais que cabiam na tela.

Quem escolhe entre mil/mi/bi/tri é a tabela do pt-BR no `notation: 'compact'`,
não uma lista escrita aqui.

**O valor exato nunca se perde**: fica no `title` de todo número abreviado —
passar o mouse mostra. Num painel que existe para ser conferido, arredondar
sem deixar o número original ao alcance seria trocar clareza por exatidão.

### "R$ mil" do IBGE são milhares de reais

O SIDRA publica o PIB com unidade `R$ mil`: o valor 430.987.853 da Bahia são
**R$ 430 bilhões**, não R$ 430 milhões. Exibir o número cru com o símbolo na
frente erraria por mil vezes — `formatarIndicador()` multiplica e diz no
`title` qual era a unidade publicada.
