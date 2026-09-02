/* Controle de abas e atalhos de teclado (WAI-ARIA). */
import { $, $$ } from './ui.js';
import { atualizarItemAtivoDrawer } from './drawer.js';
import { usuarioAutenticado, abaRequerAuth, abrirModalAvisoRegistro } from './auth.js';

export const abasCarregadas = new Set();
export const ganchosDeAba = {};

export function registrarGanchoAba(nome, fn) {
  ganchosDeAba[nome] = fn;
}

export function normalizarNomeAba(destino) {
  if (!destino) return 'inicio';
  // Sub-âncoras de glossário mapeiam para a aba glossario
  if (destino.startsWith('glos-') || destino.startsWith('glossario-')) {
    return 'glossario';
  }
  return destino;
}

export function trocarAba(destino, { focar = false } = {}) {
  if (!destino) return;

  const subAncora = (destino.startsWith('glos-') || destino.startsWith('glossario-')) ? destino : null;
  const abaReal = normalizarNomeAba(destino);

  // Intercepta tentativas de acesso a abas de dados sem autenticação
  if (abaRequerAuth(abaReal) && !usuarioAutenticado()) {
    abrirModalAvisoRegistro(abaReal);
    const abaAtual = normalizarNomeAba(location.hash.slice(1));
    if (!abaAtual || abaRequerAuth(abaAtual)) {
      destino = 'inicio';
    } else {
      return;
    }
  }

  const abaAlvo = normalizarNomeAba(destino);

  $$('header nav button[data-aba], .drawer-nav-item[data-aba]').forEach((b) => {
    const ativa = b.dataset.aba === abaAlvo;
    b.setAttribute('aria-selected', String(ativa));
    b.tabIndex = ativa ? 0 : -1;
  });
  $$('main > section').forEach((sec) => {
    const ativa = sec.id === `aba-${abaAlvo}`;
    sec.hidden = !ativa;
    sec.style.display = ativa ? 'block' : 'none';
    if (ativa) sec.classList.add('aba-ativa');
    else sec.classList.remove('aba-ativa');
  });

  atualizarItemAtivoDrawer(abaAlvo);

  if (focar) $(`#aba-${abaAlvo}`)?.focus();
  if (location.hash.slice(1) !== destino) history.replaceState(null, '', `#${destino}`);

  if (subAncora) {
    setTimeout(() => {
      const el = document.getElementById(subAncora) || document.querySelector(`[data-ancora="${subAncora}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  const carregar = ganchosDeAba[abaAlvo];

  if (carregar && !abasCarregadas.has(abaAlvo)) {
    abasCarregadas.add(abaAlvo);
    Promise.resolve(carregar()).catch((erro) => {
      abasCarregadas.delete(abaAlvo);
      console.error(`aba ${abaAlvo}`, erro);
    });
  }
}

export function forcarRecargaAba(destino) {
  if (!destino) return Promise.resolve();
  abasCarregadas.delete(destino);
  const carregar = ganchosDeAba[destino];
  if (carregar) {
    abasCarregadas.add(destino);
    return Promise.resolve(carregar()).catch((erro) => {
      abasCarregadas.delete(destino);
      console.error(`aba ${destino}`, erro);
    });
  }
  return Promise.resolve();
}

export function ligarTeclasDasAbas() {
  const botoes = $$('header nav button[data-aba]');
  const navPrincipal = $('header nav');
  if (!navPrincipal) return;

  navPrincipal.addEventListener('keydown', (ev) => {
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

