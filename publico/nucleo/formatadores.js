/* Formatação, sanitização e tratamento de dados numéricos/textuais. */

const escapar = (v) => (v === null || v === undefined ? '' : String(v)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));

const atributo = (v) => escapar(v).replace(/"/g, '&quot;').replace(/'/g, '&#39;');

/** Texto vindo da API, com travessão quando não veio nada. */
const txt = (v) => (v === null || v === undefined || v === '' ? '—' : escapar(v));

/** Endereço vindo da API, para entrar num `href`.
 *
 *  A API controla `url_norma` e `url` de proposição, e um `href` aceita
 *  `javascript:` — `rel="noopener"` não protege contra isso. Só http e https
 *  passam; qualquer outra coisa vira link nenhum. */
const endereco = (v) => {
  if (!v) return '';
  try {
    const u = new URL(String(v), location.origin);
    return (u.protocol === 'http:' || u.protocol === 'https:') ? atributo(u.href) : '';
  } catch { return ''; }
};

const API = '';
const estado = {
  nivel: 'pais',      // pais | estado
  uf: null,
  ano: null,
  metrica: 'despesa_per_capita',
  rotulos: 'auto',     // auto | todos | nenhum
  entes: [],
  malha: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const dinheiro = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
});
// O `title` promete "o valor exato". Com `maximumFractionDigits: 0` ele
// arredondava os centavos — e o exato de R$ 22.752.837.820,49 virava
// ...820. Quem abre o title está justamente conferindo contra a fonte.
const dinheiroExato = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL', minimumFractionDigits: 2,
});
const data = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' });
const dataHora = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short', timeStyle: 'short',
});

/** null/undefined viram NaN, não 0. Suporta números, strings monetárias brasileiras ("1.900.000,00") e float padrão. */
const aNumero = (v) => {
  if (v === null || v === undefined || v === '') return NaN;
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const s = v.trim();
    if (!s) return NaN;
    if (s.includes(',') && s.includes('.')) {
      return Number(s.replace(/\./g, '').replace(',', '.'));
    }
    if (s.includes(',')) {
      return Number(s.replace(',', '.'));
    }
    return Number(s);
  }
  return Number(v);
};

const porcento = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });
const porcentoExato = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

/** Contagem que distingue nulo de zero — `Intl.format(null)` devolve "0" e
 *  `format(undefined)` devolve "NaN", e os dois apareciam na tela. */
const contagem = (v) => {
  const n = aNumero(v);
  return Number.isFinite(n) ? numero.format(n) : '—';
};

/** R$ com a casa dita por extenso: "R$ 81,38 bi".
 *
 *  Ler "R$ 81.379.195.222" exige contar dígitos de três em três, e é aí que
 *  bilhão vira milhão na cabeça de quem lê. O valor exato não se perde: fica
 *  no `title` de todo lugar que usa esta função — passar o mouse mostra.
 *
 *  `notation: 'compact'` é do próprio Intl, então quem escolhe "mil/mi/bi/tri"
 *  é a tabela do pt-BR, não uma lista minha. */
const _compacto = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL',
  notation: 'compact', minimumFractionDigits: 0, maximumFractionDigits: 2,
});

// Abaixo de um milhão o número inteiro já se lê de relance, e a casa não
// ajuda: "R$ 5,47 mil" é pior que "R$ 5.472" para despesa por habitante,
// porque esconde reais que cabiam na tela. A abreviação começa onde a leitura
// começa a exigir contar dígitos.
const LIMIAR_COMPACTO = 1e6;

/** Teto das consultas de lista. Fica visível na tela quando é atingido —
 *  cortar em silêncio faz o painel parecer completo quando não está. */
const LIMITE_CONSULTA = 300;

/** Situação de coleta → cor do selo. `vazio` é neutro de propósito: a fonte
 *  respondeu e não tinha dado, o que não é erro nosso nem alarme. */
const SELO_SITUACAO = {
  ok: 'calmo', erro: 'risco', parcial: 'atento', configuracao: 'atento',
  sem_dado: 'neutro', vazio: 'neutro', nao_publicado: 'neutro',
};

const dinheiroCurto = { format: (v) =>
  (Math.abs(v) >= LIMIAR_COMPACTO ? _compacto : dinheiro).format(v) };

const formatar = (valor, metrica) => {
  if (!Number.isFinite(valor)) return '—';
  if (metrica === 'populacao') return numero.format(valor);
  if (CONTAGENS.has(metrica)) return numero.format(valor);
  if (PERCENTUAIS.has(metrica)) return `${porcento.format(valor)}%`;
  return dinheiroCurto.format(valor);
};

/** O valor por extenso, para o `title`. */
const exato = (valor, metrica) => {
  if (!Number.isFinite(valor)) return 'sem dado coletado';
  if (metrica === 'populacao') return `${numero.format(valor)} habitantes`;
  if (CONTAGENS.has(metrica)) return numero.format(valor);
  if (PERCENTUAIS.has(metrica)) return `${porcentoExato.format(valor)}%`;
  return dinheiroExato.format(valor);
};

