/* Painel da Transparência — lógica da página.
 *
 * Regra que atravessa o arquivo inteiro: número que não veio do armazém não
 * aparece. Ente sem dado fica cinza e o rodapé diz quantos entes têm dado.
 */

import { desenharGeoJson, calcularQuebras, corDe, RAMPA } from './mapa.js';

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
const data = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' });

/** null/undefined viram NaN, não 0.
 *  `Number(null)` é 0 em JavaScript — era isso que escrevia "R$ 0" nos 27
 *  estados de um ano sem coleta, três centímetros abaixo de um rodapé
 *  dizendo "cinza = ainda não coletado, não zero". */
const aNumero = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));

const porcento = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });

const formatar = (valor, metrica) => {
  if (!Number.isFinite(valor)) return '—';
  if (metrica === 'populacao') return numero.format(valor);
  if (metrica === 'dependencia_transferencia') return `${porcento.format(valor)}%`;
  return dinheiro.format(valor);
};

const ROTULO_METRICA = {
  despesa_per_capita: 'Despesa por habitante',
  despesa_total: 'Despesa total',
  receita_total: 'Arrecadação',
  receita_per_capita: 'Arrecadação por habitante',
  transferencia_recebida: 'Transferências recebidas',
  dependencia_transferencia: 'Dependência de transferências',
  populacao: 'População',
};

const formatarData = (texto) => {
  if (!texto) return '—';
  const d = new Date(texto);
  return Number.isNaN(d.getTime()) ? String(texto).slice(0, 10) : data.format(d);
};

