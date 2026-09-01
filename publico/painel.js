/* Painel da Transparência — Ponto de Entrada Modular. */

import { $, $$ } from './nucleo/ui.js';
import { buscar } from './nucleo/api.js';
import { trocarAba, ligarTeclasDasAbas, registrarGanchoAba } from './nucleo/abas.js';
import { reavaliarTema } from './mapa.js';

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
  carregarSituacao
} from './secoes/fontes.js';

import {
  montarCatalogo, mostrarEstadoDaChave, dispararColeta, salvarChave,
  renderizarColeta, acompanharColeta
} from './secoes/atualizar.js';

import {
  carregarExplorador
} from './secoes/explorador.js';

// Registro dos ganchos de carregamento preguiçoso por aba
registrarGanchoAba('politicos', carregarPoliticos);
registrarGanchoAba('executivo', carregarExecutivo);
registrarGanchoAba('legislativo', carregarLegislativo);
registrarGanchoAba('judiciario', carregarJudiciario);
registrarGanchoAba('mp', carregarMp);
registrarGanchoAba('proposicoes', () => montarFiltrosDeProposicao().then(carregarProposicoes));
registrarGanchoAba('custo', carregarCusto);
registrarGanchoAba('atualizar', () => Promise.all([montarCatalogo(), mostrarEstadoDaChave()]));
registrarGanchoAba('fontes', carregarSituacao);
registrarGanchoAba('explorador', carregarExplorador);


async function iniciar() {
  const botoesAbas = $$('header nav button[data-aba]');
  botoesAbas.forEach((b) => b.addEventListener('click', () => trocarAba(b.dataset.aba)));
  ligarTeclasDasAbas();

  const abaInicial = location.hash.slice(1);
  if (botoesAbas.some((b) => b.dataset.aba === abaInicial)) trocarAba(abaInicial);
  window.addEventListener('hashchange', () => {
    const aba = location.hash.slice(1);
    if (botoesAbas.some((b) => b.dataset.aba === aba)) trocarAba(aba);
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


  $('#fechar-detalhe').addEventListener('click', () => $('#detalhe').close());
  $('#botao-atualizar').addEventListener('click', dispararColeta);
  $('#salvar-chave').addEventListener('click', salvarChave);
  $('#campo-chave').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') salvarChave();
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

iniciar();
