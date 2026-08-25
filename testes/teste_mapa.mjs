/* Testes do desenho do mapa (sem navegador).
 *
 *   node --test testes/teste_mapa.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  criarProjecao, desenharGeoJson, calcularQuebras, corDe, RAMPA,
  centroideDeAnel,
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
