/* Módulo de Autenticação Google & Perfil do Usuário - Indústrias Trigo */

const CLIENT_ID_GOOGLE = '557640394651-7p5hjc27lsjj2s3eklm3d3q97pvc412g.apps.googleusercontent.com';
const CHAVE_STORAGE_USUARIO = 'painel_usuario_google';
const CHAVE_STORAGE_CGU = 'painel_chave_cgu_pessoal';

// Abas públicas que não exigem registro
const ABAS_PUBLICAS = new Set(['inicio', 'glossario']);

let usuarioAtual = null;
let destinoPendenteAposLogin = null;
const ouvintesAuth = [];

export function inicializarAuth() {
  // Carrega usuário salvo na sessão
  const salvo = localStorage.getItem(CHAVE_STORAGE_USUARIO);
  if (salvo) {
    try {
      usuarioAtual = JSON.parse(salvo);
    } catch (e) {
      usuarioAtual = null;
    }
  }

  renderizarWidgetAuth();
  configurarEventosAuth();
  notificarMudancaAuth();

  // Inicializa Google Identity Services se disponível
  if (window.google?.accounts?.id) {
    window.google.accounts.id.initialize({
      client_id: CLIENT_ID_GOOGLE,
      callback: lidarComRespostaGoogle,
      auto_select: false,
      cancel_on_tap_outside: true,
    });
  } else {
    // Tenta novamente caso o script ainda esteja carregando
    window.addEventListener('load', () => {
      if (window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID_GOOGLE,
          callback: lidarComRespostaGoogle,
        });
      }
    });
  }
}

export function usuarioAutenticado() {
  return Boolean(usuarioAtual);
}

export function abaRequerAuth(aba) {
  if (!aba) return false;
  return !ABAS_PUBLICAS.has(aba);
}

export function aoMudarAuth(callback) {
  if (typeof callback === 'function') {
    ouvintesAuth.push(callback);
    callback(usuarioAtual);
  }
}

function notificarMudancaAuth() {
  ouvintesAuth.forEach((fn) => {
    try { fn(usuarioAtual); } catch (e) { console.error('Erro em ouvinte auth:', e); }
  });
}

export function obterUsuarioAtual() {
  return usuarioAtual;
}

export function obterChaveCguPessoal() {
  return localStorage.getItem(CHAVE_STORAGE_CGU) || '';
}

export function salvarChaveCguPessoal(chave) {
  if (chave && chave.trim()) {
    localStorage.setItem(CHAVE_STORAGE_CGU, chave.trim());
  } else {
    localStorage.removeItem(CHAVE_STORAGE_CGU);
  }
}

function lidarComRespostaGoogle(resposta) {
  if (!resposta || !resposta.credential) return;

  try {
    const payload = decodificarJwt(resposta.credential);
    usuarioAtual = {
      id: payload.sub,
      nome: payload.name,
      email: payload.email,
      foto: payload.picture,
      primeiroNome: payload.given_name || payload.name?.split(' ')[0],
      conectadoEm: new Date().toISOString(),
    };

    localStorage.setItem(CHAVE_STORAGE_USUARIO, JSON.stringify(usuarioAtual));
    renderizarWidgetAuth();
    notificarMudancaAuth();

    // Fecha modal de aviso se estiver aberto
    const modalAviso = document.getElementById('modal-aviso-registro');
    if (modalAviso && modalAviso.close) modalAviso.close();

    // Redireciona para o destino desejado se houver
    if (destinoPendenteAposLogin) {
      const destino = destinoPendenteAposLogin;
      destinoPendenteAposLogin = null;
      import('./abas.js').then((m) => m.trocarAba(destino));
    }
  } catch (erro) {
    console.error('Erro ao processar login Google:', erro);
  }
}

function decodificarJwt(token) {
  const base64Url = token.split('.')[1];
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
  const jsonPayload = decodeURIComponent(
    atob(base64)
      .split('')
      .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
      .join('')
  );
  return JSON.parse(jsonPayload);
}

