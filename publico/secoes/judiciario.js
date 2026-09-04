/* Seção Poder Judiciário — Magistrados, Ministros e Remunerações. */

import { $, $$ } from '../nucleo/ui.js';
import { buscar } from '../nucleo/api.js';
import {
  txt, escapar, dinheiro, dinheiroCurto, contagem, formatarData
} from '../nucleo/formatadores.js';

let magistradosCache = [];

export async function carregarJudiciario() {
  const container = $('#tabela-magistrados-corpo');
  if (!container) return;

  container.innerHTML = '<tr><td colspan="7" class="carregando">Carregando dados do Poder Judiciário...</td></tr>';

  try {
    // 1. Carrega o Sumário / KPIs
    const sumario = await buscar('/api/judiciario/sumario').catch(() => null);
    if (sumario && sumario.kpis) {
      const k = sumario.kpis;
      $('#jud-kpi-total').textContent = contagem(k.total_magistrados || 0);
      $('#jud-kpi-folha').textContent = dinheiroCurto.format(k.total_folha_mensal || 0);
      $('#jud-kpi-media').textContent = dinheiro.format(k.media_liquida || 0);
      $('#jud-kpi-tribunais').textContent = contagem(k.total_tribunais || 0);
    }

    // 2. Monta os filtros e busca a lista de magistrados
    await carregarListaMagistrados();
  } catch (erro) {
    console.error('Erro ao carregar judiciário:', erro);
    container.innerHTML = `<tr><td colspan="7" class="erro">Falha ao carregar magistrados: ${escapar(erro.message)}</td></tr>`;
  }
}

export async function carregarListaMagistrados() {
  const container = $('#tabela-magistrados-corpo');
  if (!container) return;

  const busca = $('#filtro-jud-busca')?.value?.trim() || '';
  const ramo = $('#filtro-jud-ramo')?.value || '';
  const tribunal = $('#filtro-jud-tribunal')?.value || '';
  const cargo = $('#filtro-jud-cargo')?.value || '';
  const ordem = $('#filtro-jud-ordem')?.value || 'remuneracao';

  const params = new URLSearchParams();
  if (busca) params.set('busca', busca);
  if (ramo) params.set('ramo', ramo);
  if (tribunal) params.set('tribunal', tribunal);
  if (cargo) params.set('cargo', cargo);
  if (ordem) params.set('ordenar', ordem);

  const url = `/api/judiciario/magistrados?${params.toString()}`;
  const lista = await buscar(url);
  magistradosCache = lista || [];

  renderizarTabelaMagistrados(magistradosCache);
}

function renderizarTabelaMagistrados(lista) {
  const container = $('#tabela-magistrados-corpo');
  const contador = $('#jud-total-filtrado');
  if (contador) contador.textContent = `${lista.length} magistrado(s) encontrado(s)`;

  if (!lista || lista.length === 0) {
    container.innerHTML = '<tr><td colspan="7" class="vazio">Nenhum magistrado encontrado com os filtros selecionados.</td></tr>';
    return;
  }

  const linhas = lista.map((m) => {
    const penduricalhos = (m.indenizacoes || 0) + (m.gratificacoes || 0);
    const badgeRamo = {
      'Supremo': 'selo-supremo',
      'Superior': 'selo-superior',
      'Federal': 'selo-federal',
      'Estadual': 'selo-estadual',
      'Trabalho': 'selo-trabalho',
    }[m.ramo] || 'selo-padrao';

    return `
      <tr class="linha-clicavel" data-sk="${escapar(m.sk)}">
        <td class="col-foto">
          <img src="${escapar(m.url_foto)}" alt="${escapar(m.nome)}" class="avatar-magistrado" loading="lazy" />
        </td>
        <td class="col-nome">
          <strong class="nome-destaque">${escapar(m.nome)}</strong>
          <span class="subtexto">${txt(m.orgao_lotacao)}</span>
        </td>
        <td>
          <span class="cargo-texto">${escapar(m.cargo_descricao || m.cargo)}</span>
          <span class="subtexto">${m.sigla_uf ? `UF: ${m.sigla_uf}` : 'Nacional'}</span>
        </td>
        <td>
          <span class="selo-tribunal ${badgeRamo}">${escapar(m.tribunal)}</span>
        </td>
        <td class="num">${dinheiro.format(m.subsidio || 0)}</td>
        <td class="num">${penduricalhos > 0 ? dinheiro.format(penduricalhos) : '—'}</td>
        <td class="num col-liquido">
          <strong>${dinheiro.format(m.total_liquido || 0)}</strong>
        </td>
      </tr>
    `;
  }).join('');

  container.innerHTML = linhas;

  const rodape = $('#tabela-magistrados-rodape');
  if (rodape && lista && lista.length > 0) {
    const totalSubsidio = lista.reduce((acc, m) => acc + (m.subsidio || 0), 0);
    const totalPenduricalhos = lista.reduce((acc, m) => acc + (m.indenizacoes || 0) + (m.gratificacoes || 0), 0);
    const totalLiquido = lista.reduce((acc, m) => acc + (m.total_liquido || 0), 0);
    rodape.innerHTML = `
      <tr style="border-top:2px solid var(--borda-forte, #475569); background:var(--superficie-3, rgba(255,255,255,0.06)); font-weight:bold">
        <td colspan="4"><strong>TOTAL / SOMA (${contagem(lista.length)} magistrados listados)</strong></td>
        <td class="num"><strong style="color:var(--realce, #38bdf8)">${dinheiro.format(totalSubsidio)}</strong></td>
        <td class="num"><strong style="color:var(--alerta, #f59e0b)">${dinheiro.format(totalPenduricalhos)}</strong></td>
        <td class="num"><strong style="color:var(--calmo, #10b981)">${dinheiro.format(totalLiquido)}</strong></td>
      </tr>
    `;
  } else if (rodape) {
    rodape.innerHTML = '';
  }

  // Adiciona evento de clique nas linhas para abrir a ficha
  container.querySelectorAll('tr[data-sk]').forEach((tr) => {
    tr.addEventListener('click', () => {
      abrirFichaMagistrado(tr.dataset.sk);
    });
  });
}

