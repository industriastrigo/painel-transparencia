/* Painel da Transparência — lógica da página.
 *
 * Regra que atravessa o arquivo inteiro: número que não veio do armazém não
 * aparece. Ente sem dado fica cinza e o rodapé diz quantos entes têm dado.
 */

import {
  desenharGeoJson, calcularQuebras, corDe, tintaSobre,
  reavaliarTema, RAMPA,
} from './mapa.js';

/* ------------------------------------------------------------- segurança
 *
 * TODO texto que vem da API passa por aqui antes de entrar em `innerHTML`.
 *
 * O painel monta HTML com template string, e o conteúdo é texto de terceiros
 * por definição: ementa de projeto de lei escrita por assessoria, nome de
 * político do TSE, mensagem de erro de coletor, rótulo de conta do SICONFI.
 * Nenhum deles é hostil hoje — e nenhum deles é nosso. Um `<` numa ementa já
 * basta para quebrar a tabela em silêncio; o resto do caminho é curto.
 *
 * `atributo()` é mais estrito porque uma aspa dentro de `data-uf="…"` fecha o
 * atributo e o que vem depois vira marcação.
 */
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

/** null/undefined viram NaN, não 0.
 *  `Number(null)` é 0 em JavaScript — era isso que escrevia "R$ 0" nos 27
 *  estados de um ano sem coleta, três centímetros abaixo de um rodapé
 *  dizendo "cinza = ainda não coletado, não zero". */
const aNumero = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));

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

async function buscar(rota, parametros = {}, { sinal } = {}) {
  const url = new URL(API + rota, location.origin);
  Object.entries(parametros).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  });
  const resp = await fetch(url, { signal: sinal });
  if (!resp.ok) throw new Error(`${resp.status} em ${rota}`);
  return resp.json();
}

/* --------------------------------------------------- estados compartilhados
 *
 * Três estados, três aparências. Antes eram dois, e o que faltava era o
 * terceiro: **falha de servidor renderizada como "não há dados"**. A tela
 * dizia "Nenhuma proposição coletada. Use a aba Atualizar" quando o acervo
 * estava cheio e quem tinha caído era a API — mandando o usuário coletar de
 * novo o que já estava no disco.
 *
 * Ausência é uma afirmação sobre o acervo; falha é uma afirmação sobre o
 * servidor. Trocar uma pela outra é a mesma família de erro que trocar cinza
 * por zero no mapa.
 */
/** Sentinela de falha, para distinguir de "veio vazio". */
const FALHOU = Symbol('falhou');

const esqueleto = (linhas = 4) =>
  `<div class="esqueleto" aria-hidden="true">${'<i></i>'.repeat(linhas)}</div>`;

const falha = (oQue, erro) =>
  `<p class="vazio falhou">${escapar(oQue)}<br>`
  + `<span class="rodape-mapa">${escapar(erro?.message || 'sem resposta do servidor')}`
  + ` — o painel está no ar, a consulta é que falhou. Tente de novo.</span></p>`;

const falhaEmLinha = (colunas, oQue, erro) =>
  `<tr><td colspan="${colunas}" class="vazio falhou">${escapar(oQue)}<br>`
  + `<span class="rodape-mapa">${escapar(erro?.message || 'sem resposta')}</span></td></tr>`;

/** Abre o diálogo já rotulado. Sem `aria-labelledby` o leitor anuncia só
 *  "diálogo" — e o título só existe depois que a resposta chega. */
function abrirDialogo(dialogo, rotuloProvisorio) {
  dialogo.setAttribute('aria-label', rotuloProvisorio);
  dialogo.removeAttribute('aria-labelledby');
  if (!dialogo.open) dialogo.showModal();
}

/* ---------------------------------------------------------------- abas */

/** Abas já carregadas com SUCESSO.
 *
 *  Antes a condição era "o tbody está vazio?" — e todo caminho de erro
 *  INSERE uma linha ("Sem resultados", "Não deu para buscar"). Resultado: se
 *  a primeira visita à aba falhou, ela nunca mais tentava de novo. Só
 *  recarregando a página. Marcar o sucesso, e não a ausência de linhas,
 *  desfaz isso: falhou, tenta na próxima visita. */
const abasCarregadas = new Set();

function trocarAba(destino, { focar = false } = {}) {
  $$('nav button').forEach((b) => {
    const ativa = b.dataset.aba === destino;
    b.setAttribute('aria-selected', String(ativa));
    // Roving tabindex: o conjunto de abas é UMA parada de Tab, não seis.
    b.tabIndex = ativa ? 0 : -1;
  });
  $$('main section').forEach((sec) => { sec.hidden = sec.id !== `aba-${destino}`; });

  if (focar) $(`#aba-${destino}`)?.focus();
  if (location.hash.slice(1) !== destino) history.replaceState(null, '', `#${destino}`);

  const carregar = {
    politicos: carregarPoliticos,
    proposicoes: () => montarFiltrosDeProposicao().then(carregarProposicoes),
    custo: carregarCusto,
    atualizar: () => Promise.all([montarCatalogo(), mostrarEstadoDaChave()]),
    fontes: carregarSituacao,
  }[destino];

  if (carregar && !abasCarregadas.has(destino)) {
    abasCarregadas.add(destino);
    Promise.resolve(carregar()).catch((erro) => {
      // Falhou: sai do conjunto para poder tentar de novo na próxima visita.
      abasCarregadas.delete(destino);
      console.error(`aba ${destino}`, erro);
    });
  }
}

/* ---------------------------------------------------------------- mapa */

/** Nomes dos blocos de dado, para dizer o que falta em vez de "não coletado". */
const BLOCOS = {
  financas: 'arrecadação e despesa',
  populacao: 'população',
  despesa_funcao: 'despesa por função',
  indicador_fiscal: 'indicadores da LRF',
  transferencias: 'transferências da União',
};

/** O que falta num ano, por extenso. Vazio quando o ano está completo. */
function faltaNoAno(ano) {
  if (!ano || ano.completo) return [];
  const tem = new Set(ano.blocos || []);
  return Object.entries(BLOCOS)
    .filter(([chave]) => !tem.has(chave))
    .map(([, rotulo]) => rotulo);
}

/** Normaliza a resposta de `/api/anos`, venha ela em que formato vier.
 *
 *  Esta função existe por um defeito de ENTREGA, não de lógica. O `painel.js`
 *  é arquivo estático: o navegador pega a versão nova no primeiro F5. O
 *  servidor Python, não — ele continua com o processo antigo em memória até
 *  alguém reiniciar. Entre uma coisa e outra existe uma janela em que o front
 *  novo conversa com o backend velho.
 *
 *  Nessa janela o front pedia `resposta.anos`, o backend devolvia `[2026,
 *  2025, …]`, e o seletor ficava "sem dados" — o painel inteiro parecia ter
 *  perdido o acervo, com o acervo intacto no disco. Aceitar os dois formatos
 *  custa cinco linhas e faz a atualização deixar de ter esse buraco.
 */
function normalizarAnos(resposta) {
  if (Array.isArray(resposta)) {          // backend antigo: lista de números
    const anos = resposta.map((a) => ({ ano: Number(a), completo: true,
      blocos_com_dado: 0, blocos_no_total: 0, blocos: [] }));
    return { anos, padrao: anos[0]?.ano ?? null };
  }
  const anos = Array.isArray(resposta?.anos) ? resposta.anos : [];
  return { anos, padrao: resposta?.padrao ?? anos[0]?.ano ?? null };
}

async function carregarAnos() {
  const bruta = await buscar('/api/anos').catch(() => null);
  const resposta = normalizarAnos(bruta);
  const anos = resposta.anos;
  const seletor = $('#ano');
  seletor.innerHTML = '';
  if (!anos.length) {
    seletor.innerHTML = '<option>sem dados</option>';
    seletor.disabled = true;
    return null;
  }

  // O ano corrente costuma ter RREO (bimestral) e não ter DCA (anual, sai
  // no exercício seguinte). Abrir nele mostrava metade dos cartões vazios e
  // parecia acervo perdido. O seletor continua oferecendo o ano parcial —
  // ele tem dado legítimo —, mas marcado, e a tela abre no último completo.
  anos.forEach((a) => {
    const rotulo = a.completo ? String(a.ano) : `${a.ano} · parcial`;
    seletor.add(new Option(rotulo, a.ano));
  });

  estado.anos = anos;
  estado.ano = resposta.padrao ?? anos[0].ano;
  seletor.value = estado.ano;
  avisarAnoParcial();
  return estado.ano;
}

/** Diz na tela POR QUE os cartões estão vazios, quando estão. */
function avisarAnoParcial() {
  const alvo = $('#aviso-ano');
  if (!alvo) return;
  const ano = (estado.anos || []).find((a) => a.ano === Number(estado.ano));
  const falta = faltaNoAno(ano);
  if (!falta.length) { alvo.hidden = true; alvo.innerHTML = ''; return; }

  alvo.hidden = false;
  alvo.innerHTML = `<div class="aviso">
    <strong>${escapar(estado.ano)} ainda não está completo na fonte</strong>
    <div>Falta ${falta.map(escapar).join(', ')} — e o que falta aparece como
    <em>não coletado</em> nos cartões. Não é acervo perdido: é o calendário
    das fontes. O RREO é bimestral e já publica o ano corrente; o DCA, de
    onde vêm arrecadação e despesa total, é anual e só sai no exercício
    seguinte.</div>
  </div>`;
}

/** Geração da requisição em voo. Trocar a métrica depressa disparava vários
 *  `carregarMapa()`, e a resposta MAIS LENTA chegava por último — desenhando
 *  dados antigos por cima dos novos, sem nenhum sinal de que isso ocorreu. */
let geracaoMapa = 0;

/** A malha por UF não muda quando só a métrica muda. Refazer o download e
 *  reprojetar 5.570 polígonos a cada troca de métrica custava o mesmo que
 *  trocar de estado. */
const malhasEmCache = new Map();

async function carregarMapa() {
  if (!estado.ano) return;
  const minhaVez = ++geracaoMapa;
  const escopo = estado.uf || 'brasil';

  $('#moldura-mapa')?.setAttribute('aria-busy', 'true');
  try {
    const [resposta, malha] = await Promise.all([
      buscar('/api/mapa', { ano: estado.ano, uf: estado.uf, metrica: estado.metrica }),
      malhasEmCache.get(escopo)
        ?? buscar(`/api/malha/${escopo}`).then((m) => {
          malhasEmCache.set(escopo, m);
          return m;
        }),
    ]);

    // Chegou tarde: outra troca já está em voo. Desenhar agora seria mostrar
    // o recorte anterior como se fosse o pedido.
    if (minhaVez !== geracaoMapa) return;

    estado.entes = resposta.entes;
    estado.malha = malha;
    renderizarMapa(resposta);
    renderizarRanking(resposta);
    renderizarMigalha();
    // O mapa muda de assunto a cada métrica e a cada UF; o nome tem de mudar
    // junto, senão o leitor de tela continua dizendo "Mapa do Brasil" dentro
    // da Bahia.
    $('#mapa')?.setAttribute('aria-label',
      `Mapa de ${escopo === 'brasil' ? 'estados do Brasil' : `municípios de ${escopo}`}`
      + `, ${ROTULO_METRICA[estado.metrica] ?? 'valor'} em ${estado.ano}`);
  } finally {
    if (minhaVez === geracaoMapa) $('#moldura-mapa')?.removeAttribute('aria-busy');
  }
}

/* ------------------------------------------------------- zoom e rótulos */

const NS = 'http://www.w3.org/2000/svg';
const LARGURA = 760, ALTURA = 620;

// Altura mínima, em pixels da tela, para um ente comportar QUALQUER texto.
// Só barra as fatias finas: quem decide de verdade é a medida do nome contra
// a largura do ente, em `encaixarRotulo`.
const CABE_ROTULO = 16;

const zoom = { escala: 1, x: 0, y: 0 };

/** Os rótulos do desenho atual. Guardados no lugar de um `querySelectorAll`
 *  sobre o documento inteiro a cada quadro do zoom. */
let rotulosDesenhados = [];

/** Move e escala o mapa.
 *
 *  `soReposicionar` existe porque reajustar rótulo é CARO: cada um mede o
 *  texto com `getComputedTextLength`, o que força layout síncrono, e são até
 *  cinco medições por rótulo. No mapa de Minas são 853 rótulos — perto de
 *  4.000 reflows por chamada.
 *
 *  E `aplicarZoom` era chamado a cada `pointermove` do arrasto, onde **a
 *  escala não muda**: o reajuste inteiro era trabalho jogado fora, 60 vezes
 *  por segundo. Arrastar agora só mexe no `transform`. */
function aplicarZoom(soReposicionar = false) {
  const grupo = $('#camada-mapa');
  if (!grupo) return;
  grupo.setAttribute('transform',
    `translate(${zoom.x} ${zoom.y}) scale(${zoom.escala})`);
  if (soReposicionar) return;
  // O rótulo vive dentro do grupo que escala, então o corpo da fonte é
  // dividido pela escala para o texto continuar do mesmo tamanho na tela —
  // é o zoom do mapa, não o da tipografia.
  //
  // Via `style`, não via atributo: a regra de folha de estilo vence o atributo
  // de apresentação do SVG, e foi assim que os nomes cresceram junto com o
  // mapa até tapar a Bahia inteira. O `style` inline vence a folha.
  (rotulosDesenhados.length ? rotulosDesenhados : $$('#mapa text.rotulo'))
    .forEach((texto) => {
    if (estado.rotulos === 'nenhum') { texto.style.display = 'none'; return; }
    texto.style.display = '';
    const coube = encaixarRotulo(texto);
    if (!coube && estado.rotulos === 'auto') texto.style.display = 'none';
  });
  $('#zoom-reset').disabled = zoom.escala === 1 && !zoom.x && !zoom.y;
}

/** Comprimento da maior linha do rótulo, em unidades do viewBox.
 *
 *  Medido pelo navegador, não estimado por contagem de caracteres: a conta
 *  "0,52 do corpo por letra" escondia nomes que cabiam — "Salinas da
 *  Margarida" tem muitos caracteres estreitos, e o chute somava a largura de
 *  um "M" para cada "i". */
function medirRotulo(texto) {
  const linhas = texto.children.length ? [...texto.children] : [texto];
  let maior = 0;
  for (const linha of linhas) {
    // getComputedTextLength devolve 0 quando o elemento não está sendo
    // desenhado (aba oculta). Nesse caso o chute antigo ainda serve.
    const medida = linha.getComputedTextLength?.() ?? 0;
    maior = Math.max(maior, medida);
  }
  if (maior > 0) return maior;
  const corpo = Number(texto.dataset.corpo) / zoom.escala;
  return texto.textContent.length * corpo * 0.52;
}

