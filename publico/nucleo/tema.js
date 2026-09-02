/* Módulo de Gestão de Temas (Claro / Escuro) - Indústrias Trigo */

const CHAVE_STORAGE = 'painel_tema_preferido';

let temaAtual = 'dark'; // 'dark' | 'light'

export function inicializarTema() {
  const salvo = localStorage.getItem(CHAVE_STORAGE);
  if (salvo && ['dark', 'light'].includes(salvo)) {
    temaAtual = salvo;
  } else {
    // Detecta padrão do sistema na primeira visita
    const prefereDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    temaAtual = prefereDark ? 'dark' : 'light';
  }

  aplicarTema(temaAtual);

  // Se o usuário não tiver preferência fixa salva, acompanha o SO
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', (e) => {
    if (!localStorage.getItem(CHAVE_STORAGE)) {
      temaAtual = e.matches ? 'dark' : 'light';
      aplicarTema(temaAtual);
    }
  });
}

export function obterTemaAtual() {
  return temaAtual;
}

export function obterTemaEfetivo() {
  return temaAtual;
}

export function definirTema(novoTema) {
  if (!['dark', 'light'].includes(novoTema)) return;
  temaAtual = novoTema;
  localStorage.setItem(CHAVE_STORAGE, novoTema);
  aplicarTema(novoTema);
}

export function alternarTema() {
  const proximo = temaAtual === 'dark' ? 'light' : 'dark';
  definirTema(proximo);
  return proximo;
}

function aplicarTema(tema) {
  const raiz = document.documentElement;
  raiz.setAttribute('data-tema', tema);
  raiz.setAttribute('data-tema-modo', tema);

  // Atualiza os botões/ícones de tema na interface
  atualizarIconesTema(tema);

  // Troca sutil da logo conforme o tema
  const srcIcone = tema === 'dark'
    ? 'ativos/logos/icone_trigo_transparente.png'
    : 'ativos/logos/icone_trigo_light_transparente.png';

  const logoTop = document.getElementById('topbar-logo-img');
  if (logoTop) logoTop.src = srcIcone;

  const logoDrawer = document.getElementById('drawer-logo-img');
  if (logoDrawer) logoDrawer.src = srcIcone;
}

function atualizarIconesTema(tema) {
  const botoes = document.querySelectorAll('.btn-toggle-tema');
  botoes.forEach((btn) => {
    if (tema === 'dark') {
      // Estando no Escuro, exibe o Sol para mudar para Claro
      btn.innerHTML = '<svg class="item-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';
      btn.title = 'Mudar para Tema Claro (Marfim Trigo)';
    } else {
      // Estando no Claro, exibe a Lua para mudar para Escuro
      btn.innerHTML = '<svg class="item-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
      btn.title = 'Mudar para Tema Escuro (Ônix Trigo)';
    }
  });

  const rotuloModal = document.getElementById('perfil-tema-rotulo');
  if (rotuloModal) {
    rotuloModal.textContent = tema === 'dark' ? 'Tema Escuro (Ônix)' : 'Tema Claro (Marfim)';
  }
}
