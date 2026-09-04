/* Painel da Transparência — Ponto de Entrada Modular. */

import { $, $$ } from './nucleo/ui.js';
import { buscar } from './nucleo/api.js';
import { trocarAba, ligarTeclasDasAbas, registrarGanchoAba, forcarRecargaAba } from './nucleo/abas.js';
import { reavaliarTema } from './mapa.js';
import { inicializarTema, alternarTema, definirTema } from './nucleo/tema.js';
import { inicializarAuth } from './nucleo/auth.js';
import { inicializarDrawer } from './nucleo/drawer.js';

import {
  estado, carregarAnos, avisarAnoParcial, carregarMapa,
  ligarControlesDoMapa
} from './secoes/mapa.js';

import {
  carregarPoliticos, ligarDicaDePoliticos
} from './secoes/politicos.js';

import {
  carregarExecutivo, configurarEventosExecutivo
} from './secoes/executivo.js';

import {
  carregarLegislativo, inicializarEventosLegislativo
} from './secoes/legislativo.js';

import {
  carregarJudiciario, configurarEventosJudiciario
} from './secoes/judiciario.js';

import {
  carregarMp, inicializarEventosMp
} from './secoes/mp.js';

import {
  montarFiltrosDeProposicao, carregarProposicoes
} from './secoes/proposicoes.js';

import {
  carregarCusto
} from './secoes/custo.js';

import {
  carregarInicio
} from './secoes/inicio.js';

import {
  carregarGlossario
} from './secoes/glossario.js';

import {
  carregarCatalogo
} from './secoes/catalogo.js';

// Registro dos ganchos de carregamento preguiçoso por aba
registrarGanchoAba('inicio', carregarInicio);
registrarGanchoAba('mapa', async () => {
  if (!estado.ano || !estado.anos?.length) {
    await carregarAnos();
  }
  await carregarMapa();
});
registrarGanchoAba('politicos', carregarPoliticos);
registrarGanchoAba('executivo', carregarExecutivo);
registrarGanchoAba('legislativo', carregarLegislativo);
registrarGanchoAba('judiciario', carregarJudiciario);
registrarGanchoAba('mp', carregarMp);
registrarGanchoAba('proposicoes', () => montarFiltrosDeProposicao().then(carregarProposicoes));
registrarGanchoAba('custo', carregarCusto);
registrarGanchoAba('glossario', carregarGlossario);
registrarGanchoAba('catalogo', carregarCatalogo);


