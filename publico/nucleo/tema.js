/* Módulo de Gestão de Temas (Dark / Light / Sistema) - Indústrias Trigo */

const CHAVE_STORAGE = 'painel_tema_preferido';

let temaAtual = 'sistema'; // 'sistema' | 'dark' | 'light'

export function inicializarTema() {
  const salvo = localStorage.getItem(CHAVE_STORAGE);
  if (salvo && ['sistema', 'dark', 'light'].includes(salvo)) {
    temaAtual = salvo;
  } else {
    temaAtual = 'sistema';
  }

  aplicarTema(temaAtual);

  // Escuta alterações sistêmicas no SO
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', () => {
    if (temaAtual === 'sistema') {
      aplicarTema('sistema');
    }
  });
}

export function obterTemaAtual() {
  return temaAtual;
}

export function obterTemaEfetivo() {
  if (temaAtual === 'sistema') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return temaAtual;
}

export function definirTema(novoTema) {
  if (!['sistema', 'dark', 'light'].includes(novoTema)) return;
  temaAtual = novoTema;
  localStorage.setItem(CHAVE_STORAGE, novoTema);
  aplicarTema(novoTema);
}

export function alternarTema() {
  const proximo = temaAtual === 'dark' ? 'light' : (temaAtual === 'light' ? 'sistema' : 'dark');
  definirTema(proximo);
  return proximo;
}

function aplicarTema(tema) {
  const raiz = document.documentElement;
  const efetivo = tema === 'sistema'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : tema;

  raiz.setAttribute('data-tema', efetivo);
  raiz.setAttribute('data-tema-modo', tema);

  // Atualiza os botões/ícones de tema na interface
  atualizarIconesTema(tema, efetivo);

  // Troca sutil da logo conforme o tema efetivo
  const srcIcone = efetivo === 'dark'
    ? 'ativos/logos/icone_trigo_transparente.png'
    : 'ativos/logos/icone_trigo_light_transparente.png';

  const logoTop = document.getElementById('topbar-logo-img');
  if (logoTop) logoTop.src = srcIcone;

  const logoDrawer = document.getElementById('drawer-logo-img');
  if (logoDrawer) logoDrawer.src = srcIcone;
}

function atualizarIconesTema(modo, efetivo) {
  const botoes = document.querySelectorAll('.btn-toggle-tema');
  botoes.forEach((btn) => {
    if (modo === 'sistema') {
      btn.innerHTML = '<svg class="item-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>';
      btn.title = `Tema: Automático (${efetivo === 'dark' ? 'Escuro' : 'Claro'}) — Clique para alternar`;
    } else if (modo === 'dark') {
      btn.innerHTML = '<svg class="item-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
      btn.title = 'Tema: Escuro (Ônix Trigo) — Clique para alternar';
    } else {
      btn.innerHTML = '<svg class="item-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';
      btn.title = 'Tema: Claro (Marfim Trigo) — Clique para alternar';
    }
  });

  const rotuloModal = document.getElementById('perfil-tema-rotulo');
  if (rotuloModal) {
    if (modo === 'sistema') rotuloModal.textContent = `Automático (${efetivo === 'dark' ? 'Escuro' : 'Claro'})`;
    else if (modo === 'dark') rotuloModal.textContent = 'Escuro (Ônix Trigo)';
    else rotuloModal.textContent = 'Claro (Marfim Trigo)';
  }
}
