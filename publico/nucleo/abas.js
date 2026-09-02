/* Controle de abas e atalhos de teclado (WAI-ARIA). */
import { $, $$ } from './ui.js';
import { atualizarItemAtivoDrawer } from './drawer.js';
import { usuarioAutenticado, abaRequerAuth, abrirModalAvisoRegistro } from './auth.js';

export const abasCarregadas = new Set();
export const ganchosDeAba = {};

export function registrarGanchoAba(nome, fn) {
  ganchosDeAba[nome] = fn;
}

export function trocarAba(destino, { focar = false } = {}) {
  if (!destino) return;

  // Intercepta tentativas de acesso a abas de dados sem autenticação
  if (abaRequerAuth(destino) && !usuarioAutenticado()) {
    abrirModalAvisoRegistro(destino);
    // Se a página já está no início ou glossário, permanece nela
    const abaAtual = location.hash.slice(1);
    if (!abaAtual || abaRequerAuth(abaAtual)) {
      destino = 'inicio';
    } else {
      return;
    }
  }

  $$('header nav button[data-aba], .drawer-nav-item[data-aba]').forEach((b) => {
    const ativa = b.dataset.aba === destino;
    b.setAttribute('aria-selected', String(ativa));
    b.tabIndex = ativa ? 0 : -1;
  });
  $$('main > section').forEach((sec) => {
    const ativa = sec.id === `aba-${destino}`;
    sec.hidden = !ativa;
    sec.style.display = ativa ? 'block' : 'none';
    if (ativa) sec.classList.add('aba-ativa');
    else sec.classList.remove('aba-ativa');
  });

  atualizarItemAtivoDrawer(destino);

  if (focar) $(`#aba-${destino}`)?.focus();
  if (location.hash.slice(1) !== destino) history.replaceState(null, '', `#${destino}`);

  const carregar = ganchosDeAba[destino];

  if (carregar && !abasCarregadas.has(destino)) {
    abasCarregadas.add(destino);
    Promise.resolve(carregar()).catch((erro) => {
      abasCarregadas.delete(destino);
      console.error(`aba ${destino}`, erro);
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

