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