function escreverLinhas(texto, linhas) {
  texto.textContent = '';
  if (linhas.length === 1) { texto.textContent = linhas[0]; return; }
  linhas.forEach((conteudo, i) => {
    const tspan = document.createElementNS(NS, 'tspan');
    tspan.setAttribute('x', texto.getAttribute('x'));
    tspan.setAttribute('dy', i === 0 ? '-0.5em' : '1.05em');
    tspan.textContent = conteudo;
    texto.appendChild(tspan);
  });
}

/** Parte o nome no espaço mais próximo do meio. "Salinas da Margarida" vira
 *  "Salinas da" / "Margarida", não "Salinas" / "da Margarida". */
function partirEmDuas(nome) {
  const espacos = [];
  for (let i = 0; i < nome.length; i += 1) if (nome[i] === ' ') espacos.push(i);
  if (!espacos.length) return null;
  const meio = nome.length / 2;
  const corte = espacos.reduce((a, b) =>
    (Math.abs(b - meio) < Math.abs(a - meio) ? b : a));
  return [nome.slice(0, corte), nome.slice(corte + 1)];
}

/** Escreve o nome do ente do maior jeito que couber.
 *
 *  Antes o rótulo tinha um tamanho só: cabia ou sumia. Agora há três degraus
 *  antes de desistir — encolher um pouco, quebrar em duas linhas, encolher
 *  mais. Sumir é o último recurso, não o primeiro.
 *
 *  Devolve `false` quando nem assim coube.
 */
function encaixarRotulo(texto) {
  const base = Number(texto.dataset.corpo);
  const nome = texto.dataset.nome || texto.textContent;
  const disponivel = Number(texto.dataset.largura) * 0.9;   // unidades do viewBox
  const menorLado = Number(texto.dataset.caixa) * zoom.escala;

  const tentar = (corpo, linhas) => {
    texto.style.fontSize = `${corpo / zoom.escala}px`;
    texto.style.strokeWidth = `${2.4 / zoom.escala}px`;
    escreverLinhas(texto, linhas);
    // A medida sai em unidades do viewBox; `disponivel` também. Comparar nas
    // mesmas unidades dispensa multiplicar pela escala dos dois lados.
    return medirRotulo(texto) * zoom.escala <= disponivel * zoom.escala;
  };

  if (estado.rotulos === 'todos') { tentar(base, [nome]); return true; }

  // Faixa estreita demais para qualquer texto: nem tenta.
  if (menorLado < CABE_ROTULO) { tentar(base, [nome]); return false; }

  if (tentar(base, [nome])) return true;
  if (tentar(base * 0.85, [nome])) return true;

  const duas = partirEmDuas(nome);
  // Duas linhas só onde há altura para elas.
  if (duas && menorLado >= CABE_ROTULO * 1.6) {
    if (tentar(base * 0.9, duas)) return true;
    if (tentar(base * 0.75, duas)) return true;
  }

  tentar(base, [nome]);
  return false;
}

function ajustarZoom(fator, foco) {
  const antes = zoom.escala;
  const novo = Math.min(12, Math.max(1, antes * fator));
  if (novo === antes) return;
  // Mantém sob o cursor o mesmo ponto do mapa que estava lá antes.
  const px = foco ? foco.x : LARGURA / 2;
  const py = foco ? foco.y : ALTURA / 2;
  zoom.x = px - ((px - zoom.x) * novo) / antes;
  zoom.y = py - ((py - zoom.y) * novo) / antes;
  zoom.escala = novo;
  limitarZoom();
  aplicarZoom();
}

/** Impede que o mapa seja arrastado para fora da moldura. */
function limitarZoom() {
  const folgaX = LARGURA * (zoom.escala - 1);
  const folgaY = ALTURA * (zoom.escala - 1);
  zoom.x = Math.min(0, Math.max(-folgaX, zoom.x));
  zoom.y = Math.min(0, Math.max(-folgaY, zoom.y));
}

function reenquadrar() {
  zoom.escala = 1; zoom.x = 0; zoom.y = 0;
  aplicarZoom();
}

/** Converte coordenada da tela para coordenada do viewBox. */
function pontoNoMapa(evento) {
  const svg = $('#mapa');
  const caixa = svg.getBoundingClientRect();
  return {
    x: ((evento.clientX - caixa.left) / caixa.width) * LARGURA,
    y: ((evento.clientY - caixa.top) / caixa.height) * ALTURA,
  };
}

/** Desenha o contorno do ente sob o cursor, sem tocar na ordem do DOM. */
function realcar(d) {
  const realce = $('#realce-mapa');
  if (!realce) return;
  if (!d) { realce.style.display = 'none'; return; }
  realce.setAttribute('d', d);
  realce.style.display = '';
}

/* ------------------------------------------------------------- tooltip */

function linhaDica(rotulo, valor, metrica) {
  const vazio = !Number.isFinite(valor);
  return `<dt>${rotulo}</dt>`
    + `<dd class="${vazio ? 'ausente' : ''}" title="${atributo(exato(valor, metrica))}">`
    + `${vazio ? 'não coletado' : formatar(valor, metrica)}</dd>`;
}

/** A frase da LRF, quando há o que dizer.
 *
 *  `acima_do_limite` é NULO quando o ente publicou o percentual mas não o
 *  limite — e nulo aqui não é "está dentro". Nesse caso mostramos o
 *  percentual sem veredito, porque afirmar qualquer um dos dois seria
 *  inventar. Quem crava o limite é o próprio demonstrativo: ele muda por
 *  esfera e por poder. */
function avisoLRF(ente) {
  const pct = aNumero(ente.percentual_pessoal);
  if (!Number.isFinite(pct)) return '';

  const acima = ente.acima_do_limite;
  const veredito = acima === true ? ' — <strong>acima do limite da LRF</strong>'
    : acima === false ? ' — dentro do limite da LRF'
      : ' (o ente não publicou o limite aplicável)';
  return `<p class="pe ${acima === true ? 'alerta' : ''}">`
    + `${porcento.format(pct)}% da receita corrente líquida vai para pessoal`
    + `${veredito}.</p>`;
}

function mostrarDica(ente, evento) {
  const dica = $('#dica-mapa');
  if (!ente) { dica.hidden = true; return; }
  // Sem `aria-live`: a dica era reescrita a cada ente sob o cursor, e
  // arrastar o mouse pelo mapa enfileirava uma leitura por município
  // atravessado. O leitor de tela chega ao mesmo número pelo `aria-label` do
  // próprio ente, que é onde o foco está.

  const uf = ente.sigla_uf ? `<span class="uf">${escapar(ente.sigla_uf)}</span>` : '';
  dica.innerHTML = `
    <h3>${escapar(ente.nome)}${uf}</h3>
    <dl>
      ${linhaDica('População', aNumero(ente.populacao), 'populacao')}
      ${linhaDica('Arrecadação', aNumero(ente.receita_total), 'receita_total')}
      ${linhaDica('Despesa', aNumero(ente.despesa_total), 'despesa_total')}
      ${linhaDica('Transferências recebidas',
                  aNumero(ente.transferencia_recebida), 'transferencia_recebida')}
      ${linhaDica('Repasses da União',
                  aNumero(ente.transferencia_uniao), 'transferencia_uniao')}
      ${linhaDica('Despesa por habitante',
                  aNumero(ente.despesa_per_capita), 'despesa_per_capita')}
      ${linhaDica('Saúde', aNumero(ente.despesa_saude), 'despesa_saude')}
      ${linhaDica('Educação', aNumero(ente.despesa_educacao), 'despesa_educacao')}
    </dl>
    ${Number.isFinite(aNumero(ente.dependencia_transferencia))
      ? `<p class="pe">${porcento.format(aNumero(ente.dependencia_transferencia))}% da
         arrecadação veio de transferências.</p>` : ''}
    ${avisoLRF(ente)}
    <p class="pe">Receita bruta realizada e despesa empenhada, SICONFI ${estado.ano}.</p>`;

  dica.hidden = false;
  posicionarDica(evento);
}

function posicionarDica(evento) {
  const dica = $('#dica-mapa');
  if (dica.hidden) return;
  const moldura = $('#moldura-mapa').getBoundingClientRect();
  const largura = dica.offsetWidth, altura = dica.offsetHeight;
  let x = evento.clientX - moldura.left + 16;
  let y = evento.clientY - moldura.top + 16;
  // Perto da borda direita ou de baixo, a dica vira para o outro lado em vez
  // de ser cortada pela moldura.
  if (x + largura > moldura.width) x = evento.clientX - moldura.left - largura - 12;
  if (y + altura > moldura.height) y = evento.clientY - moldura.top - altura - 12;
  dica.style.left = `${Math.max(4, x)}px`;
  dica.style.top = `${Math.max(4, y)}px`;
}

/* ---------------------------------------------------------------- desenho */

function renderizarMapa(resposta) {
  const svg = $('#mapa');
  const largura = LARGURA, altura = ALTURA;
  svg.setAttribute('viewBox', `0 0 ${largura} ${altura}`);
  svg.innerHTML = '';

  const camada = document.createElementNS(NS, 'g');
  camada.id = 'camada-mapa';
  svg.appendChild(camada);
  const rotulos = document.createElementNS(NS, 'g');

  rotulosDesenhados = [];
  const porCodigo = new Map(estado.entes.map((e) => [String(e.cod_ibge), e]));
  const valores = estado.entes.map((e) => aNumero(e[estado.metrica]));
  const quebras = calcularQuebras(valores);
  const formas = desenharGeoJson(estado.malha, { largura, altura });

  const ns = NS;
  formas.forEach((forma) => {
    // No mapa do Brasil o código vem com 2 dígitos (UF); no de UF, com 7.
    // Só o Map. O `find` que existia aqui comparava EXATAMENTE o mesmo
    // critério da chave (`String(e.cod_ibge)`), então nunca achava nada que o
    // Map não tivesse achado — mas materializava um array com todos os entes
    // para cada forma sem correspondência. Com 5.570 municípios, isso é
    // O(n²) e milhares de arrays descartados por desenho.
    const ente = porCodigo.get(forma.codigo);
    const valor = ente ? aNumero(ente[estado.metrica]) : NaN;

    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', forma.d);
    const cor = corDe(valor, quebras);
    path.setAttribute('fill', cor);
    const nome = ente?.nome || forma.nome || forma.codigo;
    // O aria-label carrega o valor da MÉTRICA em vigor, não só o nome: é o
    // único caminho pelo qual o leitor de tela chega ao número, porque a
    // dica visual não é lida.
    path.setAttribute('aria-label',
      `${nome}: ${ROTULO_METRICA[estado.metrica] ?? 'valor'} `
      + `${Number.isFinite(valor) ? exato(valor, estado.metrica) : 'sem dado coletado'}`);

    // Sem <title> nativo: ele e a dica apareceriam juntos, dizendo a mesma
    // coisa duas vezes. O aria-label continua servindo ao leitor de tela.
    // `pointerenter` e não `mouseenter`: no celular não existe hover, e a
    // dica — oito valores por ente — era simplesmente inalcançável. Com
    // ponteiro, o toque mostra a dica antes de o clique agir.
    path.addEventListener('pointerenter', (ev) => {
      realcar(forma.d);
      mostrarDica(ente, ev);
    });
    path.addEventListener('pointermove', posicionarDica);
    path.addEventListener('pointerleave', () => {
      realcar(null);
      $('#dica-mapa').hidden = true;
    });
    path.addEventListener('focus', () => {
      realcar(forma.d);
      const caixa = path.getBoundingClientRect();
      mostrarDica(ente, { clientX: caixa.left + caixa.width / 2,
                          clientY: caixa.top + caixa.height / 2 });
    });
    path.addEventListener('blur', () => {
      realcar(null);
      $('#dica-mapa').hidden = true;
    });

    // O rótulo é o nome curto: sigla no mapa do país, nome no da UF.
    const texto = ente?.sigla_uf && estado.nivel === 'pais'
      ? ente.sigla_uf : (ente?.nome || forma.nome);
    if (texto && forma.centro) {
      const marca = document.createElementNS(ns, 'text');
      marca.setAttribute('class',
        `rotulo${estado.nivel === 'pais' ? '' : ' municipio'}`);
      marca.setAttribute('x', forma.centro[0].toFixed(1));
      marca.setAttribute('y', forma.centro[1].toFixed(1));
      marca.dataset.corpo = estado.nivel === 'pais' ? '12' : '10';
      marca.dataset.nome = texto;
      marca.dataset.caixa = String(forma.caixa || 0);
      marca.dataset.largura = String(forma.largura || 0);
      // A tinta é escolhida contra a COR DA FAIXA, não contra o tema da
      // página. Uma tinta só para os sete tons da rampa deixava o pior caso
      // em 1,7:1; por faixa, o pior caso vira 4,2:1.
      const { tinta, halo } = tintaSobre(
        Number.isFinite(valor) ? cor : (getComputedStyle(document.documentElement)
          .getPropertyValue('--sem-dado').trim() || '#dcdcd6'));
      marca.style.setProperty('--tinta-rotulo', tinta);
      marca.style.setProperty('--halo-rotulo', halo);
      marca.textContent = texto;
      rotulos.appendChild(marca);
      rotulosDesenhados.push(marca);
    }

    // No país, clicar desce um nível. Dentro de uma UF, clicar abre a ficha
    // do município — que é onde "quem governa" encontra "quanto gasta".
    const agir = estado.nivel === 'pais'
      ? (ente?.sigla_uf ? () => entrarNaUf(ente.sigla_uf) : null)
      : (ente?.cod_ibge ? () => abrirFicha(ente.cod_ibge) : null);

    if (agir) {
      // Só quem AGE recebe foco. `tabindex` em todo município punha 645
      // paradas de Tab no mapa de SP e 853 no de MG, sem saída — e entes sem
      // ação nem faziam nada ao receber o foco.
      path.setAttribute('role', 'button');
      path.setAttribute('tabindex', '0');
      path.addEventListener('click', agir);
      path.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar') {
          ev.preventDefault(); agir();
        }
      });
    } else {
      path.classList.add('inerte');
      path.setAttribute('role', 'img');
    }
    camada.appendChild(path);
  });

  // O contorno de realce é UM path só, sem preenchimento e sem eventos, que
  // recebe a forma do ente sob o cursor. A alternativa — mover o próprio ente
  // para o fim da fila — reordenava o DOM a cada `mouseenter`, e cada
  // reinserção refaz o hit-test e reinicia a sequência do clique: o mapa
  // mostrava a dica e não abria mais o estado.
  const realce = document.createElementNS(ns, 'path');
  realce.id = 'realce-mapa';
  realce.setAttribute('fill', 'none');
  realce.style.display = 'none';
  camada.appendChild(realce);

  // Rótulos por último: dentro do mesmo grupo que escala, mas depois de todos
  // os polígonos, senão o vizinho desenhado a seguir cobre o nome.
  camada.appendChild(rotulos);
  aplicarZoom();

  renderizarLegenda(quebras);
  $('#rodape-mapa').textContent =
    `${resposta.entes_com_dado} de ${resposta.total_entes} `
    + `${estado.nivel === 'pais' ? 'UFs' : 'municípios'} com dado em ${estado.ano}.`
    + (resposta.entes_com_dado < resposta.total_entes
      ? ' Cinza = ainda não coletado, não zero.' : '');
}