/** Fatia percentual de um total. Devolve '—' quando não dá para afirmar.
 *
 *  Antes: `(100 * x.valor / total).toFixed(1)`. Três defeitos numa linha —
 *  `valor` nulo virava "0.0%" (afirmação sobre o mundo) em vez de "—";
 *  `toFixed` escrevia ponto decimal no meio de uma tela em pt-BR; e quando o
 *  total era zero sobrava o literal "%" solto depois do travessão. */
const fatia = (valor, total) => {
  const v = aNumero(valor);
  if (!Number.isFinite(v) || !Number.isFinite(total) || total === 0) return '—';
  return `${porcento.format((100 * v) / total)}%`;
};

/** Soma que ignora nulo sem transformá-lo em zero. */
const somar = (linhas, campo = 'valor') => linhas.reduce((s, x) => {
  const v = aNumero(x[campo]);
  return Number.isFinite(v) ? s + v : s;
}, 0);

/** Valor de indicador do IBGE, que vem com a unidade ao lado.
 *
 *  Duas armadilhas aqui. A primeira é cosmética: "430.987.853 R$ mil" põe o
 *  símbolo DEPOIS do número. A segunda não é — **"R$ mil" quer dizer milhares
 *  de reais**, então o PIB da Bahia são R$ 430 bilhões, não R$ 430 milhões.
 *  Exibir o número cru com "R$" na frente erraria por mil vezes. */
const formatarIndicador = (valor, unidade) => {
  const n = aNumero(valor);
  if (!Number.isFinite(n)) return { texto: '—', title: 'sem dado coletado' };

  const u = String(unidade ?? '').trim();
  if (/^R\$\s*mil$/i.test(u)) {
    return { texto: dinheiroCurto.format(n * 1000),
             title: `${dinheiro.format(n * 1000)} — a fonte publica em ${u}` };
  }
  if (/^R\$$/i.test(u)) {
    return { texto: dinheiroCurto.format(n), title: dinheiro.format(n) };
  }
  return { texto: `${numero.format(n)}${u ? ` ${u}` : ''}`,
           title: `${numero.format(n)}${u ? ` ${u}` : ''}` };
};

const ROTULO_METRICA = {
  despesa_per_capita: 'Despesa por habitante',
  despesa_total: 'Despesa total',
  receita_total: 'Arrecadação',
  receita_per_capita: 'Arrecadação por habitante',
  transferencia_recebida: 'Transferências recebidas',
  transferencia_uniao: 'Transferências da União',
  dependencia_transferencia: 'Dependência de transferências',
  despesa_saude: 'Despesa em saúde',
  saude_per_capita: 'Saúde por habitante',
  despesa_educacao: 'Despesa em educação',
  educacao_per_capita: 'Educação por habitante',
  percentual_pessoal: 'Pessoal sobre a receita corrente líquida',
  divida_liquida: 'Dívida consolidada líquida',
  populacao: 'População',
};

/** Métricas que são percentual, não dinheiro. */
const PERCENTUAIS = new Set(['dependencia_transferencia', 'percentual_pessoal']);
// Métricas que são CONTAGEM, não dinheiro. Esta lista existe por um defeito
// real: `formatar()` cai em dinheiro quando não reconhece a métrica, então
// 13 ausências apareceram na tela como "R$ 13". Um nome de métrica errado
// não pode virar reais em silêncio — é a mesma família de erro que o painel
// existe para não cometer.
const CONTAGENS = new Set(['quantidade', 'contagem', 'sessoes', 'notas']);

/** Data da fonte → dd/mm/aaaa, sem perder um dia no caminho.
 *
 *  `new Date("2024-05-01")` é meia-noite **UTC** pela especificação. Em
 *  UTC−3, formatado no fuso local, isso imprime **30/04/2024** — toda data
 *  só-data do painel saía um dia antes da que está na fonte. Numa tela cujo
 *  propósito é ser conferível contra o documento oficial, isso é grave: o
 *  usuário compara com o Diário Oficial e vê duas datas diferentes.
 *
 *  Data com hora (tramitação) é instante de verdade e continua no fuso local
 *  — aí o deslocamento é o comportamento certo. */
const _SO_DATA = /^\d{4}-\d{2}-\d{2}$/;

const formatarData = (texto, comHora = false) => {
  if (!texto) return '—';
  const bruto = String(texto);
  const d = new Date(_SO_DATA.test(bruto) ? `${bruto}T12:00:00` : bruto);
  if (Number.isNaN(d.getTime())) return escapar(bruto.slice(0, 10));
  return (comHora ? dataHora : data).format(d);
};


export {
  escapar, atributo, txt, endereco,
  numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, _compacto,
  formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS, LIMITE_CONSULTA, SELO_SITUACAO
};