async function buscar(rota, parametros = {}) {
  const url = new URL(API + rota, location.origin);
  Object.entries(parametros).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') url.searchParams.set(k, v);
  });
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} em ${rota}`);
  return resp.json();
}

/* ---------------------------------------------------------------- abas */

function trocarAba(destino) {
  $$('nav button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.aba === destino)));
  $$('main section').forEach((s) => { s.hidden = s.id !== `aba-${destino}`; });
  if (destino === 'politicos' && !$('#tabela-politicos tbody').children.length) carregarPoliticos();
  if (destino === 'proposicoes' && !$('#tabela-proposicoes tbody').children.length) {
    montarFiltrosDeProposicao().then(carregarProposicoes);
  }
  if (destino === 'custo' && !$('#tabela-custo tbody').children.length) carregarCusto();
  if (destino === 'atualizar' && !$('#catalogo-fontes').children.length) {
    montarCatalogo();
    mostrarEstadoDaChave();
  }
}

/* ---------------------------------------------------------------- mapa */

async function carregarAnos() {
  const anos = await buscar('/api/anos').catch(() => []);
  const seletor = $('#ano');
  seletor.innerHTML = '';
  if (!anos.length) {
    seletor.innerHTML = '<option>sem dados</option>';
    seletor.disabled = true;
    return null;
  }
  anos.forEach((a) => seletor.add(new Option(a, a)));
  estado.ano = anos[0];
  return anos[0];
}

async function carregarMapa() {
  if (!estado.ano) return;

  const [resposta, malha] = await Promise.all([
    buscar('/api/mapa', { ano: estado.ano, uf: estado.uf, metrica: estado.metrica }),
    buscar(`/api/malha/${estado.uf || 'brasil'}`),
  ]);

  estado.entes = resposta.entes;
  estado.malha = malha;
  renderizarMapa(resposta);
  renderizarRanking(resposta);
  renderizarMigalha();
}

/* ------------------------------------------------------- zoom e rótulos */

const NS = 'http://www.w3.org/2000/svg';
const LARGURA = 760, ALTURA = 620;

// Largura mínima, em pixels da tela, para um ente caber com o nome escrito
// dentro. Abaixo disto o rótulo sai — 5.570 nomes sobrepostos não são
// informação, são uma mancha.
const CABE_ROTULO = 34;

const zoom = { escala: 1, x: 0, y: 0 };

function aplicarZoom() {
  const grupo = $('#camada-mapa');
  if (!grupo) return;
  grupo.setAttribute('transform',
    `translate(${zoom.x} ${zoom.y}) scale(${zoom.escala})`);
  // O rótulo vive dentro do grupo que escala, então o tamanho da fonte é
  // dividido pela escala para o texto continuar do mesmo tamanho na tela —
  // é o zoom do mapa, não o da tipografia.
  $$('#mapa text.rotulo').forEach((texto) => {
    texto.setAttribute('font-size', `${Number(texto.dataset.corpo) / zoom.escala}`);
    texto.setAttribute('stroke-width', `${2.6 / zoom.escala}`);
    const cabe = Number(texto.dataset.caixa) * zoom.escala >= CABE_ROTULO;
    texto.style.display =
      (estado.rotulos === 'todos' || (estado.rotulos === 'auto' && cabe))
        ? '' : 'none';
  });
  $('#zoom-reset').disabled = zoom.escala === 1 && !zoom.x && !zoom.y;
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

/* ------------------------------------------------------------- tooltip */

function linhaDica(rotulo, valor, metrica) {
  const vazio = !Number.isFinite(valor);
  return `<dt>${rotulo}</dt><dd class="${vazio ? 'ausente' : ''}">`
    + `${vazio ? 'não coletado' : formatar(valor, metrica)}</dd>`;
}

function mostrarDica(ente, evento) {
  const dica = $('#dica-mapa');
  if (!ente) { dica.hidden = true; return; }

  const uf = ente.sigla_uf ? ` <span style="color:var(--texto-fraco)">${ente.sigla_uf}</span>` : '';
  dica.innerHTML = `
    <h3>${ente.nome}${uf}</h3>
    <dl>
      ${linhaDica('População', aNumero(ente.populacao), 'populacao')}
      ${linhaDica('Arrecadação', aNumero(ente.receita_total), 'receita_total')}
      ${linhaDica('Despesa', aNumero(ente.despesa_total), 'despesa_total')}
      ${linhaDica('Transferências recebidas',
                  aNumero(ente.transferencia_recebida), 'transferencia_recebida')}
      ${linhaDica('Despesa por habitante',
                  aNumero(ente.despesa_per_capita), 'despesa_per_capita')}
    </dl>
    ${Number.isFinite(aNumero(ente.dependencia_transferencia))
      ? `<p class="pe">${porcento.format(ente.dependencia_transferencia)}% da
         arrecadação veio de transferências.</p>` : ''}
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

  const porCodigo = new Map(estado.entes.map((e) => [String(e.cod_ibge), e]));
  const valores = estado.entes.map((e) => aNumero(e[estado.metrica]));
  const quebras = calcularQuebras(valores);
  const formas = desenharGeoJson(estado.malha, { largura, altura });

  const ns = NS;
  formas.forEach((forma) => {
    // No mapa do Brasil o código vem com 2 dígitos (UF); no de UF, com 7.
    const ente = porCodigo.get(forma.codigo)
      || [...porCodigo.values()].find((e) => String(e.cod_ibge) === forma.codigo);
    const valor = ente ? aNumero(ente[estado.metrica]) : NaN;

    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', forma.d);
    path.setAttribute('fill', corDe(valor, quebras));
    const nome = ente?.nome || forma.nome || forma.codigo;
    path.setAttribute('tabindex', '0');
    path.setAttribute('role', estado.nivel === 'pais' ? 'button' : 'img');
    path.setAttribute('aria-label',
      `${nome}: ${Number.isFinite(valor) ? formatar(valor, estado.metrica) : 'sem dado'}`);

    // Sem <title> nativo: ele e a dica apareceriam juntos, dizendo a mesma
    // coisa duas vezes. O aria-label continua servindo ao leitor de tela.
    path.addEventListener('mouseenter', (ev) => {
      path.classList.add('realcada');
      mostrarDica(ente, ev);
    });
    path.addEventListener('mousemove', posicionarDica);
    path.addEventListener('mouseleave', () => {
      path.classList.remove('realcada');
      $('#dica-mapa').hidden = true;
    });
    path.addEventListener('focus', (ev) => mostrarDica(ente, {
      clientX: path.getBoundingClientRect().left,
      clientY: path.getBoundingClientRect().top,
      ...ev,
    }));
    path.addEventListener('blur', () => { $('#dica-mapa').hidden = true; });

    // O rótulo é o nome curto: sigla no mapa do país, nome no da UF.
    const texto = ente?.sigla_uf && estado.nivel === 'pais'
      ? ente.sigla_uf : (ente?.nome || forma.nome);
    if (texto && forma.centro) {
      const marca = document.createElementNS(ns, 'text');
      marca.setAttribute('class',
        `rotulo${estado.nivel === 'pais' ? '' : ' municipio'}`);
      marca.setAttribute('x', forma.centro[0].toFixed(1));
      marca.setAttribute('y', forma.centro[1].toFixed(1));
      marca.dataset.corpo = estado.nivel === 'pais' ? '11' : '8.5';
      marca.dataset.caixa = String(forma.caixa || 0);
      marca.textContent = texto;
      rotulos.appendChild(marca);
    }

    // No país, clicar desce um nível. Dentro de uma UF, clicar abre a ficha
    // do município — que é onde "quem governa" encontra "quanto gasta".
    const agir = estado.nivel === 'pais'
      ? (ente?.sigla_uf ? () => entrarNaUf(ente.sigla_uf) : null)
      : (ente?.cod_ibge ? () => abrirFicha(ente.cod_ibge) : null);

    if (agir) {
      path.setAttribute('role', 'button');
      path.addEventListener('click', agir);
      path.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); agir(); }
      });
    } else {
      path.classList.add('inerte');
      path.removeAttribute('tabindex');
    }
    camada.appendChild(path);
  });

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

  lista.innerHTML = ordenados.slice(0, 60).map((e, i) => `
    <li>
      <span class="pos">${i + 1}</span>
      ${estado.nivel === 'pais'
        ? `<button data-uf="${e.sigla_uf}">${e.nome}</button>`
        : `<button data-ente="${e.cod_ibge}">${e.nome}</button>`}
      <span class="valor">${formatar(aNumero(e[estado.metrica]), estado.metrica)}</span>
    </li>`).join('');

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
  const codUf = estado.entes[0]?.cod_ibge?.slice(0, 2);
  migalha.innerHTML = `<button id="voltar-brasil">Brasil</button> › ${estado.uf}`
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
    $('#tela-cheia').textContent = ampliado ? 'Reduzir' : 'Ampliar';
    $('#tela-cheia').setAttribute('aria-pressed', String(ampliado));
  });
  // Esc fecha a ampliação. Sem isto, quem ampliou fica preso: o cartão cobre
  // a tela inteira e o botão de reduzir é a única saída visível.
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && $('#cartao-mapa').classList.contains('ampliado')) {
      $('#tela-cheia').click();
    }
  });

  const svg = $('#mapa');
  svg.addEventListener('wheel', (ev) => {
    ev.preventDefault();
    ajustarZoom(ev.deltaY < 0 ? 1.18 : 1 / 1.18, pontoNoMapa(ev));
  }, { passive: false });

  // Arrastar move o mapa; só a partir de 4px, senão um clique com a mão
  // trêmula vira arrasto e a ficha do município não abre.
  let arrastando = null;
  svg.addEventListener('pointerdown', (ev) => {
    if (zoom.escala === 1) return;
    arrastando = { x: ev.clientX, y: ev.clientY, x0: zoom.x, y0: zoom.y, moveu: false };
    svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener('pointermove', (ev) => {
    if (!arrastando) return;
    const caixa = svg.getBoundingClientRect();
    const dx = ((ev.clientX - arrastando.x) / caixa.width) * LARGURA;
    const dy = ((ev.clientY - arrastando.y) / caixa.height) * ALTURA;
    if (Math.abs(dx) + Math.abs(dy) > 4) arrastando.moveu = true;
    zoom.x = arrastando.x0 + dx;
    zoom.y = arrastando.y0 + dy;
    limitarZoom();
    aplicarZoom();
  });
  const soltar = () => { arrastando = null; };
  svg.addEventListener('pointerup', soltar);
  svg.addEventListener('pointercancel', soltar);
  svg.addEventListener('click', (ev) => {
    if (arrastando?.moveu) { ev.stopPropagation(); ev.preventDefault(); }
  }, true);
}

/* ---------------------------------------------------------- ficha do ente */

async function abrirFicha(codIbge) {
  const dialogo = $('#detalhe');
  const alvo = $('#detalhe-conteudo');
  alvo.innerHTML = '<p class="vazio">Carregando…</p>';
  dialogo.showModal();

  const f = await buscar(`/api/ente/${codIbge}`).catch(() => null);
  if (!f) { alvo.innerHTML = '<p class="vazio">Ente não encontrado.</p>'; return; }

  const r = f.resumo || {};
  const cartao = (rotulo, valor) => `
    <div class="cartao" style="padding:12px">
      <div class="rotulo-numero">${rotulo}</div>
      <div class="numero-grande">${valor}</div>
    </div>`;

  alvo.innerHTML = `
    <h2>${f.ente.nome}${f.ente.sigla_uf && f.ente.nivel === 'municipio'
      ? ` — ${f.ente.sigla_uf}` : ''}</h2>
    <p class="rodape-mapa">${f.ente.nivel} · código IBGE ${f.ente.cod_ibge}
      ${f.ano ? ` · dados de ${f.ano}` : ''}</p>

    <div class="tiras">
      ${cartao('Despesa total', formatar(Number(r.despesa_total), 'despesa_total'))}
      ${cartao('População', formatar(Number(r.populacao), 'populacao'))}
      ${cartao('Despesa por habitante',
              formatar(Number(r.despesa_per_capita), 'despesa_per_capita'))}
    </div>

    <h2>Quem governa</h2>
    ${f.governantes.length ? `<table><thead><tr>
        <th>Cargo</th><th>Nome</th><th>Partido</th><th>Mandato</th>
      </tr></thead><tbody>
      ${f.governantes.map((g) => `<tr>
        <td>${g.cargo}</td><td>${g.nome ?? '—'}</td>
        <td>${g.sigla_partido ?? '—'}</td>
        <td>${g.ano_inicio ?? '?'}–${g.ano_fim ?? '?'}</td></tr>`).join('')}
      </tbody></table>`
      : `<p class="vazio">Nenhum mandato ligado a este ente.
         Rode o coletor do TSE — e, se ele já rodou, confira
         <code>/api/de-para/pendencias</code>: pode ser o nome da cidade
         que não casou.</p>`}

    ${f.legislativo.length ? `<h2>Legislativo</h2>
      <table><thead><tr><th>Cargo</th><th>Quantidade</th></tr></thead><tbody>
      ${f.legislativo.map((l) => `<tr><td>${l.cargo}</td>
        <td class="valor">${numero.format(l.quantidade)}</td></tr>`).join('')}
      </tbody></table>` : ''}

    <h2>Em que gasta</h2>
    ${f.financas.length ? `<table><thead><tr>
        <th>Função</th><th>Empenhado</th><th>Fatia</th>
      </tr></thead><tbody>
      ${(() => {
        const total = f.financas.reduce((s, x) => s + Number(x.valor || 0), 0);
        return f.financas.map((x) => `<tr>
          <td>${x.funcao ?? x.cod_funcao}</td>
          <td class="valor">${formatar(Number(x.valor), 'despesa_total')}</td>
          <td class="valor">${total ? (100 * x.valor / total).toFixed(1) : '—'}%</td>
        </tr>`).join('');
      })()}
      </tbody></table>`
      : '<p class="vazio">Finanças não coletadas para este ente.</p>'}

    ${f.indicadores.length ? `<h2>Indicadores</h2>
      <table><thead><tr><th>Indicador</th><th>Ano</th><th>Valor</th></tr></thead>
      <tbody>${f.indicadores.map((i) => `<tr>
        <td>${i.rotulo ?? i.cod_metrica}</td><td>${i.ano}</td>
        <td class="valor">${numero.format(Number(i.valor))}
          ${i.unidade ?? ''}</td></tr>`).join('')}</tbody></table>` : ''}`;
}

/* ---------------------------------------------------------------- políticos */

async function carregarResumoPoliticos() {
  const resumo = await buscar('/api/politicos/resumo').catch(() => null);
  const alvo = $('#resumo-politicos');
  if (!resumo || !resumo.cargos.length) {
    alvo.innerHTML = '<p class="vazio">Nenhum político coletado ainda.</p>';
    return;
  }
  alvo.innerHTML = `
    <table><thead><tr><th>Cargo</th><th>Quantidade</th></tr></thead><tbody>
    ${resumo.cargos.map((c) => `<tr><td>${c.cargo ?? '—'}</td>
      <td class="valor">${numero.format(c.quantidade)}</td></tr>`).join('')}
    </tbody></table>
    <p class="rodape-mapa">Total coletado: ${numero.format(resumo.total)}.</p>`;
}

async function carregarPoliticos() {
  await carregarResumoPoliticos();
  const linhas = await buscar('/api/politicos', {
    uf: $('#filtro-uf').value,
    cargo: $('#filtro-cargo').value,
    busca: $('#filtro-nome').value,
    limite: 300,
  }).catch(() => []);

  const corpo = $('#tabela-politicos tbody');
  corpo.innerHTML = linhas.length ? linhas.map((p) => `
    <tr><td>${p.nome_eleitoral || p.nome || '—'}${
        p.nome && p.nome_eleitoral && p.nome !== p.nome_eleitoral
          ? `<br><span class="cadencia">${p.nome}</span>` : ''}</td>
        <td>${p.cargo ?? '—'}</td>
        <td>${p.sigla_partido ?? '—'}</td>
        <td>${p.sigla_uf ?? '—'}</td>
        <td>${p.fonte_origem ?? '—'}</td></tr>`).join('')
    : '<tr><td colspan="5" class="vazio">Sem resultados.</td></tr>';
}

/* ---------------------------------------------------------------- proposições */

/** Preenche um seletor a partir dos valores que EXISTEM no acervo. */
async function preencherSeletor(seletor, rota, campo, rotuloTodos) {
  const alvo = $(seletor);
  const escolhido = alvo.value;
  const valores = await buscar(rota).catch(() => []);

  alvo.innerHTML = `<option value="">${rotuloTodos}</option>`
    + valores.map((v) => `<option value="${String(v[campo]).replace(/"/g, '&quot;')}">`
      + `${v[campo]} (${numero.format(v.quantidade)})</option>`).join('');

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
  const linhas = await buscar('/api/proposicoes', {
    busca: $('#filtro-proposicao').value,
    situacao: $('#filtro-situacao').value,
    tipo: $('#filtro-tipo').value,
    de: $('#filtro-de').value,
    ate: $('#filtro-ate').value,
    limite: 300,
  }).catch(() => []);

  const corpo = $('#tabela-proposicoes tbody');
  const resumo = $('#resumo-proposicoes');
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

  resumo.textContent = `${numero.format(linhas.length)} proposiç${
    linhas.length === 1 ? 'ão' : 'ões'}`
    + (linhas.length === 300 ? ' (limite da consulta — refine o filtro)' : '');

  corpo.innerHTML = linhas.map((p) => `
    <tr class="clicavel" data-casa="${p.casa}" data-id="${p.id_proposicao}">
      <td><span class="etiqueta">${p.identificador ?? p.sigla_tipo ?? '—'}</span></td>
      <td>${(p.ementa ?? '').slice(0, 190)}${(p.ementa ?? '').length > 190 ? '…' : ''}</td>
      <td>${p.nome_autor ?? '—'}${p.partido_autor ? ` (${p.partido_autor}-${p.uf_autor ?? ''})` : ''}</td>
      <td>${formatarData(p.data_apresentacao)}</td>
      <td>${p.situacao ?? '—'}${p.orgao_atual
        ? `<br><span class="cadencia">${p.orgao_atual}</span>` : ''}</td>
    </tr>`).join('');

  corpo.querySelectorAll('tr.clicavel').forEach((tr) => {
    tr.addEventListener('click', () => abrirProposicao(tr.dataset.casa, tr.dataset.id));
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
  alvo.innerHTML = `
    <h2>${p.identificador ?? ''}</h2>
    <p>${p.ementa ?? ''}</p>
    <p class="rodape-mapa">Autor: <strong>${p.nome_autor ?? '—'}</strong>
      ${p.partido_autor ? `(${p.partido_autor}-${p.uf_autor ?? ''})` : ''}
      · Apresentada em ${formatarData(p.data_apresentacao)}
      · ${p.qtd_autores ?? 0} autor(es)</p>

    <h2>Tramitação — todas as etapas</h2>
    ${detalhe.tramitacoes.length ? `<table><thead><tr>
        <th>Data</th><th>Órgão</th><th>Etapa</th></tr></thead><tbody>
      ${detalhe.tramitacoes.map((t) => `<tr>
        <td>${formatarData(t.data_hora)}</td><td>${t.orgao ?? '—'}</td>
        <td>${t.descricao_tramitacao ?? t.descricao_situacao ?? '—'}</td></tr>`).join('')}
      </tbody></table>`
      : '<p class="vazio">Tramitações não coletadas para esta proposição.</p>'}

    <h2>Votações</h2>
    ${detalhe.votacoes.length ? detalhe.votacoes.map((v) => `
      <div class="cartao" style="margin-bottom:10px">
        <strong>${formatarData(v.data_hora)} · ${v.sigla_orgao ?? ''}</strong>
        <p>${v.descricao ?? ''}</p>
        <div class="placar">
          <span class="sim">A favor: ${v.sim ?? 0}</span>
          <span class="nao">Contra: ${v.nao ?? 0}</span>
          <span>Abstenção: ${v.abstencao ?? 0}</span>
          <span>Outros: ${v.outros ?? 0}</span>
        </div>
        <button class="ver-votos" data-casa="${casa}" data-votacao="${v.id_votacao}">
          Ver quem votou</button>
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
        ${r.votos.map((v) => `<tr>
          <td>${v.nome_politico ?? '—'}</td><td>${v.sigla_partido ?? '—'}</td>
          <td>${v.sigla_uf ?? '—'}</td>
          <td style="color:${/^Sim/i.test(v.voto) ? 'var(--favor)'
            : /^N[ãa]o/i.test(v.voto) ? 'var(--contra)' : 'inherit'}">
            ${v.voto ?? '—'}</td></tr>`).join('')}
        </tbody></table>`;
    });
  });
}

/* ---------------------------------------------------------------- fontes */

async function carregarSituacao() {
  const saude = await buscar('/api/saude').catch(() => null);
  const alvo = $('#situacao-fontes');
  if (!saude || !saude.fontes.length) {
    alvo.innerHTML = '<p class="vazio">Nenhuma coleta registrada. '
      + 'Rode <code>python -m src.scripts.coletar --tudo</code>.</p>';
    return;
  }
  alvo.innerHTML = `<table><thead><tr>
      <th>Fonte</th><th>Recurso</th><th>Linhas</th><th>Situação</th><th>Lido em</th>
    </tr></thead><tbody>
    ${saude.fontes.map((f) => `<tr>
      <td>${f.fonte}</td><td>${f.recurso}</td>
      <td class="valor">${numero.format(f.linhas ?? 0)}</td>
      <td>${f.situacao}</td><td>${formatarData(f.lido_em)}</td></tr>`).join('')}
    </tbody></table>`;
}

/* ------------------------------------------------------------- custo */

async function carregarCusto() {
  const [cargos, resumo] = await Promise.all([
    buscar('/api/custo/cargos').catch(() => []),
    buscar('/api/custo/resumo').catch(() => null),
  ]);

  renderizarTopoDeCusto(resumo);
  renderizarAvisosDeCusto(resumo);
  renderizarTabelaDeCusto(cargos);
  renderizarLateralDeCusto(resumo);
}

function renderizarTopoDeCusto(resumo) {
  const alvo = $('#topo-custo');
  if (!resumo) { alvo.innerHTML = ''; return; }

  const estimado = (resumo.estimado_por_poder || [])
    .reduce((s, p) => s + Number(p.custo_estimado || 0), 0);
  const despesa = (resumo.despesa_por_funcao || [])
    .reduce((s, f) => s + Number(f.valor || 0), 0);

  const tira = (rotulo, valor, nota) => `
    <div class="cartao" style="padding:12px">
      <div class="rotulo-numero">${rotulo}</div>
      <div class="numero-grande">${valor}</div>
      ${nota ? `<div class="cadencia">${nota}</div>` : ''}
    </div>`;

  alvo.innerHTML =
    tira('Arrecadado pelo governo',
         resumo.arrecadacao == null ? 'não coletado'
           : dinheiro.format(resumo.arrecadacao),
         resumo.arrecadacao == null ? 'fonte ainda não implementada' : '')
    + tira('Sai dos cofres — Legislativo, Judiciário e Administração',
           despesa ? dinheiro.format(despesa) : '—',
           resumo.ano ? `despesa empenhada em ${resumo.ano} (SICONFI)` : '')
    + tira('Subsídios (estimativa)',
           estimado ? dinheiro.format(estimado) : '—',
           'ocupantes × subsídio × 13,33');
}

function renderizarAvisosDeCusto(resumo) {
  const alvo = $('#avisos-custo');
  const avisos = resumo?.avisos || [];
  alvo.innerHTML = avisos.length
    ? `<div class="aviso"><strong>Leia antes de citar estes números</strong>
       ${avisos.map((a) => `<div>· ${a}</div>`).join('')}</div>`
    : '';
}

function renderizarTabelaDeCusto(cargos) {
  const corpo = $('#tabela-custo tbody');
  if (!cargos.length) {
    corpo.innerHTML = '<tr><td colspan="5" class="vazio">'
      + 'Nenhum cargo com subsídio no acervo. Se você já rodou '
      + '<strong>Referências</strong>, confira o arquivo '
      + '<code>referencias/subsidios.csv</code>.'
      + '</td></tr>';
    return;
  }

  corpo.innerHTML = cargos.map((c) => `
    <tr>
      <td>${c.cargo}${c.ramo ? `<br><span class="cadencia">${c.ramo}</span>` : ''}</td>
      <td class="valor">${c.ocupantes ? numero.format(c.ocupantes) : '—'}</td>
      <td class="valor">${c.valor_mensal == null ? '—'
        : dinheiro.format(c.valor_mensal)}
        ${c.valor_mensal != null && !c.conferido
          ? ' <span class="nao-conferido" title="valor transcrito e ainda não conferido contra a norma">⚠ a conferir</span>'
          : ''}</td>
      <td class="valor">${c.custo_anual_estimado == null ? '—'
        : dinheiro.format(c.custo_anual_estimado)}</td>
      <td>${c.url_norma
        ? `<a href="${c.url_norma}" target="_blank" rel="noopener">${c.norma ?? 'norma'}</a>`
        : (c.norma ?? '—')}
        ${c.observacao ? `<br><span class="cadencia">${c.observacao}</span>` : ''}</td>
    </tr>`).join('');
}

function renderizarLateralDeCusto(resumo) {
  const alvo = $('#lateral-custo');
  if (!resumo) { alvo.innerHTML = '<p class="vazio">Sem dados.</p>'; return; }

  const bloco = (titulo, linhas, rotulo, campo, nota) => {
    if (!linhas.length) return '';
    const total = linhas.reduce((s, l) => s + Number(l[campo] || 0), 0);
    return `
      <h2 style="margin-top:14px">${titulo}</h2>
      ${nota ? `<p class="rodape-mapa">${nota}</p>` : ''}
      <table><tbody>
        ${linhas.map((l) => `<tr>
          <td>${l[rotulo] ?? '—'}</td>
          <td class="valor">${dinheiro.format(Number(l[campo] || 0))}</td>
        </tr>`).join('')}
        <tr><td><strong>Total</strong></td>
            <td class="valor"><strong>${dinheiro.format(total)}</strong></td></tr>
      </tbody></table>`;
  };

  const conteudo =
    bloco('Despesa por função', resumo.despesa_por_funcao || [], 'funcao',
          'valor', `Valor empenhado em ${resumo.ano ?? '—'} — o que de fato saiu.`)
    + bloco('Custo medido federal', resumo.custo_medido_federal || [],
            'conjunto', 'valor', 'Apurado pelo Tesouro/SIC.')
    + bloco('Subsídios por poder (estimativa)',
            resumo.estimado_por_poder || [], 'poder', 'custo_estimado',
            'Conta, não medição.');

  alvo.innerHTML = conteudo
    || '<p class="vazio">Colete SICONFI, Tesouro e Referências para preencher.</p>';
}

/* ------------------------------------------------------------- atualizar */

let relogioColeta = null;

async function montarCatalogo() {
  const fontes = await buscar('/api/coleta/catalogo').catch(() => []);
  const alvo = $('#catalogo-fontes');
  if (!fontes.length) {
    alvo.innerHTML = '<p class="vazio">Catálogo indisponível.</p>';
    return;
  }
  alvo.innerHTML = fontes.map((f) => `
    <label class="opcao">
      <input type="checkbox" value="${f.fonte}"
             ${['camara', 'senado'].includes(f.fonte) ? 'checked' : ''}>
      <span>${f.rotulo}</span>
      <span class="cadencia">${f.cadencia}</span>
    </label>`).join('');
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

  const r = await fetch('/api/config/chave-portal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chave: campo.value }),
  });
  const corpo = await r.json().catch(() => ({}));
  botao.disabled = false;

  if (!r.ok) {
    resposta.textContent = corpo.detail || `Não deu para salvar (${r.status}).`;
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

  const resp = await fetch('/api/coleta', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo),
  });

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

function acompanharColeta() {
  if (relogioColeta) clearInterval(relogioColeta);
  relogioColeta = setInterval(async () => {
    const tarefa = await buscar('/api/coleta').catch(() => null);
    if (!tarefa) return;
    renderizarColeta(tarefa);
    if (tarefa.situacao !== 'executando') {
      clearInterval(relogioColeta);
      relogioColeta = null;
      $('#botao-atualizar').disabled = false;
      // O armazém mudou: recria as views e recarrega o que está na tela.
      await fetch('/api/recarregar', { method: 'POST' }).catch(() => {});
      await carregarAnos();
      await carregarSituacao();
      await carregarMapa().catch(() => {});
      // Coletar pode ter trazido situações que não existiam no acervo.
      if ($('#tabela-proposicoes tbody').children.length) {
        await montarFiltrosDeProposicao();
        await carregarProposicoes();
      }
    }
  }, 2000);
}

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

  alvo.innerHTML = `
    <p class="rodape-mapa">
      Atualização #${tarefa.id} · ${emAndamento
        ? `rodando ${tarefa.fonte_atual ?? ''}` : tarefa.situacao}
      · ${p.feitas}/${p.total} fontes${problemas.length
        ? ` · <strong>${problemas.join(', ')}</strong>` : ''}
    </p>
    <ul class="etapas">
      ${tarefa.fontes.map((f) => {
        const e = (tarefa.etapas || []).find((x) => x.fonte === f)
          || { situacao: 'aguardando', detalhe: '', erros: [] };
        return `<li class="${e.situacao}">
          <span class="sinal">${SINAIS[e.situacao] ?? '·'}</span>
          <span>${f}</span>
          <span class="cadencia">${ROTULO_ETAPA[e.situacao] ?? e.situacao}</span>
          ${e.detalhe ? `<span class="detalhe">${e.detalhe}</span>` : ''}
          ${(e.erros || []).slice(0, 3).map((m) =>
            `<span class="detalhe">${m}</span>`).join('')}
        </li>`;
      }).join('')}
    </ul>`;

  const registro = $('#log-coleta');
  const linhas = tarefa.linhas || [];
  registro.hidden = linhas.length === 0;
  const colado = registro.scrollTop + registro.clientHeight
    >= registro.scrollHeight - 30;
  registro.innerHTML = linhas.map((l) =>
    `<span class="hora">${l.hora}</span> <span class="${l.nivel}">${
      l.texto.replace(/</g, '&lt;')}</span>`).join('\n');
  if (colado) registro.scrollTop = registro.scrollHeight;
}

/* ---------------------------------------------------------------- início */

async function iniciar() {
  $$('nav button').forEach((b) => b.addEventListener('click', () => trocarAba(b.dataset.aba)));
  $('#ano').addEventListener('change', (e) => { estado.ano = Number(e.target.value); carregarMapa(); });
  $('#metrica').addEventListener('change', (e) => { estado.metrica = e.target.value; carregarMapa(); });
  ligarControlesDoMapa();
  $('#buscar-politicos').addEventListener('click', carregarPoliticos);
  $('#buscar-proposicoes').addEventListener('click', carregarProposicoes);
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
  await carregarSituacao();

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