function renderizarLegenda(quebras) {
  const faixa = $('#legenda-faixa');
  faixa.innerHTML = RAMPA.map((cor) => `<i style="background:${cor}"></i>`).join('');
  // As quebras são QUANTIS, não mínimo e máximo — há entes acima e abaixo
  // delas de propósito, para o degradê não ser dominado por outliers. A
  // legenda precisa dizer isso em vez de se apresentar como o intervalo.
  $('#legenda-min').textContent = quebras.length
    ? `p14 ${formatar(quebras[0], estado.metrica)}` : '—';
  $('#legenda-max').textContent = quebras.length
    ? `p86 ${formatar(quebras[quebras.length - 1], estado.metrica)}` : '—';
}

function renderizarRanking(resposta) {
  const lista = $('#ranking');
  const ordenados = resposta.entes
    .filter((e) => Number.isFinite(aNumero(e[estado.metrica])))
    .sort((a, b) => aNumero(b[estado.metrica]) - aNumero(a[estado.metrica]));

  const medida = ROTULO_METRICA[estado.metrica] ?? 'valor';
  $('#titulo-ranking').textContent = estado.nivel === 'pais'
    ? `Estados por ${medida.toLowerCase()}`
    : `Municípios de ${estado.uf} por ${medida.toLowerCase()}`;

  if (!ordenados.length) {
    lista.innerHTML = '<li class="vazio">Nenhum ente com dado neste recorte.</li>';
    return;
  }

  // A barra de proporção mostra a DISTÂNCIA entre as posições. Ordem sozinha
  // faz o 1º e o 2º parecerem vizinhos mesmo quando um vale o triplo.
  const teto = Math.max(...ordenados.map((e) => aNumero(e[estado.metrica])), 0);
  const MOSTRAR = 60;

  lista.innerHTML = ordenados.slice(0, MOSTRAR).map((e, i) => {
    const v = aNumero(e[estado.metrica]);
    const largura = teto > 0 ? Math.max(0, (v / teto) * 100) : 0;
    return `
    <li>
      <span class="barra-proporcao" style="width:${largura.toFixed(1)}%"></span>
      <span class="pos">${i + 1}</span>
      ${estado.nivel === 'pais'
        ? `<button data-uf="${atributo(e.sigla_uf)}" title="${atributo(e.nome)}">${escapar(e.nome)}</button>`
        : `<button data-ente="${atributo(e.cod_ibge)}" title="${atributo(e.nome)}">${escapar(e.nome)}</button>`}
      <span class="valor" title="${atributo(exato(v, estado.metrica))}"
        >${formatar(v, estado.metrica)}</span>
    </li>`;
  }).join('');

  // Cortar em silêncio é esconder: em SP são 585 municípios com dado, e 525
  // sumiam sem nenhum sinal na tela.
  if (ordenados.length > MOSTRAR) {
    lista.insertAdjacentHTML('beforeend',
      `<li class="rodape-mapa" style="border:0">mostrando os ${MOSTRAR} maiores `
      + `de ${contagem(ordenados.length)} com dado</li>`);
  }

  lista.querySelectorAll('button[data-uf]').forEach((b) => {
    b.addEventListener('click', () => entrarNaUf(b.dataset.uf));
  });
  lista.querySelectorAll('button[data-ente]').forEach((b) => {
    b.addEventListener('click', () => abrirFicha(b.dataset.ente));
  });
}

function renderizarMigalha() {
  const migalha = $('#migalha');
  if (!estado.uf) {
    migalha.textContent = 'Brasil';
    return;
  }
  // `String(...)` antes do slice: `cod_ibge` chega como NÚMERO em várias
  // respostas (o resto do arquivo já faz String() por isso), e `.slice` num
  // número lançava TypeError — que derrubava carregarMapa() inteiro numa
  // rejeição silenciosa, sem catch em quatro dos cinco chamadores.
  const codUf = String(estado.entes[0]?.cod_ibge ?? '').slice(0, 2) || null;
  migalha.innerHTML = `<button id="voltar-brasil">Brasil</button> › ${escapar(estado.uf)}`
    + (codUf ? ` · <button id="ficha-uf">ver ficha do estado</button>` : '');

  $('#voltar-brasil')?.addEventListener('click', () => {
    estado.uf = null; estado.nivel = 'pais'; reenquadrar(); carregarMapa();
  });
  $('#ficha-uf')?.addEventListener('click', () => abrirFicha(codUf));
}

function entrarNaUf(uf) {
  if (!uf) return;
  estado.uf = uf; estado.nivel = 'estado';
  reenquadrar();   // o zoom do Brasil não faz sentido sobre outra malha
  carregarMapa();
}

function ligarControlesDoMapa() {
  $('#rotulos').addEventListener('change', (e) => {
    estado.rotulos = e.target.value;
    aplicarZoom();
  });
  $('#zoom-mais').addEventListener('click', () => ajustarZoom(1.5));
  $('#zoom-menos').addEventListener('click', () => ajustarZoom(1 / 1.5));
  $('#zoom-reset').addEventListener('click', reenquadrar);

  $('#tela-cheia').addEventListener('click', () => {
    const cartao = $('#cartao-mapa');
    const ampliado = cartao.classList.toggle('ampliado');
    // O NOME do botão fica estável e o estado vai no `aria-pressed`. Trocar
    // os dois fazia o leitor anunciar "Reduzir, pressionado" — dois jeitos de
    // dizer a mesma coisa, contradizendo-se.
    $('#tela-cheia').setAttribute('aria-pressed', String(ampliado));
    cartao.setAttribute('role', ampliado ? 'region' : 'group');
    cartao.setAttribute('aria-label', 'Mapa ampliado');
    document.body.classList.toggle('com-ampliacao', ampliado);
    if (ampliado) $('#zoom-reset').focus();
    else $('#tela-cheia').focus();
    // O cartão muda de tamanho: o que cabia antes pode não caber agora.
    requestAnimationFrame(() => aplicarZoom());
  });
  // Esc fecha a ampliação — mas só quando não há diálogo aberto por cima.
  // Sem a checagem, um Esc fechava a ficha E saía da ampliação de uma vez.
  document.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Escape') return;
    if ($('#detalhe').open) return;
    if ($('#cartao-mapa').classList.contains('ampliado')) $('#tela-cheia').click();
  });

  const svg = $('#mapa');
  svg.addEventListener('wheel', (ev) => {
    // Sem zoom aplicado, a roda continua rolando a PÁGINA. Antes o
    // `preventDefault` era incondicional e o dedo em cima do mapa prendia a
    // rolagem — no celular, prendia a página inteira.
    if (zoom.escala === 1 && ev.deltaY > 0) return;
    ev.preventDefault();
    ajustarZoom(ev.deltaY < 0 ? 1.18 : 1 / 1.18, pontoNoMapa(ev));
  }, { passive: false });

  // Teclado: mover o mapa com as setas. Com escala 8× o Tab só alcançava o
  // que estivesse enquadrado, e não havia como enquadrar outra coisa sem
  // mouse — o zoom existia e era inutilizável sem ponteiro.
  svg.addEventListener('keydown', (ev) => {
    const passo = ev.shiftKey ? 80 : 26;
    const acao = {
      ArrowLeft: () => { zoom.x += passo; },
      ArrowRight: () => { zoom.x -= passo; },
      ArrowUp: () => { zoom.y += passo; },
      ArrowDown: () => { zoom.y -= passo; },
      '+': () => ajustarZoom(1.3), '=': () => ajustarZoom(1.3),
      '-': () => ajustarZoom(1 / 1.3), _: null,
      0: () => reenquadrar(),
    }[ev.key];
    if (!acao) return;
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(ev.key)) {
      if (zoom.escala === 1) return;   // sem zoom não há para onde mover
      ev.preventDefault();
      acao(); limitarZoom(); aplicarZoom(true);
      return;
    }
    ev.preventDefault();
    acao();
  });

  // Arrastar move o mapa; só a partir de 4px, senão um clique com a mão
  // trêmula vira arrasto e a ficha do município não abre.
  //
  // SEM `setPointerCapture`. Capturar o ponteiro no <svg> faz o `click`
  // seguinte ter o SVG como alvo, e não o <path> — então o clique deixava de
  // entrar no estado, mas SÓ com zoom > 1, que era a condição para capturar.
  // Os ouvintes ficam no `document`, o que também mantém o arrasto vivo
  // quando o ponteiro sai da moldura.
  let arrastando = null;
  let bloquearClique = false;

  const mover = (ev) => {
    if (!arrastando) return;
    const caixa = svg.getBoundingClientRect();
    const dx = ((ev.clientX - arrastando.x) / caixa.width) * LARGURA;
    const dy = ((ev.clientY - arrastando.y) / caixa.height) * ALTURA;
    if (Math.abs(dx) + Math.abs(dy) > 4) bloquearClique = true;
    zoom.x = arrastando.x0 + dx;
    zoom.y = arrastando.y0 + dy;
    limitarZoom();
    aplicarZoom(true);   // a escala não mudou: rótulo não precisa reencaixar
  };

  const soltar = () => {
    if (!arrastando) return;
    arrastando = null;
    document.removeEventListener('pointermove', mover);
    // Um reencaixe só, no fim: o que sumiu por falta de espaço durante o
    // arrasto reaparece, sem pagar o preço a cada quadro.
    aplicarZoom();
  };

  svg.addEventListener('pointerdown', (ev) => {
    // Um arrasto anterior que terminou fora da janela deixaria a trava ligada
    // e engoliria o próximo clique legítimo.
    bloquearClique = false;
    if (zoom.escala === 1) return;
    arrastando = { x: ev.clientX, y: ev.clientY, x0: zoom.x, y0: zoom.y };
    document.addEventListener('pointermove', mover);
    document.addEventListener('pointerup', soltar, { once: true });
    document.addEventListener('pointercancel', soltar, { once: true });
  });

  svg.addEventListener('click', (ev) => {
    if (!bloquearClique) return;
    bloquearClique = false;
    ev.stopPropagation();
    ev.preventDefault();
  }, true);
}

/* ---------------------------------------------------------- ficha do ente */

const POR_EXTENSO_PODER = {
  E: 'Executivo', L: 'Legislativo', J: 'Judiciário',
  M: 'Ministério Público', D: 'Defensoria',
};

/** Uma tabela dentro de um contêiner que rola.
 *
 *  Sem ele, uma tabela de seis colunas empurra a PÁGINA inteira para o lado
 *  no celular — o usuário perde a coluna da esquerda e não descobre por quê.
 *  Quem rola tem de ser a tabela. */
const tabela = (cabecalho, linhas) =>
  `<div class="rolagem"><table><thead><tr>${cabecalho}</tr></thead>`
  + `<tbody>${linhas}</tbody></table></div>`;

/** Cartão de número grande. Distingue ausência de valor com classe própria:
 *  "—" cinza e menor não compete visualmente com um número real ao lado. */
// `textoBruto` para o que já vem pronto e não é dinheiro nem contagem — uma
// taxa de presença, por exemplo. O cartão continua sendo o mesmo objeto na
// tela; só o miolo vem formatado de fora.
const cartaoNumero = (rotulo, valor, metrica, nota = '', exatoNaTela = false,
                      textoBruto = null) => {
  const v = aNumero(valor);
  const vazio = textoBruto == null && !Number.isFinite(v);
  // `exatoNaTela` para valor de NORMA: o subsídio é R$ 41.650,92 e a norma
  // diz isso com centavos. Arredondar um número que a lei fixa é reescrever
  // a lei — diferente de abreviar um total orçamentário de bilhões.
  const texto = textoBruto != null ? textoBruto
    : vazio ? '—'
    : (exatoNaTela ? dinheiroExato.format(v) : formatar(v, metrica));
  return `
    <div class="cartao">
      <div class="rotulo-numero">${escapar(rotulo)}</div>
      <div class="numero-grande${vazio ? ' ausente' : ''}"
           title="${atributo(exato(v, metrica))}">${escapar(texto)}</div>
      ${nota ? `<div class="nota-numero">${escapar(nota)}</div>` : ''}
    </div>`;
};

