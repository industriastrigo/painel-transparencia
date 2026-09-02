/* Testes do desenho do mapa (sem navegador).
 *
 *   node --test testes/teste_mapa.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  criarProjecao, desenharGeoJson, calcularQuebras, corDe, RAMPA,
  centroideDeAnel, tintaSobre, faixaDe,
} from '../publico/mapa.js';

const quadrado = (lon, lat, tamanho, props) => ({
  type: 'Feature',
  properties: props,
  geometry: {
    type: 'Polygon',
    coordinates: [[
      [lon, lat], [lon + tamanho, lat], [lon + tamanho, lat + tamanho],
      [lon, lat + tamanho], [lon, lat],
    ]],
  },
});

test('projeção é determinística', () => {
  const p = criarProjecao();
  assert.deepEqual(p([-46.6, -23.5]), p([-46.6, -23.5]));
});

test('Albers preserva a ordem leste-oeste', () => {
  const p = criarProjecao();
  const [xOeste] = p([-70, -10]);
  const [xLeste] = p([-35, -10]);
  assert.ok(xOeste < xLeste, 'oeste deve ficar à esquerda de leste');
});

test('Albers preserva a ordem norte-sul', () => {
  const p = criarProjecao();
  const [, yNorte] = p([-54, 4]);
  const [, ySul] = p([-54, -33]);
  assert.ok(yNorte < ySul, 'norte deve ficar acima de sul no SVG');
});

test('áreas iguais em latitudes diferentes ficam comparáveis', () => {
  // O ponto de usar Albers: Mercator infla o extremo sul em ~2x.
  const p = criarProjecao();
  const areaEm = (lat) => {
    const [x0, y0] = p([-54, lat]);
    const [x1] = p([-53, lat]);
    const [, y1] = p([-54, lat + 1]);
    return Math.abs((x1 - x0) * (y1 - y0));
  };
  const razao = areaEm(-30) / areaEm(-2);
  assert.ok(razao > 0.8 && razao < 1.25, `distorção alta demais: ${razao}`);
});

test('desenha um path por feição e extrai o código do IBGE', () => {
  const geo = {
    type: 'FeatureCollection',
    features: [
      quadrado(-50, -20, 2, { codarea: '35' }),
      quadrado(-40, -12, 2, { codarea: '29' }),
    ],
  };
  const formas = desenharGeoJson(geo, { largura: 400, altura: 300 });
  assert.equal(formas.length, 2);
  assert.deepEqual(formas.map((f) => f.codigo), ['35', '29']);
  assert.ok(formas[0].d.startsWith('M'));
  assert.ok(formas[0].d.endsWith('Z'));
});

test('desenho cabe dentro da caixa pedida', () => {
  const geo = {
    type: 'FeatureCollection',
    features: [quadrado(-60, -30, 25, { codarea: '1' })],
  };
  const [forma] = desenharGeoJson(geo, { largura: 200, altura: 100, margem: 5 });
  const numeros = forma.d.slice(1, -1).split('L')
    .flatMap((par) => par.split(',').map(Number));
  const xs = numeros.filter((_, i) => i % 2 === 0);
  const ys = numeros.filter((_, i) => i % 2 === 1);
  assert.ok(Math.min(...xs) >= 0 && Math.max(...xs) <= 200);
  assert.ok(Math.min(...ys) >= 0 && Math.max(...ys) <= 100);
});

test('quebras por quantil resistem a outlier', () => {
  const valores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000];
  const quebras = calcularQuebras(valores);
  assert.equal(quebras.length, RAMPA.length - 1);
  assert.ok(quebras[0] < 5, 'a primeira quebra não pode ser puxada pelo outlier');
});

test('valor ausente recebe a cor de sem-dado, nunca a cor de zero', () => {
  const quebras = calcularQuebras([1, 2, 3, 4, 5, 6, 7]);
  assert.equal(corDe(null, quebras), 'var(--sem-dado)');
  assert.equal(corDe(NaN, quebras), 'var(--sem-dado)');
  assert.notEqual(corDe(0, quebras), 'var(--sem-dado)');
});

test('cor sobe monotonicamente com o valor', () => {
  const valores = [10, 20, 30, 40, 50, 60, 70, 80];
  const quebras = calcularQuebras(valores);
  const indices = valores.map((v) => RAMPA.indexOf(corDe(v, quebras)));
  for (let i = 1; i < indices.length; i += 1) {
    assert.ok(indices[i] >= indices[i - 1], 'rampa deve ser monotônica');
  }
});

test('sem valores, tudo fica sem-dado', () => {
  assert.equal(corDe(5, calcularQuebras([])), 'var(--sem-dado)');
});

/* --------------------------------------------------- rótulos e centroides */

