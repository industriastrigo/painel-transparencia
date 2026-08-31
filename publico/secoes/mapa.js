/* Seção do Mapa interativo, projeção, legenda, ranking e zoom. */
import { $, $$ } from '../nucleo/ui.js';
import {
  escapar, atributo, txt, endereco, numero, dinheiro, dinheiroExato, dinheiroCurto, data, dataHora,
  aNumero, porcento, porcentoExato, contagem, formatar, exato, fatia, somar, formatarIndicador, formatarData,
  ROTULO_METRICA, PERCENTUAIS, CONTAGENS
} from '../nucleo/formatadores.js';
import { buscar } from '../nucleo/api.js';
import {
  desenharGeoJson, calcularQuebras, corDe, tintaSobre,
  reavaliarTema, RAMPA,
} from '../mapa.js';
import { abrirFicha } from './entes.js';

export const estado = {
  nivel: 'pais',      // pais | estado
  uf: null,
  ano: null,
  metrica: 'despesa_per_capita',
  rotulos: 'auto',     // auto | todos | nenhum
  entes: [],
  malha: null,
};

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


export {
  faltaNoAno, normalizarAnos, carregarAnos, avisarAnoParcial, carregarMapa,
  aplicarZoom, medirRotulo, escreverLinhas, partirEmDuas, encaixarRotulo,
  ajustarZoom, limitarZoom, reenquadrar, pontoNoMapa, realcar,
  linhaDica, avisoLRF, mostrarDica, posicionarDica,
  renderizarMapa, renderizarLegenda, renderizarRanking, renderizarMigalha,
  entrarNaUf, ligarControlesDoMapa
};
