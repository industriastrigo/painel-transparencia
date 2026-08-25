/* Testes do desenho do mapa (sem navegador).
 *
 *   node --test testes/teste_mapa.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  criarProjecao, desenharGeoJson, calcularQuebras, corDe, RAMPA,
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