async function abrirFicha(codIbge) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = esqueleto();
  abrirDialogo(dialogo, 'Ficha do ente');

  let f;
  try {
    f = await buscar(`/api/ente/${encodeURIComponent(codIbge)}`);
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para carregar a ficha deste ente.', erro);
    return;
  }
  if (!f || !f.ente) {
    alvo.innerHTML = '<p class="vazio">Ente não encontrado.</p>';
    return;
  }

  const r = f.resumo || {};
  const governantes = f.governantes ?? [];
  const legislativo = f.legislativo ?? [];
  const financas = f.financas ?? [];
  const funcoes = f.funcoes ?? [];
  const lrf = f.lrf ?? [];
  const indicadores = f.indicadores ?? [];

  alvo.innerHTML = `
    <h2 id="titulo-detalhe">${escapar(f.ente.nome)}${
      f.ente.sigla_uf && f.ente.nivel === 'municipio'
        ? ` <span style="color:var(--texto-fraco)">${escapar(f.ente.sigla_uf)}</span>` : ''}</h2>
    <p class="rodape-mapa">${escapar(f.ente.nivel)}${
      f.ente.regiao ? ` · região ${escapar(f.ente.regiao)}` : ''
      } · código IBGE ${escapar(f.ente.cod_ibge)}${
      f.ano ? ` · dados de ${escapar(f.ano)}` : ''}</p>

    ${resumoDeRisco(r)}

    <h2>Quanto entra e quanto sai</h2>
    <div class="tiras">
      ${cartaoNumero('Arrecadação', r.receita_total, 'receita_total')}
      ${cartaoNumero('Despesa total', r.despesa_total, 'despesa_total')}
      ${cartaoNumero('População', r.populacao, 'populacao')}
      ${cartaoNumero('Despesa por habitante', r.despesa_per_capita, 'despesa_per_capita')}
    </div>

    ${Number.isFinite(aNumero(r.dependencia_transferencia)) ? `
      <p class="rodape-mapa">
        <strong>${porcento.format(aNumero(r.dependencia_transferencia))}%</strong>
        da arrecadação veio de transferências, não de tributo próprio.
        ${aNumero(r.dependencia_transferencia) > 80
          ? ' É o número que explica a dependência do FPM.' : ''}</p>` : ''}

    <h2>Saúde, educação e a folha</h2>
    <div class="tiras">
      ${cartaoNumero('Saúde', r.despesa_saude, 'despesa_saude',
        Number.isFinite(aNumero(r.saude_per_capita))
          ? `${formatar(aNumero(r.saude_per_capita), 'despesa_per_capita')} por habitante` : '')}
      ${cartaoNumero('Educação', r.despesa_educacao, 'despesa_educacao',
        Number.isFinite(aNumero(r.educacao_per_capita))
          ? `${formatar(aNumero(r.educacao_per_capita), 'despesa_per_capita')} por habitante` : '')}
      ${cartaoNumero('Pessoal sobre a RCL', r.percentual_pessoal, 'percentual_pessoal',
        'limite da LRF')}
      ${cartaoNumero('Dívida líquida', r.divida_liquida, 'despesa_total', 'saldo, RGF')}
    </div>
    ${avisoLRF(r)}
    ${Number.isFinite(aNumero(r.despesa_saude))
      ? `<p class="rodape-mapa">Saúde e educação vêm do RREO Anexo 02, que é
         acumulado no exercício — vale o bimestre mais recente entregue, e não
         a soma dos seis. É outro recorte da mesma despesa: não se soma com a
         despesa por natureza abaixo.</p>` : ''}

    <h2>Quem governa</h2>
    ${governantes.length
      ? tabela('<th>Cargo</th><th>Nome</th><th>Partido</th><th>Mandato</th>',
          governantes.map((g) => `<tr>
            <td>${txt(g.cargo)}</td><td>${txt(g.nome)}</td>
            <td>${txt(g.sigla_partido)}</td>
            <td>${escapar(g.ano_inicio ?? '?')}–${escapar(g.ano_fim ?? '?')}</td>
          </tr>`).join(''))
      : `<p class="vazio">Nenhum mandato ligado a este ente.
         Rode o coletor do TSE — e, se ele já rodou, pode ser o nome da cidade
         que não casou com o cadastro do IBGE.</p>`}

    ${legislativo.length ? `<h2>Legislativo</h2>
      ${tabela('<th>Cargo</th><th>Quantidade</th>',
        legislativo.map((l) => `<tr><td>${txt(l.cargo)}</td>
          <td class="valor">${contagem(l.quantidade)}</td></tr>`).join(''))}` : ''}

    <h2>Em que gasta — por natureza</h2>
    ${financas.length ? (() => {
      const total = somar(financas);
      return tabela('<th>Natureza</th><th>Empenhado</th><th>Fatia</th>',
        financas.map((x) => `<tr>
          <td>${txt(x.natureza ?? x.cod_natureza)}</td>
          <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
            >${formatar(aNumero(x.valor), 'despesa_total')}</td>
          <td class="valor">${fatia(x.valor, total)}</td>
        </tr>`).join(''))
        + (funcoes.length ? `<p class="rodape-mapa">Pessoal, juros,
            investimentos: <strong>o quê</strong> foi comprado. A tabela
            seguinte mostra <strong>para quê</strong>. São dois recortes do
            mesmo dinheiro — somar os dois dobra a despesa do ente.</p>` : '');
    })() : '<p class="vazio">Despesa por natureza não coletada para este ente.</p>'}

    ${conferencia('a soma das categorias', f.conferencia_despesa)}

    ${funcoes.length ? `<h2>Para que gasta — por função de governo</h2>
      <p class="rodape-mapa">Do RREO Anexo 02, ${
        escapar(String(funcoes[0].periodo ?? '').replace('_', ' '))} de ${escapar(f.ano)}.
        Acumulado no exercício: é o retrato do bimestre mais recente entregue,
        não a soma dos bimestres.</p>
      ${(() => {
        const total = somar(funcoes);
        return tabela('<th>Função</th><th>Empenhado</th><th>Fatia</th>',
          funcoes.map((x) => `<tr>
            <td>${txt(x.funcao ?? x.cod_funcao)}</td>
            <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
              >${formatar(aNumero(x.valor), 'despesa_total')}</td>
            <td class="valor">${fatia(x.valor, total)}</td>
          </tr>`).join(''));
      })()}
      ${conferencia('a soma das funções', f.conferencia_funcao)}` : ''}

    ${lrf.length ? `<h2>Limites da Lei de Responsabilidade Fiscal</h2>
      <p class="rodape-mapa">Do RGF, ${
        escapar(String(lrf[0].periodo ?? '').replace('_', ' '))} de ${escapar(f.ano)}.
        O percentual <strong>e</strong> o limite vêm os dois do demonstrativo do
        próprio ente — o limite muda por esfera e por poder, então o painel não
        o calcula. Sem limite publicado, ele não afirma nada.</p>
      ${tabela(`<th>Poder</th><th>Pessoal</th><th>Receita corrente líquida</th>
                <th>% sobre a RCL</th><th>Prudencial</th><th>Limite</th>
                <th>Dívida líquida</th>`,
        lrf.map((x) => `<tr>
          <td>${escapar(POR_EXTENSO_PODER[x.poder] ?? x.poder ?? '—')}</td>
          <td class="valor">${formatar(aNumero(x.despesa_pessoal_liquida), 'despesa_total')}</td>
          <td class="valor">${formatar(aNumero(x.receita_corrente_liquida), 'despesa_total')}</td>
          <td class="valor">${seloLimite(x)}</td>
          <td class="valor">${formatar(aNumero(x.limite_prudencial), 'percentual_pessoal')}</td>
          <td class="valor">${formatar(aNumero(x.limite_maximo), 'percentual_pessoal')}</td>
          <td class="valor">${formatar(aNumero(x.divida_liquida), 'despesa_total')}</td>
        </tr>`).join(''))}` : ''}

    ${f.transferencias_uniao?.length ? `<h2>O que a União repassou</h2>
      <p class="rodape-mapa">Pago pelo Tesouro em ${escapar(f.ano)}, por modalidade.
        É outra medida da <strong>arrecadação</strong> acima, que é o que o
        próprio ente declarou ao SICONFI — as duas não batem, e nenhuma das
        duas está errada.</p>
      ${(() => {
        const total = somar(f.transferencias_uniao);
        return tabela('<th>Modalidade</th><th>Valor</th><th>Fatia</th>',
          f.transferencias_uniao.map((x) => `<tr>
            <td>${txt(x.transferencia ?? x.cod_transferencia)}</td>
            <td class="valor" title="${atributo(exato(aNumero(x.valor), 'transferencia_uniao'))}"
              >${formatar(aNumero(x.valor), 'transferencia_uniao')}</td>
            <td class="valor">${fatia(x.valor, total)}</td>
          </tr>`).join(''));
      })()}` : ''}

    ${f.credito ? `<h2>O que pediu emprestado</h2>
      <p class="rodape-mapa">Pedidos de Verificação de Limites protocolados no
        Tesouro (SADIPEM) em ${escapar(f.ano)}. <strong>Não é o saldo
        devedor</strong> — esse é a dívida líquida, acima. É o valor pleiteado
        na época, e parte dele pode nunca ter virado contrato.</p>
      <div class="tiras">
        ${cartaoNumero('Pleiteado', f.credito.valor_pleiteado, 'despesa_total')}
        ${cartaoNumero('Deferido', f.credito.valor_deferido, 'despesa_total')}
        ${cartaoNumero('Contratado', f.credito.valor_contratado, 'despesa_total')}
        ${cartaoNumero('Pedidos', f.credito.pleitos, 'populacao')}
      </div>
      ${f.credito_finalidade?.length
        ? tabela('<th>Finalidade</th><th>Credor</th><th>Valor deferido</th>',
            f.credito_finalidade.map((x) => `<tr>
              <td>${txt(x.finalidade)}</td>
              <td>${txt(x.credor ?? x.tipo_credor)}</td>
              <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
                >${formatar(aNumero(x.valor), 'despesa_total')}</td>
            </tr>`).join(''))
        : ''}` : ''}

    ${indicadores.length ? `<h2>Indicadores</h2>
      ${tabela('<th>Indicador</th><th>Ano</th><th>Valor</th>',
        indicadores.map((i) => {
          const v = formatarIndicador(i.valor, i.unidade);
          return `<tr>
            <td>${txt(i.rotulo ?? i.cod_metrica)}</td><td>${escapar(i.ano)}</td>
            <td class="valor" title="${atributo(v.title)}">${escapar(v.texto)}</td></tr>`;
        }).join(''))}` : ''}`;

  dialogo.setAttribute('aria-labelledby', 'titulo-detalhe');
}

/** A linha de selos no alto da ficha.
 *
 *  O que o painel sabe afirmar sobre este ente, em três palavras, antes de
 *  qualquer tabela. Só entra selo cujo dado existe: ausência não vira selo
 *  neutro, vira silêncio. */
function resumoDeRisco(r) {
  const selos = [];

  if (r.acima_do_limite === true) {
    selos.push('<span class="selo risco">Pessoal acima do limite da LRF</span>');
  } else if (r.acima_do_limite === false) {
    selos.push('<span class="selo calmo">Pessoal dentro do limite da LRF</span>');
  }

  const dep = aNumero(r.dependencia_transferencia);
  if (Number.isFinite(dep) && dep >= 80) {
    selos.push(`<span class="selo atento">${porcento.format(dep)}% de dependência de transferências</span>`);
  }

  const receita = aNumero(r.receita_total);
  const despesa = aNumero(r.despesa_total);
  if (Number.isFinite(receita) && Number.isFinite(despesa) && despesa > receita) {
    selos.push('<span class="selo atento">Empenhou mais do que arrecadou</span>');
  }

  return selos.length
    ? `<p style="display:flex;gap:8px;flex-wrap:wrap;margin:16px 0">${selos.join('')}</p>`
    : '';
}

/** O percentual da folha com o veredito ao lado, em três estados.
 *
 *  Três, não dois: acima do limite, acima do prudencial (que é aviso, não
 *  infração) e dentro. O prudencial estava sendo calculado pela view e
 *  jogado fora pela tela. */
function seloLimite(x) {
  const pct = formatar(aNumero(x.percentual_pessoal), 'percentual_pessoal');
  if (x.acima_do_limite === true) return `<span class="selo risco">${pct}</span>`;
  if (x.acima_do_prudencial === true) return `<span class="selo atento">${pct}</span>`;
  if (x.acima_do_limite === false) return `<span class="selo calmo">${pct}</span>`;
  return pct;
}

/** Duas medidas do mesmo número por caminhos diferentes.
 *
 *  É a checagem que teria pego a despesa inflada em 5× no dia em que ela
 *  apareceu — e por isso ela fica na TELA, não só no teste. */
function conferencia(oQue, c) {
  if (!c) return '';
  const somado = aNumero(c.somado);
  const declarado = aNumero(c.declarado);
  if (!Number.isFinite(somado) || !Number.isFinite(declarado)) return '';

  const dif = Math.abs(somado - declarado);
  const bate = dif <= Math.max(1, Math.abs(declarado) * 0.001);
  return `<p class="rodape-mapa${bate ? '' : ' alerta'}">Conferência: ${escapar(oQue)}
    dá ${formatar(somado, 'despesa_total')} e o ente declarou
    ${formatar(declarado, 'despesa_total')} —
    ${bate ? 'batem.' : `<strong>divergem em ${formatar(dif, 'despesa_total')}</strong>.`}</p>`;
}

/* ---------------------------------------------------------------- políticos */

async function carregarResumoPoliticos() {
  const alvo = $('#resumo-politicos');
  let resumo;
  try {
    resumo = await buscar('/api/politicos/resumo');
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para ler o resumo de políticos.', erro);
    return;
  }
  if (!resumo || !resumo.cargos?.length) {
    alvo.innerHTML = '<p class="vazio">Nenhum político coletado ainda.</p>';
    return;
  }
  alvo.innerHTML = `
    <table><thead><tr><th>Cargo</th><th>Quantidade</th></tr></thead><tbody>
    ${resumo.cargos.map((c) => `<tr><td>${txt(c.cargo)}</td>
      <td class="valor">${contagem(c.quantidade)}</td></tr>`).join('')}
    </tbody></table>
    <p class="rodape-mapa">Total coletado: ${contagem(resumo.total)}.</p>`;
}

async function carregarPoliticos() {
  const corpo = $('#tabela-politicos tbody');
  const botao = $('#buscar-politicos');
  corpo.innerHTML = `<tr><td colspan="5">${esqueleto(5)}</td></tr>`;
  botao.disabled = true;

  await carregarResumoPoliticos();
  await renderizarExecutivo($('#filtro-uf').value.trim().toUpperCase());

  let linhas;
  try {
    linhas = await buscar('/api/politicos', {
      uf: $('#filtro-uf').value.trim().toUpperCase(),
      cargo: $('#filtro-cargo').value,
      partido: $('#filtro-partido')?.value.trim().toUpperCase(),
      busca: $('#filtro-nome').value,
      limite: LIMITE_CONSULTA,
    });
  } catch (erro) {
    corpo.innerHTML = falhaEmLinha(5, 'Não deu para buscar os políticos.', erro);
    return;
  } finally {
    botao.disabled = false;
  }
  // O registro inteiro fica num Map, indexado pela chave da linha: enfiar o
  // JSON num `data-` seria repetir o acervo dentro do HTML.
  _politicoPorLinha = new Map(linhas.map((p, i) => [String(p.sk ?? i), p]));

  corpo.innerHTML = linhas.length ? linhas.map((p, i) => `
    <tr class="clicavel" tabindex="0" role="button"
        aria-label="Abrir ficha de ${atributo(p.nome_eleitoral || p.nome || '')}"
        data-politico="${atributo(p.sk ?? i)}"><td>${escapar(p.nome_eleitoral || p.nome) || '—'}${
        p.nome && p.nome_eleitoral && p.nome !== p.nome_eleitoral
          ? `<br><span class="cadencia">${escapar(p.nome)}</span>` : ''}</td>
        <td>${txt(p.cargo)}</td>
        <td>${txt(p.sigla_partido)}</td>
        <td>${txt(p.sigla_uf)}</td>
        <td>${txt(p.fonte_origem)}</td></tr>`).join('')
    : '<tr><td colspan="5" class="vazio">Sem resultados.</td></tr>';

  if (linhas.length === LIMITE_CONSULTA) {
    corpo.insertAdjacentHTML('beforeend',
      `<tr><td colspan="5" class="rodape-mapa">Limite da consulta `
      + `(${LIMITE_CONSULTA}) — refine o filtro para ver o resto.</td></tr>`);
  }
}