test('centroide de área não é puxado pelo lado com mais vértices', () => {
  // Quadrado 0..10, mas a aresta de baixo tem dez vezes mais pontos. A média
  // de vértices desceria o rótulo para lá; o centroide de área não.
  const denso = [];
  for (let x = 0; x <= 10; x += 1) denso.push([x, 0]);
  const anel = [...denso, [10, 10], [0, 10]];
  const { centro } = centroideDeAnel(anel);
  assert.ok(Math.abs(centro[0] - 5) < 0.01, `x=${centro[0]}`);
  assert.ok(Math.abs(centro[1] - 5) < 0.5,
    `y=${centro[1]} — a média de vértices daria ~1,5`);
});

test('anel degenerado cai para o centro da caixa em vez de NaN', () => {
  const { centro, area } = centroideDeAnel([[3, 4], [3, 4], [3, 4]]);
  assert.equal(area, 0);
  assert.deepEqual(centro, [3, 4]);
  assert.ok(Number.isFinite(centro[0]) && Number.isFinite(centro[1]));
});

test('o rótulo vai no maior anel, não no primeiro', () => {
  // MultiPolygon cujo PRIMEIRO anel é uma ilhota longe do continente. Escrever
  // o nome do estado sobre a ilha é o defeito que este teste impede.
  const geo = { features: [{
    properties: { codarea: '35', nome: 'Teste' },
    geometry: { type: 'MultiPolygon', coordinates: [
      [[[-40, -25], [-39.9, -25], [-39.9, -24.9], [-40, -24.9]]],
      [[[-52, -23], [-46, -23], [-46, -20], [-52, -20]]],
    ] },
  }] };
  const [forma] = desenharGeoJson(geo, { largura: 300, altura: 300 });
  assert.ok(forma.centro, 'a forma precisa trazer um centro para o rótulo');
  assert.ok(forma.caixa > 20,
    'a caixa deve descrever o anel grande, e é ela que decide se cabe rótulo');

  // O centro tem de cair dentro do continente desenhado, não sobre a ilhota.
  const xs = [...forma.d.matchAll(/[ML]([-\d.]+),/g)].map((m) => Number(m[1]));
  assert.ok(forma.centro[0] > Math.min(...xs) && forma.centro[0] < Math.max(...xs));
});

test('a caixa da forma é o menor lado, que é o que limita o texto', () => {
  const geo = { features: [{
    properties: { codarea: '99', nome: 'Fita' },
    // Retângulo bem largo e baixo: cabe pouco texto, e é a altura que manda.
    geometry: { type: 'Polygon', coordinates: [
      [[-60, -10], [-40, -10], [-40, -9.5], [-60, -9.5]],
    ] },
  }] };
  const [forma] = desenharGeoJson(geo, { largura: 400, altura: 400 });
  assert.ok(forma.caixa < 40, `caixa=${forma.caixa} deveria ser o lado curto`);
});

/* ------------------------------------------------ o rótulo e a escala */

