/* Módulo de Autenticação Google & Perfil do Usuário - Indústrias Trigo */

const CLIENT_ID_GOOGLE = '557640394651-7p5hjc27lsjj2s3eklm3d3q97pvc412g.apps.googleusercontent.com';
const CHAVE_STORAGE_USUARIO = 'painel_usuario_google';
const CHAVE_STORAGE_CGU = 'painel_chave_cgu_pessoal';

let usuarioAtual = null;

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
      <button id="btn-login-google" class="btn-login-google-topbar" title="Entrar com conta para personalizar o painel">
        <span>Entrar</span>
      </button>
    `;
  }

  // Atualiza modal de perfil se estiver aberto
  atualizarModalPerfil();
}

function configurarEventosAuth() {
  document.addEventListener('click', (e) => {
    if (e.target.closest('#btn-login-google')) {
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

function dispararLoginGoogle() {
  if (window.google?.accounts?.id) {
    window.google.accounts.id.prompt();
  } else {
    // Fallback simulado
    const nomeDemo = prompt('Digite seu nome para login no painel:', 'Johnny Trigo');
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
    }
  }
}

function desconectarUsuario() {
  usuarioAtual = null;
  localStorage.removeItem(CHAVE_STORAGE_USUARIO);
  renderizarWidgetAuth();
  const modal = document.getElementById('modal-perfil-usuario');
  if (modal && modal.close) modal.close();
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