export async function abrirFichaMagistrado(sk) {
  if (!sk) return;
  const modal = $('#detalhe');
  const corpo = $('#detalhe-conteudo');
  if (!modal || !corpo) return;

  corpo.innerHTML = '<div class="carregando">Carregando ficha detalhada do magistrado...</div>';
  modal.showModal();

  try {
    const dados = await buscar(`/api/judiciario/magistrados/${sk}`);
    const m = dados.magistrado;
    const totais = dados.totais || {};
    const historico = dados.historico || [];
    const tetoSTF = dados.teto_stf_referencia || 46366.19;

    const ultimaFolha = historico[0] || {};
    const ultrapassaTeto = (ultimaFolha.total_bruto || 0) > tetoSTF;

    corpo.innerHTML = `
      <div class="ficha-magistrado-detalhe">
        <header class="ficha-cabecalho">
          <img src="${escapar(m.url_foto)}" class="ficha-avatar-grande" alt="${escapar(m.nome)}" />
          <div class="ficha-titulos">
            <h2>${escapar(m.nome)}</h2>
            <p class="ficha-subtitulo"><b>${escapar(m.cargo_descricao)}</b> — <span class="selo-tribunal">${escapar(m.tribunal)}</span></p>
            <p class="subtexto">Lotação: ${txt(m.orgao_lotacao)} | Posse: ${formatarData(m.data_posse)}</p>
          </div>
        </header>

        <section class="ficha-cards-resumo">
          <div class="card-kpi">
            <span class="rotulo">Remuneração Líquida Média</span>
            <span class="valor-destaque">${dinheiro.format(totais.media_mensal_liquida || 0)}</span>
          </div>
          <div class="card-kpi">
            <span class="rotulo">Subsídio Base Mensal</span>
            <span class="valor">${dinheiro.format(ultimaFolha.subsidio || 0)}</span>
          </div>
          <div class="card-kpi">
            <span class="rotulo">Indenizações & Auxílios</span>
            <span class="valor">${dinheiro.format(ultimaFolha.indenizacoes || 0)}</span>
          </div>
          <div class="card-kpi">
            <span class="rotulo">Gratificações (Acervo/Função)</span>
            <span class="valor">${dinheiro.format(ultimaFolha.gratificacoes || 0)}</span>
          </div>
        </section>

        ${ultrapassaTeto ? `
          <div class="alerta-teto-constitucional">
            <strong><svg class="item-svg-inline" viewBox="0 0 24 24" width="14" height="14"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>Total de Créditos Brutos (${dinheiro.format(ultimaFolha.total_bruto)}) acima do Teto do STF (${dinheiro.format(tetoSTF)})</strong>
            <p>Valores que excedem o teto decorrem de verbas indenizatórias (como auxílio-alimentação e moradia) e gratificações por acúmulo de processos autorizadas pelo CNJ.</p>
          </div>
        ` : ''}

        <section class="ficha-decomposicao">
          <h3>Decomposição da Folha Mensal mais Recente (${ultimaFolha.mes}/${ultimaFolha.ano})</h3>
          <table class="tabela-decomposicao">
            <tr><td>Subsídio Constitucional</td><td class="num">${dinheiro.format(ultimaFolha.subsidio || 0)}</td></tr>
            <tr><td>Vantagens Pessoais (Adicionais)</td><td class="num">${dinheiro.format(ultimaFolha.vantagens_pessoais || 0)}</td></tr>
            <tr><td>Indenizações (Auxílios isentos)</td><td class="num">${dinheiro.format(ultimaFolha.indenizacoes || 0)}</td></tr>
            <tr><td>Gratificações (Acúmulo de Acervo/Plantão)</td><td class="num">${dinheiro.format(ultimaFolha.gratificacoes || 0)}</td></tr>
            <tr class="linha-total-bruto"><td><b>Total de Créditos Brutos</b></td><td class="num"><b>${dinheiro.format(ultimaFolha.total_bruto || 0)}</b></td></tr>
            <tr class="linha-desconto"><td>Retenção por Teto Constitucional (Abate-teto)</td><td class="num">- ${dinheiro.format(ultimaFolha.retencao_teto || 0)}</td></tr>
            <tr class="linha-desconto"><td>Descontos Obrigatórios (IRPF / Previdência)</td><td class="num">- ${dinheiro.format(ultimaFolha.descontos_legais || 0)}</td></tr>
            <tr class="linha-liquido-final"><td><b>Rendimento Líquido Efetivo</b></td><td class="num"><b>${dinheiro.format(ultimaFolha.total_liquido || 0)}</b></td></tr>
          </table>
        </section>

        <section class="ficha-historico-pagamentos">
          <h3>Histórico Mensal de Pagamentos</h3>
          <div class="tabela-responsiva">
            <table class="tabela-dados">
              <thead>
                <tr>
                  <th>Competência</th>
                  <th class="num">Subsídio</th>
                  <th class="num">Indenizações</th>
                  <th class="num">Gratificações</th>
                  <th class="num">Abate-teto</th>
                  <th class="num">Líquido</th>
                </tr>
              </thead>
              <tbody>
                ${historico.slice(0, 12).map((h) => `
                  <tr>
                    <td>${String(h.mes).padStart(2, '0')}/${h.ano}</td>
                    <td class="num">${dinheiro.format(h.subsidio || 0)}</td>
                    <td class="num">${dinheiro.format(h.indenizacoes || 0)}</td>
                    <td class="num">${dinheiro.format(h.gratificacoes || 0)}</td>
                    <td class="num">${h.retencao_teto > 0 ? dinheiro.format(h.retencao_teto) : '—'}</td>
                    <td class="num"><b>${dinheiro.format(h.total_liquido || 0)}</b></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    `;
  } catch (erro) {
    corpo.innerHTML = `<div class="erro">Não foi possível carregar a ficha: ${escapar(erro.message)}</div>`;
  }
}

export function configurarEventosJudiciario() {
  $('#filtro-jud-busca')?.addEventListener('input', () => carregarListaMagistrados());
  $('#filtro-jud-ramo')?.addEventListener('change', () => carregarListaMagistrados());
  $('#filtro-jud-tribunal')?.addEventListener('change', () => carregarListaMagistrados());
  $('#filtro-jud-cargo')?.addEventListener('change', () => carregarListaMagistrados());
  $('#filtro-jud-ordem')?.addEventListener('change', () => carregarListaMagistrados());
  $('#filtro-jud-limpar')?.addEventListener('click', () => {
    if ($('#filtro-jud-busca')) $('#filtro-jud-busca').value = '';
    if ($('#filtro-jud-ramo')) $('#filtro-jud-ramo').value = '';
    if ($('#filtro-jud-tribunal')) $('#filtro-jud-tribunal').value = '';
    if ($('#filtro-jud-cargo')) $('#filtro-jud-cargo').value = '';
    if ($('#filtro-jud-ordem')) $('#filtro-jud-ordem').value = 'remuneracao';
    carregarListaMagistrados();
  });
}