test('a folha de estilo não define o corpo do rótulo', async () => {
  // Regra de folha de estilo vence ATRIBUTO de apresentação do SVG. Quando o
  // `.rotulo` tinha `font-size` no CSS, o `setAttribute('font-size', ...)`
  // que compensa o zoom era ignorado e os nomes cresciam junto com o mapa,
  // até um município tapar meio estado. Quem define o corpo é o `style`
  // inline, em painel.js. Este teste existe para a regra não voltar ao CSS.
  const { readFile } = await import('node:fs/promises');
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const bloco = css.match(/svg#mapa text\.rotulo[^{]*\{[^}]*\}/g) || [];
  assert.ok(bloco.length, 'o seletor do rótulo sumiu do CSS');
  for (const regra of bloco) {
    assert.ok(!/font-size/.test(regra),
      `font-size no CSS do rótulo anula a compensação de zoom:\n${regra}`);
    assert.ok(!/stroke-width/.test(regra),
      `stroke-width no CSS do rótulo engrossa o halo ao aproximar:\n${regra}`);
  }
});

test('a forma traz largura além do menor lado', () => {
  const geo = { features: [{
    properties: { codarea: '99', nome: 'Fita' },
    geometry: { type: 'Polygon', coordinates: [
      [[-60, -10], [-40, -10], [-40, -9.5], [-60, -9.5]],
    ] },
  }] };
  const [forma] = desenharGeoJson(geo, { largura: 400, altura: 400 });
  assert.ok(forma.largura > forma.caixa,
    'num ente comprido e baixo, a largura tem de ser maior que o menor lado');
});

test('nome comprido é partido no espaço mais próximo do meio', async () => {
  // A função vive em painel.js, que toca o DOM. A regra em si é pura, então
  // ela é reproduzida aqui — se mudar lá, este teste deixa de descrever o
  // comportamento e é para ser atualizado junto.
  const partir = (nome) => {
    const espacos = [];
    for (let i = 0; i < nome.length; i += 1) if (nome[i] === ' ') espacos.push(i);
    if (!espacos.length) return null;
    const meio = nome.length / 2;
    const corte = espacos.reduce((a, b) =>
      (Math.abs(b - meio) < Math.abs(a - meio) ? b : a));
    return [nome.slice(0, corte), nome.slice(corte + 1)];
  };

  assert.deepEqual(partir('Salinas da Margarida'), ['Salinas da', 'Margarida']);
  assert.deepEqual(partir('São Sebastião do Passé'),
    ['São Sebastião', 'do Passé']);
  assert.equal(partir('Salvador'), null, 'sem espaço não há onde partir');
});

test('o CSS do mapa não escala a espessura da divisa', async () => {
  // Sem `non-scaling-stroke`, aproximar 8× engrossa a divisa 8× e o mapa vira
  // uma grade preta com manchas de cor no meio.
  const { readFile } = await import('node:fs/promises');
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const regra = css.match(/svg#mapa path \{[^}]*\}/);
  assert.ok(regra, 'a regra do polígono sumiu do CSS');
  assert.match(regra[0], /vector-effect:\s*non-scaling-stroke/);
});

test('o foco não desenha a caixa delimitadora', async () => {
  // `outline` no SVG é o retângulo que envolve a forma — num estado recortado
  // como a Bahia, um retângulo que não tem nada a ver com o contorno.
  const { readFile } = await import('node:fs/promises');
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const foco = css.match(/svg#mapa path:focus-visible \{[^}]*\}/g) || [];
  assert.ok(foco.length, 'o seletor de foco sumiu — o teclado ficaria sem indicação');
  assert.ok(foco.some((r) => /outline:\s*none/.test(r)),
    'o outline precisa ser desligado explicitamente');
  assert.match(css, /path:focus-visible[^{]*\{[^}]*stroke:/,
    'desligar o outline sem pôr contorno deixaria o teclado sem foco visível');
});

/* ------------------------------------------------------ escala do dinheiro */

test('a casa do valor aparece a partir de um milhão', () => {
  // A regra vive em painel.js, que toca o DOM; a formatação em si é pura.
  const compacto = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL',
    notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 2,
  });
  const cheio = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  });
  const curto = (v) => (Math.abs(v) >= 1e6 ? compacto : cheio).format(v);

  // O símbolo vem SEMPRE antes do número — era "430.987.853 R$ mil".
  for (const v of [5472, 149164574, 81379195222]) {
    assert.ok(curto(v).startsWith('R$'), `${curto(v)} não começa com R$`);
  }

  assert.match(curto(81379195222), /bi$/, 'bilhão precisa dizer "bi"');
  assert.match(curto(149164574), /mi$/, 'milhão precisa dizer "mi"');
  assert.match(curto(4.31e12), /tri$/, 'trilhão precisa dizer "tri"');
  assert.ok(!/mil|mi|bi|tri/.test(curto(5472)),
    'despesa por habitante fica por extenso: "R$ 5,47 mil" esconde reais');
});

