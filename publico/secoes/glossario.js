/* Seção Glossário, Conceitos & Metodologia - Indústrias Trigo */

import { $, $$ } from '../nucleo/ui.js';

export function carregarGlossario() {
  configurarEventosGlossario();
}

export function configurarEventosGlossario() {
  // Configuração dos links rápidos do índice
  $$('.indice-glossario a').forEach((link) => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (href && href.startsWith('#')) {
        const id = href.slice(1);
        const destino = document.getElementById(id);
        if (destino) {
          e.preventDefault();
          history.replaceState(null, '', href);
          destino.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });
}
