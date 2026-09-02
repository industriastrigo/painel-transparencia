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

// Registro dos ganchos de carregamento preguiçoso por aba (Produção)
registrarGanchoAba('inicio', carregarInicio);
registrarGanchoAba('politicos', carregarPoliticos);
registrarGanchoAba('executivo', carregarExecutivo);
registrarGanchoAba('legislativo', carregarLegislativo);
registrarGanchoAba('judiciario', carregarJudiciario);
registrarGanchoAba('mp', carregarMp);
registrarGanchoAba('proposicoes', () => montarFiltrosDeProposicao().then(carregarProposicoes));
registrarGanchoAba('custo', carregarCusto);


async function iniciar() {
  // Inicialização do Design System Indústrias Trigo
  inicializarTema();
  inicializarAuth();
  inicializarDrawer();

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
  ['#filtro-uf', '#filtro-nome'].forEach((sel) => {
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

  $('#fechar-detalhe').addEventListener('click', () => $('#detalhe').close());
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

export function mostrarNotificacaoRecarga(msg = '🔄 Painel atualizado com sucesso!') {
  let toast = $('#toast-notificacao');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast-notificacao';
    toast.style.cssText = 'position:fixed; bottom:24px; right:24px; background:var(--superficie-3, #1e293b); color:var(--texto, #f8fafc); border:1px solid var(--realce, #38bdf8); padding:10px 18px; border-radius:8px; box-shadow:0 10px 25px rgba(0,0,0,0.5); z-index:9999; font-weight:600; display:flex; align-items:center; gap:8px; transition:opacity 0.25s ease, transform 0.25s ease; opacity:0; transform:translateY(10px); pointer-events:none;';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
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
    mostrarNotificacaoRecarga('🔄 Painel e dados atualizados com sucesso!');
  } catch (erro) {
    console.error('Erro ao atualizar painel:', erro);
    mostrarNotificacaoRecarga('⚠️ Erro ao atualizar painel');
  }
}

iniciar();