/** O chefe do Executivo do recorte, no alto da aba.
 *
 *  A lista de políticos tinha 69 mil nomes em ordem alfabética e abria num
 *  vereador qualquer. Sem UF mostra o presidente; com UF, o governador.
 *
 *  O subsídio vem com a norma ao lado e com o aviso de "a conferir" quando a
 *  fonte é transcrição não verificada — que é o caso de TODOS os valores do
 *  acervo hoje. Mostrar o número limpo seria apresentar rascunho como fato.
 */
async function renderizarExecutivo(uf) {
  const alvo = $('#destaque-executivo');
  if (!alvo) return;

  const achados = await buscar('/api/politicos/executivo', { uf }).catch(() => []);
  const e = achados?.[0];
  if (!e) {
    // Sumir em silêncio faz parecer que a tela não tem esse recurso. O que
    // falta aqui é COLETA — o cadastro do Executivo vem da eleição geral, e
    // quem rodou só a municipal de 2024 tem 69 mil vereadores e nenhum
    // governador. Dizer isso é mais útil que uma caixa que nunca aparece.
    alvo.innerHTML = `<p class="vazio" style="padding:0">
      ${uf ? `Nenhum governador de ${escapar(uf)} no acervo.`
           : 'Nenhum presidente no acervo.'}
      O cadastro do Executivo vem da <strong>eleição geral</strong>: na aba
      Atualizar, marque o TSE e peça o ano <strong>2022</strong>.</p>`;
    alvo.hidden = false;
    return;
  }

  const nome = String(e.nome ?? '');
  const foto = endereco(e.url_foto);
  const iniciais = nome.split(/\s+/).filter(Boolean)
    .slice(0, 2).map((p) => p[0]).join('').toUpperCase() || '?';

  const salario = aNumero(e.salario);
  const norma = endereco(e.url_norma_salario);
  const temSalario = Number.isFinite(salario);

  alvo.innerHTML = `
    ${foto
      ? `<img src="${foto}" alt="" loading="lazy">`
      : `<div class="iniciais" aria-hidden="true">${escapar(iniciais)}</div>`}
    <div class="quem">
      <div class="nome">${txt(e.nome)}</div>
      <div class="abaixo">
        <span class="etiqueta">${txt(e.cargo)}</span>
        ${e.sigla_partido ? `<span>${escapar(e.sigla_partido)}</span>` : ''}
        ${e.sigla_uf ? `<span class="cadencia">${escapar(e.sigla_uf)}</span>` : ''}
        ${e.ano_inicio
          ? `<span class="cadencia">mandato ${escapar(e.ano_inicio)}–${
              escapar(e.ano_fim ?? '?')}</span>` : ''}
      </div>
    </div>
    <div class="salario">
      <div class="rotulo-numero">Subsídio mensal</div>
      <div class="numero-grande${temSalario ? '' : ' ausente'}">${
        temSalario ? escapar(dinheiroExato.format(salario)) : 'não cadastrado'}</div>
      ${temSalario && e.salario_conferido === false
        ? `<div class="nota-numero"><span class="nao-conferido"
             title="valor transcrito e ainda não conferido contra a norma"
             >⚠ a conferir</span></div>` : ''}
      ${temSalario && e.norma_salario
        ? `<div class="nota-numero">${norma
            ? `<a class="fonte-oficial" href="${norma}" target="_blank"
                 rel="noopener noreferrer">${escapar(e.norma_salario)}</a>`
            : escapar(e.norma_salario)}</div>` : ''}
    </div>`;
  alvo.hidden = false;
}

/* ------------------------------------------------- dica do político
 *
 * O que ela acrescenta à linha da tabela: o nome civil ao lado do nome de
 * urna, o poder e a esfera do cargo, e o **subsídio da função**.
 *
 * O subsídio é por CARGO, não por pessoa — o acervo não tem folha individual,
 * e a dica diz isso com todas as letras. Mostrar "R$ 41.650,92" embaixo do
 * nome de um deputado, sem essa ressalva, seria afirmar quanto ELE recebe, o
 * que o painel não sabe.
 */
let _politicoPorLinha = new Map();

function dicaDoPolitico(p) {
  const subsidio = aNumero(p.subsidio_cargo);
  const nomeCivil = p.nome && p.nome_eleitoral && p.nome !== p.nome_eleitoral;

  return `
    <h3>${txt(p.nome_eleitoral || p.nome)}</h3>
    ${nomeCivil ? `<p class="pe" style="margin-top:-4px;padding:0;border:0"
      >nome civil: ${escapar(p.nome)}</p>` : ''}
    <dl>
      <dt>Cargo</dt><dd>${txt(p.cargo_extenso ?? p.cargo)}</dd>
      ${p.poder ? `<dt>Poder</dt><dd>${escapar(p.poder)}${
        p.esfera ? ` · ${escapar(p.esfera)}` : ''}</dd>` : ''}
      <dt>Partido</dt><dd>${txt(p.sigla_partido)}</dd>
      <dt>UF</dt><dd>${txt(p.sigla_uf)}</dd>
      ${p.casa ? `<dt>Casa</dt><dd>${escapar(p.casa)}</dd>` : ''}
    </dl>
    ${Number.isFinite(subsidio) ? `
      <div class="subsidio">
        <span>Subsídio do cargo</span>
        <strong>${escapar(dinheiroExato.format(subsidio))}</strong>
      </div>
      <p class="pe" style="border:0;padding:0">
        Valor da FUNÇÃO, não desta pessoa — o acervo não tem folha individual.
        ${p.subsidio_conferido === false
          ? '<strong>Ainda não conferido contra a norma.</strong>' : ''}
        ${p.norma_subsidio ? escapar(p.norma_subsidio) : ''}</p>`
      : '<p class="pe">Subsídio deste cargo não cadastrado em referências.</p>'}
    <p class="pe">Cadastro do ${txt(p.fonte_origem)}.</p>`;
}

function ligarDicaDePoliticos() {
  const corpo = $('#tabela-politicos tbody');
  const dica = $('#dica-politico');
  if (!corpo || !dica) return;

  // UM ouvinte no corpo da tabela, não 300 nas linhas. Com o limite de
  // consulta em 300, instalar por linha seriam 900 registros de evento a
  // cada busca — e todos descartados na busca seguinte.
  corpo.addEventListener('pointerover', (ev) => {
    const linha = ev.target.closest('tr[data-politico]');
    if (!linha) { dica.hidden = true; return; }
    const p = _politicoPorLinha.get(linha.dataset.politico);
    if (!p) { dica.hidden = true; return; }
    dica.innerHTML = dicaDoPolitico(p);
    dica.hidden = false;
    posicionarDicaSolta(ev);
  });
  corpo.addEventListener('pointermove', (ev) => {
    if (!dica.hidden) posicionarDicaSolta(ev);
  });
  corpo.addEventListener('pointerleave', () => { dica.hidden = true; });
  corpo.addEventListener('click', (ev) => {
    const linha = ev.target.closest('tr[data-politico]');
    if (linha) { dica.hidden = true; abrirFichaDoPolitico(linha.dataset.politico); }
  });
  corpo.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    const linha = ev.target.closest('tr[data-politico]');
    if (linha) { ev.preventDefault(); abrirFichaDoPolitico(linha.dataset.politico); }
  });
  // Rolar com a dica aberta deixaria ela flutuando sobre outra linha.
  window.addEventListener('scroll', () => { dica.hidden = true; }, { passive: true });
}

/** Posiciona contra a JANELA, não contra um contêiner. */
function posicionarDicaSolta(evento) {
  const dica = $('#dica-politico');
  if (dica.hidden) return;
  const { offsetWidth: largura, offsetHeight: altura } = dica;
  let x = evento.clientX + 16;
  let y = evento.clientY + 16;
  if (x + largura > window.innerWidth - 8) x = evento.clientX - largura - 12;
  if (y + altura > window.innerHeight - 8) y = evento.clientY - altura - 12;
  dica.style.left = `${Math.max(8, x)}px`;
  dica.style.top = `${Math.max(8, y)}px`;
}

/* ------------------------------------------------- ficha do parlamentar
 *
 * O que a Câmara publica na página do deputado e o que a API de dados
 * abertos entrega NÃO são a mesma coisa. Cota parlamentar sai em arquivo
 * estruturado; verba de gabinete, pessoal de gabinete e presença existem
 * só em HTML. A ficha mostra o que tem e diz o que não tem, com o link
 * para conferir na fonte — em vez de raspar página, que quebra em silêncio
 * quando o site muda.
 */
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
               'jul', 'ago', 'set', 'out', 'nov', 'dez'];

async function abrirFichaDoPolitico(sk, ano) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = esqueleto(6);
  abrirDialogo(dialogo, 'Ficha do parlamentar');

  let f;
  try {
    f = await buscar(`/api/politicos/${encodeURIComponent(sk)}/ficha`,
                     ano ? { ano } : {});
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para carregar a ficha.', erro);
    return;
  }

  const p = f.politico;
  const oficial = endereco(f.url_oficial);
  const subsidio = aNumero(p.subsidio_cargo);
  const totalAno = somar(f.cota_por_tipo || []);

  alvo.innerHTML = `
    <h2 id="titulo-detalhe">${txt(p.nome_eleitoral || p.nome)}</h2>
    <p class="rodape-mapa">${txt(p.cargo_extenso ?? p.cargo)}${
      p.sigla_partido ? ` · ${escapar(p.sigla_partido)}` : ''}${
      p.sigla_uf ? `-${escapar(p.sigla_uf)}` : ''}${
      p.nome !== p.nome_eleitoral ? ` · nome civil: ${escapar(p.nome)}` : ''}</p>
    ${oficial ? `<p><a class="fonte-oficial" href="${oficial}" target="_blank"
        rel="noopener noreferrer">Página oficial na Câmara</a></p>` : ''}

    <div class="abas-ficha" role="tablist" aria-label="Seções da ficha">
      <button role="tab" data-painel="resumo" aria-selected="true">Resumo</button>
      <button role="tab" data-painel="atuacao" aria-selected="false"
        tabindex="-1">Presença e votos</button>
      <button role="tab" data-painel="cota" aria-selected="false" tabindex="-1"
        >Cota parlamentar</button>
      <button role="tab" data-painel="fornecedores" aria-selected="false"
        tabindex="-1">Fornecedores</button>
      <button role="tab" data-painel="notas" aria-selected="false" tabindex="-1"
        >Maiores notas</button>
    </div>

    <section class="painel-ficha" data-painel="resumo">
      <div class="tiras">
        ${cartaoNumero('Subsídio mensal', subsidio, 'despesa_total',
          p.subsidio_conferido === false ? 'valor da função, a conferir'
                                         : 'valor da função', true)}
        ${cartaoNumero(`Cota parlamentar ${f.ano ?? ''}`, totalAno || null,
          'despesa_total',
          f.cota_por_tipo?.length ? `${contagem(somar(f.cota_por_tipo, 'notas'))} notas`
                                  : 'sem notas neste ano')}
      </div>
      ${subsidio && p.subsidio_conferido === false ? `<p class="rodape-mapa">
        <span class="nao-conferido">⚠ a conferir</span>
        O subsídio é o da FUNÇÃO, transcrito da norma${
          p.norma_subsidio ? ` (${escapar(p.norma_subsidio)})` : ''} e ainda não
        conferido. O acervo não tem folha de pagamento individual.</p>` : ''}

      ${f.cota_por_ano?.length ? `<h2>Cota por ano</h2>
        ${tabela('<th>Ano</th><th>Total</th><th>Notas</th>',
          f.cota_por_ano.map((a) => `<tr>
            <td>${escapar(a.ano)}</td>
            <td class="valor" title="${atributo(exato(aNumero(a.valor), 'despesa_total'))}"
              >${formatar(aNumero(a.valor), 'despesa_total')}</td>
            <td class="valor">${contagem(a.notas)}</td></tr>`).join(''))}` : ''}

      ${f.so_na_pagina_oficial?.length ? `<h2>O que o painel não tem</h2>
        <div class="aviso">
          <strong>Isto existe só na página da Câmara, em HTML</strong>
          ${f.so_na_pagina_oficial.map((x) => `<div>· <strong>${escapar(x.item)}</strong>
            — ${escapar(x.porque)}</div>`).join('')}
          <p style="margin:8px 0 0">O painel não raspa página: raspagem quebra
          em silêncio quando o site muda, e um número errado é pior que um
          número ausente. ${oficial ? `<a class="fonte-oficial" href="${oficial}"
            target="_blank" rel="noopener noreferrer">Conferir na fonte</a>` : ''}</p>
        </div>` : ''}
    </section>

    <section class="painel-ficha" data-painel="atuacao" hidden>
      ${abaDeAtuacao(f)}
    </section>

    <section class="painel-ficha" data-painel="cota" hidden>
      ${f.cota_por_mes?.length ? `<h2>Mês a mês em ${escapar(f.ano)}</h2>
        ${barrasMensais(f.cota_por_mes)}` : ''}
      ${f.cota_por_tipo?.length ? `<h2>Em quê</h2>
        ${tabela('<th>Tipo de despesa</th><th>Valor</th><th>Fatia</th><th>Notas</th>',
          f.cota_por_tipo.map((t) => `<tr>
            <td>${txt(t.tipo_despesa)}</td>
            <td class="valor" title="${atributo(exato(aNumero(t.valor), 'despesa_total'))}"
              >${formatar(aNumero(t.valor), 'despesa_total')}</td>
            <td class="valor">${fatia(t.valor, totalAno)}</td>
            <td class="valor">${contagem(t.notas)}</td></tr>`).join(''))}`
        : '<p class="vazio">Sem cota parlamentar coletada para este ano.</p>'}
    </section>

    <section class="painel-ficha" data-painel="fornecedores" hidden>
      ${f.fornecedores?.length ? `
        <p class="rodape-mapa">Quem recebeu, no ano. O CNPJ está aqui porque é
          por ele que se reconhece o mesmo fornecedor em gabinetes
          diferentes.</p>
        ${tabela('<th>Fornecedor</th><th>CNPJ/CPF</th><th>Valor</th><th>Notas</th>',
          f.fornecedores.map((x) => `<tr>
            <td>${txt(x.fornecedor)}</td>
            <td>${txt(x.cnpj_cpf_fornecedor)}</td>
            <td class="valor" title="${atributo(exato(aNumero(x.valor), 'despesa_total'))}"
              >${formatar(aNumero(x.valor), 'despesa_total')}</td>
            <td class="valor">${contagem(x.notas)}</td></tr>`).join(''))}`
        : '<p class="vazio">Sem fornecedores neste ano.</p>'}
    </section>

    <section class="painel-ficha" data-painel="notas" hidden>
      ${f.maiores_notas?.length ? `
        <p class="rodape-mapa">As 50 maiores do ano. O link abre o documento
          digitalizado na própria Câmara.</p>
        ${tabela('<th>Data</th><th>Tipo</th><th>Fornecedor</th><th>Valor</th><th></th>',
          f.maiores_notas.map((n) => {
            const doc = endereco(n.url_documento);
            return `<tr>
              <td>${formatarData(n.data_emissao)}</td>
              <td>${txt(n.tipo_despesa)}</td>
              <td>${txt(n.fornecedor)}</td>
              <td class="valor">${formatar(aNumero(n.valor_liquido), 'despesa_total')}</td>
              <td>${doc ? `<a class="fonte-oficial" href="${doc}" target="_blank"
                     rel="noopener noreferrer">nota</a>` : '—'}</td></tr>`;
          }).join(''))}`
        : '<p class="vazio">Sem notas neste ano.</p>'}
    </section>`;

  dialogo.setAttribute('aria-labelledby', 'titulo-detalhe');
  ligarAbasDaFicha(alvo);
}

