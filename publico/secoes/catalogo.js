/* Seção Catálogo de Tabelas & Inventário de Dados (dim/fato). */

import { $, $$ } from '../nucleo/ui.js';
import { buscar } from '../nucleo/api.js';
import { contagem, escapar } from '../nucleo/formatadores.js';

let catalogoCache = [];

export async function carregarCatalogo() {
  const corpo = $('#tabela-catalogo-corpo');
  if (!corpo) return;

  corpo.innerHTML = '<tr><td colspan="7" class="carregando">Carregando inventário de dados do acervo...</td></tr>';

  try {
    const busca = $('#cat-filtro-busca')?.value?.trim() || '';
    const camada = $('#cat-filtro-camada')?.value || '';
    const status = $('#cat-filtro-status')?.value || '';
    const orgao = $('#cat-filtro-orgao')?.value || '';

    const params = new URLSearchParams();
    if (busca) params.set('tabela', busca);
    if (camada) params.set('camada', camada);
    if (status) params.set('status', status);
    if (orgao) params.set('orgao', orgao);

    const dados = await buscar(`/api/catalogo?${params.toString()}`);
    if (!dados) return;

    // 1. Atualizar KPIs do Topo
    if (dados.kpis) {
      const k = dados.kpis;
      if ($('#cat-kpi-tabelas')) $('#cat-kpi-tabelas').textContent = contagem(k.total_tabelas || 0);
      if ($('#cat-kpi-tabelas-sub')) $('#cat-kpi-tabelas-sub').textContent = `${k.total_dim || 0} dimensões · ${k.total_fato || 0} fatos`;
      if ($('#cat-kpi-linhas')) $('#cat-kpi-linhas').textContent = (k.total_linhas_global || 0).toLocaleString('pt-BR');
      if ($('#cat-kpi-total')) $('#cat-kpi-total').textContent = `${(k.qtd_total || 0) + (k.qtd_vigente || 0)} anos/lotes`;
      if ($('#cat-kpi-parcial')) $('#cat-kpi-parcial').textContent = `${k.qtd_parcial || 0} parciais`;
      if ($('#cat-kpi-amostra')) $('#cat-kpi-amostra').textContent = `${k.qtd_amostra || 0} amostras`;
    }

    catalogoCache = dados.itens || [];
    renderizarTabelaCatalogo(catalogoCache, dados.total_linhas_filtradas || 0);
  } catch (erro) {
    console.error('Erro ao carregar catálogo:', erro);
    corpo.innerHTML = `<tr><td colspan="7" class="erro">Falha ao carregar catálogo: ${escapar(erro.message)}</td></tr>`;
  }
}

