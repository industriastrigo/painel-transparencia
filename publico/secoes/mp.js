/* Seção Ministério Público — MPU (MPF, MPT, MPM, MPDFT), MPEs Estaduais e Remunerações (CNMP). */

import { $, $$ } from '../nucleo/ui.js';
import { buscar } from '../nucleo/api.js';
import {
  txt, escapar, dinheiro, dinheiroCurto, contagem, formatarNomeProprio
} from '../nucleo/formatadores.js';

let membrosMpCache = [];

export async function carregarMp() {
  const container = $('#tabela-mp-corpo');
  if (!container) return;

  container.innerHTML = '<tr><td colspan="7" class="carregando">Carregando dados do Ministério Público...</td></tr>';

  try {
    // 1. Carrega o Sumário / KPIs
    const sumario = await buscar('/api/mp/sumario').catch(() => null);
    if (sumario && sumario.kpis) {
      const k = sumario.kpis;
      $('#mp-kpi-total').textContent = contagem(k.total_membros || 0);
      $('#mp-kpi-folha').textContent = dinheiroCurto.format(k.total_folha_mensal || 0);
      $('#mp-kpi-media').textContent = dinheiro.format(k.media_liquida || 0);
      $('#mp-kpi-penduricalhos').textContent = dinheiroCurto.format(k.total_penduricalhos || 0);
    }

    // 2. Busca lista de membros com filtros
    await carregarListaMembrosMp();
  } catch (erro) {
    console.error('Erro ao carregar MP:', erro);
    container.innerHTML = `<tr><td colspan="7" class="erro">Falha ao carregar dados do MP: ${escapar(erro.message)}</td></tr>`;
  }
}

export async function carregarListaMembrosMp() {
  const container = $('#tabela-mp-corpo');
  if (!container) return;

  const busca = $('#filtro-mp-busca')?.value?.trim() || '';
  const ramo = $('#filtro-mp-ramo')?.value || '';
  const cargo = $('#filtro-mp-cargo')?.value || '';
  const uf = $('#filtro-mp-uf')?.value?.trim() || '';
  const ordem = $('#filtro-mp-ordem')?.value || 'remuneracao';

  const params = new URLSearchParams();
  if (busca) params.set('busca', busca);
  if (ramo) params.set('ramo', ramo);
  if (cargo) params.set('cargo', cargo);
  if (uf) params.set('uf', uf);
  if (ordem) params.set('ordenar', ordem);

  const url = `/api/mp/membros?${params.toString()}`;
  const lista = await buscar(url);
  membrosMpCache = lista || [];

  renderizarTabelaMembrosMp(membrosMpCache);
}

function renderizarTabelaMembrosMp(lista) {
  const container = $('#tabela-mp-corpo');
  const contador = $('#mp-total-filtrado');
  if (contador) contador.textContent = `${lista.length} membro(s) encontrado(s)`;

  if (!lista || lista.length === 0) {
    container.innerHTML = '<tr><td colspan="7" class="vazio">Nenhum membro do Ministério Público encontrado com os filtros selecionados.</td></tr>';
    return;
  }

  const linhas = lista.map((m) => {
    const penduricalhos = (m.indenizacoes || 0) + (m.gratificacoes || 0);
    const badgeRamo = {
      'Federal (MPF)': 'selo-supremo',
      'Trabalho (MPT)': 'selo-trabalho',
      'Militar (MPM)': 'selo-superior',
      'Distrito Federal (MPDFT)': 'selo-federal',
      'Estadual (MPSP)': 'selo-estadual',
      'Estadual (MPMG)': 'selo-estadual',
      'Estadual (MPRJ)': 'selo-estadual',
      'Estadual (MPRS)': 'selo-estadual',
    }[m.ramo] || 'selo-padrao';

    return `
      <tr class="linha-clicavel" data-sk="${escapar(m.sk)}">
        <td class="col-nome">
          <strong class="nome-destaque">${escapar(m.nome_formatado || m.nome)}</strong>
          <span class="subtexto"><code>${escapar(m.cod_membro_mp_interno || '—')}</code> · ${escapar(m.lotacao || 'Lotação não informada')}</span>
        </td>
        <td>
          <span class="cargo-texto">${escapar(m.cargo_descricao || m.cargo)}</span>
          <span class="subtexto">${m.sigla_uf ? `UF: ${m.sigla_uf}` : 'Nacional'}</span>
        </td>
        <td>
          <span class="selo-tribunal ${badgeRamo}">${escapar(m.orgao_mp || m.ramo)}</span>
        </td>
        <td class="num">${dinheiro.format(m.subsidio || 0)}</td>
        <td class="num" style="color:var(--alerta, #f59e0b)">${penduricalhos > 0 ? dinheiro.format(penduricalhos) : '—'}</td>
        <td class="num col-liquido">
          <strong style="color:var(--calmo, #10b981)">${dinheiro.format(m.total_liquido || 0)}</strong>
        </td>
        <td class="col-acoes">
          <button class="btn-detalhe-mp discreto" data-sk="${escapar(m.sk)}">Detalhar</button>
        </td>
      </tr>
    `;
  }).join('');

  container.innerHTML = linhas;

  const rodape = $('#tabela-mp-rodape');
  if (rodape && lista && lista.length > 0) {
    const totalSubsidio = lista.reduce((acc, m) => acc + (m.subsidio || 0), 0);
    const totalPenduricalhos = lista.reduce((acc, m) => acc + (m.indenizacoes || 0) + (m.gratificacoes || 0), 0);
    const totalLiquido = lista.reduce((acc, m) => acc + (m.total_liquido || 0), 0);
    rodape.innerHTML = `
      <tr style="border-top:2px solid var(--borda-forte, #475569); background:var(--superficie-3, rgba(255,255,255,0.06)); font-weight:bold">
        <td colspan="3"><strong>TOTAL / SOMA (${contagem(lista.length)} membros listados)</strong></td>
        <td class="num"><strong style="color:var(--realce, #38bdf8)">${dinheiro.format(totalSubsidio)}</strong></td>
        <td class="num"><strong style="color:var(--alerta, #f59e0b)">${dinheiro.format(totalPenduricalhos)}</strong></td>
        <td class="num"><strong style="color:var(--calmo, #10b981)">${dinheiro.format(totalLiquido)}</strong></td>
        <td></td>
      </tr>
    `;
  } else if (rodape) {
    rodape.innerHTML = '';
  }

  $$('.btn-detalhe-mp').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sk = btn.getAttribute('data-sk');
      abrirModalMembroMp(sk);
    });
  });
}