/** Presença em sessões deliberativas e fidelidade à bancada.
 *
 * Esta aba fala de pessoas nomeadas, então todo número sai com o
 * denominador do lado. "12 faltas" sozinho é uma acusação; "12 de 84
 * sessões, entre 3/fev e 18/dez" é um fato que o leitor pode conferir.
 */
/** A ressalva que acompanha qualquer número de presença.
 *
 * Vem da API, para o texto não divergir entre o JSON e a tela. A cópia local
 * é a rede de segurança de um caso só: acervo coletado por uma versão
 * anterior, que ainda não mandava o campo. Nunca devolve vazio — número de
 * ausência sem ressalva é uma acusação, e este projeto não publica acusação.
 */
function ressalvaDePresenca(f) {
  const daApi = Array.isArray(f && f.presenca_ressalva) ? f.presenca_ressalva : [];
  if (daApi.length) return daApi;
  return [
    'A Câmara publica QUEM ESTEVE, nunca quem faltou: a ausência é subtração nossa.',
    'Não há justificativa no dado aberto. Missão oficial, licença médica e '
      + 'licença-maternidade aparecem iguais a falta seca.',
  ];
}


function abaDeAtuacao(f) {
  const presenca = f.presenca || [];
  const fidelidade = f.fidelidade || [];
  if (!presenca.length && !fidelidade.length) {
    return '<p class="vazio">Sem registro de presença ou de votação para '
         + 'este parlamentar no acervo.</p>';
  }

  const doAno = presenca.find((p) => Number(p.ano) === Number(f.ano))
             || presenca[0];
  const fidAno = fidelidade.find((x) => Number(x.ano) === Number(f.ano))
              || fidelidade[0];
  const taxa = doAno && doAno.taxa_presenca != null
    ? `${(aNumero(doAno.taxa_presenca) * 100).toFixed(1)}%` : null;

  return `
    ${doAno ? `<div class="tiras">
      ${cartaoNumero(`Presença em ${escapar(doAno.ano)}`, null, 'quantidade',
        `${contagem(doAno.presencas)} de ${contagem(doAno.sessoes_possiveis)}`
        + ' sessões deliberativas', false, taxa)}
      ${cartaoNumero('Ausências', aNumero(doAno.ausencias), 'quantidade',
        'sessões em que não registrou presença')}
    </div>

    ${doAno.janela_aproximada ? `<div class="aviso">
      <strong>Esta taxa cobre só parte do ano</strong>
      <div>O acervo registra atividade deste parlamentar entre
      ${formatarData(doAno.primeiro_dia)} e ${formatarData(doAno.ultimo_dia)},
      e o denominador usa apenas as ${contagem(doAno.sessoes_possiveis)}
      sessões desse intervalo — de ${contagem(doAno.sessoes_no_ano)} no ano.
      Quem toma posse no meio da legislatura não faltou ao que veio antes.
      Por isso esta porcentagem <strong>não se compara</strong> com a de quem
      esteve o ano inteiro.</div>
    </div>` : ''}

    <div class="aviso">
      <strong>Como esta conta é feita, e o que ela não sabe</strong>
      ${ressalvaDePresenca(f).map((linha) => `<div>· ${escapar(linha)}</div>`).join('')}
      <div>Antes de concluir alguma coisa sobre uma pessoa, confira na página
        oficial da Câmara.</div>
    </div>` : ''}

    ${presenca.length > 1 ? `<h2>Presença por ano</h2>
      ${tabela('<th>Ano</th><th>Presenças</th><th>Sessões</th><th>Taxa</th>',
        presenca.map((p) => `<tr>
          <td>${escapar(p.ano)}${p.janela_aproximada
            ? ' <span class="nao-conferido" title="o parlamentar não esteve em exercício o ano todo">parcial</span>' : ''}</td>
          <td class="valor">${contagem(p.presencas)}</td>
          <td class="valor">${contagem(p.sessoes_possiveis)}</td>
          <td class="valor">${p.taxa_presenca != null
            ? `${(aNumero(p.taxa_presenca) * 100).toFixed(1)}%` : '—'}</td>
        </tr>`).join(''))}` : ''}

    ${fidAno && fidAno.votos_com_orientacao ? `
      <h2>Fidelidade à bancada em ${escapar(fidAno.ano)}</h2>
      <p class="rodape-mapa">Em ${contagem(fidAno.votos_com_orientacao)}
        votações a liderança orientou o voto e este parlamentar registrou
        voto. Ele seguiu a orientação em
        ${contagem(fidAno.votos_com_orientacao - fidAno.votos_divergentes)}
        e divergiu em <strong>${contagem(fidAno.votos_divergentes)}</strong>.
        Votação liberada pela bancada não entra na conta — não há o que
        descumprir. Divergir não é defeito nem virtude: é informação sobre
        quem decide o voto.</p>` : ''}

    ${f.divergencias?.length ? `
      ${tabela('<th>Data</th><th>Matéria</th><th>Bancada orientou</th><th>Votou</th>',
        f.divergencias.map((d) => `<tr>
          <td>${formatarData(d.data_hora)}</td>
          <td>${txt(d.descricao)}</td>
          <td>${txt(d.orientacao)}${d.sigla_bancada
            ? ` <span class="rodape-mapa">(${escapar(d.sigla_bancada)})</span>` : ''}</td>
          <td><strong>${txt(d.voto)}</strong></td>
        </tr>`).join(''))}` : ''}`;
}

/** Barras mensais em SVG puro — sem biblioteca, como o resto do painel. */
function barrasMensais(meses) {
  const teto = Math.max(...meses.map((m) => aNumero(m.valor) || 0), 0);
  if (!teto) return '';
  return `<div class="barras-mes">${meses.map((m) => {
    const v = aNumero(m.valor) || 0;
    return `<div class="mes" title="${atributo(
        `${MESES[(m.mes || 1) - 1]}: ${exato(v, 'despesa_total')}`)}">
      <div class="haste"><i style="height:${((v / teto) * 100).toFixed(1)}%"></i></div>
      <span class="rotulo-mes">${escapar(MESES[(m.mes || 1) - 1] ?? m.mes)}</span>
    </div>`;
  }).join('')}</div>`;
}

function ligarAbasDaFicha(raiz) {
  const botoes = [...raiz.querySelectorAll('.abas-ficha button')];
  const paineis = [...raiz.querySelectorAll('.painel-ficha')];

  const mostrar = (nome) => {
    botoes.forEach((b) => {
      const ativa = b.dataset.painel === nome;
      b.setAttribute('aria-selected', String(ativa));
      b.tabIndex = ativa ? 0 : -1;
    });
    paineis.forEach((s) => { s.hidden = s.dataset.painel !== nome; });
  };

  botoes.forEach((b) => b.addEventListener('click', () => mostrar(b.dataset.painel)));
  raiz.querySelector('.abas-ficha')?.addEventListener('keydown', (ev) => {
    const i = botoes.indexOf(document.activeElement);
    if (i < 0) return;
    const destino = { ArrowRight: (i + 1) % botoes.length,
                      ArrowLeft: (i - 1 + botoes.length) % botoes.length }[ev.key];
    if (destino === undefined) return;
    ev.preventDefault();
    botoes[destino].focus();
    mostrar(botoes[destino].dataset.painel);
  });
}

/* ---------------------------------------------------------------- proposições */

/** Preenche um seletor a partir dos valores que EXISTEM no acervo. */
async function preencherSeletor(seletor, rota, campo, rotuloTodos) {
  const alvo = $(seletor);
  const escolhido = alvo.value;
  const valores = await buscar(rota).catch(() => []);

  alvo.innerHTML = `<option value="">${rotuloTodos}</option>`
    + valores.map((v) => `<option value="${atributo(v[campo])}">`
      + `${escapar(v[campo])} (${contagem(v.quantidade)})</option>`).join('');

  // Mantém a escolha do usuário se ela continuar existindo depois de coletar.
  if (escolhido && valores.some((v) => String(v[campo]) === escolhido)) {
    alvo.value = escolhido;
  }
  alvo.disabled = valores.length === 0;
  return valores.length;
}

async function montarFiltrosDeProposicao() {
  const [situacoes] = await Promise.all([
    preencherSeletor('#filtro-situacao', '/api/proposicoes/situacoes',
                     'situacao', 'todas'),
    preencherSeletor('#filtro-tipo', '/api/proposicoes/tipos',
                     'sigla_tipo', 'todos'),
  ]);

  if (situacoes === 0) {
    $('#filtro-situacao').innerHTML =
      '<option value="">nenhuma situação no acervo</option>';
  }
}

async function carregarProposicoes() {
  const corpo = $('#tabela-proposicoes tbody');
  const resumo = $('#resumo-proposicoes');
  const botao = $('#buscar-proposicoes');
  corpo.innerHTML = `<tr><td colspan="5">${esqueleto(5)}</td></tr>`;
  botao.disabled = true;

  let linhas;
  try {
    linhas = await buscar('/api/proposicoes', {
      busca: $('#filtro-proposicao').value,
      situacao: $('#filtro-situacao').value,
      tipo: $('#filtro-tipo').value,
      de: $('#filtro-de').value,
      ate: $('#filtro-ate').value,
      limite: LIMITE_CONSULTA,
    });
  } catch (erro) {
    corpo.innerHTML = falhaEmLinha(5, 'Não deu para buscar as proposições.', erro);
    resumo.textContent = '';
    return;
  } finally {
    botao.disabled = false;
  }
  const filtrando = $('#filtro-situacao').value || $('#filtro-tipo').value
    || $('#filtro-proposicao').value || $('#filtro-de').value
    || $('#filtro-ate').value;

  if (!linhas.length) {
    corpo.innerHTML = `<tr><td colspan="5" class="vazio">${filtrando
      ? 'Nenhuma proposição neste recorte.'
      : 'Nenhuma proposição coletada. Use a aba Atualizar.'}</td></tr>`;
    resumo.textContent = '';
    return;
  }

  resumo.textContent = `${contagem(linhas.length)} proposiç${
    linhas.length === 1 ? 'ão' : 'ões'}`
    + (linhas.length === LIMITE_CONSULTA
      ? ` (limite da consulta — refine o filtro para ver o resto)` : '');

  corpo.innerHTML = linhas.map((p) => `
    <tr class="clicavel" tabindex="0" role="button"
        aria-label="Abrir ${atributo(p.identificador ?? 'proposição')}"
        data-casa="${atributo(p.casa)}" data-id="${atributo(p.id_proposicao)}">
      <td><span class="etiqueta">${txt(p.identificador ?? p.sigla_tipo)}</span></td>
      <td>${escapar((p.ementa ?? '').slice(0, 190))}${(p.ementa ?? '').length > 190 ? '…' : ''}</td>
      <td>${txt(p.nome_autor)}${p.partido_autor
        ? ` (${escapar(p.partido_autor)}-${escapar(p.uf_autor ?? '')})` : ''}${
        aNumero(p.qtd_autores) > 1
          ? `<br><span class="cadencia">e mais ${contagem(p.qtd_autores - 1)}</span>` : ''}</td>
      <td>${formatarData(p.data_apresentacao)}</td>
      <td>${txt(p.situacao)}${p.orgao_atual
        ? `<br><span class="cadencia">${escapar(p.orgao_atual)}</span>` : ''}</td>
    </tr>`).join('');

  corpo.querySelectorAll('tr.clicavel').forEach((tr) => {
    const abrir = () => abrirProposicao(tr.dataset.casa, tr.dataset.id);
    tr.addEventListener('click', abrir);
    // A linha era clicável só com mouse: `role="button"` sem tecla é uma
    // promessa que a tela não cumpria.
    tr.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrir(); }
    });
  });
}

