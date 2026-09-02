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

  // Ouve mudanças de autenticação para atualizar indicadores de bloqueio
  import('./auth.js').then(({ aoMudarAuth, abaRequerAuth }) => {
    aoMudarAuth((usuario) => {
      atualizarBloqueiosDrawer(Boolean(usuario), abaRequerAuth);
    });
  });
}

function atualizarBloqueiosDrawer(estaLogado, checarRequerAuth) {
  const drawer = document.getElementById('drawer-menu');
  if (!drawer) return;

  drawer.querySelectorAll('.drawer-nav-item').forEach((item) => {
    const aba = item.dataset.aba;
    const requerAuth = checarRequerAuth ? checarRequerAuth(aba) : (aba !== 'inicio' && aba !== 'glossario');

    // Remove badge anterior se houver
    const badgeAntigo = item.querySelector('.badge-lock-drawer');
    if (badgeAntigo) badgeAntigo.remove();

    if (requerAuth && !estaLogado) {
      item.classList.add('item-bloqueado');
      const badge = document.createElement('span');
      badge.className = 'badge-lock-drawer';
      badge.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>`;
      badge.title = 'Acesso liberado após registro';
      item.appendChild(badge);
    } else {
      item.classList.remove('item-bloqueado');
    }
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