test('"R$ mil" do IBGE são milhares de reais', () => {
  // O PIB da Bahia vem como 430.987.853 com unidade "R$ mil". Exibir o número
  // cru com R$ na frente erraria por MIL vezes — R$ 430 milhões em vez de
  // R$ 430 bilhões.
  const converter = (valor, unidade) =>
    (/^R\$\s*mil$/i.test(String(unidade).trim()) ? valor * 1000 : valor);

  assert.equal(converter(430987853, 'R$ mil'), 430987853000);
  assert.equal(converter(23531, 'R$'), 23531);
  assert.equal(converter(14870907, 'pessoas'), 14870907);
});


/* ==================================================================
 *  Contraste — o que só se descobre calculando
 * ==================================================================
 *
 * Estes testes existem porque três defeitos graves de legibilidade passaram
 * por revisão visual sem serem notados: o botão principal a 2,18:1 no tema
 * escuro, os avisos amarelos a 3,03:1 no claro, e o rótulo do mapa a 1,01:1
 * sobre a primeira faixa da rampa. Nenhum "parecia" errado. Contraste não se
 * revisa de olho — se calcula.
 */

function luminancia(hex) {
  const h = String(hex).replace('#', '');
  const c = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

function razao(a, b) {
  const [la, lb] = [luminancia(a), luminancia(b)];
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Os tokens de cor de cada tema, lidos da folha de estilo. */
async function tokens() {
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const iEscuro = css.indexOf('@media (prefers-color-scheme: dark)');
  const iFim = css.indexOf('*, *::before');
  const ler = (bloco) => Object.fromEntries(
    [...bloco.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
  const claro = ler(css.slice(0, iEscuro));
  return { claro, escuro: { ...claro, ...ler(css.slice(iEscuro, iFim)) } };
}

const PARES = [
  ['texto', 'superficie', 4.5, 'corpo'],
  ['texto-fraco', 'superficie', 4.5, 'texto de apoio'],
  ['texto-fraco', 'superficie-2', 4.5, 'apoio na linha zebrada'],
  ['realce', 'superficie', 4.5, 'link'],
  ['realce', 'realce-fraco', 4.5, 'etiqueta'],
  ['contra', 'superficie', 4.5, 'alerta'],
  ['contra', 'contra-fraco', 4.5, 'selo de risco'],
  ['atencao', 'superficie', 4.5, 'a conferir'],
  ['atencao', 'atencao-fraco', 4.5, 'selo de atenção'],
  ['atencao', 'superficie-3', 4.5, 'WARNING no log'],
  ['sobre-realce', 'realce', 4.5, 'BOTÃO PRINCIPAL'],
];

test('todo par de cor passa em AA, nos dois temas', async () => {
  const { claro, escuro } = await tokens();
  for (const [nome, mapa] of [['claro', claro], ['escuro', escuro]]) {
    for (const [frente, fundo, minimo, onde] of PARES) {
      assert.ok(mapa[frente] && mapa[fundo], `token ausente no tema ${nome}`);
      const r = razao(mapa[frente], mapa[fundo]);
      assert.ok(r >= minimo,
        `${nome}: ${onde} (${frente} sobre ${fundo}) tem ${r.toFixed(2)}:1, `
        + `abaixo de ${minimo}:1`);
    }
  }
});

test('a tinta sobre o realce NÃO é branco fixo', async () => {
  // O defeito exato: `color: #fff` cravado enquanto o fundo era token. No
  // tema escuro o verde clareia e o par cai para 2,18:1.
  const { claro, escuro } = await tokens();
  assert.notEqual(claro['sobre-realce'], escuro['sobre-realce'],
    'a tinta do botão principal precisa mudar com o tema');
});

test('o rótulo do mapa é legível sobre QUALQUER faixa da rampa', () => {
  // Uma tinta só não serve: sete faixas de quase branco a quase preto não
  // têm cor de texto que sirva às duas pontas. O pior caso com tinta fixa
  // era 1,7:1 — salvo apenas pelo halo.
  for (const cor of RAMPA) {
    const { tinta } = tintaSobre(cor);
    const r = razao(tinta, cor);
    assert.ok(r >= 4.0,
      `rótulo sobre ${cor} tem ${r.toFixed(2)}:1 — ilegível sem o halo`);
  }
});

test('o halo do rótulo é o oposto da tinta', () => {
  for (const cor of RAMPA) {
    const { tinta, halo } = tintaSobre(cor);
    assert.ok(razao(tinta, halo) > 10,
      'halo e tinta precisam ser opostos, senão o contorno não separa nada');
  }
});

test('a rampa tem uma versão por tema', async () => {
  const codigo = await readFile(new URL('../publico/mapa.js', import.meta.url), 'utf8');
  assert.match(codigo, /RAMPA_CLARA/);
  assert.match(codigo, /RAMPA_ESCURA/);
  // No escuro a rampa constante deixava `--sem-dado` MAIS ESCURO que
  // qualquer valor: o olho lia ausência como o extremo da escala, enquanto o
  // rodapé dizia "cinza = sem dado coletado".
  const escura = codigo.match(/const RAMPA_ESCURA = \[([^\]]+)\]/s)[1]
    .match(/#[0-9a-f]{6}/g);
  const semDado = '#2f353a';
  assert.ok(luminancia(escura.at(-1)) > luminancia(semDado),
    'a faixa mais alta da rampa escura tem de ser mais clara que o sem-dado');
});

test('faixaDe e corDe concordam', () => {
  const quebras = calcularQuebras([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  for (const v of [1, 3, 5, 7, 10]) {
    assert.equal(corDe(v, quebras), RAMPA[faixaDe(v, quebras)]);
  }
});

/* ==================================================================
 *  O painel monta HTML com template string
 * ==================================================================
 *
 * Nenhum destes campos é nosso: ementa de projeto de lei, nome de político do
 * TSE, rótulo de conta do SICONFI, mensagem de erro de coletor. Um `<` numa
 * ementa quebra a tabela em silêncio, e o caminho daí em diante é curto.
 */

const fonte = async () => {
  const painel = await readFile(new URL('../publico/painel.js', import.meta.url), 'utf8');
  const formatadores = await readFile(new URL('../publico/nucleo/formatadores.js', import.meta.url), 'utf8');
  const mapa = await readFile(new URL('../publico/secoes/mapa.js', import.meta.url), 'utf8');
  const politicos = await readFile(new URL('../publico/secoes/politicos.js', import.meta.url), 'utf8');
  return `${painel}\n${formatadores}\n${mapa}\n${politicos}`;
};

test('existe um escapador e ele trata as três entidades', async () => {
  const js = await fonte();
  // Recorte por linhas, não por `;`: as próprias entidades contêm `;`.
  const bloco = js.match(/const escapar = [\s\S]{0,240}/);
  assert.ok(bloco, 'a função de escape sumiu');
  for (const entidade of ['&amp;', '&lt;', '&gt;']) {
    assert.ok(bloco[0].includes(entidade), `escapar não produz ${entidade}`);
  }
  // `&` PRIMEIRO, senão o `&lt;` recém-criado vira `&amp;lt;`.
  assert.ok(bloco[0].indexOf('&amp;') < bloco[0].indexOf('&lt;'),
    'o & tem de ser escapado antes do <, senão o escape se escapa a si mesmo');
});

test('atributo escapa aspas, além do que escapar já faz', async () => {
  const js = await fonte();
  const bloco = js.match(/const atributo = [\s\S]{0,200}/);
  assert.ok(bloco, 'a função de escape de atributo sumiu');
  assert.match(bloco[0], /&quot;/,
    'uma aspa dentro de data-uf="…" fecha o atributo e o resto vira marcação');
});

test('endereço da fonte só aceita http e https', async () => {
  const js = await fonte();
  const bloco = js.match(/const endereco = [^\n]*\{[\s\S]*?\n\};/);
  assert.ok(bloco, 'a validação de endereço sumiu');
  assert.match(bloco[0], /https?:/,
    'a API controla url_norma e url de proposição; um href aceita javascript:');
});

test('os campos de terceiros nunca entram crus no HTML', async () => {
  const js = await fonte();
  // Campos que vêm de texto livre de terceiros. Se algum aparecer numa
  // interpolação sem passar por escapar/txt/atributo, é injeção esperando.
  const arriscados = ['ementa', 'nome_politico', 'nome_autor', 'descricao',
                      'rotulo_conta', 'observacao', 'despacho', 'detalhe'];
  const cruas = [];
  for (const campo of arriscados) {
    const re = new RegExp(`\\$\\{[a-z]+\\.${campo}(\\s*\\?\\?[^}]*)?\\}`, 'g');
    for (const m of js.matchAll(re)) cruas.push(m[0]);
  }
  assert.deepEqual(cruas, [],
    `interpolação sem escape: ${cruas.join(', ')}`);
});

test('data só-data é lida ao meio-dia, não à meia-noite UTC', async () => {
  const js = await fonte();
  assert.match(js, /T12:00:00/,
    'new Date("2024-05-01") é meia-noite UTC; em UTC−3 imprime 30/04/2024, '
    + 'e o painel passa a discordar do Diário Oficial por um dia');
});

test('o diálogo rola por dentro', async () => {
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const conteudo = css.match(/#detalhe-conteudo \{[^}]*\}/);
  assert.ok(conteudo, 'o seletor do conteúdo do diálogo sumiu');
  assert.match(conteudo[0], /overflow-y:\s*auto/,
    'sem rolagem, o conteúdo que passa de 88vh fica inalcançável');
  // `flex: 1` significa `flex-basis: 0` — num contêiner de altura automática
  // o único filho parte do zero e o diálogo abre VAZIO.
  assert.ok(!/flex:\s*1;/.test(conteudo[0]),
    'flex:1 (basis 0) colapsa o conteúdo; use flex: 1 1 auto');
});

test('a barra de abas rola em vez de estourar a página', async () => {
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const nav = css.match(/nav \{[^}]*\}/m) || css.match(/\.drawer-nav-lista \{[^}]*\}/m);
  assert.ok(nav, 'a regra da nav sumiu');
  assert.match(nav[0], /overflow-x:\s*auto|overflow-y:\s*auto/,
    'seis abas somam ~610px: abaixo disso o body inteiro ganhava rolagem '
    + 'horizontal e as últimas abas sumiam sem aviso');
});

test('o cabeçalho não gruda no topo', async () => {
  // 156px de cabeçalho fixo numa janela de 638px é um quarto da tela ocupado
  // o tempo todo — e a barra de filtros passava por baixo dele assim que a
  // página rolava, que é justamente quando se quer mexer no filtro.
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  const regra = css.match(/header \{[^}]*\}/m) || css.match(/\.topbar-trigo \{[^}]*\}/m);
  assert.ok(regra, 'a regra do cabeçalho sumiu');
  assert.ok(!/position:\s*sticky/.test(regra[0]),
    'cabeçalho grudado cobre a barra de filtros em janela baixa');
});

test('janela baixa esconde o subtítulo do cabeçalho', async () => {
  const css = await readFile(new URL('../publico/estilo.css', import.meta.url), 'utf8');
  assert.match(css, /@media \(max-height: 700px\)|@media \(max-width: 768px\)/,
    'sem isso o cabeçalho come 156px de uma tela de 638px');
});

test('a dica do político usa UM ouvinte, não um por linha', async () => {
  // O limite da consulta é 300: instalar por linha seriam 900 registros de
  // evento a cada busca, todos descartados na busca seguinte.
  const js = await fonte();
  const bloco = js.match(/function ligarDicaDePoliticos\(\)[\s\S]*?\n\}/);
  assert.ok(bloco, 'a delegação da dica sumiu');
  assert.match(bloco[0], /tbody'\)/,
    'o ouvinte tem de ficar no corpo da tabela');
  assert.match(bloco[0], /closest\('tr\[data-politico\]'\)/,
    'sem `closest` a delegação não sabe qual linha está sob o ponteiro');
});

test('a dica do político não afirma remuneração individual', async () => {
  // O acervo tem subsídio por CARGO, não folha por pessoa. Mostrar o número
  // embaixo de um nome, sem a ressalva, afirma quanto AQUELA pessoa recebe.
  const js = await fonte();
  const bloco = js.match(/function dicaDoPolitico\(p\)[\s\S]*?\n\}/);
  assert.ok(bloco, 'a dica do político sumiu');
  assert.match(bloco[0], /não desta pessoa/,
    'o subsídio é do cargo e a dica precisa dizer isso');
  assert.match(bloco[0], /subsidio_conferido === false/,
    'valor não conferido tem de aparecer marcado');
});

/* ------------------------------------------------------- anos e cobertura
 *
 * Estes testes existem por um incidente real: o `/api/anos` passou a
 * devolver objeto em vez de lista de números. O `painel.js` é estático e o
 * navegador pegou a versão nova no primeiro F5; o servidor Python continuou
 * com o processo antigo em memória. Nessa janela o painel inteiro disse
 * "sem dados" — com o acervo intacto no disco.
 */

/** Executa `normalizarAnos` extraída do fonte, sem navegador. */
async function normalizarAnos(resposta) {
  const js = await fonte();
  const bloco = js.match(/function normalizarAnos\(resposta\) \{[\s\S]*?\n\}/);
  assert.ok(bloco, 'normalizarAnos sumiu do painel.js');
  // eslint-disable-next-line no-new-func
  return new Function(`${bloco[0]}; return normalizarAnos(${JSON.stringify(resposta)});`)();
}

test('aceita o formato NOVO: objeto com anos e padrão', async () => {
  const r = await normalizarAnos({
    anos: [{ ano: 2026, completo: false, blocos: ['despesa_funcao'] },
           { ano: 2025, completo: true, blocos: ['financas'] }],
    padrao: 2025,
  });
  assert.equal(r.padrao, 2025, 'abriu no ano parcial havendo completo');
  assert.equal(r.anos.length, 2);
});

test('aceita o formato ANTIGO: lista de números', async () => {
  // O caso do incidente: front novo, backend ainda não reiniciado.
  const r = await normalizarAnos([2026, 2025, 2024]);
  assert.equal(r.anos.length, 3, 'o seletor ficaria "sem dados"');
  assert.equal(r.padrao, 2026);
  assert.equal(r.anos[0].ano, 2026);
});

test('resposta quebrada não zera o painel sem dizer nada', async () => {
  for (const ruim of [null, undefined, {}, { anos: null }]) {
    const r = await normalizarAnos(ruim);
    assert.deepEqual(r.anos, [], 'devolveu algo inesperado');
    assert.equal(r.padrao, null);
  }
});