function renderizarTabelaCatalogo(lista, somaLinhas) {
  const corpo = $('#tabela-catalogo-corpo');
  const rodape = $('#tabela-catalogo-rodape');
  const contador = $('#cat-total-filtrado');

  if (contador) contador.textContent = `${lista.length} registro(s) encontrado(s)`;

  if (!lista || lista.length === 0) {
    corpo.innerHTML = '<tr><td colspan="7" class="vazio">Nenhuma tabela encontrada com os filtros selecionados.</td></tr>';
    if (rodape) rodape.innerHTML = '';
    return;
  }

  const linhasHtml = lista.map((item) => {
    const isDim = item.camada === 'dim';
    const badgeCamada = isDim
      ? '<span class="selo" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3); font-weight:700">DIMENSÃO</span>'
      : '<span class="selo" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); font-weight:700">FATO</span>';

    let badgeStatus = '<span class="selo selo-padrao">' + escapar(item.status_completude) + '</span>';
    const st = (item.status_completude || '').toLowerCase();
    
    if (st === 'total' || st === 'total_ufs') {
      badgeStatus = '<span class="selo" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.4)">✓ Total</span>';
    } else if (st.includes('parcial')) {
      badgeStatus = '<span class="selo" style="background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.4)" title="Exercício corrente em curso ou varredura de municípios em andamento">⚠️ Parcial</span>';
    } else if (st.includes('amostra')) {
      badgeStatus = '<span class="selo" style="background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(168,85,247,0.4)">🔍 Amostra</span>';
    } else if (st === 'vigente') {
      badgeStatus = '<span class="selo" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.4)">📌 Vigente</span>';
    }

    const anoExibicao = item.ano_particao === 'vigente' 
      ? '<span style="color:var(--texto-suave); font-style:italic">Vigente (Sem ano)</span>'
      : (item.ano_particao === 'serie_historica' ? '<span style="color:var(--texto-suave)">Série Histórica</span>' : `<strong>${escapar(item.ano_particao)}</strong>`);

    return `
      <tr>
        <td style="font-family:monospace; font-weight:700; color:var(--texto-destaque)">
          ${escapar(item.tabela)}
        </td>
        <td>${badgeCamada}</td>
        <td class="num">${anoExibicao}</td>
        <td class="valor" style="font-weight:700; color:var(--realce, #38bdf8)">
          ${(item.total_linhas || 0).toLocaleString('pt-BR')}
        </td>
        <td>${badgeStatus}</td>
        <td>
          <span style="font-weight:600">${escapar(item.orgao_origem || '—')}</span>
        </td>
        <td style="font-size:0.85rem; line-height:1.3">
          <div><strong>${escapar(item.descricao_recurso || '')}</strong></div>
          <div style="color:var(--texto-suave); font-family:monospace; font-size:0.78rem; margin-top:2px">${escapar(item.endpoint_recurso || '')}</div>
        </td>
      </tr>
    `;
  }).join('');

  corpo.innerHTML = linhasHtml;

  // Linha de Soma e Totalizadores (tfoot)
  if (rodape) {
    const somaTotal = lista.reduce((acc, i) => acc + (Number(i.total_linhas) || 0), 0);
    rodape.innerHTML = `
      <tr style="background:var(--superficie-2); font-weight:700; border-top:2px solid var(--borda-forte)">
        <td colspan="3" style="text-align:left; padding:10px 12px">
          TOTAL GERAL DOS ITENS FILTRADOS (${lista.length} linhas de catálogo)
        </td>
        <td class="valor" style="font-size:1.05rem; color:var(--realce, #38bdf8); padding:10px 12px">
          ${somaTotal.toLocaleString('pt-BR')}
        </td>
        <td colspan="3" style="color:var(--texto-suave); font-weight:normal; font-size:0.85rem; padding:10px 12px">
          Soma de registros gravados no Lakehouse Parquet
        </td>
      </tr>
    `;
  }
}

export function configurarEventosCatalogo() {
  $('#cat-filtro-busca')?.addEventListener('input', () => {
    clearTimeout(window._timeoutBuscaCat);
    window._timeoutBuscaCat = setTimeout(carregarCatalogo, 250);
  });

  $('#cat-filtro-camada')?.addEventListener('change', carregarCatalogo);
  $('#cat-filtro-status')?.addEventListener('change', carregarCatalogo);
  $('#cat-filtro-orgao')?.addEventListener('change', carregarCatalogo);

  $('#btn-limpar-filtros-cat')?.addEventListener('click', () => {
    if ($('#cat-filtro-busca')) $('#cat-filtro-busca').value = '';
    if ($('#cat-filtro-camada')) $('#cat-filtro-camada').value = '';
    if ($('#cat-filtro-status')) $('#cat-filtro-status').value = '';
    if ($('#cat-filtro-orgao')) $('#cat-filtro-orgao').value = '';
    carregarCatalogo();
  });

  $('#btn-recalcular-catalogo')?.addEventListener('click', async () => {
    const btn = $('#btn-recalcular-catalogo');
    if (btn) btn.disabled = true;
    try {
      await fetch('/api/catalogo/atualizar', { method: 'POST' });
      await carregarCatalogo();
    } catch (e) {
      console.error('Falha ao recalcular catalogo:', e);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}