async function iniciar() {
  // Inicialização do Design System Indústrias Trigo
  inicializarTema();
  inicializarAuth();
  inicializarDrawer();

  // Controle dinâmico de visibilidade de ferramentas de engenharia por ambiente
  try {
    const resSaude = await fetch('/saude');
    if (resSaude.ok) {
      const dadosSaude = await resSaude.json();
      const isDev = dadosSaude.ambiente === 'dev' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
      if (!isDev) {
        $$('.apenas-dev').forEach((el) => {
          el.style.display = 'none';
        });
      }
    }
  } catch (e) {
    // Em caso de falha, mantém padrão seguro
  }

  // Evento do botão de alternância de tema
  $$('.btn-toggle-tema').forEach((btn) => {
    btn.addEventListener('click', () => {
      alternarTema();
      reavaliarTema();
      if (estado.entes && estado.entes.length) carregarMapa().catch(() => {});
    });
  });

  const botoesAbas = $$('header nav button[data-aba], .drawer-nav-item[data-aba]');
  botoesAbas.forEach((b) => b.addEventListener('click', () => trocarAba(b.dataset.aba)));
  ligarTeclasDasAbas();

  const abaInicial = location.hash.slice(1) || 'inicio';
  trocarAba(abaInicial);

  window.addEventListener('hashchange', () => {
    const aba = location.hash.slice(1);
    if (aba) trocarAba(aba);
  });

  $('#ano').addEventListener('change', (e) => {
    estado.ano = Number(e.target.value);
    avisarAnoParcial();
    carregarMapa();
  });
  $('#metrica').addEventListener('change', (e) => {
    estado.metrica = e.target.value;
    carregarMapa();
  });
  ligarControlesDoMapa();
  ligarDicaDePoliticos();

  window.matchMedia?.('(prefers-color-scheme: dark)')?.addEventListener?.('change', () => {
    reavaliarTema();
    if (estado.entes.length) carregarMapa().catch(() => {});
  });

  $('#buscar-politicos').addEventListener('click', carregarPoliticos);
  $('#filtro-ano-politico')?.addEventListener('change', carregarPoliticos);
  $('#filtro-cargo')?.addEventListener('change', carregarPoliticos);
  $('#buscar-proposicoes').addEventListener('click', carregarProposicoes);
  ['#filtro-uf', '#filtro-nome', '#filtro-partido'].forEach((sel) => {
    $(sel)?.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') carregarPoliticos();
    });
  });
  $('#filtro-situacao').addEventListener('change', carregarProposicoes);
  $('#filtro-tipo').addEventListener('change', carregarProposicoes);
  $('#filtro-proposicao').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') carregarProposicoes();
  });
  $('#limpar-proposicoes').addEventListener('click', () => {
    ['#filtro-proposicao', '#filtro-situacao', '#filtro-tipo',
     '#filtro-de', '#filtro-ate'].forEach((s) => { $(s).value = ''; });
    carregarProposicoes();
  });
  configurarEventosExecutivo();
  inicializarEventosLegislativo();
  configurarEventosJudiciario();
  inicializarEventosMp();
  configurarEventosCatalogo();

  const modalDetalhe = $('#detalhe');
  const btnFechar = $('#fechar-detalhe');
  if (modalDetalhe) {
    const fecharModal = (e) => {
      if (e) e.stopPropagation();
      modalDetalhe.close();
    };
    btnFechar?.addEventListener('click', fecharModal);
    btnFechar?.addEventListener('touchend', fecharModal);

    // Fechar ao clicar fora (no backdrop escuro)
    modalDetalhe.addEventListener('click', (e) => {
      const rect = modalDetalhe.getBoundingClientRect();
      const clicouDentro = (
        rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
        rect.left <= e.clientX && e.clientX <= rect.left + rect.width
      );
      if (!clicouDentro) modalDetalhe.close();
    });
  }

  $('#botao-atualizar').addEventListener('click', dispararColeta);
  $('#salvar-chave').addEventListener('click', salvarChave);
  $('#campo-chave').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') salvarChave();
  });

  // Atalho de teclado Ctrl + T para refresh rápido do painel
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 't') {
      e.preventDefault();
      recarregarPainelCompleto();
    }
  });

  // Botão de refresh no cabeçalho
  $('#btn-recarregar-painel')?.addEventListener('click', () => {
    recarregarPainelCompleto();
  });

  await carregarAnos();

  const ultima = await buscar('/api/coleta').catch(() => null);
  if (ultima && ultima.situacao !== 'nenhuma') {
    await montarCatalogo();
    renderizarColeta(ultima);
    if (ultima.situacao === 'executando') {
      $('#botao-atualizar').disabled = true;
      acompanharColeta();
    }
  }
  if (estado.ano) {
    await carregarMapa().catch((erro) => {
      $('#rodape-mapa').textContent = `Não foi possível montar o mapa: ${erro.message}`;
    });
  } else {
    $('#rodape-mapa').textContent =
      'Nenhum dado no armazém. Rode a primeira carga: INSTALAR.bat';
  }
}

export function mostrarNotificacaoRecarga(msg = '<svg class="item-svg-inline" viewBox="0 0 24 24" width="16" height="16"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> Painel atualizado com sucesso!') {
  let toast = $('#toast-notificacao');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast-notificacao';
    toast.style.cssText = 'position:fixed; bottom:24px; right:24px; background:var(--superficie-3, #1e293b); color:var(--texto, #f8fafc); border:1px solid var(--realce, #38bdf8); padding:10px 18px; border-radius:8px; box-shadow:0 10px 25px rgba(0,0,0,0.5); z-index:9999; font-weight:600; display:flex; align-items:center; gap:8px; transition:opacity 0.25s ease, transform 0.25s ease; opacity:0; transform:translateY(10px); pointer-events:none;';
    document.body.appendChild(toast);
  }
  toast.innerHTML = msg;
  toast.style.opacity = '1';
  toast.style.transform = 'translateY(0)';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
  }, 2200);
}

export async function recarregarPainelCompleto() {
  const abaAtiva = location.hash.slice(1) || 'mapa';
  try {
    await fetch('/api/recarregar', { method: 'POST' }).catch(() => {});
    if (abaAtiva === 'mapa') {
      await carregarAnos();
      await carregarMapa();
    } else {
      await forcarRecargaAba(abaAtiva);
    }
    mostrarNotificacaoRecarga('<svg class="item-svg-inline" viewBox="0 0 24 24" width="16" height="16"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> Painel e dados atualizados com sucesso!');
  } catch (erro) {
    console.error('Erro ao atualizar painel:', erro);
    mostrarNotificacaoRecarga('<svg class="item-svg-inline" viewBox="0 0 24 24" width="16" height="16"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> Erro ao atualizar painel');
  }
}

iniciar();
