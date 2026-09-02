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
  const logoImg = document.getElementById('topbar-logo-img');
  if (logoImg) {
    logoImg.src = efetivo === 'dark'
      ? 'ativos/logos/icone_trigo_dark.png'
      : 'ativos/logos/icone_trigo_light.jpg';
  }
}

function atualizarIconesTema(modo, efetivo) {
  const botoes = document.querySelectorAll('.btn-toggle-tema');
  botoes.forEach((btn) => {
    if (modo === 'sistema') {
      btn.innerHTML = '<span>🌓</span>';
      btn.title = `Tema: Automático (${efetivo === 'dark' ? 'Escuro' : 'Claro'}) — Clique para alternar`;
    } else if (modo === 'dark') {
      btn.innerHTML = '<span>🌙</span>';
      btn.title = 'Tema: Escuro (Ônix Trigo) — Clique para alternar';
    } else {
      btn.innerHTML = '<span>☀️</span>';
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