async function abrirProposicao(casa, id) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = '<p class="vazio">Carregando…</p>';
  dialogo.showModal();

  const detalhe = await buscar(`/api/proposicoes/${casa}/${id}`).catch(() => null);
  if (!detalhe) { alvo.innerHTML = '<p class="vazio">Não encontrada.</p>'; return; }

  const p = detalhe.proposicao;
  const oficial = endereco(p.url);
  const tramitacoes = detalhe.tramitacoes ?? [];
  const votacoes = detalhe.votacoes ?? [];

  alvo.innerHTML = `
    <h2>${txt(p.identificador)}</h2>
    ${p.situacao ? `<p><span class="etiqueta">${escapar(p.situacao)}</span>${
      p.orgao_atual ? ` <span class="rodape-mapa">em ${escapar(p.orgao_atual)}</span>` : ''
    }</p>` : ''}
    <p>${txt(p.ementa)}</p>
    <p class="rodape-mapa">Autor: <strong>${txt(p.nome_autor)}</strong>
      ${p.partido_autor ? `(${escapar(p.partido_autor)}-${escapar(p.uf_autor ?? '')})` : ''}
      · Apresentada em ${formatarData(p.data_apresentacao)}
      ${aNumero(p.qtd_autores) > 0 ? `· ${contagem(p.qtd_autores)} autor(es)` : ''}</p>
    ${oficial
      ? `<p><a class="fonte-oficial" href="${oficial}" target="_blank"
             rel="noopener noreferrer">Ver na fonte oficial</a></p>`
      : ''}

    <h2>Tramitação — todas as etapas</h2>
    ${tramitacoes.length ? `<div class="rolagem"><table><thead><tr>
        <th>Data</th><th>Órgão</th><th>Etapa</th></tr></thead><tbody>
      ${tramitacoes.map((t) => `<tr>
        <td>${formatarData(t.data_hora, true)}</td><td>${txt(t.orgao)}</td>
        <td>${txt(t.descricao_tramitacao ?? t.descricao_situacao)}${
          t.despacho ? `<br><span class="cadencia">${escapar(t.despacho)}</span>` : ''}
        </td></tr>`).join('')}
      </tbody></table></div>`
      : '<p class="vazio">Tramitações não coletadas para esta proposição.</p>'}

    <h2>Votações</h2>
    ${votacoes.length ? votacoes.map((v) => `
      <div class="cartao" style="margin-bottom:12px">
        <strong>${formatarData(v.data_hora, true)} · ${escapar(v.sigla_orgao ?? '')}</strong>
        ${v.aprovada === true || v.aprovada === false
          ? `<span class="selo ${v.aprovada ? 'calmo' : 'risco'}"
                   style="margin-left:8px">${v.aprovada ? 'Aprovada' : 'Rejeitada'}</span>`
          : ''}
        <p>${txt(v.descricao)}</p>
        <div class="placar">
          <span class="sim">A favor: ${contagem(v.sim)}</span>
          <span class="nao">Contra: ${contagem(v.nao)}</span>
          <span>Abstenção: ${contagem(v.abstencao)}</span>
          <span>Outros: ${contagem(v.outros)}</span>
        </div>
        <button class="ver-votos discreto" data-casa="${atributo(casa)}"
                data-votacao="${atributo(v.id_votacao)}">Ver quem votou</button>
        <div class="lista-votos"></div>
      </div>`).join('')
      : '<p class="vazio">Sem votação nominal registrada para esta proposição.</p>'}`;

  alvo.querySelectorAll('.ver-votos').forEach((b) => {
    b.addEventListener('click', async () => {
      const destino = b.nextElementSibling;
      destino.innerHTML = '<p class="vazio">Carregando…</p>';
      const r = await buscar(
        `/api/votacoes/${b.dataset.casa}/${b.dataset.votacao}/votos`).catch(() => null);
      if (!r || !r.votos.length) {
        destino.innerHTML = '<p class="vazio">Votos não disponíveis para esta '
          + 'votação. Rode o coletor em lote da Câmara.</p>';
        return;
      }
      destino.innerHTML = `<table><thead><tr>
          <th>Parlamentar</th><th>Partido</th><th>UF</th><th>Voto</th>
        </tr></thead><tbody>
        ${r.votos.map((v) => {
          const voto = String(v.voto ?? '');
          const classe = /^Sim/i.test(voto) ? 'sim'
            : /^N[ãa]o/i.test(voto) ? 'nao' : '';
          return `<tr>
          <td>${txt(v.nome_politico)}</td><td>${txt(v.sigla_partido)}</td>
          <td>${txt(v.sigla_uf)}</td>
          <td class="${classe}">${txt(v.voto)}</td></tr>`;
        }).join('')}
        </tbody></table>`;
    });
  });
}

/* ---------------------------------------------------------------- fontes */

async function carregarSituacao() {
  const saude = await buscar('/api/saude').catch(() => FALHOU);
  const alvo = $('#situacao-fontes');
  if (saude === FALHOU) {
    alvo.innerHTML = falha('Não deu para ler a situação das fontes.');
    return;
  }
  if (!saude || !saude.fontes?.length) {
    alvo.innerHTML = '<p class="vazio">Nenhuma coleta registrada. '
      + 'Rode <code>python -m src.scripts.coletar --tudo</code>.</p>';
    return;
  }
  alvo.innerHTML = `<table><thead><tr>
      <th>Fonte</th><th>Recurso</th><th>Linhas</th><th>Situação</th><th>Lido em</th>
    </tr></thead><tbody>
    ${saude.fontes.map((f) => `<tr>
      <td>${txt(f.fonte)}</td><td>${txt(f.recurso)}</td>
      <td class="valor">${contagem(f.linhas)}</td>
      <td><span class="selo ${SELO_SITUACAO[f.situacao] ?? 'neutro'}"
          >${txt(f.situacao)}</span></td>
      <td>${formatarData(f.lido_em, true)}</td></tr>`).join('')}
    </tbody></table>`;
}

/* ------------------------------------------------------------- custo */

async function carregarCusto() {
  $('#tabela-custo tbody').innerHTML = `<tr><td colspan="5">${esqueleto(4)}</td></tr>`;
  const [cargos, resumo] = await Promise.all([
    buscar('/api/custo/cargos').catch(() => FALHOU),
    buscar('/api/custo/resumo').catch(() => FALHOU),
  ]);

  renderizarTopoDeCusto(resumo);
  renderizarAvisosDeCusto(resumo);
  renderizarTabelaDeCusto(cargos);
  renderizarLateralDeCusto(resumo);
}

function renderizarTopoDeCusto(resumo) {
  const alvo = $('#topo-custo');
  if (!resumo || resumo === FALHOU) { alvo.innerHTML = ''; return; }

  const estimado = somar(resumo.estimado_por_poder || [], 'custo_estimado');
  const ocupantes = somar(resumo.estimado_por_poder || [], 'ocupantes');
  // Só estes entram no valor. `somar` ignora custo nulo mas somava
  // TODOS os ocupantes, então o rótulo cobria 64.323 pessoas e o
  // número cobria 594.
  const comSubsidio = somar(resumo.estimado_por_poder || [], 'ocupantes_com_subsidio');

  // A cobertura ao lado do número, não escondida num aviso. A soma de 27 UFs
  // e a de 5.570 municípios são grandezas diferentes e se parecem igualmente
  // com "o total do Brasil" — quem lê precisa ver de quantos entes ela veio.
  // CADA CARTÃO DIZ DE QUE ANO ELE É.
  //
  // As fontes têm calendários diferentes: o RREO é bimestral e já publica o
  // exercício corrente; o DCA, de onde vêm arrecadação e despesa total, é
  // anual e sai no seguinte. Fixar UM ano para a aba inteira fazia a
  // arrecadação de 2025 desaparecer da tela assim que 2026 passava a existir
  // pela metade — com o número no disco. Melhor mostrar 2025 dizendo 2025.
  const nota = (valor, entesDoBloco, anoDoBloco) => {
    if (valor == null) return 'nada coletado ainda';
    const partes = [];
    if (entesDoBloco) partes.push(`${contagem(entesDoBloco)} ente(s) do acervo`);
    if (anoDoBloco) partes.push(String(anoDoBloco));
    return partes.join(' · ');
  };

  alvo.innerHTML =
    cartaoNumero('Arrecadação de estados e municípios', resumo.arrecadacao,
                 'receita_total',
                 nota(resumo.arrecadacao, resumo.arrecadacao_entes,
                      resumo.ano_arrecadacao ?? resumo.ano))
    + cartaoNumero('Despesa de estados e municípios', resumo.despesa_subnacional,
                   'despesa_total',
                   nota(resumo.despesa_subnacional, resumo.despesa_entes,
                        resumo.ano_despesa_subnacional ?? resumo.ano))
    + cartaoNumero('Subsídios (estimativa)', estimado || null, 'despesa_total',
                   comSubsidio
                     ? `${contagem(comSubsidio)} de ${contagem(ocupantes)} `
                       + 'ocupantes têm subsídio cadastrado × 13,33'
                     : 'ocupantes × subsídio × 13,33');
}

function renderizarAvisosDeCusto(resumo) {
  const alvo = $('#avisos-custo');
  const avisos = resumo?.avisos || [];
  alvo.innerHTML = avisos.length
    ? `<div class="aviso"><strong>Leia antes de citar estes números</strong>
       ${avisos.map((a) => `<div>· ${escapar(a)}</div>`).join('')}</div>`
    : '';
}

function renderizarTabelaDeCusto(cargos) {
  const corpo = $('#tabela-custo tbody');
  if (cargos === FALHOU) {
    corpo.innerHTML = falhaEmLinha(5, 'Não deu para ler os cargos.');
    return;
  }
  if (!cargos.length) {
    corpo.innerHTML = '<tr><td colspan="5" class="vazio">'
      + 'Nenhum cargo com subsídio no acervo. Se você já rodou '
      + '<strong>Referências</strong>, confira o arquivo '
      + '<code>referencias/subsidios.csv</code>.'
      + '</td></tr>';
    return;
  }

  corpo.innerHTML = cargos.map((c) => {
    // A API controla este endereço, e um `href` aceita `javascript:` — o
    // `rel="noopener"` não protege contra isso. Só http e https passam.
    const norma = endereco(c.url_norma);
    return `
    <tr>
      <td>${txt(c.cargo)}${c.ramo ? `<br><span class="cadencia">${escapar(c.ramo)}</span>` : ''}
        ${c.poder ? `<br><span class="cadencia">${escapar(c.poder)}${
          c.esfera ? ` · ${escapar(c.esfera)}` : ''}</span>` : ''}</td>
      <td class="valor">${contagem(c.ocupantes)}</td>
      <td class="valor">${c.valor_mensal == null ? '—'
        : escapar(dinheiro.format(c.valor_mensal))}
        ${c.valor_mensal != null && !c.conferido
          ? ' <span class="nao-conferido" title="valor transcrito e ainda não conferido contra a norma">⚠ a conferir</span>'
          : ''}</td>
      <td class="valor">${c.custo_anual_estimado == null ? '—'
        : escapar(dinheiro.format(c.custo_anual_estimado))}</td>
      <td>${norma
        ? `<a class="fonte-oficial" href="${norma}" target="_blank"
             rel="noopener noreferrer">${txt(c.norma ?? 'norma')}</a>`
        : txt(c.norma)}
        ${c.observacao ? `<br><span class="cadencia">${escapar(c.observacao)}</span>` : ''}</td>
    </tr>`;
  }).join('');
}

function renderizarLateralDeCusto(resumo) {
  const alvo = $('#lateral-custo');
  if (resumo === FALHOU) { alvo.innerHTML = falha('Resumo indisponível.'); return; }
  if (!resumo) { alvo.innerHTML = '<p class="vazio">Sem dados.</p>'; return; }

  const bloco = (titulo, linhas, rotulo, campo, nota, extra) => {
    if (!linhas.length) return '';
    const total = somar(linhas, campo);
    // Recorte cuja coleta terminou `parcial` ou `erro` não vira valor apurado:
    // vira PISO, com o selo e a contagem de linhas ao lado. O total do bloco
    // herda o piso, porque somar um número completo com um truncado devolve um
    // truncado — e a soma é justamente onde a marca se perderia.
    const parcial = linhas.some((l) => l.completo === false);
    const piso = (v) => (parcial ? '≥ ' : '') + formatar(v, 'despesa_total');
    return `
      <h2 style="margin-top:20px">${escapar(titulo)}</h2>
      ${nota ? `<p class="rodape-mapa">${escapar(nota)}</p>` : ''}
      ${tabela('<th>Item</th><th>Valor</th>',
        linhas.map((l) => `<tr>
          <td>${txt(l[rotulo])}${l.esfera
            ? ` <span class="cadencia">${escapar(l.esfera)}</span>` : ''}${
            extra && l[extra] != null
              ? `<br><span class="cadencia">${contagem(l[extra])} ocupantes</span>` : ''}</td>
          <td class="valor" title="${atributo(exato(aNumero(l[campo]), 'despesa_total'))}"
            >${l.completo === false ? '≥ ' : ''}${formatar(aNumero(l[campo]), 'despesa_total')}${
            l.completo === false
              ? `<br><span class="nao-conferido" title="A coleta deste recorte terminou como '${
                  atributo(l.situacao_coleta || 'incompleta')}': o valor é um piso, não o total apurado."
                  >⚠ coleta incompleta</span>`
              : ''}${l.linhas != null
              ? `<br><span class="cadencia">${contagem(l.linhas)} linha(s)</span>` : ''}</td>
        </tr>`).join('')
        + `<tr><td><strong>Total</strong></td>
             <td class="valor"><strong>${piso(total)}</strong></td></tr>`)}`;
  };

  const conteudo =
    bloco('Despesa por função', resumo.despesa_por_funcao || [], 'funcao',
          'valor', `Valor empenhado em ${resumo.ano ?? '—'} — o que de fato saiu.`)
    + bloco('Custo medido federal', resumo.custo_medido_federal || [],
            'conjunto', 'valor', 'Apurado pelo Tesouro/SIC.')
    + bloco('Subsídios por poder (estimativa)',
            resumo.estimado_por_poder || [], 'poder', 'custo_estimado',
            'Conta, não medição — ocupantes × subsídio × 13,33.', 'ocupantes');

  alvo.innerHTML = conteudo
    || '<p class="vazio">Colete SICONFI, Tesouro e Referências para preencher.</p>';
}

/* ------------------------------------------------------------- atualizar */

let relogioColeta = null;

async function montarCatalogo() {
  const alvo = $('#catalogo-fontes');
  let fontes;
  try {
    fontes = await buscar('/api/coleta/catalogo');
  } catch (erro) {
    alvo.innerHTML = falha('Não deu para ler o catálogo de fontes.', erro);
    return;
  }
  if (!fontes.length) {
    alvo.innerHTML = '<p class="vazio">Catálogo indisponível.</p>';
    return;
  }
  fontes.forEach((f) => { ROTULOS_FONTE[f.fonte] = f.rotulo; });
  // Cada fonte traz COMO ela atualiza. Duas fontes marcadas na mesma tela
  // não significam a mesma coisa: a Câmara republica o ano corrente todo dia,
  // o SICONFI só fecha o exercício anterior, o TSE só muda a cada eleição.
  // Esconder isso faz a pessoa esperar dado que ainda não existe.
  alvo.innerHTML = fontes.map((f, i) => `
    <div class="fonte">
      <label class="opcao">
        <input type="checkbox" value="${atributo(f.fonte)}"
               aria-describedby="sobre-${i}"
               ${['camara', 'senado'].includes(f.fonte) ? 'checked' : ''}>
        <span>${escapar(f.rotulo)}</span>
        <span class="cadencia">${escapar(f.cadencia)}</span>
      </label>
      <div class="sobre-fonte" id="sobre-${i}">
        <dl>
          <dt>Recorte do ano</dt>
          <dd>${f.usa_ano ? escapar(f.periodo)
                          : `<span class="sem-ano">ignora o campo Ano</span>
                             — ${escapar(f.periodo)}`}</dd>
          <dt>Cada linha é</dt><dd>${escapar(f.granularidade)}</dd>
          <dt>Costuma levar</dt><dd>${escapar(f.duracao)}</dd>
        </dl>
        ${f.requer ? `<p class="exige">⚙ Precisa antes: ${escapar(f.requer)}</p>` : ''}
        ${f.observacao ? `<p>${escapar(f.observacao)}</p>` : ''}
      </div>
    </div>`).join('');
}

async function mostrarEstadoDaChave() {
  const cfg = await buscar('/api/config').catch(() => null);
  const cartao = $('#cartao-chave');
  const estado = $('#estado-chave');
  if (!cfg) { cartao.hidden = true; return; }

  const portal = cfg.portal_transparencia;
  cartao.hidden = false;
  estado.textContent = portal.configurada
    ? `Configurada (final ${portal.mascara}). Cole uma nova para substituir.`
    : 'Sem chave — as emendas parlamentares não podem ser coletadas.';
  $('#campo-chave').placeholder = portal.configurada
    ? 'substituir a chave atual' : 'cole aqui — a chave ou o bloco de exemplo';
}

