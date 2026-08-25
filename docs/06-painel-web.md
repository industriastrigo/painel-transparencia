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

## Cor

Rampa **sequencial de matiz única** (verde-azulado, sete degraus), segura para
daltônicos e legível em impressão preto e branco. Nada de arco-íris: matiz
variável faz o olho ler categorias onde existe uma escala contínua.

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

## Zoom, arrasto e ampliar

Roda do mouse aproxima no ponto sob o cursor; arrastar move; **Enquadrar**
volta ao início. O deslocamento é limitado à moldura, senão o mapa some da
tela e não há como trazê-lo de volta.

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

## Acessibilidade

- Cada polígono tem `tabindex`, `role` e `aria-label` com nome e valor
- Enter e Espaço fazem o drill-down, igual ao clique
- Foco visível, sem depender só de cor
- `prefers-reduced-motion` desliga as transições
- Rampa de matiz única
- Toda tabela tem cabeçalho semântico

## Formatação

`Intl.NumberFormat('pt-BR')` para tudo. Moeda em BRL sem centavos — em valores
orçamentários, centavo é ruído.