async function abrirModalMembroMp(sk) {
  const modal = $('#modal-mp-detalhe');
  const corpo = $('#modal-mp-corpo');
  if (!modal || !corpo) return;

  corpo.innerHTML = '<div class="carregando">Carregando ficha e histórico remuneratório...</div>';
  modal.removeAttribute('hidden');

  try {
    const dados = await buscar(`/api/mp/membros/${sk}`);
    const m = dados?.membro || {};
    const hist = dados?.historico || [];

    corpo.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:16px">
        <div style="border-bottom:1px solid var(--borda); padding-bottom:12px">
          <h2 style="margin:0; font-size:1.4rem">${escapar(m.nome_formatado || m.nome)}</h2>
          <p class="subtexto" style="margin-top:4px">
            <strong>${escapar(m.cargo_descricao || m.cargo)}</strong> · ${escapar(m.orgao_mp || m.ramo)} · ${escapar(m.lotacao || '')}
          </p>
          <p class="subtexto" style="margin-top:2px">
            Código Canônico: <code>${escapar(m.cod_membro_mp_interno || '—')}</code>
          </p>
        </div>

        <div class="tiras">
          <div class="tira">
            <span>Subsídio Base</span>
            <div style="display:flex; flex-direction:column; align-items:flex-end">
              <strong style="font-size:1.1rem">${dinheiro.format(m.subsidio || 0)}</strong>
              <span style="font-size:0.8rem; color:var(--texto-fraco)">vencimento padrão</span>
            </div>
          </div>
          <div class="tira">
            <span>Indenizações & Auxílios</span>
            <div style="display:flex; flex-direction:column; align-items:flex-end">
              <strong style="font-size:1.1rem; color:var(--alerta, #f59e0b)">${dinheiro.format(m.indenizacoes || 0)}</strong>
              <span style="font-size:0.8rem; color:var(--texto-fraco)">fora do teto</span>
            </div>
          </div>
          <div class="tira">
            <span>Gratificações (PAE/Função)</span>
            <div style="display:flex; flex-direction:column; align-items:flex-end">
              <strong style="font-size:1.1rem; color:var(--alerta, #f59e0b)">${dinheiro.format(m.gratificacoes || 0)}</strong>
              <span style="font-size:0.8rem; color:var(--texto-fraco)">adicionais</span>
            </div>
          </div>
          <div class="tira">
            <span>Remuneração Líquida</span>
            <div style="display:flex; flex-direction:column; align-items:flex-end">
              <strong style="font-size:1.15rem; color:var(--calmo, #10b981)">${dinheiro.format(m.total_liquido || 0)}</strong>
              <span style="font-size:0.8rem; color:var(--texto-fraco)">valor em conta</span>
            </div>
          </div>
        </div>
      </div>
    `;
  } catch (erro) {
    corpo.innerHTML = `<div class="erro">Erro ao carregar detalhes: ${escapar(erro.message)}</div>`;
  }
}

export function inicializarEventosMp() {
  const btnLimpar = $('#filtro-mp-limpar');
  const inputBusca = $('#filtro-mp-busca');
  const seletorRamo = $('#filtro-mp-ramo');
  const seletorCargo = $('#filtro-mp-cargo');
  const seletorOrdem = $('#filtro-mp-ordem');
  const modal = $('#modal-mp-detalhe');
  const btnFecharModal = $('#modal-mp-fechar');

  if (btnLimpar) {
    btnLimpar.addEventListener('click', () => {
      if (inputBusca) inputBusca.value = '';
      if (seletorRamo) seletorRamo.value = '';
      if (seletorCargo) seletorCargo.value = '';
      if (seletorOrdem) seletorOrdem.value = 'remuneracao';
      carregarListaMembrosMp();
    });
  }

  if (inputBusca) {
    inputBusca.addEventListener('input', () => {
      clearTimeout(inputBusca._timer);
      inputBusca._timer = setTimeout(carregarListaMembrosMp, 350);
    });
  }

  if (seletorRamo) seletorRamo.addEventListener('change', carregarListaMembrosMp);
  if (seletorCargo) seletorCargo.addEventListener('change', carregarListaMembrosMp);
  if (seletorOrdem) seletorOrdem.addEventListener('change', carregarListaMembrosMp);

  if (btnFecharModal && modal) {
    btnFecharModal.addEventListener('click', () => modal.setAttribute('hidden', ''));
  }
}