async function salvarChave() {
  const campo = $('#campo-chave');
  const resposta = $('#resposta-chave');
  const botao = $('#salvar-chave');

  if (!campo.value.trim()) {
    resposta.textContent = 'Cole a chave antes de salvar.';
    return;
  }

  botao.disabled = true;
  resposta.textContent = 'salvando e testando…';

  // `try/finally`: sem ele, uma falha de rede pulava o `disabled = false` e
  // o botão Salvar ficava travado com "salvando e testando…" para sempre.
  let r;
  let corpo = {};
  try {
    r = await fetch('/api/config/chave-portal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chave: campo.value }),
    });
    corpo = await r.json().catch(() => ({}));
  } catch (erro) {
    resposta.textContent = `Não deu para falar com o painel: ${erro.message}`;
    return;
  } finally {
    botao.disabled = false;
  }

  if (!r.ok) {
    resposta.textContent = corpo.detail || corpo.erro
      || `Não deu para salvar (${r.status}).`;
    return;
  }

  // Some da tela assim que sai daqui: não fica chave guardada no campo.
  campo.value = '';
  resposta.textContent = corpo.validada
    ? `Salva e ${corpo.mensagem}`
    : `Salva (${corpo.mascara}), mas ${corpo.mensagem}`;
  await mostrarEstadoDaChave();
}

function fontesMarcadas() {
  return [...$$('#catalogo-fontes input:checked')].map((i) => i.value);
}

async function dispararColeta() {
  const fontes = fontesMarcadas();
  const aviso = $('#aviso-coleta');
  if (!fontes.length) {
    aviso.textContent = 'Marque ao menos uma fonte.';
    return;
  }

  const ano = $('#coleta-ano').value;
  const corpo = {
    fontes,
    ano: ano ? Number(ano) : null,
    nivel: $('#coleta-nivel').value,
    uf: $('#coleta-uf').value.trim().toUpperCase() || null,
  };

  $('#botao-atualizar').disabled = true;
  aviso.textContent = 'iniciando…';

  let resp;
  try {
    resp = await fetch('/api/coleta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corpo),
    });
  } catch (erro) {
    // Mesmo defeito de `salvarChave`: sem isto o botão Atualizar ficava
    // desabilitado e o aviso preso em "iniciando…", sem saída.
    aviso.textContent = `Não deu para falar com o painel: ${erro.message}`;
    $('#botao-atualizar').disabled = false;
    return;
  }

  if (resp.status === 409) {
    aviso.textContent = 'Já existe uma atualização rodando — espere terminar.';
    $('#botao-atualizar').disabled = false;
    acompanharColeta();
    return;
  }
  if (!resp.ok) {
    aviso.textContent = `Não deu para iniciar (${resp.status}).`;
    $('#botao-atualizar').disabled = false;
    return;
  }

  aviso.textContent = '';
  renderizarColeta(await resp.json());
  acompanharColeta();
}

/** Acompanha a coleta em andamento.
 *
 *  Três correções sobre a versão anterior, todas do mesmo tipo — laço que
 *  não sabia parar:
 *
 *  1. **Sem trava de requisição em voo.** `/api/coleta` durante uma coleta
 *     pesada leva mais de 2 s; os ticks se acumulavam e as respostas chegavam
 *     fora de ordem, fazendo a barra de progresso ANDAR PARA TRÁS.
 *  2. **Falha do polling era `return` mudo.** API fora do ar no meio da
 *     coleta = painel congelado no último estado conhecido, para sempre, sem
 *     dizer nada.
 *  3. **Nunca parava.** Se a tarefa travasse em `executando`, o relógio
 *     seguia batendo com o usuário em outra aba e a máquina desligada.
 */
function acompanharColeta() {
  if (relogioColeta) clearInterval(relogioColeta);
  let emVoo = false;
  let falhasSeguidas = 0;

  relogioColeta = setInterval(async () => {
    if (emVoo) return;
    if (document.hidden) return;   // aba escondida: nada para atualizar
    emVoo = true;
    let tarefa;
    try {
      tarefa = await buscar('/api/coleta');
      falhasSeguidas = 0;
    } catch (erro) {
      falhasSeguidas += 1;
      if (falhasSeguidas >= 5) {
        pararColeta();
        $('#aviso-coleta').textContent =
          'Perdi contato com o painel. A coleta pode continuar rodando no '
          + 'servidor — recarregue a página para reencontrá-la.';
      }
      return;
    } finally {
      emVoo = false;
    }

    renderizarColeta(tarefa);
    if (tarefa.situacao === 'executando') return;

    pararColeta();
    $('#botao-atualizar').disabled = false;
    // O armazém mudou: recria as views e recarrega o que está na tela.
    await fetch('/api/recarregar', { method: 'POST' }).catch(() => {});
    // O ano escolhido pelo usuário é preservado: `carregarAnos` reatribuía
    // `estado.ano` para o mais recente e o mapa saltava de exercício sozinho,
    // no fim de uma coleta que podia ter durado horas.
    const anoEscolhido = estado.ano;
    await carregarAnos();
    if (anoEscolhido && [...$('#ano').options].some((o) => Number(o.value) === anoEscolhido)) {
      estado.ano = anoEscolhido;
      $('#ano').value = String(anoEscolhido);
    }
    malhasEmCache.clear();
    abasCarregadas.clear();   // o acervo mudou: toda aba precisa reler
    await carregarSituacao().catch(() => {});
    await carregarMapa().catch(() => {});
    if ($('#tabela-proposicoes tbody').children.length) {
      await montarFiltrosDeProposicao();
      await carregarProposicoes();
    }
  }, 2000);
}

function pararColeta() {
  if (relogioColeta) clearInterval(relogioColeta);
  relogioColeta = null;
}

// Sair da página com um relógio batendo deixa requisição em voo sem dono.
window.addEventListener('beforeunload', pararColeta);

/** Rótulo legível de cada fonte, preenchido pelo catálogo da API. A lista de
 *  etapas mostrava o nome interno (`siconfi_rgf`) enquanto a lista de seleção,
 *  logo acima, mostrava o nome por extenso — duas telas falando da mesma
 *  coisa com nomes diferentes. */
const ROTULOS_FONTE = {};

const SINAIS = {
  aguardando: '·', executando: '▸', ok: '✓', parcial: '!', erro: '✕',
  configuracao: '⚙',
};

const ROTULO_ETAPA = {
  aguardando: 'aguardando', executando: 'coletando', ok: 'ok',
  parcial: 'parcial', erro: 'erro', configuracao: 'falta configurar',
};

function renderizarColeta(tarefa) {
  const alvo = $('#progresso-coleta');
  if (!tarefa || tarefa.situacao === 'nenhuma') {
    alvo.innerHTML = '<p class="vazio">Nenhuma atualização em andamento.</p>';
    return;
  }

  const p = tarefa.progresso || { feitas: 0, total: 0 };
  const emAndamento = tarefa.situacao === 'executando';

  // "8/8 fontes" com um ✓ verde escondia que uma delas terminou parcial —
  // e era justamente a que deixou a aba Custo do Estado vazia. O resumo
  // agora conta por desfecho, não por conclusão.
  const porSituacao = {};
  (tarefa.etapas || []).forEach((e) => {
    porSituacao[e.situacao] = (porSituacao[e.situacao] || 0) + 1;
  });
  const problemas = Object.entries(porSituacao)
    .filter(([s]) => !['ok', 'aguardando', 'executando'].includes(s))
    .map(([s, n]) => `${n} ${ROTULO_ETAPA[s] ?? s}`);

  const pct = p.total ? Math.round((p.feitas / p.total) * 100) : 0;
  const duracao = tarefa.inicio
    ? formatarData(tarefa.fim || tarefa.inicio, true) : '';

  alvo.innerHTML = `
    <p class="rodape-mapa" role="status">
      Atualização #${escapar(tarefa.id)} · ${emAndamento
        ? `rodando ${escapar(tarefa.fonte_atual ?? '')}` : escapar(tarefa.situacao)}
      · ${p.feitas}/${p.total} fontes${problemas.length
        ? ` · <strong>${escapar(problemas.join(', '))}</strong>` : ''}
      ${duracao ? `· ${emAndamento ? 'desde' : 'terminou'} ${duracao}` : ''}
    </p>
    <div class="progresso-trilho" role="progressbar" aria-valuemin="0"
         aria-valuemax="100" aria-valuenow="${pct}"
         aria-label="Progresso da atualização">
      <i style="width:${pct}%"></i>
    </div>
    <ul class="etapas">
      ${(tarefa.fontes || []).map((f) => {
        const e = (tarefa.etapas || []).find((x) => x.fonte === f)
          || { situacao: 'aguardando', detalhe: '', erros: [] };
        return `<li class="${escapar(e.situacao)}">
          <span class="sinal" aria-hidden="true">${SINAIS[e.situacao] ?? '·'}</span>
          <span>${escapar(ROTULOS_FONTE[f] ?? f)}</span>
          <span class="cadencia">${escapar(ROTULO_ETAPA[e.situacao] ?? e.situacao)}</span>
          ${e.detalhe ? `<span class="detalhe">${escapar(e.detalhe)}</span>` : ''}
          ${(e.erros || []).slice(0, 3).map((m) =>
            `<span class="detalhe">${escapar(m)}</span>`).join('')}
        </li>`;
      }).join('')}
    </ul>`;

  const registro = $('#log-coleta');
  const linhas = tarefa.linhas || [];
  registro.hidden = linhas.length === 0;
  const colado = registro.scrollTop + registro.clientHeight
    >= registro.scrollHeight - 30;
  // Só as últimas: numa coleta municipal de três horas o array só cresce, e
  // o log inteiro era reconstruído a cada dois segundos. O que interessa é o
  // fim dele.
  const ULTIMAS = 400;
  const recorte = linhas.slice(-ULTIMAS);
  registro.innerHTML = (linhas.length > ULTIMAS
      ? `<span class="hora">… ${contagem(linhas.length - ULTIMAS)} linha(s) `
        + `anteriores omitidas; o log completo está em logs/</span>\n` : '')
    + recorte.map((l) =>
      `<span class="hora">${escapar(l.hora)}</span> `
      + `<span class="${escapar(l.nivel)}">${escapar(l.texto)}</span>`).join('\n');
  if (colado) registro.scrollTop = registro.scrollHeight;
}

/* ---------------------------------------------------------------- início */

/** Setas navegam entre abas, como manda o padrão de tablist. Sem isso, seis
 *  abas eram seis paradas de Tab e o conjunto não se comportava como um. */
function ligarTeclasDasAbas() {
  const botoes = $$('nav button');
  $('nav').addEventListener('keydown', (ev) => {
    const i = botoes.indexOf(document.activeElement);
    if (i < 0) return;
    const destino = {
      ArrowRight: (i + 1) % botoes.length,
      ArrowLeft: (i - 1 + botoes.length) % botoes.length,
      Home: 0, End: botoes.length - 1,
    }[ev.key];
    if (destino === undefined) return;
    ev.preventDefault();
    botoes[destino].focus();
    trocarAba(botoes[destino].dataset.aba);
  });
}

async function iniciar() {
  $$('nav button').forEach((b) => b.addEventListener('click', () => trocarAba(b.dataset.aba)));
  ligarTeclasDasAbas();
  // A aba fica na URL: recarregar volta para onde se estava, e uma visão do
  // painel passa a ser compartilhável por link — o que num painel de
  // transparência é metade do ponto.
  const abaInicial = location.hash.slice(1);
  if ($$('nav button').some((b) => b.dataset.aba === abaInicial)) trocarAba(abaInicial);
  window.addEventListener('hashchange', () => {
    const aba = location.hash.slice(1);
    if ($$('nav button').some((b) => b.dataset.aba === aba)) trocarAba(aba);
  });

  $('#ano').addEventListener('change', (e) => {
    estado.ano = Number(e.target.value);
    avisarAnoParcial();   // o aviso segue o ano escolhido
    carregarMapa();
  });
  $('#metrica').addEventListener('change', (e) => { estado.metrica = e.target.value; carregarMapa(); });
  ligarControlesDoMapa();
  ligarDicaDePoliticos();

  // O sistema pode trocar de tema com a página aberta. A rampa do mapa tem
  // uma versão por tema, então ela precisa ser refeita — senão fica a rampa
  // clara sobre o papel escuro, que é o defeito que se acabou de consertar.
  matchMedia?.('(prefers-color-scheme: dark)')?.addEventListener?.('change', () => {
    reavaliarTema();
    if (estado.entes.length) carregarMapa().catch(() => {});
  });

  $('#buscar-politicos').addEventListener('click', carregarPoliticos);
  $('#buscar-proposicoes').addEventListener('click', carregarProposicoes);
  ['#filtro-uf', '#filtro-nome'].forEach((sel) => {
    $(sel)?.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') carregarPoliticos();
    });
  });
  $('#filtro-situacao').addEventListener('change', carregarProposicoes);
  $('#filtro-tipo').addEventListener('change', carregarProposicoes);
  $('#filtro-proposicao').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') carregarProposicoes();
  });
  $('#limpar-proposicoes').addEventListener('click', () => {
    ['#filtro-proposicao', '#filtro-situacao', '#filtro-tipo',
     '#filtro-de', '#filtro-ate'].forEach((s) => { $(s).value = ''; });
    carregarProposicoes();
  });
  $('#fechar-detalhe').addEventListener('click', () => $('#detalhe').close());
  $('#botao-atualizar').addEventListener('click', dispararColeta);
  $('#salvar-chave').addEventListener('click', salvarChave);
  $('#campo-chave').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') salvarChave();
  });

  await carregarAnos();

  // A coleta leva minutos, e quem volta à aba depois é justamente quem quer
  // saber o que deu errado. Recarregar a página apagava o log e os erros da
  // tela, embora o servidor ainda os tivesse. Agora a última execução é
  // sempre reexibida — em andamento ou já terminada.
  const ultima = await buscar('/api/coleta').catch(() => null);
  if (ultima && ultima.situacao !== 'nenhuma') {
    await montarCatalogo();
    renderizarColeta(ultima);
    if (ultima.situacao === 'executando') {
      $('#botao-atualizar').disabled = true;
      acompanharColeta();
    }
  }
  if (estado.ano) {
    await carregarMapa().catch((erro) => {
      $('#rodape-mapa').textContent = `Não foi possível montar o mapa: ${erro.message}`;
    });
  } else {
    $('#rodape-mapa').textContent =
      'Nenhum dado no armazém. Rode a primeira carga: INSTALAR.bat';
  }
}

iniciar();