export function renderizarWidgetAuth() {
  const container = document.getElementById('topbar-auth-widget');
  if (!container) return;

  if (usuarioAtual) {
    container.innerHTML = `
      <button id="btn-abrir-perfil" class="btn-perfil-topbar" title="Perfil: ${usuarioAtual.nome} (${usuarioAtual.email})">
        <img src="${usuarioAtual.foto || 'ativos/logos/icone_trigo_dark.png'}" alt="${usuarioAtual.nome}" class="avatar-topbar" />
        <span class="nome-perfil-topbar">${usuarioAtual.primeiroNome || 'Auditor'}</span>
        <span class="seta-perfil">▾</span>
      </button>
    `;
  } else {
    container.innerHTML = `
      <button id="btn-login-google" class="btn-login-google-topbar" title="Entrar com conta Google para ter acesso ao painel">
        <span>Entrar</span>
      </button>
    `;
  }

  // Atualiza modal de perfil se estiver aberto
  atualizarModalPerfil();
}

function configurarEventosAuth() {
  document.addEventListener('click', (e) => {
    if (e.target.closest('#btn-login-google') || e.target.closest('#btn-login-modal-aviso') || e.target.closest('#btn-entrar-hero-inicio') || e.target.closest('#btn-aderir-hero-inicio')) {
      dispararLoginGoogle();
    } else if (e.target.closest('#btn-abrir-perfil')) {
      abrirModalPerfil();
    } else if (e.target.closest('#btn-logout-perfil')) {
      desconectarUsuario();
    } else if (e.target.closest('#btn-salvar-chave-cgu')) {
      const input = document.getElementById('input-chave-cgu-perfil');
      if (input) {
        salvarChaveCguPessoal(input.value);
        const feedback = document.getElementById('feedback-chave-cgu');
        if (feedback) {
          feedback.textContent = '✓ Chave salva com sucesso!';
          feedback.style.display = 'block';
          setTimeout(() => { feedback.style.display = 'none'; }, 2500);
        }
      }
    }
  });
}

export function dispararLoginGoogle(destinoAposLogin = null) {
  if (destinoAposLogin) {
    destinoPendenteAposLogin = destinoAposLogin;
  }

  if (window.google?.accounts?.id) {
    window.google.accounts.id.prompt();
  } else {
    // Fallback amigável de demonstração
    const nomeDemo = prompt('Digite seu nome para login no Painel da Transparência:', 'Johnny Trigo');
    if (nomeDemo) {
      usuarioAtual = {
        id: 'demo_' + Date.now(),
        nome: nomeDemo,
        email: 'johnny.trigo@industriastrigo.com.br',
        foto: 'ativos/logos/icone_trigo_dark.png',
        primeiroNome: nomeDemo.split(' ')[0],
        conectadoEm: new Date().toISOString(),
      };
      localStorage.setItem(CHAVE_STORAGE_USUARIO, JSON.stringify(usuarioAtual));
      renderizarWidgetAuth();
      notificarMudancaAuth();

      const modalAviso = document.getElementById('modal-aviso-registro');
      if (modalAviso && modalAviso.close) modalAviso.close();

      if (destinoPendenteAposLogin) {
        const destino = destinoPendenteAposLogin;
        destinoPendenteAposLogin = null;
        import('./abas.js').then((m) => m.trocarAba(destino));
      }
    }
  }
}

export function abrirModalAvisoRegistro(destinoDesejado = null) {
  if (destinoDesejado) {
    destinoPendenteAposLogin = destinoDesejado;
  }
  const modal = document.getElementById('modal-aviso-registro');
  if (modal && modal.showModal) {
    modal.showModal();
  } else {
    dispararLoginGoogle(destinoDesejado);
  }
}

export function desconectarUsuario() {
  usuarioAtual = null;
  localStorage.removeItem(CHAVE_STORAGE_USUARIO);
  renderizarWidgetAuth();
  notificarMudancaAuth();

  const modal = document.getElementById('modal-perfil-usuario');
  if (modal && modal.close) modal.close();

  // Força retorno à página inicial aberta
  import('./abas.js').then((m) => m.trocarAba('inicio'));
}

function abrirModalPerfil() {
  const modal = document.getElementById('modal-perfil-usuario');
  if (!modal) return;
  atualizarModalPerfil();
  modal.showModal();
}

function atualizarModalPerfil() {
  const avatar = document.getElementById('perfil-modal-avatar');
  const nome = document.getElementById('perfil-modal-nome');
  const email = document.getElementById('perfil-modal-email');
  const inputCgu = document.getElementById('input-chave-cgu-perfil');

  if (avatar) avatar.src = usuarioAtual?.foto || 'ativos/logos/icone_trigo_dark.png';
  if (nome) nome.textContent = usuarioAtual?.nome || 'Usuário Visitante';
  if (email) email.textContent = usuarioAtual?.email || 'Acesso não autenticado';
  if (inputCgu) inputCgu.value = obterChaveCguPessoal();
}

