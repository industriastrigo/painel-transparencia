/* Controle de abas e atalhos de teclado (WAI-ARIA). */
import { $, $$ } from './ui.js';

export const abasCarregadas = new Set();
export const ganchosDeAba = {};

export function registrarGanchoAba(nome, fn) {
  ganchosDeAba[nome] = fn;
}

export function trocarAba(destino, { focar = false } = {}) {
  if (!destino) return;

  $$('header nav button[data-aba]').forEach((b) => {
    const ativa = b.dataset.aba === destino;
    b.setAttribute('aria-selected', String(ativa));
    b.tabIndex = ativa ? 0 : -1;
  });
  $$('main > section').forEach((sec) => { sec.hidden = sec.id !== `aba-${destino}`; });

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
