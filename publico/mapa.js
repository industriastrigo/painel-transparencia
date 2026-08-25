/* Mapa coroplético sem biblioteca.
 *
 * Projeção Albers cônica equivalente, não Mercator: num mapa que compara
 * áreas e valores, Mercator infla o Rio Grande do Sul e achata o Amazonas.
 * Albers é o que o IBGE usa em cartografia temática.
 *
 * A cor carrega o valor (rampa sequencial de matiz única, segura para
 * daltônicos). O ranking ao lado é onde a leitura precisa acontece.
 */

export const ALBERS_BR = { lon0: -54, lat0: -12, phi1: -2, phi2: -22 };

const rad = (g) => (g * Math.PI) / 180;

export function criarProjecao({ lon0, lat0, phi1, phi2 } = ALBERS_BR) {
  const p1 = rad(phi1), p2 = rad(phi2), l0 = rad(lon0), f0 = rad(lat0);
  const n = (Math.sin(p1) + Math.sin(p2)) / 2;
  const C = Math.cos(p1) ** 2 + 2 * n * Math.sin(p1);
  const rho0 = Math.sqrt(C - 2 * n * Math.sin(f0)) / n;

  // O y sai negado porque no hemisfério sul n < 0 e a fórmula devolve o eixo
  // crescendo para o norte, enquanto o y do SVG cresce para baixo. Sem isso o
  // Brasil aparece de cabeça para baixo.
  return ([lon, lat]) => {
    const theta = n * (rad(lon) - l0);
    const rho = Math.sqrt(C - 2 * n * Math.sin(rad(lat))) / n;
    return [rho * Math.sin(theta), -(rho0 - rho * Math.cos(theta))];
  };
}

function* percorrerCoordenadas(geometria) {
  const { type, coordinates } = geometria;
  if (type === 'Polygon') for (const anel of coordinates) yield anel;
  else if (type === 'MultiPolygon') for (const p of coordinates) for (const anel of p) yield anel;
}

/** Converte o GeoJSON em paths SVG já ajustados à caixa pedida. */
export function desenharGeoJson(geojson, { largura, altura, margem = 8 }) {
  const projetar = criarProjecao();
  const feicoes = geojson.features || [];

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const projetadas = feicoes.map((f) => {
    const aneis = [];
    for (const anel of percorrerCoordenadas(f.geometry || {})) {
      const pontos = anel.map(projetar);
      for (const [x, y] of pontos) {
        if (x < minX) minX = x; if (x > maxX) maxX = x;
        if (y < minY) minY = y; if (y > maxY) maxY = y;
      }
      aneis.push(pontos);
    }
    return { feicao: f, aneis };
  });

  const escala = Math.min(
    (largura - margem * 2) / (maxX - minX || 1),
    (altura - margem * 2) / (maxY - minY || 1),
  );
  const deslocX = margem + (largura - margem * 2 - (maxX - minX) * escala) / 2;
  const deslocY = margem + (altura - margem * 2 - (maxY - minY) * escala) / 2;
  const ajustar = ([x, y]) => [
    ((x - minX) * escala + deslocX).toFixed(1),
    ((y - minY) * escala + deslocY).toFixed(1),
  ];

  return projetadas.map(({ feicao, aneis }) => ({
    codigo: String(
      feicao.properties?.codarea ?? feicao.properties?.id ?? feicao.id ?? '',
    ).trim(),
    nome: feicao.properties?.nome ?? feicao.properties?.name ?? '',
    d: aneis
      .map((anel) => 'M' + anel.map(ajustar).map((p) => p.join(',')).join('L') + 'Z')
      .join(''),
  }));
}

/* ------------------------------------------------------------------ cores */

/** Rampa sequencial de matiz única (verde-azulado), clara → escura. */
export const RAMPA = [
  '#e4efeb', '#c2ded6', '#9bcabd', '#72b3a2', '#4b9884', '#2b7a67', '#175a4c',
];

/** Quebras por quantil: resiste a outliers, que é a regra em dado municipal. */
export function calcularQuebras(valores, faixas = RAMPA.length) {
  const ordenados = valores.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (ordenados.length === 0) return [];
  const quebras = [];
  for (let i = 1; i < faixas; i += 1) {
    const pos = (i / faixas) * (ordenados.length - 1);
    const baixo = Math.floor(pos), alto = Math.ceil(pos);
    quebras.push(ordenados[baixo] + (ordenados[alto] - ordenados[baixo]) * (pos - baixo));
  }
  return quebras;
}

export function corDe(valor, quebras, semDado = 'var(--sem-dado)') {
  if (!Number.isFinite(valor) || quebras.length === 0) return semDado;
  let i = 0;
  while (i < quebras.length && valor > quebras[i]) i += 1;
  return RAMPA[i];
}
