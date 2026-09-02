/* Módulo do Menu Lateral Deslizante (Drawer) - Indústrias Trigo */

import { trocarAba } from './abas.js';

let drawerAberto = false;

export function inicializarDrawer() {
  const btnHamburguer = document.getElementById('btn-menu-hamburguer');
  const btnFechar = document.getElementById('btn-fechar-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const drawer = document.getElementById('drawer-menu');

  if (!drawer) return;

  btnHamburguer?.addEventListener('click', () => {
    if (drawerAberto) fecharDrawer();
    else abrirDrawer();
  });

  btnFechar?.addEventListener('click', fecharDrawer);
  backdrop?.addEventListener('click', fecharDrawer);

  // Fecha com a tecla ESC
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawerAberto) {
      fecharDrawer();
    }
  });

  // Links de navegação dentro do drawer
  const links = drawer.querySelectorAll('.drawer-nav-item');
  links.forEach((link) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const destino = link.dataset.aba;
      if (destino) {
        trocarAba(destino, { focar: true });
        fecharDrawer();
      }
    });
  });
}

export function abrirDrawer() {
  const drawer = document.getElementById('drawer-menu');
  const backdrop = document.getElementById('drawer-backdrop');
  const btnHamburguer = document.getElementById('btn-menu-hamburguer');

  if (!drawer || !backdrop) return;

  drawerAberto = true;
  drawer.classList.add('aberto');
  backdrop.classList.add('ativo');
  btnHamburguer?.classList.add('ativo');
  document.body.style.overflow = 'hidden';
}

export function fecharDrawer() {
  const drawer = document.getElementById('drawer-menu');
  const backdrop = document.getElementById('drawer-backdrop');
  const btnHamburguer = document.getElementById('btn-menu-hamburguer');

  if (!drawer || !backdrop) return;

  drawerAberto = false;
  drawer.classList.remove('aberto');
  backdrop.classList.remove('ativo');
  btnHamburguer?.classList.remove('ativo');
  document.body.style.overflow = '';
}

export function atualizarItemAtivoDrawer(abaId) {
  const drawer = document.getElementById('drawer-menu');
  if (!drawer) return;

  drawer.querySelectorAll('.drawer-nav-item').forEach((item) => {
    if (item.dataset.aba === abaId) {
      item.classList.add('ativo');
      item.setAttribute('aria-current', 'page');
    } else {
      item.classList.remove('ativo');
      item.removeAttribute('aria-current');
    }
  });

  // Atualiza título da topbar
  const tituloPagina = document.getElementById('topbar-titulo-pagina');
  const itemAtivo = drawer.querySelector(`.drawer-nav-item[data-aba="${abaId}"]`);
  if (tituloPagina && itemAtivo) {
    const texto = itemAtivo.querySelector('.item-texto')?.textContent || itemAtivo.textContent;
    const iconeHtml = itemAtivo.querySelector('.item-icone')?.innerHTML || '';
    tituloPagina.innerHTML = `${iconeHtml} <strong>${texto.trim()}</strong>`;
  }
}
