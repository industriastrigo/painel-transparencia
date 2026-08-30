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

/** Centroide de área do anel (fórmula do polígono, não média de vértices).
 *
 * Média de vértices puxa o rótulo para onde a costa tem mais pontos — no
 * Brasil, sempre para o litoral. O centroide de área não tem esse viés.
 * Anel degenerado (área ~0) cai para o centro da caixa, que é o que sobra.
 */
export function centroideDeAnel(pontos) {
  let area2 = 0, cx = 0, cy = 0;
  for (let i = 0, j = pontos.length - 1; i < pontos.length; j = i, i += 1) {
    const [x0, y0] = pontos[j], [x1, y1] = pontos[i];
    const cruz = x0 * y1 - x1 * y0;
    area2 += cruz;
    cx += (x0 + x1) * cruz;
    cy += (y0 + y1) * cruz;
  }
  if (Math.abs(area2) < 1e-9) {
    const xs = pontos.map((p) => p[0]), ys = pontos.map((p) => p[1]);
    return {
      centro: [(Math.min(...xs) + Math.max(...xs)) / 2,
               (Math.min(...ys) + Math.max(...ys)) / 2],
      area: 0,
    };
  }
  return { centro: [cx / (3 * area2), cy / (3 * area2)], area: Math.abs(area2) / 2 };
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
    (x - minX) * escala + deslocX,
    (y - minY) * escala + deslocY,
  ];

  return projetadas.map(({ feicao, aneis }) => {
    const ajustados = aneis.map((anel) => anel.map(ajustar));

    // O rótulo vai no maior anel, não no primeiro: em MultiPolygon o primeiro
    // pode ser uma ilha. Escrever "SP" sobre Ilhabela seria o resultado.
    let maior = { centro: [0, 0], area: -1 };
    let caixa = 0, largura = 0;
    for (const anel of ajustados) {
      const c = centroideDeAnel(anel);
      if (c.area > maior.area) {
        maior = c;
        const xs = anel.map((p) => p[0]), ys = anel.map((p) => p[1]);
        largura = Math.max(...xs) - Math.min(...xs);
        caixa = Math.min(largura, Math.max(...ys) - Math.min(...ys));
      }
    }

    return {
      codigo: String(
        feicao.properties?.codarea ?? feicao.properties?.id ?? feicao.id ?? '',
      ).trim(),
      nome: feicao.properties?.nome ?? feicao.properties?.name ?? '',
      d: ajustados
        .map((anel) => 'M' + anel.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('L') + 'Z')
        .join(''),
      centro: maior.centro,
      // Caixa do maior anel, em px do viewBox. `caixa` é o menor lado (o ente
      // é pequeno demais para qualquer texto?) e `largura` é o lado horizontal
      // (o NOME cabe?). São perguntas diferentes: um município achatado e
      // comprido reprova na primeira e passa na segunda.
      caixa,
      largura,
    };
  });
}

/* ------------------------------------------------------------------ cores */

/** Rampa sequencial de matiz única (verde-azulado).
 *
 *  DUAS rampas, uma por tema, e não uma só. A versão anterior era constante,
 *  e no tema escuro isso produzia dois defeitos ao mesmo tempo:
 *
 *  - o rótulo (`--texto`, quase branco) caía sobre a primeira faixa, quase
 *    branca também: **1,01:1**, ilegível, salvo apenas pelo halo;
 *  - `--sem-dado` escurecia com o tema enquanto a rampa continuava clara,
 *    então o cinza de "sem dado" ficava MAIS ESCURO que qualquer valor. O
 *    olho lia ausência como o extremo da escala, enquanto o rodapé dizia
 *    "cinza = sem dado coletado". Num painel de transparência, é o pior tipo
 *    de erro: o mapa afirmando o contrário do que a legenda promete.
 *
 *  No escuro a rampa vai de escuro para claro — a mesma leitura ("mais tinta
 *  = mais valor") invertida junto com o papel.
 */
const RAMPA_CLARA = [
  '#e4efeb', '#c2ded6', '#9bcabd', '#72b3a2', '#4b9884', '#2b7a67', '#175a4c',
];
const RAMPA_ESCURA = [
  '#12312a', '#17453a', '#1c5b4b', '#22745e', '#2e9077', '#4bae92', '#78cbb2',
];

const _escuro = () => typeof matchMedia === 'function'
  && matchMedia('(prefers-color-scheme: dark)').matches;

/** A rampa do tema em vigor. É `let` + getter para o painel poder redesenhar
 *  quando o usuário troca o tema do sistema com a página aberta. */
export let RAMPA = _escuro() ? RAMPA_ESCURA : RAMPA_CLARA;

const TINTA_ESCURA = '#0d241e';
const TINTA_CLARA = '#f2faf7';

/** Luminância relativa (WCAG). */
function luminancia(hex) {
  const h = String(hex).replace('#', '');
  if (h.length !== 6) return 1;
  const canais = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2];
}

/** A tinta e o halo do rótulo PARA A COR EM QUE ELE CAI.
 *
 *  Uma tinta só para a rampa inteira é impossível: sete faixas que vão de
 *  quase branco a quase preto não têm uma cor de texto que sirva às duas
 *  pontas. Com uma tinta fixa, o pior caso ficava em **1,7:1**.
 *
 *  Escolhendo por faixa — escura sobre as faixas claras, clara sobre as
 *  escuras — o PIOR caso da rampa passa a **4,2:1**. O halo deixa de ser a
 *  única coisa segurando a legibilidade e volta a ser o que devia: reforço.
 *
 *  O limiar 0,19 não é chute: é o ponto em que as duas tintas empatam nas
 *  duas rampas. Ver `testes/teste_mapa.mjs`.
 */
export function tintaSobre(cor) {
  const claro = luminancia(cor) >= 0.19;
  return claro
    ? { tinta: TINTA_ESCURA, halo: TINTA_CLARA }
    : { tinta: TINTA_CLARA, halo: TINTA_ESCURA };
}

/** Reavalia a rampa. Chamada quando o sistema troca de tema. */
export function reavaliarTema() {
  RAMPA = _escuro() ? RAMPA_ESCURA : RAMPA_CLARA;
  return RAMPA;
}

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
  return RAMPA[faixaDe(valor, quebras)];
}

/** O índice da faixa em que este valor cai. Separado de `corDe` porque o
 *  rótulo precisa saber SOBRE QUE COR vai ser escrito. */
export function faixaDe(valor, quebras) {
  let i = 0;
  while (i < quebras.length && valor > quebras[i]) i += 1;
  return i;
}
